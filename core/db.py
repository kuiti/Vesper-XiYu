# core/db.py  |  v3.8.1
# 完整数据库操作模块，包含提醒、记忆、预设等所有功能

import sqlite3
import json
from datetime import datetime, timedelta
import os

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)
DB_FILE = os.path.join("data", "vesper.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    return conn

def init_db():
    """初始化所有数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # config 表
    cursor.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
    # memory 表
    cursor.execute('CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)')
    # chat_history 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    ''')
    # todos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            done INTEGER,
            created TEXT
        )
    ''')
    # notes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            created TEXT
        )
    ''')
    # countdowns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS countdowns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            target_date TEXT
        )
    ''')
    # reminders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            target_time TEXT,
            level INTEGER,
            done INTEGER,
            last_reminded TEXT
        )
    ''')
    # presets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            data TEXT
        )
    ''')
    # conversation_summary 摘要表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            summary TEXT,
            key_points TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # FTS5 全文搜索表
    cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts 
        USING fts5(content, role, timestamp, tokenize='unicode61')
    ''')
    # 触发器：插入时同步
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS chat_fts_insert 
        AFTER INSERT ON chat_history
        BEGIN
            INSERT INTO chat_fts(rowid, content, role, timestamp)
            VALUES (new.id, new.content, new.role, new.timestamp);
        END;
    ''')
    # 触发器：删除时同步
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS chat_fts_delete 
        AFTER DELETE ON chat_history
        BEGIN
            DELETE FROM chat_fts WHERE rowid = old.id;
        END;
    ''')
    conn.commit()
    conn.close()

# ========== config 操作 ==========
def get_config(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["value"])
        except:
            return row["value"]
    return default

def set_config(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    else:
        value = str(value)
    cursor.execute("REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ========== memory 操作 ==========
def get_memory():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM memory")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def set_memory(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO memory (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def delete_memory(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
    conn.commit()
    conn.close()

# ========== chat_history ==========
def get_all_chat_messages():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

def add_chat_message(role, content, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
                   (role, content, timestamp))
    conn.commit()
    conn.close()

def clear_chat_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history")
    cursor.execute("DELETE FROM chat_fts")
    conn.commit()
    conn.close()

def delete_chat_history_older_than(days: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("SELECT id FROM chat_history WHERE timestamp < ?", (cutoff,))
    ids = [row["id"] for row in cursor.fetchall()]
    if ids:
        placeholders = ','.join('?' for _ in ids)
        cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
        cursor.execute("DELETE FROM chat_history WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()

def delete_chat_history_between(start_iso: str, end_iso: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
    ids = [row["id"] for row in cursor.fetchall()]
    if ids:
        placeholders = ','.join('?' for _ in ids)
        cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
        cursor.execute("DELETE FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
        conn.commit()
        return len(ids)
    return 0

def search_chat_messages(keyword: str, limit: int = 20):
    conn = get_db_connection()
    cursor = conn.cursor()
    safe_keyword = '"' + keyword.replace('"', '""') + '"'
    cursor.execute('''
        SELECT rowid, content, role, timestamp
        FROM chat_fts
        WHERE chat_fts MATCH ? 
        ORDER BY rank
        LIMIT ?
    ''', (safe_keyword, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["rowid"], "content": r["content"], "role": r["role"], "timestamp": r["timestamp"]} for r in rows]

def rebuild_fts_index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_fts")
    cursor.execute("""
        INSERT INTO chat_fts(rowid, content, role, timestamp)
        SELECT id, content, role, timestamp FROM chat_history
    """)
    conn.commit()
    conn.close()

# ========== todos ==========
def get_todos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, task, done, created FROM todos ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "task": r["task"], "done": bool(r["done"]), "created": r["created"]} for r in rows]

def add_todo(task):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO todos (task, done, created) VALUES (?, ?, ?)",
                   (task, 0, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def toggle_todo(todo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET done = NOT done WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def set_todo_done(todo_id, done):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE todos SET done = ? WHERE id = ?", (done, todo_id))
    conn.commit()
    conn.close()

def delete_todo(todo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

# ========== notes ==========
def get_notes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content, created FROM notes ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "title": r["title"], "content": r["content"], "created": r["created"]} for r in rows]

def add_note(title, content):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notes (title, content, created) VALUES (?, ?, ?)",
                   (title, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def delete_note(note_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

# ========== countdowns ==========
def get_countdowns():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, target_date FROM countdowns")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "target": r["target_date"]} for r in rows]

def add_countdown(name, target_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO countdowns (name, target_date) VALUES (?, ?)", (name, target_date))
    conn.commit()
    conn.close()

def delete_countdown(cd_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM countdowns WHERE id = ?", (cd_id,))
    conn.commit()
    conn.close()

# ========== reminders ==========
def get_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, target_time, level, done, last_reminded FROM reminders")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "content": r["content"], "target_time": r["target_time"], "level": r["level"], "done": bool(r["done"]), "last_reminded": r["last_reminded"]} for r in rows]

def add_reminder(content, target_time, level):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reminders (content, target_time, level, done, last_reminded) VALUES (?, ?, ?, ?, ?)",
                   (content, target_time, level, 0, None))
    conn.commit()
    conn.close()

def update_reminder_done(reminder_id, done=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET done = ? WHERE id = ?", (1 if done else 0, reminder_id))
    conn.commit()
    conn.close()

def update_reminder_last_reminded(reminder_id, last_reminded):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET last_reminded = ? WHERE id = ?", (last_reminded, reminder_id))
    conn.commit()
    conn.close()

def delete_reminder(reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

# ========== presets ==========
_SENSITIVE_KEYS = {"api_key", "amap_key"}


def get_presets():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, data FROM presets")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        d = json.loads(r["data"])
        for k in _SENSITIVE_KEYS:
            d.pop(k, None)
        result[r["name"]] = d
    return result


def save_preset(name, data):
    clean = {k: v for k, v in data.items() if k not in _SENSITIVE_KEYS}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                   (name, json.dumps(clean, ensure_ascii=False)))
    conn.commit()
    conn.close()

def delete_preset(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM presets WHERE name = ?", (name,))
    conn.commit()
    conn.close()

# ========== conversation summary ==========
def get_last_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversation_summary ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "summary": row["summary"],
            "key_points": json.loads(row["key_points"]) if row["key_points"] else [],
            "created_at": row["created_at"]
        }
    return None

def add_summary(start_time, end_time, summary, key_points):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversation_summary (start_time, end_time, summary, key_points) VALUES (?, ?, ?, ?)",
        (start_time, end_time, summary, json.dumps(key_points, ensure_ascii=False))
    )
    conn.commit()
    conn.close()
    set_memory("_active_summary", summary)
    old_keypoints = get_active_keypoints()
    merged = merge_keypoints(old_keypoints, key_points)
    set_memory("_active_keypoints", json.dumps(merged, ensure_ascii=False))

def get_active_summary():
    return get_memory().get("_active_summary", "")

def get_active_keypoints():
    val = get_memory().get("_active_keypoints", "[]")
    try:
        return json.loads(val)
    except:
        return []

def merge_keypoints(old_list, new_list, max_items=10):
    combined = new_list + old_list
    seen = set()
    unique = []
    for item in combined:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:max_items]

def reset_active_memory():
    set_memory("_active_summary", "")
    set_memory("_active_keypoints", "[]")

def get_messages_since_last_summary():
    last = get_last_summary()
    if last:
        start_time = last["end_time"]
    else:
        start_time = None
    conn = get_db_connection()
    cursor = conn.cursor()
    if start_time:
        cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE timestamp > ? ORDER BY id", (start_time,))
    else:
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

# 初始化数据库（如果不存在）
init_db()