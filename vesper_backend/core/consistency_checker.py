# core/consistency_checker.py — 回复一致性检查（三层）
"""回复一致性检查器：通过启发式规则、记忆匹配和 LLM 深度检查三层验证 AI 回复质量。"""

import logging
from core.llm_client import call_llm

logger = logging.getLogger(__name__)

def _heuristic_check(user_msg: str, ai_reply: str) -> str | None:
    """第一层：轻量启发式检查（无 LLM 调用），检测截断、重复和语言切换。"""
    if not ai_reply:
        return None

    # 1. 回复过短（可能是截断）
    if len(ai_reply.strip()) < 3 and not ai_reply.strip() in ("嗯", "哦", "好", "行", "是", "不"):
        return "（回复似乎被截断了）"

    # 2. 重复用户消息（可能是模型卡住）
    if user_msg and ai_reply.strip() == user_msg.strip():
        return None  # 让 LLM 处理

    # 3. 检测明显的语言切换（用户用中文，AI 用英文）
    chinese_chars = sum(1 for c in user_msg if '\u4e00' <= c <= '\u9fff')
    ai_chinese = sum(1 for c in ai_reply if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > len(user_msg) * 0.3 and ai_chinese < len(ai_reply) * 0.1 and len(ai_reply) > 10:
        logger.info("[一致性] 检测到语言切换，可能需要修正")
        return None  # 不自动修正，但记录

    return None


def _should_llm_check(ai_reply: str) -> bool:
    """判断是否需要 LLM 深度检查（仅在检测到强烈情感时触发）。"""
    from core.emotion_patterns import detect_emotion
    return detect_emotion(ai_reply) in ("sad", "love")


def _memory_consistency_check(ai_reply: str) -> str | None:
    """第二层：检查回复是否与已知用户事实（如性别、名字）矛盾，仅记录不修正。"""
    try:
        from core.profile_builder import get_profile
        profile = get_profile()
        if not profile:
            return None

        # 检查性别矛盾
        gender_info = profile.get("gender", {})
        if isinstance(gender_info, dict):
            gender = gender_info.get("value", "")
        else:
            gender = str(gender_info)
        if gender:
            if gender in ("男", "男性", "male") and any(w in ai_reply for w in ["小姐姐", "姐姐", "美女", "女士"]):
                logger.info(f"[一致性] 性别矛盾: 用户={gender}, 回复含女性称呼")
                return ai_reply  # 返回原回复，但记录
            if gender in ("女", "女性", "female") and any(w in ai_reply for w in ["小哥哥", "哥哥", "帅哥", "先生"]):
                logger.info(f"[一致性] 性别矛盾: 用户={gender}, 回复含男性称呼")
                return ai_reply

        # 检查名字矛盾（AI 用了错误的用户名字）
        name_info = profile.get("name", {})
        if isinstance(name_info, dict):
            user_name = name_info.get("value", "")
        else:
            user_name = str(name_info) if name_info else ""
        # 如果用户有名字，但回复中用了其他常见名字（排除 AI 自称）
        # 这个检查太严格，跳过

    except Exception:
        pass
    return None


def _correction_intercept(user_msg: str, ai_reply: str, character_id: int = 0) -> str | None:
    """第 2.5 层：纠错拦截——若 AI 又犯了之前纠正过的错，直接替换。"""
    try:
        from core.correction_memory import get_relevant_corrections, apply_correction_to_reply, mark_applied
        corrections = get_relevant_corrections(user_msg, top_k=3, character_id=character_id)
        if not corrections:
            return None
        fixed = apply_correction_to_reply(ai_reply, corrections)
        if fixed and fixed != ai_reply:
            try:
                mark_applied(corrections[0]["id"], character_id)
            except Exception:
                pass
            logger.info(f"[一致性] 纠错拦截触发: {ai_reply[:30]} → {fixed[:30]}")
            return fixed
    except Exception as e:
        logger.warning(f"[一致性] 纠错拦截失败: {e}")
    return None


def reflect_response(user_msg: str, ai_reply: str, persona: str, character_id: int = 0) -> str | None:
    """执行三层一致性检查，返回修正后的回复或 None（无需修正）。"""
    if not ai_reply:
        return None

    heuristic_result = _heuristic_check(user_msg, ai_reply)
    if heuristic_result:
        return heuristic_result

    _memory_consistency_check(ai_reply)

    correction_result = _correction_intercept(user_msg, ai_reply, character_id)
    if correction_result:
        return correction_result

    # 第三层：LLM 深度检查（仅情感强烈时）
    if not persona:
        return None
    if not _should_llm_check(ai_reply):
        return None

    prompt = f"""你是一个一致性检查器。检查以下 AI 回复是否与角色设定一致。

角色设定：{persona[:500]}
用户消息：{user_msg[:200]}
AI 回复：{ai_reply[:300]}

检查要点：
1. 语气是否符合角色设定？
2. AI 是否编造了没有的事实？
3. 回复是否自然不突兀？

如果全部通过，只输出"OK"。
如果有问题，输出修正后的回复。不要解释。"""

    try:
        result = call_llm(prompt=prompt, temperature=0.1, max_tokens=300, timeout=10)
        if result and result.strip() != "OK" and len(result.strip()) > 5:
            logger.info(f"[一致性] LLM 修正: {result[:60]}...")
            return result.strip()
    except Exception as e:
        logger.warning(f"[一致性] LLM 检查失败: {e}")
    return None
