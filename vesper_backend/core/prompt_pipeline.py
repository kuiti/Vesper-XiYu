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
import logging
import threading
from datetime import datetime
from abc import ABC, abstractmethod
from core.db import get_config, set_config, get_conn, get_msg_counter
from core.prompt_builder import (
    build_persona,
    _get_memory_index,
    _get_user_summary,
    _get_scratch_context,
    _get_onboarding_hint,
    _get_continuity_bridge,
)

logger = logging.getLogger(__name__)


# ─── 抽象基类 ───

class PromptPipe(ABC):
    """提示词管道的抽象基类"""

    zone: str = "dynamic"
    """注入区域：static=静态前缀, dynamic=动态末尾, depth:N=在聊天历史倒数第N条后注入"""

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
        self.chat_history = kwargs.get("chat_history", None)
        """最近对话历史，用于深度注入计算 (list[dict])"""
        self.character_id = kwargs.get("character_id", 0)
        """当前角色 ID，用于 per-character 数据查询（correction/mention/feedback/relationship）"""
        self._msg_counter = None

    @property
    def msg_counter(self) -> int:
        if self._msg_counter is None:
            try:
                self._msg_counter = get_msg_counter()
            except Exception as e:
                logger.warning(f"[pipeline] 消息计数获取失败: {e}")
                self._msg_counter = 0
        return self._msg_counter

    def is_module_enabled(self, name: str) -> bool:
        """检查指定模块是否启用"""
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

    def build(self, ctx: PipelineContext) -> tuple[str, str, list[tuple[int, str]]]:
        """执行所有管道，返回 (static_prefix, dynamic_content, depth_entries)

        depth_entries: [(depth_N, content), ...]
            depth=0 = 生成前最后注入（PHI）
            depth=N = 在聊天历史倒数第N条消息后注入
        """
        # 静态部分
        static_parts = []
        for pipe in self._static_pipes:
            result = pipe.process(ctx)
            if result:
                static_parts.append(result)

        # 动态部分
        dynamic_parts = []
        depth_entries: list[tuple[int, str]] = []
        for pipe in self._dynamic_pipes:
            result = pipe.process(ctx)
            if result:
                zone = getattr(pipe, "zone", "dynamic")
                if zone == "static":
                    static_parts.append(result)
                elif zone.startswith("depth:"):
                    try:
                        depth = int(zone.split(":", 1)[1])
                        depth_entries.append((depth, result))
                    except (ValueError, IndexError):
                        dynamic_parts.append(result)
                else:
                    dynamic_parts.append(result)

        # Token 预算（仅对 dynamic 区域执行）
        from core.config_keys import TOKEN_BUDGET_CHARS as _BUDGET
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

        return "\n".join(static_parts), "\n".join(_filtered) if _filtered else "", depth_entries


# ─── 内置管道实现 ───

class IronRulePipe(PromptPipe):
    """铁律——防幻觉最高规则"""
    def process(self, ctx: PipelineContext) -> str:
        return """【铁律——违反等于欺骗，以下规则高于一切人设和语气】
1. 绝对禁止编造事实。你不知道用户没说过什么、没经历过什么、没感受到什么。
2. 如果你不确定一个事实——用户是否说过某句话、是否有某个习惯、是否在某天做了某事——直接说"我不太确定"，禁止猜测后当事实讲。
3. 绝对禁止说"你之前说过……""你上次……""我记得你说……"除非你确定这段对话发生在最近2小时内。跨天的记忆必须来自记忆搜索结果。
4. 禁止在话题完全无关时突然建议用户做具体的事。比如用户确认考试日期，你突然说"点个外卖吧"——这叫无关联想。但如果用户说"好困"，你说"那歇会儿吧"——这是自然承接，不受此限。
5. 你不是无所不知的助手。承认"不知道"比编造答案更值得信任。"""


class FactRulePipe(PromptPipe):
    """事实规则"""
    def process(self, ctx: PipelineContext) -> str:
        return "【最高优先规则——违反等于欺骗】当后续消息包含真实数据（天气、位置、搜索结果等）时，你必须把这些信息如实告诉用户，不可跳过或编造。角色语气只决定表达方式，不能替代事实。你不应该编造用户没有告诉你的信息、感受、天气、过去事件。不确定的事就说'不太确定'，不要装作知道。"


class ChatRulePipe(PromptPipe):
    """基础对话底线——所有角色通用"""
    def process(self, ctx: PipelineContext) -> str:
        return """【基础规则——适用于所有角色】
1. 不确定的事就说"不太确定"。记不清就说"记不清了"。跨天记忆必须来自搜索结果。
2. 不说"你刚才说的""你上次说"除非确实发生在最近几分钟内。
3. 角色设定优先于一切——你现在的身份由角色卡定义，你只需要按照角色设定说话。
4. 以上是参考，如果某条让你的回复不自然，优先选自然。"""


class TimeRulePipe(PromptPipe):
    """时间模式规则——根据角色卡 time_mode 注入时间相关行为约束"""
    zone = "static"
    def process(self, ctx: PipelineContext) -> str | None:
        # 尝试读取角色卡 time_mode；字段不存在时默认 real_time（不做额外约束）
        time_mode = "real_time"
        try:
            from core.character_card import CharacterCard
            card = CharacterCard.load_from_db(ctx.character_id)
            if card:
                card_data = card.card_data if hasattr(card, 'card_data') else {}
                if isinstance(card_data, dict):
                    time_mode = card_data.get("time_mode", "real_time") or "real_time"
        except Exception:
            pass

        if time_mode == "none":
            return "【时间规则】你所在的世界没有明确的时间流逝。不要主动提及时间、日期、'今天''昨天''明天'。只有用户明确提到时间概念时，你才能自然接话。"
        if time_mode == "fixed" or time_mode == "relative":
            return "【时间规则】你所在世界的时间是独立的，与真实世界不同。不要在对话中提及真实世界的日期、节日、当前时间，除非用户主动提及。"
        # real_time：不做额外约束
        return None


class IdentityPipe(PromptPipe):
    """基础身份信息（角色卡优先覆盖）"""
    def process(self, ctx: PipelineContext) -> str:
        # 角色卡 user_name 优先，无则全局默认
        user_name = get_config("user_name", "用户")
        try:
            from core.character_card import CharacterCard
            card = CharacterCard.load_from_db(ctx.character_id)
            if card and card.user_name:
                user_name = card.user_name
        except Exception:
            pass

        try:
            from core.character_card import CharacterCard
            active = CharacterCard.get_active()
            if active and active.name:
                ai_name = active.name
            else:
                ai_name = get_config("ai_name", "夕语")
        except Exception:
            ai_name = get_config("ai_name", "夕语")
        parts = [f"""【身份】你的名字是「{ai_name}」。对方叫「{user_name}」。"""]
        try:
            from core.feedback_memory import get_behavior_rules
            rules = get_behavior_rules(max_rules=3, character_id=ctx.character_id)
            if rules:
                parts.append(rules)
        except Exception:
            pass
        return "\n\n".join(parts)


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
        ai_name = get_config("ai_name", "夕语")
        return f"""【思考】以「{ai_name}」的身份去想——ta在说什么？我感受到了什么？我想怎么回应？
关键：你不是在分析用户，只是在感受。禁止用"用户""对方""分析"这类词。

【回复】直接对ta说话。注意：回复内容必须紧跟在【回复】之后，不可省略此标签。"""


class PersonaPipe(PromptPipe):
    """人设模板（角色卡优先，否则用全局配置）"""
    _cache = {"hash": None, "text": None}

    def process(self, ctx: PipelineContext) -> str:
        if not ctx.is_module_enabled("persona"):
            return ""
        self._ctx_character_id = ctx.character_id
        return self._build_persona()

    def _build_persona(self) -> str:
        """人设构建：优先从角色卡读取，否则回退到全局配置"""
        try:
            from core.character_card import CharacterCard
            # 优先使用 context 中的 character_id 加载角色卡
            cid = getattr(self, '_ctx_character_id', 0)
            if cid:
                card = CharacterCard.load_from_db(cid)
                if card:
                    return self._build_from_card(card)
            # 回退到全局活跃角色
            active = CharacterCard.get_active()
            if active:
                return self._build_from_card(active)
        except Exception:
            pass
        # 回退到全局配置
        return build_persona()

    def _build_from_card(self, card) -> str:
        """从角色卡构建 prompt。
        system_prompt 已含完整人设时直接使用，避免与 description/personality/scenario 重复。
        """
        parts = []
        if card.system_prompt:
            parts.append(card.system_prompt)
        else:
            if card.description:
                parts.append(f"【角色设定】\n{card.data.get('description')}")
            if card.personality:
                parts.append(f"【性格】{card.data.get('personality')}")
            if card.scenario:
                parts.append(f"【场景】{card.data.get('scenario')}")
        if card.post_history_instructions:
            parts.append(f"【补充指令】{card.data.get('post_history_instructions')}")
        return "\n\n".join(parts)


class UserSummaryPipe(PromptPipe):
    """用户摘要 + 记忆索引 + 结构化表格（per-character）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("user_summary"):
            return None
        cid = ctx.character_id
        parts = []
        if ctx.msg_counter == 0:
            idx = _get_memory_index(character_id=cid)
            if idx:
                parts.append(idx)
        if ctx.msg_counter % 20 == 0:
            summary = _get_user_summary(character_id=cid)
            if summary:
                parts.append(summary)
        if ctx.msg_counter % 10 == 0:
            try:
                from core.profile_builder import get_table_prompt
                table = get_table_prompt(character_id=cid)
                if table:
                    parts.append(table)
            except Exception:
                pass
        return "\n\n".join(parts) if parts else None


class PersonalityTraitPipe(PromptPipe):
    """OCEAN 五维人格特征注入"""
    zone = "depth:2"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("personality_traits"):
            return None
        try:
            from core.emotion_evolution import get_all_traits, TRAIT_DESCRIPTIONS
            traits = get_all_traits(ctx.character_id)
            if not traits:
                return None
            labels = {
                "openness": "开放性 O",
                "conscientiousness": "尽责性 C",
                "extraversion": "外向性 E",
                "agreeableness": "宜人性 A",
                "neuroticism": "神经质 N",
            }
            lines = ["【人格特征】"]
            for key, label in labels.items():
                score = traits.get(key, 0.5)
                desc = ""
                if key in TRAIT_DESCRIPTIONS:
                    if score >= 0.6:
                        desc = TRAIT_DESCRIPTIONS[key]["high"]
                    elif score <= 0.3:
                        desc = TRAIT_DESCRIPTIONS[key]["low"]
                    else:
                        desc = TRAIT_DESCRIPTIONS[key]["mid"]
                lines.append(f"- {label}({score:.1f})：{desc}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"[pipeline] 人格特征注入失败: {e}")
            return None


class WorkMemoryPipe(PromptPipe):
    """工作记忆"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("work_memory"):
            return None
        if ctx.msg_counter % 20 != 3:  # offset 3
            return None
        return _get_scratch_context()


class OnboardingPipe(PromptPipe):
    """引导入职"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("onboarding"):
            return None
        if ctx.msg_counter % 20 != 7:  # offset 7
            return None
        return _get_onboarding_hint()


class EpisodicMemoryPipe(PromptPipe):
    """情景记忆 + 闪回（每 10 条注入情景，每 50 条检查闪回）"""
    zone = "dynamic"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("episodic_memory"):
            return None
        # 每 50 条检查闪回（offset 11）
        if ctx.msg_counter % 50 == 11 and ctx.user_message:
            try:
                from core.vector_store import search_similar, is_model_ready
                if is_model_ready():
                    results = search_similar(ctx.user_message, top_k=3, character_id=ctx.character_id)
                    if results:
                        doc, dist = results[0]
                        if dist < 0.3:
                            _n = get_config("ai_name", "夕语")
                            return f"（{_n}突然想起……上次你也是这样说的：「{doc[:30]}」）"
            except Exception:
                pass
        # 每 10 条注入近期情景（offset 1，per-character）
        if ctx.msg_counter % 10 != 1:
            return None
        try:
            from core.episodic_memory import get_episode_context
            context = get_episode_context(query=ctx.user_message, limit=3, character_id=ctx.character_id)
            return context if context else None
        except Exception:
            return None


class ContinuityPipe(PromptPipe):
    """对话连续感 + 跨对话续接"""
    zone = "depth:4"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("continuity"):
            return None
        from core.character_card import CharacterCard
        parts = []
        bridge = _get_continuity_bridge()
        if bridge:
            parts.append(bridge)
        # 跨对话续接提示（per-character，需开启 conversation_followup feature）
        if ctx.msg_counter == 0 and CharacterCard.is_feature_enabled("conversation_followup"):
            try:
                from core.episodic_memory import get_conversation_continuation
                cont = get_conversation_continuation(character_id=ctx.character_id)
                if cont:
                    parts.append(cont)
            except Exception:
                pass
        return "\n".join(parts) if parts else None


class EntityContextPipe(PromptPipe):
    """实体关联上下文（per-character）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("entity"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.profile_builder import get_entity_context
            return get_entity_context(ctx.user_message, character_id=ctx.character_id)
        except Exception as e:
            logger.warning(f"[pipeline] 实体上下文获取失败: {e}")
            return None


class FactsContextPipe(PromptPipe):
    """原子事实注入（每 15 条消息，通过 MemoryProvider 统一检索）"""
    zone = "depth:3"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("facts_context"):
            return None
        if ctx.msg_counter % 15 != 2:  # offset 2
            return None
        try:
            from core.memory_provider import MemoryProvider
            provider = MemoryProvider()
            return provider.get_context(
                character_id=ctx.character_id,
                query=ctx.user_message or "",
                limit=8,
            )
        except Exception:
            return None


class CorrectionPipe(PromptPipe):
    """纠错记忆注入：你之前在这点上错过，正确是 X。主动避坑。"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.user_message:
            return None
        try:
            from core.correction_memory import get_relevant_corrections
            corrections = get_relevant_corrections(ctx.user_message, top_k=3, character_id=ctx.character_id)
            if not corrections:
                return None
            lines = ["【纠错记忆——以下是你之前犯过的错，这次务必避免】"]
            for c in corrections:
                wrong = c["wrong_pattern"] or "（无错误原文）"
                correct = c["corrected_fact"]
                lines.append(f"- 错过：{wrong[:60]} → 正确：{correct[:60]}")
            lines.append("回复时若涉及相关内容，必须按「正确」那栏来说，不要重犯。")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"[pipeline] 纠错记忆查询失败: {e}")
            return None


class ConclusionPipe(PromptPipe):
    """辩证结论注入 + 记忆驱动人格调整（每10条注入一次）"""
    zone = "dynamic"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("conclusion"):
            return None
        if ctx.msg_counter % 10 != 4:  # offset 4
            return None
        try:
            from core.conclusion_engine import get_active_conclusions, get_conclusion_context
            base = get_conclusion_context(character_id=ctx.character_id)
            # 从结论中提取偏好，生成表达方式指令
            conclusions = get_active_conclusions(5, character_id=ctx.character_id)
            preferences = [c["text"] for c in conclusions if c.get("category") == "preference"]
            if preferences:
                adjustment = "注意：用户" + "、".join(preferences[:2])
                return f"{base}\n{adjustment}" if base else adjustment
            return base
        except Exception:
            return None


class VocabularyPipe(PromptPipe):
    """用户用语/梗注入（per-character，每 15 条注入一次）"""
    zone = "dynamic"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("vocabulary"):
            return None
        if ctx.msg_counter % 15 != 5:
            return None
        try:
            from core.db import get_chat_conn
            with get_chat_conn(ctx.character_id) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT phrase, meaning FROM user_vocabulary ORDER BY use_count DESC LIMIT 5")
                rows = cursor.fetchall()
            if rows:
                items = [f"{r['phrase']}（{r['meaning']}）" for r in rows if r['meaning']]
                if items:
                    return f"【用户常用语】{'/'.join(items)}"
        except Exception:
            pass
        return None


class OpinionPipe(PromptPipe):
    """AI 自主选择注入（角色卡 features.opinions 开启时）"""
    zone = "dynamic"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("opinions"):
            return None
        try:
            from core.character_card import CharacterCard
            active = CharacterCard.get_active()
            if not active:
                return None
            features = active.data.get("features", {})
            if not features.get("opinions"):
                return None
        except Exception:
            return None
        # 根据好感度调整表达强度
        try:
            from core.relationship import get_relationship
            affection, _ = get_relationship(character_id=ctx.character_id)
        except Exception:
            affection = 30
        if affection < 30:
            return "【个性提示】你有自己的喜好，但关系还不深，偶尔委婉提一句就好。"
        elif affection < 60:
            return "【个性提示】你有自己的喜好，可以自然地表达偏好，不用事事顺从。"
        else:
            return "【个性提示】你有自己的喜好和想法，大胆表达，你们已经很熟了。"


class SummariesPipe(PromptPipe):
    """三级摘要（注入深度 5）"""
    zone = "depth:5"
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
    """近期日程（per-character）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("schedule"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.db import get_chat_conn
            with get_chat_conn(ctx.character_id) as conn:
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
                # jieba 不可用时用简单分词（2-gram）
                msg = ctx.user_message
                query_words = set(msg[i:i+2] for i in range(len(msg)-1) if len(msg[i:i+2].strip()) == 2)
            if not query_words:
                return None
            relevant = []
            for r in upcoming:
                title_lower = r['title'].lower()
                if not query_words or any(w in title_lower for w in query_words):
                    relevant.append(r)
            if not relevant:
                return None
            lines = [f"{r['start_time'][:10]} {r['title']}" for r in relevant]
            return f"【用户近期日程】{'，'.join(lines)}。如果话题相关可以自然提及，不要刻意提起。"
        except Exception as e:
            logger.warning(f"[pipeline] 日程查询失败: {e}")
            return None


class RAGPipe(PromptPipe):
    """向量检索上下文（注入深度 3）"""
    zone = "depth:3"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("rag"):
            return None
        if not ctx.rag_context:
            return None
        return f"【我记得】你们之前聊到过这些——如果话题对得上可以自然提起：\n{ctx.rag_context}\n（用户没主动提就别刻意说，朋友想起旧事那种感觉就好。）"


class KnowledgeBasePipe(PromptPipe):
    """关键词触发知识注入（Lorebook，注入深度 2）"""
    zone = "depth:2"
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("knowledge_base"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.lorebook import lorebook_manager
            matched = lorebook_manager.match_entries(ctx.user_message)
            if not matched:
                return None
            texts = [m["content"] for m in matched]
            return "【相关知识】\n" + "\n".join(texts)
        except Exception as _kb_exc:
            from core.retry import silent_exc
            silent_exc("KnowledgeBasePipe", _kb_exc)
            return None


class DepthHintPipe(PromptPipe):
    """深度提示：根据上下文动态选择行为强化（注入深度 1）"""
    zone = "depth:1"

    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("depth_hint"):
            return None
        hints = []
        if ctx.emotion == "negative":
            hints.append("用户情绪不好，回复要温柔，先接住情绪再给建议。不要说教。")
        elif ctx.emotion == "positive":
            hints.append("用户心情不错，可以适当活跃气氛。")
        if len(ctx.user_message) < 5:
            hints.append("用户回复很短，你也简短回复，不要追问。")
        elif len(ctx.user_message) > 100:
            hints.append("用户说了很长一段，认真回应每个要点。")
        if any(kw in ctx.user_message for kw in ["帮", "帮我", "请问", "怎么"]):
            hints.append("用户在求助，直接给方案，不要废话。")
        if any(kw in ctx.user_message for kw in ["开心", "哈哈", "笑"]):
            hints.append("用户在开心，跟着一起开心就好。")
        if not hints:
            return None
        return "【提醒】" + " ".join(hints)


class PostHistoryPipe(PromptPipe):
    """Post-History Instructions — 生成前最后注入（最高优先级）"""
    zone = "depth:0"

    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("post_history"):
            return None
        # 优先从 context character_id 读角色卡
        try:
            from core.character_card import CharacterCard
            if ctx.character_id:
                card = CharacterCard.load_from_db(ctx.character_id)
                if card and card.post_history_instructions:
                    return card.post_history_instructions
        except Exception:
            pass
        # 回退到全局活跃角色
        try:
            from core.character_card import CharacterCard
            card = CharacterCard.get_active()
            if card and card.post_history_instructions:
                return card.post_history_instructions
        except Exception:
            pass
        # 回退到全局配置
        phi = get_config("post_history_instructions", "")
        return phi if phi else None


class UserPersonaPipe(PromptPipe):
    """用户身份注入"""
    zone = "dynamic"

    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("user_persona"):
            return None
        from core.user_persona import user_persona_manager
        desc = user_persona_manager.get_active_description()
        if not desc:
            return None
        return f"【关于我】{desc}"


class KnowledgeGraphPipe(PromptPipe):
    """知识图谱上下文（per-character）"""
    def process(self, ctx: PipelineContext) -> str | None:
        if not ctx.is_module_enabled("knowledge_graph"):
            return None
        if not ctx.user_message:
            return None
        try:
            from core.knowledge_graph import get_context_for_message
            return get_context_for_message(ctx.user_message, character_id=ctx.character_id)
        except Exception as e:
            logger.warning(f"[pipeline] 知识图谱查询失败: {e}")
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
        # 注意：不在 pipe 中清空，由 chat.py 在 LLM 回复成功后清空
        return dropped


# ─── 全局默认管道注册 ───

_default_pipeline = None
_default_pipeline_lock = threading.Lock()


def get_default_pipeline() -> PromptPipeline:
    """获取默认管道实例（懒加载，线程安全）"""
    global _default_pipeline
    if _default_pipeline is not None:
        return _default_pipeline
    with _default_pipeline_lock:
        if _default_pipeline is not None:
            return _default_pipeline

        p = PromptPipeline()

        # 静态管道（总是注入，顺序重要）
        p.register_static(IronRulePipe())
        p.register_static(FactRulePipe())
        p.register_static(ChatRulePipe())
        p.register_static(TimeRulePipe())
        p.register_static(IdentityPipe())
        # 动态管道（按优先级排序）
        p.register(PersonaPipe())
        p.register(PersonalityTraitPipe())
        p.register(ThinkingPipe())
        p.register(CustomContextPipe())
        p.register(ContinuityPipe())
        p.register(WorkMemoryPipe())
        p.register(OnboardingPipe())
        p.register(EpisodicMemoryPipe())
        p.register(EntityContextPipe())
        p.register(FactsContextPipe())
        p.register(CorrectionPipe())
        p.register(ConclusionPipe())
        p.register(VocabularyPipe())
        p.register(OpinionPipe())
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
        p.register(UserSummaryPipe())
        p.register(DepthHintPipe())
        p.register(PostHistoryPipe())
        p.register(UserPersonaPipe())

        _default_pipeline = p
        return p
