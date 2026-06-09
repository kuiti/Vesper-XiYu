# core/db/tools.py  |  todos + notes + countdowns + reminders + presets + habits

import json
from datetime import datetime
from . import get_conn


# ========== habits ==========

def get_habits():
    """获取所有习惯"""
    with get_conn() as conn:
        rows = conn.cursor().execute("SELECT * FROM habits ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def add_habit(name: str):
    """添加习惯"""
    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute("INSERT INTO habits (name, date, created) VALUES (?, ?, ?)", (name, today, now))


def update_habit(habit_id: int, checked: bool, streak: int):
    """更新习惯状态"""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute("UPDATE habits SET checked=?, streak=?, date=? WHERE id=?", (1 if checked else 0, streak, today, habit_id))


def delete_habit(habit_id: int) -> bool:
    """删除习惯"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM habits WHERE id=?", (habit_id,))
        return c.rowcount > 0


def reset_habits_daily():
    """每日重置：未打卡的连续天数归零"""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE habits SET checked=0, streak=CASE WHEN date != ? THEN 0 ELSE streak END WHERE date != ?",
            (today, today)
        )


# ========== todos ==========

def get_todos():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, task, done, created FROM todos ORDER BY id")
        rows = cursor.fetchall()
    return [{"id": r["id"], "task": r["task"], "done": bool(r["done"]), "created": r["created"]} for r in rows]


def add_todo(task):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO todos (task, done, created) VALUES (?, ?, ?)",
                       (task, 0, datetime.now().isoformat()))


def toggle_todo(todo_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE todos SET done = NOT done WHERE id = ?", (todo_id,))


def set_todo_done(todo_id, done):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE todos SET done = ? WHERE id = ?", (done, todo_id))


def delete_todo(todo_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))


# ========== notes ==========

def get_notes():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, content, created FROM notes ORDER BY id")
        rows = cursor.fetchall()
    return [{"id": r["id"], "title": r["title"], "content": r["content"], "created": r["created"]} for r in rows]


def add_note(title, content):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (title, content, created) VALUES (?, ?, ?)",
                       (title, content, datetime.now().isoformat()))


def delete_note(note_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))


# ========== countdowns ==========

def get_countdowns():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, target_date FROM countdowns")
        rows = cursor.fetchall()
    return [{"id": r["id"], "name": r["name"], "target": r["target_date"]} for r in rows]


def add_countdown(name, target_date):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO countdowns (name, target_date) VALUES (?, ?)", (name, target_date))


def delete_countdown(cd_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM countdowns WHERE id = ?", (cd_id,))


# ========== reminders ==========

def get_reminders():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, target_time, level, done, last_reminded FROM reminders")
        rows = cursor.fetchall()
    return [{"id": r["id"], "content": r["content"], "target_time": r["target_time"], "level": r["level"], "done": bool(r["done"]), "last_reminded": r["last_reminded"]} for r in rows]


def add_reminder(content, target_time, level):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO reminders (content, target_time, level, done, last_reminded) VALUES (?, ?, ?, ?, ?)",
                       (content, target_time, level, 0, None))


def update_reminder_done(reminder_id, done=True):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET done = ? WHERE id = ?", (1 if done else 0, reminder_id))


def update_reminder_last_reminded(reminder_id, last_reminded):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reminders SET last_reminded = ? WHERE id = ?", (last_reminded, reminder_id))


def delete_reminder(reminder_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


# ========== presets ==========
# 预设中的敏感键，保存/加载时静默过滤以保护 API 密钥不泄露
_SENSITIVE_KEYS = {"api_key", "amap_key"}


def get_presets():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, data FROM presets")
        rows = cursor.fetchall()
    result = {}
    for r in rows:
        d = json.loads(r["data"])
        for k in _SENSITIVE_KEYS:
            d.pop(k, None)
        result[r["name"]] = d
    return result


def save_preset(name, data):
    clean = {k: v for k, v in data.items() if k not in _SENSITIVE_KEYS}
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                       (name, json.dumps(clean, ensure_ascii=False)))


def delete_preset(name):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM presets WHERE name = ?", (name,))