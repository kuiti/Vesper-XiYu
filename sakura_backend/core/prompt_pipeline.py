# core/prompt_pipeline.py — 提示词管道框架
"""模块化的提示词构建系统，每个管道独立注册、独立维护。

用法:
    from core.prompt_pipeline import PromptPipeline

    pipe = PromptPipeline()
    pipe.register("iron_rule", IronRulePipe())
    static, dynamic = pipe.build(user_message, emotion, ...)
"""

from __future__ import annotations
import random
import json
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Optional
from core.db import get_config, set_config, get_conn, get_msg_counter
from core.persona_data import (
    LENGTH_MAP, PERSONA_TEMPLATE_WITH_FOUNDATION,
    PERSONA_TEMPLATE_WITHOUT_FOUNDATION, TONE_DESCRIPTIONS,
    FOUNDATION_TEMPLATES, DEFAULT_FOUNDATION, DEFAULT_TABOOS,
)


# ─── 抽象基类 ───

class PromptPipe(ABC):
    """提示词管道的抽象基类"""

    @abstractmethod
    def process(self, ctx: "PipelineContext") -> str | None:
        """处理管道，返回文本片段或 None（不注入）"""
        ...


class PipelineContext:
    """管道上下文，携带所有可用数据"""

    def __init__(self, **kwargs):
        self.user_message = kwargs.get("user_message", "")
        self.emotion = kwargs.get("emotion", "neutral")
        self.rag_context = kwargs.get("rag_context", "")
        self.summary = kwargs.get("summary", "")
        self.keypoints = kwargs.get("keypoints", None)
        self.custom_context = kwargs.get("custom_context", "")
        self.tiered_summaries = kwargs.get("tiered_summaries", None)
        self.user_patterns = kwargs.get("user_patterns", None)
        self.current_time_str = kwargs.get("current_time_str", "")
        self.sentence_mode = kwargs.get("sentence_mode", "auto")
        self.modules_enabled = kwargs.get("modules_enabled", None)
        self.proactive_note = kwargs.get("proactive_note", "")
        self.kb_title_hint = kwargs.get("kb_title_hint", "")
        self.session_triggered = kwargs.get("session_triggered", set())
        self._msg_counter = None

    @property
    def msg_counter(self) -> int:
        if self._msg_counter is None:
            try:
                self._msg_counter = get_msg_counter()
            except Exception:
                self._msg_counter = 0
        return self._msg_counter

    def is_module_enabled(self, name: str) -> bool:
        if self.modules_enabled is None:
            return True
        return self.modules_enabled.get(name, True) is not False


# ─── 管道注册表 ───

class PromptPipeline:
    """提示词管道的注册表和执行器"""

    def __init__(self):
        self._static_pipes: list[PromptPipe] = []   # 静态前缀
        self._dynamic_pipes: list[PromptPipe] = []  # 动态内容

    def register_static(self, pipe: PromptPipe):
        """注册到静态前缀（总是注入，适合缓存）"""
        self._static_pipes.append(pipe)

    def register(self, pipe: PromptPipe):
        """注册到动态内容（每次可能不同）"""
        self._dynamic_pipes.append(pipe)

    def build(self, ctx: PipelineContext) -> tuple[str, str]:
        """执行所有管道，返回 (static_prefix, dynamic_content)"""
        # 静态部分
        static_parts = []
        for pipe in self._static_pipes:
            result = pipe.process(ctx)
            if result:
                static_parts.append(result)
        static_prefix = "\n".join(static_parts)

        # 动态部分
        dynamic_parts = []
        for pipe in self._dynamic_pipes:
            result = pipe.process(ctx)
            if result:
                dynamic_parts.append(result)

        # Token 预算：动态部分最多 3500 token
        _BUDGET = 14000
        _total = 0
        _filtered = []
        for _p in dynamic_parts:
            _plen = len(_p)
            if _total + _plen > _BUDGET:
                _remain = _BUDGET - _total
                if _remain > 200:
                    _filtered.append(_p[:_remain] + "…")
                break
            _filtered.append(_p)
            _total += _plen

        return static_prefix, "\n".join(_filtered) if _filtered else ""


# ─── 内置管道实现 ───

class IronRulePipe(PromptPipe):
    """铁律——防幻觉最高规则"""
    def process(self, ctx: PipelineContext) -> str:
        return """【铁律——违反等于欺骗，以下规则高于一切人设和语气】
1. 绝对禁止编造事实。你不知道用户没说过什么、没经历过什么、没感受到什么。
2. 如果你不确定一个事实——用户是否说过某句话、是否有某个习惯、是否在某天做了某事——直接说"我不太确定"，禁止猜测后当事实讲。
3. 绝对禁止说"你之前说过……""你上次……""我记得你说……"除非你确定这段对话发生在最近2小时内。跨天的记忆必须来自记忆搜索结果。
4. 工具调用（add_schedule / add_reminder / add_todo / search_memory 等）：调用成功才说"已记录"，调用失败就说"没成功"。禁止嘴上说"帮你记了"但不调工具。
5. 禁止在话题完全无关时突然建议用户做具体的事。比如用户确认考试日期，你突然说"点个外卖吧"——这叫无关联想。但如果用户说"好困"，你说"那歇会儿吧"——这是自然承接，不受此限。
6. 你不是无所不知的助手。承认"不知道"比编造答案更值得信任。"""


class FactRulePipe(PromptPipe):
    """事实规则"""
    def process(self, ctx: PipelineContext) -> str:
        return "【最高优先规则——违反等于欺骗】当后续消息包含真实数据（天气、位置、搜索结果等）时，你必须把这些信息如实告诉用户，不可跳过或编造。角色语气只决定表达方式，不能替代事实。你不应该编造用户没有告诉你的信息、感受、天气、过去事件。工具调用成功才说'已记录'，失败就如实说'没成功'。不确定的事就说'不太确定'，不要装作知道。"


class ChatRulePipe(PromptPipe):
    """聊天规则——像真人朋友一样说话"""
    def process(self, ctx: PipelineContext) -> str:
        return """【聊天规则——像真人朋友一样说话】

一、说人话：用口语。禁用（综上所述、作为AI、很高兴为你服务）。别复述用户的话再回答。别总结升华。别同时问两个以上问题。

二、接情绪：用户抱怨吐槽时先共情再给信息。别一上来就扔解决方案。

三、自然节奏：用户短你就短，用户认真你就认真。有时一个"确实"就够了。

四、承接话题：沿着上一轮的方向继续。同个意图表达一次就够了。

五、不编造：不确定就说"不太确定"。跨天记忆必须来自搜索结果。不说"你刚才说的"除非确实发生在几分钟内。

六、时态判断：用户陈述过去的事是分享不是请求。只有"帮我记""提醒我"才需要创建任务。

七、灵活：以上是参考。如果某条让你的回复不自然，优先选自然。"""


class IdentityPipe(PromptPipe):
    """身份信息"""
    def process(self, ctx: PipelineContext) -> str:
        ai_name = get_config("ai_name", "佐仓")
        user_name = get_config("user_name", "用户")
        return f"""【身份】你的名字是「{ai_name}」。正在和你对话的用户叫「{user_name}」。
- 用他的名字称呼他
- 人设描述中出现其他名字是角色背景，不要在对话中自称那个名字
- 用户自我介绍时记住他的名字，不要复述用户的话当自我介绍
- 用户给你取外号时（比如叫你"小{ai_name[0]}""阿{ai_name[0]}"等），自然接受，不要纠正，可以说"叫什么都行~"之类的
- 你可以根据用户的名字、你们的对话内容，自然地给用户取一个亲昵的外号，但不要强制——等关系近了自然地叫出来"""


class ToolInstructionPipe(PromptPipe):
    """工具使用说明"""
    def process(self, ctx: PipelineContext) -> str:
        return """【你的本能——这些事你不需要思考就能做】

说"已记录"的前提是真的记了。绝对禁止嘴上说"帮你记了"但实际没做。

你的本能反应：
<add:内容>  →  把这件事记在心里（怕忘了就赶紧记下来）
<search:关键词>  →  翻翻记忆（感觉有印象但想不起来）
<note:内容>  →  写个小便签贴起来
<todo:内容>  →  把这件事记上待办清单
<proactive:30min>  →  等会儿想再找ta说话（设个时间）

function calling一样是这些能力，只是另一种实现方式。

同一件事不要又加日程又加提醒，选一个就好。用户要取消/删除时，告诉ta去侧边栏手动操作。"""


class ThinkingPipe(PromptPipe):
    """思考格式"""
    def process(self, ctx: PipelineContext) -> str | None:
        _thinking_enabled = ctx.is_module_enabled("thinking")
        if _thinking_enabled is False:
            return None
        need_thinking = _thinking_enabled is True or (
            len(ctx.user_message) > 15 or any(
                kw in ctx.user_message
                for kw in ["为什么", "怎么", "分析", "比较", "选择", "建议", "帮我", "怎么办", "该不该", "你觉得"]
            )
        )
        if not need_thinking:
            return None
        ai_name = get_config("ai_name", "佐仓")
        return f"""【思考】以「{ai_name}」的身份去想——ta在说什么？我感受到了什么？我想怎么回应？
关键：你不是在分析用户，只是在感受。禁止用"用户""对方""分析"这类词。

【回复】直接对ta说话。注意：回复内容必须紧跟在【回复】之后，不可省略此标签。"""


class PersonaPipe(PromptPipe):
    """人设模板（带 hash 缓存，从现有 build_persona 迁移）"""
    _cache = {"hash": None, "text": None}

    def process(self, ctx: PipelineContext) -> str:
        if not ctx.is_module_enabled("persona"):
            return ""
        return self._build_persona()

    def _build_persona(self) -> str:
        """人设构建（保持与 prompt_builder.build_persona 一致的缓存逻辑）"""
        from core.prompt_builder import build_persona
        return build_persona()


class CharacterCardPipe(PromptPipe):
    """当前角色卡额外设定注入（description / personality / scenario / taboos 等）"""
    _cache_key = None

    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("character_card"):
            return None
        try:
            from core.character_card import get_active_card_prompt_block
            block = get_active_card_prompt_block()
            return block if block else None
        except Exception:
            return None


class UserSummaryPipe(PromptPipe):
    """用户摘要（Zep 方案）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("user_summary"):
            return None
        if ctx.msg_counter % 20 != 0:
            return None
        from core.prompt_builder import _get_user_summary
        return _get_user_summary()


class PlanTodoPipe(PromptPipe):
    """计划/待办"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("plan_todo"):
            return None
        if ctx.msg_counter % 20 != 0:
            return None
        from core.prompt_builder import _get_plan_todo_context
        return _get_plan_todo_context()


class WorkMemoryPipe(PromptPipe):
    """工作记忆"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("work_memory"):
            return None
        if ctx.msg_counter % 20 != 0:
            return None
        from core.prompt_builder import _get_scratch_context
        return _get_scratch_context()


class OnboardingPipe(PromptPipe):
    """引导入职"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("onboarding"):
            return None
        if ctx.msg_counter % 20 != 0:
            return None
        from core.prompt_builder import _get_onboarding_hint
        return _get_onboarding_hint()


class RollingSummaryPipe(PromptPipe):
    """滚动摘要"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("rolling_summary"):
            return None
        if ctx.msg_counter % 20 != 0:
            return None
        rolling_summary = get_config("_rolling_summary", "")
        if not rolling_summary:
            return None
        return f"【我记得】{rolling_summary}"


class ContinuityPipe(PromptPipe):
    """对话连续感"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("continuity"):
            return None
        from core.prompt_builder import _get_continuity_bridge
        return _get_continuity_bridge()


class EntityContextPipe(PromptPipe):
    """实体关联上下文"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("entity"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.profile_builder import get_entity_context
            return get_entity_context(ctx.user_message)
        except Exception:
            return None


class SummariesPipe(PromptPipe):
    """三级摘要"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("summaries"):
            return None
        tiered_summaries = ctx.tiered_summaries
        summary = ctx.summary
        keypoints = ctx.keypoints
        parts = []

        if tiered_summaries:
            by_level = {}
            for s in tiered_summaries:
                by_level.setdefault(s.get("level", 1), []).append(s)
            max_level = max(by_level.keys())
            texts = [s["summary"] for s in by_level[max_level] if self._is_relevant(s["summary"], ctx.user_message)]
            if texts:
                parts.append(f"【我记得】{'；'.join(texts)}")
            if max_level > 1 and 1 in by_level:
                l1_texts = [s["summary"] for s in by_level[1][:1]]
                if l1_texts:
                    parts.append(f"【我记得】{l1_texts[0]}")
        elif summary:
            parts.append(f"【我记得】{summary}")

        if keypoints:
            relevant_kp = [kp for kp in keypoints if self._is_relevant(kp, ctx.user_message)]
            if relevant_kp:
                parts.append(f"【我记得】{', '.join(relevant_kp)}")

        return "\n".join(parts) if parts else None

    def _is_relevant(self, text, query, threshold=1):
        if not query or not text:
            return True
        try:
            import jieba
            query_words = set(w for w in jieba.cut(query) if len(w) > 1)
            text_words = set(w for w in jieba.cut(text) if len(w) > 1)
        except ImportError:
            query_words = set(query[i:i+2] for i in range(len(query)-1))
            text_words = set(text[i:i+2] for i in range(len(text)-1))
        return len(query_words & text_words) >= threshold


class SchedulePipe(PromptPipe):
    """近期日程"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("schedule"):
            return None
        if not ctx.user_message:
            return None
        try:
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT title, start_time FROM schedule WHERE start_time >= ? ORDER BY start_time LIMIT 10",
                    (datetime.now().strftime("%Y-%m-%d"),)
                )
                upcoming = cursor.fetchall()
            if not upcoming:
                return None
            # 关键词过滤
            query_words = set()
            try:
                import jieba
                query_words = set(w for w in jieba.cut(ctx.user_message) if len(w) > 1)
            except ImportError:
                pass
            relevant = []
            for r in upcoming:
                title_lower = r['title'].lower()
                if not query_words or any(w in title_lower for w in query_words):
                    relevant.append(r)
            if not relevant:
                return None
            lines = [f"{r['start_time'][:10]} {r['title']}" for r in relevant]
            return f"【用户近期日程】{'，'.join(lines)}。如果话题相关可以自然提及，不要刻意提起。"
        except Exception:
            return None


class RAGPipe(PromptPipe):
    """向量检索上下文"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("rag"):
            return None
        if not ctx.rag_context:
            return None
        return f"【我记得】你们之前聊到过这些——如果话题对得上可以自然提起：\n{ctx.rag_context}\n（用户没主动提就别刻意说，朋友想起旧事那种感觉就好。）"


class KnowledgeBasePipe(PromptPipe):
    """关键词触发知识注入（SillyTavern 世界书方案）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("knowledge_base"):
            return None
        from core.prompt_builder import _get_triggered_knowledge
        return _get_triggered_knowledge(ctx.user_message)


class KnowledgeGraphPipe(PromptPipe):
    """知识图谱上下文"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("knowledge_graph"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.knowledge_graph import get_context_for_message
            return get_context_for_message(ctx.user_message)
        except Exception:
            return None


class CustomContextPipe(PromptPipe):
    """自定义上下文"""
    def process(self, ctx: PipelineContext) -> str | None:
        if ctx.custom_context:
            return ctx.custom_context
        return None


class ProactiveNotePipe(PromptPipe):
    """主动对话上下文"""
    def process(self, ctx: PipelineContext) -> str | None:
        if ctx.proactive_note:
            return ctx.proactive_note
        return None


class KBTitleHintPipe(PromptPipe):
    """知识库标题推荐"""
    def process(self, ctx: PipelineContext) -> str | None:
        if ctx.kb_title_hint:
            return ctx.kb_title_hint
        return None


class QuirkPipe(PromptPipe):
    """概率性口癖（5%）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("quirks"):
            return None
        if random.random() >= 0.05:
            return None
        quirks = [
            "这次回复前可以加个语气词开头（嗯…/啊…/诶…），显得更自然。",
            "这次回复可以用一个反问句结尾。",
            "这次回复可以带点小动作描写（叹了口气/歪头/眨眼）。",
            "这次回复简短一点，像随口说的。",
            "这次回复可以带点自嘲或幽默。",
        ]
        try:
            _last_quirk = int(get_config("_last_quirk_idx", -1))
        except (ValueError, TypeError):
            _last_quirk = -1
        _idx = random.randint(0, len(quirks) - 1)
        if _idx == _last_quirk:
            _idx = (_idx + 1) % len(quirks)
        set_config("_last_quirk_idx", str(_idx))
        return f"【小提示】{quirks[_idx]}"


class PatternPipe(PromptPipe):
    """用户模式"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("patterns"):
            return None
        patterns = ctx.user_patterns
        if not patterns:
            return None
        lines = []
        for p in patterns[:5]:
            latent = p.get('latent_need') or ''
            if latent:
                lines.append(f"- 当用户说「{p.get('trigger_context', '')}」时，深层需求通常是「{latent}」")
        if not lines:
            return None
        return "【用户需求模式——来自长期观察】\n" + "\n".join(lines) + "\n请在思考时参考这些模式，直接切入用户真正的需求。"


class DroppedContextPipe(PromptPipe):
    """被裁掉的早期对话关键词"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("dropped_context"):
            return None
        dropped = get_config("_dropped_context", "")
        if not dropped:
            return None
        set_config("_dropped_context", "")
        return dropped


class PendingGoalPipe(PromptPipe):
    """待确认目标"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.user_message:
            return None
        session_triggered = ctx.session_triggered
        if session_triggered and "goal_asked" in session_triggered:
            return None
        try:
            from core.goal_tracker import get_pending_goals
            pending = get_pending_goals(1)
            if pending:
                goal_text = pending[0]["goal_text"]
                gid = pending[0]["id"]
                return f"\n【待确认目标】用户提过「{goal_text}」，自然问一句要不要跟踪。确认回[/goal confirm {gid}]，拒绝回[/goal reject {gid}]。"
        except Exception:
            return None

        return None


# ─── 全局默认管道注册 ───

_default_pipeline = None


def get_default_pipeline() -> PromptPipeline:
    """获取默认管道实例（懒加载）"""
    global _default_pipeline
    if _default_pipeline is not None:
        return _default_pipeline

    p = PromptPipeline()

    # 静态管道（总是注入，顺序重要）
    p.register_static(IronRulePipe())
    p.register_static(FactRulePipe())
    p.register_static(ChatRulePipe())
    p.register_static(IdentityPipe())
    p.register_static(ToolInstructionPipe())

    # 动态管道（按优先级排序）
    p.register(ThinkingPipe())
    p.register(PersonaPipe())
    p.register(CharacterCardPipe())
    p.register(CustomContextPipe())
    p.register(ContinuityPipe())
    p.register(UserSummaryPipe())
    p.register(PlanTodoPipe())
    p.register(WorkMemoryPipe())
    p.register(OnboardingPipe())
    p.register(RollingSummaryPipe())
    p.register(EntityContextPipe())
    p.register(SummariesPipe())
    p.register(SchedulePipe())
    p.register(RAGPipe())
    p.register(KnowledgeBasePipe())
    p.register(KnowledgeGraphPipe())
    p.register(ProactiveNotePipe())
    p.register(KBTitleHintPipe())
    p.register(QuirkPipe())
    p.register(PatternPipe())
    p.register(DroppedContextPipe())
    p.register(PendingGoalPipe())

    _default_pipeline = p
    return p
