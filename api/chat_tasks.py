"""
chat_tasks.py —— 从 chat.py 提取的后台任务和工具函数

包含：深度提示、DSML清理、提醒规则、背景更新、每日演化、成就、惊喜等。
天气/日记调度器因依赖全局 WS 状态，留在 chat.py。
"""

import asyncio
import json
import random
import re
import threading
from datetime import datetime, timedelta

from core.db import (
    get_config, set_config, get_reminders, update_reminder_last_reminded, get_conn,
)


# ─── 深度提示 ───

def _build_depth_hint(user_message: str, emotion: str) -> str:
    """构建深度提示：根据上下文动态选择行为强化提示"""
    hints = []
    if emotion == "negative":
        hints.append("用户情绪不好，回复要温柔，先接住情绪再给建议。不要说教。")
    elif emotion == "positive":
        hints.append("用户心情不错，可以适当活跃气氛。")
    if len(user_message) < 5:
        hints.append("用户回复很短，你也简短回复，不要追问。")
    elif len(user_message) > 100:
        hints.append("用户说了很长一段，认真回应每个要点。")
    if any(kw in user_message for kw in ["帮", "帮我", "请问", "怎么"]):
        hints.append("用户在求助，直接给方案，不要废话。")
    if any(kw in user_message for kw in ["开心", "哈哈", "笑"]):
        hints.append("用户在开心，跟着一起开心就好。")
    if not hints:
        return ""
    return "【提醒】" + " ".join(hints)


# ─── DSML 清理 ───

def _clean_dsml(text: str) -> str:
    """清理 DSML 工具调用文本，防止泄露到聊天记录"""
    text = re.sub(r'<\|\|DSML\|\|tool_calls>.*?</\|\|DSML\|\|tool_calls>', '', text, flags=re.DOTALL)
    text = re.sub(r'<\|\|DSML\|\|[^>]*>', '', text)
    text = re.sub(r'</\|\|DSML\|\|[^>]*>', '', text)
    return text.strip()


# ─── 提醒规则 ───

REMINDER_RULES = {
    7: {"name": "强制", "advance_minutes": 0, "repeat_interval": 30},
    6: {"name": "重要", "advance_minutes": 21*24*60, "repeat_interval": 1440},
    5: {"name": "考试", "advance_minutes": 14*24*60, "repeat_interval": 1440},
    4: {"name": "待办", "advance_minutes": 5*24*60, "repeat_interval": 720},
    3: {"name": "计划", "advance_minutes": 2*24*60, "repeat_interval": 360},
    2: {"name": "日常", "advance_minutes": 5*60, "repeat_interval": None},
    1: {"name": "喝水", "advance_minutes": 30, "repeat_interval": None},
}


# ─── 背景更新 ───

def _apply_background_update(background_update):
    """将 LLM（情感分析）检测到的背景更新写入 ai_background（结构化JSON）"""
    if not background_update:
        return
    if isinstance(background_update, dict):
        action = background_update.get("action", "add")
        key = background_update.get("key", "")
        value = background_update.get("value", "")
        if not key:
            return
        current = get_config("ai_background", "")
        bg = {}
        if current:
            try:
                bg = json.loads(current)
            except json.JSONDecodeError:
                bg = {"legacy": current}
        if action == "remove":
            bg.pop(key, None)
        elif action == "replace":
            bg[key] = value
        else:
            if key in bg and bg[key] == value:
                return
            bg[key] = value
        set_config("ai_background", json.dumps(bg, ensure_ascii=False))
        return
    if isinstance(background_update, str):
        bg_text = background_update.strip()
        if not bg_text:
            return
        current = get_config("ai_background", "")
        if current:
            try:
                existing = json.loads(current)
            except json.JSONDecodeError:
                existing = {"legacy": current}
        else:
            existing = {}
        if bg_text not in str(existing):
            existing[f"text_{len(existing)}"] = bg_text
            set_config("ai_background", json.dumps(existing, ensure_ascii=False))


# ─── 提醒检查 ───

def check_reminders():
    """检查所有未完成的提醒，返回结构化数据列表"""
    now = datetime.now()
    reminders = get_reminders()
    results = []
    for r in reminders:
        if r.get("done"):
            continue
        try:
            target = datetime.fromisoformat(r["target_time"])
        except ValueError:
            continue
        if now > target and r.get("level") != 7:
            continue
        minutes_left = (target - now).total_seconds() / 60
        rule = REMINDER_RULES.get(r["level"], REMINDER_RULES[4])
        advance = rule.get("advance_minutes", 0)
        if minutes_left > advance:
            continue
        last_reminded = r.get("last_reminded")
        repeat_interval = rule.get("repeat_interval")
        if last_reminded is None:
            need_remind = True
        elif repeat_interval is None:
            need_remind = False
        else:
            try:
                last = datetime.fromisoformat(last_reminded)
                need_remind = (now - last).total_seconds() / 60 >= repeat_interval
            except ValueError:
                need_remind = True
        if need_remind:
            results.append({
                "id": r["id"], "level": r["level"], "level_name": rule["name"],
                "content": r["content"], "target_time": target.strftime("%Y-%m-%d %H:%M"),
                "minutes_left": int(minutes_left),
            })
            update_reminder_last_reminded(r["id"], now.isoformat())
    return results


# ─── 每日情绪演化 ───

def _trigger_daily_evolution():
    try:
        from core.emotion_evolution import process_daily_evolution
        process_daily_evolution()
    except Exception as e:
        print(f"[情绪演化] 触发异常: {e}")


# ─── 连续天数 + 成就 ───

def _calc_consecutive_days(msg_count, ws, loop):
    """后台计算连续互动天数 + 触发成就检查"""
    try:
        cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        with get_conn() as cc:
            cur = cc.execute(
                "SELECT DISTINCT substr(timestamp,1,10) as d FROM chat_history "
                "WHERE timestamp >= ? ORDER BY d DESC", (cutoff,)
            )
            dates = [r["d"] for r in cur.fetchall()]
        today = datetime.now().strftime("%Y-%m-%d")
        consec = 0
        expected = datetime.strptime(today, "%Y-%m-%d")
        for d in dates:
            d_parsed = datetime.strptime(d, "%Y-%m-%d")
            if d_parsed == expected:
                consec += 1
                expected -= timedelta(days=1)
            else:
                break
        _check_achievements(msg_count, consec, ws, loop)
    except Exception as e:
        print(f"[连续天数] 计算失败: {e}")


def _check_achievements(msg_count, consecutive_days, ws, loop):
    try:
        from core.db import check_achievements as _check_ach
        from core.relationship import get_relationship
        affection, trust = get_relationship()
        hour = datetime.now().hour
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT substr(timestamp,1,10)) as days FROM chat_history")
            total_days = cursor.fetchone()["days"] or 0
        unlocked = _check_ach(msg_count, consecutive_days, total_days, hour, affection, trust)
        if unlocked:
            for a in unlocked:
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_text(json.dumps({"type": "achievement", "data": a})), loop
                    )
                except Exception:
                    pass
    except Exception as e:
        print(f"[成就] 检查失败: {e}")


# ─── 小惊喜 ───

def _maybe_surprise(ws, loop):
    """后台随机触发小惊喜"""
    try:
        from core.relationship import get_relationship
        affection, _ = get_relationship()
        hour = datetime.now().hour
        last_surprise = get_config("_last_surprise", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if affection >= 30 and hour >= 18 and last_surprise != today and random.random() < 0.1:
            from core.llm_client import call_llm
            ai_name = get_config("ai_name", "夕语")
            _p = get_config('personality', {})
            _tone = _p.get('tone', '冷静') if isinstance(_p, dict) else '冷静'
            prompt = (f"你是「{ai_name}」，一个AI伙伴。请给用户分享一个小惊喜——"
                      f"可以是一首短诗、一个有趣的冷知识、或一句暖心的话。不超过50字，语气{_tone}。")
            result = call_llm(prompt=prompt, temperature=0.9, max_tokens=100, timeout=10)
            if result:
                set_config("_last_surprise", today)
                asyncio.run_coroutine_threadsafe(
                    ws.send_text(json.dumps({"type": "surprise", "content": result})), loop
                )
    except Exception as e:
        print(f"[惊喜] 生成失败: {e}")


# ─── 目标完成检查 ───

def _check_goal_completion(user_message: str):
    try:
        from core.goal_tracker import check_goal_completion
        check_goal_completion(user_message)
    except Exception as e:
        print(f"[目标检测] 异常: {e}")


# ─── DSML 工具调用解析 ───

def _parse_dsml_tool_calls(text: str) -> list:
    """解析 DeepSeek DSML 格式的工具调用文本"""
    results = []
    pattern = r'<\｜\｜DSML\｜\｜invoke\s+name="([^"]+)">(.*?)</\｜\｜DSML\｜\｜invoke>'
    for match in re.finditer(pattern, text, re.DOTALL):
        func_name = match.group(1)
        body = match.group(2)
        args = {}
        param_pattern = r'<\｜\｜DSML\｜\｜parameter\s+name="([^"]+)"[^>]*>(.*?)</\｜\｜DSML\｜\｜parameter>'
        for pm in re.finditer(param_pattern, body, re.DOTALL):
            pname = pm.group(1)
            pval = pm.group(2).strip()
            try:
                pval = int(pval)
            except ValueError:
                pass
            args[pname] = pval
        results.append({"name": func_name, "args": args})
    return results
