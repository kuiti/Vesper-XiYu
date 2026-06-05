# core/db.py  |  v3.8.1
# 完整数据库操作模块，包含提醒、记忆、预设等所有功能

import sqlite3
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
import os

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)
DB_FILE = os.path.join("data", "sakura.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # WAL 模式支持 WebSocket 线程并发读写不互锁
    conn.execute("PRAGMA journal_mode=WAL")
    # busy_timeout=3000：写锁等待最多 3 秒再放弃，避免并发写入立即报错
    conn.execute("PRAGMA busy_timeout=3000")
    return conn

_db_initialized = False

def _ensure_db():
    """首次连接时执行数据库初始化（建表 + 迁移），后续调用跳过"""
    global _db_initialized
    if _db_initialized:
        return
    _db_initialized = True
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # config 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
        )""")
        # chat_history 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT, content TEXT, timestamp TEXT,
            parent_id INTEGER, branch_id TEXT, archived INTEGER DEFAULT 0
        )""")
        # memory 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS memory (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
        )""")
        # user_profile 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS user_profile (
            key TEXT PRIMARY KEY, value TEXT, confidence REAL, extracted_at TEXT
        )""")
        # summary 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary TEXT, key_points TEXT,
            start_time TEXT, end_time TEXT, created_at TEXT,
            is_active INTEGER DEFAULT 1
        )""")
        # tiered_summary 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS tiered_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level INTEGER, summary TEXT, key_points TEXT,
            importance REAL, remaining_days REAL,
            start_time TEXT, end_time TEXT, created_at TEXT,
            is_active INTEGER DEFAULT 1
        )""")
        # summary_msg_counter 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS summary_msg_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            count INTEGER DEFAULT 0,
            last_level1_at INTEGER DEFAULT 0,
            last_level2_at INTEGER DEFAULT 0,
            last_level3_at INTEGER DEFAULT 0
        )""")
        cursor.execute("INSERT OR IGNORE INTO summary_msg_counter (id) VALUES (1)")
        # todos 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT, done INTEGER DEFAULT 0, created_at TEXT
        )""")
        # notes 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, content TEXT, created_at TEXT, updated_at TEXT
        )""")
        # countdowns 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS countdowns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, target_time TEXT, created_at TEXT
        )""")
        # reminders 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT, target_time TEXT, level INTEGER DEFAULT 2,
            done INTEGER DEFAULT 0, last_reminded TEXT, created_at TEXT
        )""")
        # presets 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS presets (
            name TEXT PRIMARY KEY, data TEXT, created_at TEXT
        )""")
        # documents 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT, chunks INTEGER, size INTEGER, uploaded_at TEXT
        )""")
        # 情绪每日记录
        cursor.execute("""CREATE TABLE IF NOT EXISTS emotion_daily (
            date TEXT PRIMARY KEY,
            score REAL DEFAULT 0,
            positive_count INTEGER DEFAULT 0,
            negative_count INTEGER DEFAULT 0,
            neutral_count INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            updated_at TEXT
        )""")
        # 好感度/信任度
        cursor.execute("""CREATE TABLE IF NOT EXISTS relationship (
            key TEXT PRIMARY KEY,
            value REAL DEFAULT 50,
            updated_at TEXT
        )""")
        # 需求模式积累
        cursor.execute("""CREATE TABLE IF NOT EXISTS demand_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_context TEXT,
            demand_level TEXT,
            emotion_analysis TEXT,
            latent_need TEXT,
            frequency INTEGER DEFAULT 1,
            last_matched TEXT,
            created_at TEXT
        )""")
        # FTS5 全文搜索
        cursor.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5(
            content, content_rowid='id', content='chat_history'
        )""")
        # FTS5 同步触发器
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_ai AFTER INSERT ON chat_history BEGIN
            INSERT INTO chat_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_ad AFTER DELETE ON chat_history BEGIN
            INSERT INTO chat_fts(chat_fts, rowid, content) VALUES('delete', old.id, old.content);
        END""")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_au AFTER UPDATE ON chat_history BEGIN
            INSERT INTO chat_fts(chat_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO chat_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        conn.commit()

        # 初始化好感度/信任度/AI情绪（仅首次）
        now_iso = datetime.now().isoformat()
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('affection', 30, ?)", (now_iso,))
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('trust', 50, ?)", (now_iso,))
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('ai_emotion', 'neutral', ?)", (now_iso,))
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('recent_negative_count', 0, ?)", (now_iso,))
        conn.commit()

        # schema 迁移（安全，重复执行不报错）
        for col, col_def in [("parent_id", "INTEGER"), ("branch_id", "TEXT"), ("archived", "INTEGER DEFAULT 0")]:
            try:
                conn.execute(f"ALTER TABLE chat_history ADD COLUMN {col} {col_def}")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # 一次性迁移：旧摘要系统 → 三级摘要系统
        if not _get_config_direct(cursor, "_tiered_migration_done"):
            try:
                # migrate_old_summaries 用 get_conn()，这里直接内联关键逻辑
                cursor.execute("SELECT summary, key_points, start_time, end_time FROM summary WHERE is_active=1")
                old_rows = cursor.fetchall()
                for r in old_rows:
                    kp = r["key_points"]
                    if isinstance(kp, str):
                        try:
                            kp = json.loads(kp)
                        except (json.JSONDecodeError, ValueError):
                            kp = []
                    cursor.execute(
                        """INSERT INTO tiered_summary
                           (level, summary, key_points, importance, remaining_days, start_time, end_time)
                           VALUES (1, ?, ?, 0.5, 5, ?, ?)""",
                        (r["summary"], json.dumps(kp, ensure_ascii=False), r["start_time"], r["end_time"])
                    )
                cursor.execute("SELECT COUNT(*) FROM chat_history")
                msg_count = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE summary_msg_counter SET count=?, last_level1_at=?, last_level2_at=?, last_level3_at=? WHERE id=1",
                    (msg_count, (msg_count // 10) * 10, (msg_count // 50) * 50, (msg_count // 100) * 100)
                )
                # 标记迁移完成
                now = datetime.now().isoformat()
                cursor.execute("REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                               ("_tiered_migration_done", "true", now))
                conn.commit()
                print("[迁移] 旧摘要数据已迁移至三级摘要系统")
            except Exception as e:
                print(f"[迁移] 摘要迁移失败: {e}")
    finally:
        conn.close()


def _get_config_direct(cursor, key, default=""):
    """内部用：直接用游标读 config，避免递归调用 get_conn"""
    cursor.execute("SELECT value FROM config WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default


@contextmanager
def get_conn():
    """数据库连接上下文管理器，自动 commit/rollback/close"""
    _ensure_db()
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """初始化所有数据库表"""
    with get_conn() as conn:
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
        # 文档知识库表
        cursor.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, chunks INTEGER DEFAULT 1, size INTEGER DEFAULT 0, uploaded_at TEXT NOT NULL)''')
        # 用户画像表
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_profile (key TEXT PRIMARY KEY, value TEXT NOT NULL, confidence REAL DEFAULT 1.0, extracted_at TEXT NOT NULL)''')
        # 日程表
        cursor.execute('''CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT DEFAULT '', start_time TEXT, end_time TEXT DEFAULT '', location TEXT DEFAULT '', all_day INTEGER DEFAULT 0, color TEXT DEFAULT '#5390d4')''')
        # FTS5 全文搜索表
        # unicode61 分词器正确处理中英混合文本（按 Unicode 边界分词）
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
        # ========== 三级摘要系统表 ==========
        # 三级摘要表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiered_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level INTEGER NOT NULL,
                summary TEXT NOT NULL,
                key_points TEXT,
                importance REAL DEFAULT 0.5,
                remaining_days REAL NOT NULL,
                start_time TEXT,
                end_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_summary_ids TEXT,
                mention_count INTEGER DEFAULT 0,
                daily_boost REAL DEFAULT 0
            )
        ''')
        # 亡语表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS death_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                level INTEGER NOT NULL,
                summary TEXT NOT NULL,
                key_points TEXT,
                importance REAL,
                start_time TEXT,
                end_time TEXT,
                created_at TEXT,
                archived_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 消息计数器（单例）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summary_msg_counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                count INTEGER NOT NULL DEFAULT 0,
                last_level1_at INTEGER DEFAULT 0,
                last_level2_at INTEGER DEFAULT 0,
                last_level3_at INTEGER DEFAULT 0
            )
        ''')
        # 确保计数器单例行存在
        cursor.execute('INSERT OR IGNORE INTO summary_msg_counter (id, count) VALUES (1, 0)')

# ========== config 操作 ==========
def get_config(key, default=None):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, ValueError):
            v = row["value"]
            if v in ("True", "true"):
                return True
            if v in ("False", "false"):
                return False
            return v
    return default

def set_config(key, value):
    with get_conn() as conn:
        cursor = conn.cursor()
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        cursor.execute("REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))

# ========== memory 操作 ==========
def get_memory():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM memory")
        rows = cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}

def set_memory(key, value):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO memory (key, value) VALUES (?, ?)", (key, value))

def delete_memory(key):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory WHERE key = ?", (key,))

# ========== chat_history ==========
def get_all_chat_messages():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

def get_last_user_messages(n=3):
    """获取最近 n 条用户消息（按时间倒序）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT ?",
            (n,)
        )
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

def add_chat_message(role, content, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
                       (role, content, timestamp))

def clear_chat_history():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM chat_fts")
        cursor.execute("DELETE FROM tiered_summary")
        cursor.execute("DELETE FROM death_archive")
    reset_msg_counter()
    reset_active_memory()

def delete_chat_history_older_than(days: int):
    with get_conn() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("SELECT id FROM chat_history WHERE timestamp < ?", (cutoff,))
        ids = [row["id"] for row in cursor.fetchall()]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
            cursor.execute("DELETE FROM chat_history WHERE timestamp < ?", (cutoff,))

def delete_chat_history_between(start_iso: str, end_iso: str):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
        ids = [row["id"] for row in cursor.fetchall()]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
            cursor.execute("DELETE FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
            return len(ids)
    return 0

def search_chat_messages(keyword: str, limit: int = 20):
    with get_conn() as conn:
        cursor = conn.cursor()
        # FTS5 MATCH 不支持标准参数化查询，必须手动转义双引号防止注入和语法错误
        safe_keyword = '"' + keyword.replace('"', '""') + '"'
        cursor.execute('''
            SELECT rowid, content, role, timestamp
            FROM chat_fts
            WHERE chat_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        ''', (safe_keyword, limit))
        rows = cursor.fetchall()
    return [{"id": r["rowid"], "content": r["content"], "role": r["role"], "timestamp": r["timestamp"]} for r in rows]

def rebuild_fts_index():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_fts")
        cursor.execute("""
            INSERT INTO chat_fts(rowid, content, role, timestamp)
            SELECT id, content, role, timestamp FROM chat_history
        """)

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

# ========== conversation summary ==========
def get_last_summary():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversation_summary ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
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
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversation_summary (start_time, end_time, summary, key_points) VALUES (?, ?, ?, ?)",
            (start_time, end_time, summary, json.dumps(key_points, ensure_ascii=False))
        )
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
    except (json.JSONDecodeError, ValueError):
        return []

def merge_keypoints(old_list, new_list, max_items=10):
    # 新关键点优先（new_list + old_list），最多保留 max_items 条，精确文本去重
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
    with get_conn() as conn:
        cursor = conn.cursor()
        if start_time:
            cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE timestamp > ? ORDER BY id", (start_time,))
        else:
            cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

# ========== 三级摘要系统操作 ==========

# --- 消息计数器 ---
def get_msg_counter():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row["count"] if row else 0

def increment_msg_counter():
    """原子递增并返回新值"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = count + 1 WHERE id = 1")
        cursor.execute("SELECT count FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row["count"] if row else 1

def get_last_trigger_at(level):
    if level not in (1, 2, 3):
        raise ValueError(f"Invalid level: {level}")
    col = f"last_level{level}_at"
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {col} FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row[col] if row else 0

def set_last_trigger_at(level, count):
    if level not in (1, 2, 3):
        raise ValueError(f"Invalid level: {level}")
    col = f"last_level{level}_at"
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE summary_msg_counter SET {col} = ? WHERE id = 1", (count,))

def reset_msg_counter():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = 0, last_level1_at = 0, last_level2_at = 0, last_level3_at = 0 WHERE id = 1")

# --- 三级摘要 CRUD ---
def add_tiered_summary(level, summary, key_points, importance, remaining_days, start_time, end_time, source_ids=None):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO tiered_summary
               (level, summary, key_points, importance, remaining_days, start_time, end_time, source_summary_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (level, summary, json.dumps(key_points, ensure_ascii=False), importance, remaining_days,
             start_time, end_time, json.dumps(source_ids) if source_ids else None)
        )
        summary_id = cursor.lastrowid
    return summary_id

def get_active_tiered_summaries():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE remaining_days > 0 ORDER BY level, created_at")
        rows = cursor.fetchall()
    result = []
    for r in rows:
        kp = r["key_points"]
        if isinstance(kp, str):
            try:
                kp = json.loads(kp)
            except (json.JSONDecodeError, ValueError):
                kp = []
        result.append({
            "id": r["id"], "level": r["level"], "summary": r["summary"],
            "key_points": kp or [], "importance": r["importance"],
            "remaining_days": r["remaining_days"], "start_time": r["start_time"],
            "end_time": r["end_time"], "created_at": r["created_at"],
            "mention_count": r["mention_count"], "daily_boost": r["daily_boost"]
        })
    return result

def get_tiered_summaries_by_level(level):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE level = ? AND remaining_days > 0 ORDER BY created_at", (level,))
        rows = cursor.fetchall()
    result = []
    for r in rows:
        kp = r["key_points"]
        if isinstance(kp, str):
            try:
                kp = json.loads(kp)
            except (json.JSONDecodeError, ValueError):
                kp = []
        result.append({
            "id": r["id"], "level": r["level"], "summary": r["summary"],
            "key_points": kp or [], "importance": r["importance"],
            "remaining_days": r["remaining_days"], "mention_count": r["mention_count"],
            "daily_boost": r["daily_boost"]
        })
    return result

def get_all_active_keypoints(max_items=30):
    summaries = get_active_tiered_summaries()
    seen = set()
    unique = []
    for s in summaries:
        for kp in s.get("key_points", []):
            if kp not in seen:
                seen.add(kp)
                unique.append(kp)
    return unique[:max_items]

def get_messages_since_last_tiered_summary(limit=None):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT end_time FROM tiered_summary ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row and row["end_time"]:
            sql = "SELECT role, content, timestamp FROM chat_history WHERE timestamp > ? ORDER BY id"
            params = (row["end_time"],)
        else:
            sql = "SELECT role, content, timestamp FROM chat_history ORDER BY id"
            params = ()
        if limit:
            # 先倒序取最近 N 条，再恢复正序
            sql = sql.replace("ORDER BY id", "ORDER BY id DESC")
            sql += " LIMIT ?"
            params = (*params, limit) if params else (limit,)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if limit:
            rows = rows[::-1]  # 恢复时间正序
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

def decay_summaries(days_elapsed):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tiered_summary SET remaining_days = remaining_days - ? WHERE remaining_days > 0", (days_elapsed,))

def archive_expired_summaries():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE remaining_days <= 0")
        expired = cursor.fetchall()
        count = 0
        for r in expired:
            cursor.execute(
                """INSERT INTO death_archive
                   (original_id, level, summary, key_points, importance, start_time, end_time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["id"], r["level"], r["summary"], r["key_points"], r["importance"],
                 r["start_time"], r["end_time"], r["created_at"])
            )
            count += 1
        if expired:
            cursor.execute("DELETE FROM tiered_summary WHERE remaining_days <= 0")
    return count

def get_death_archive():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM death_archive ORDER BY archived_at DESC")
        rows = cursor.fetchall()
    return [{"id": r["id"], "original_id": r["original_id"], "level": r["level"],
             "summary": r["summary"], "key_points": json.loads(r["key_points"]) if r["key_points"] else [],
             "importance": r["importance"], "start_time": r["start_time"],
             "end_time": r["end_time"], "created_at": r["created_at"],
             "archived_at": r["archived_at"]} for r in rows]

# --- 提及操作 ---
def increment_mention(summary_id, boost_days):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tiered_summary SET mention_count = mention_count + 1, daily_boost = daily_boost + ? WHERE id = ?",
            (boost_days, summary_id)
        )

def reset_daily_boost():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tiered_summary SET daily_boost = 0 WHERE daily_boost > 0")

# --- 迁移 ---
def migrate_old_summaries():
    """一次性迁移：旧 conversation_summary → tiered_summary level=1"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversation_summary ORDER BY id")
        old_rows = cursor.fetchall()
        for r in old_rows:
            kp = r["key_points"]
            if isinstance(kp, str):
                try:
                    kp = json.loads(kp)
                except (json.JSONDecodeError, ValueError):
                    kp = []
            cursor.execute(
                """INSERT INTO tiered_summary
                   (level, summary, key_points, importance, remaining_days, start_time, end_time)
                   VALUES (1, ?, ?, 0.5, 5, ?, ?)""",
                (r["summary"], json.dumps(kp, ensure_ascii=False), r["start_time"], r["end_time"])
            )
        # 初始化消息计数器为实际消息数
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        msg_count = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE summary_msg_counter SET count = ?, last_level1_at = ?, last_level2_at = ?, last_level3_at = ? WHERE id = 1",
            (msg_count, (msg_count // 10) * 10, (msg_count // 50) * 50, (msg_count // 100) * 100)
        )
    # 清理旧的活跃摘要标记
    reset_active_memory()

# ========== documents 操作 ==========
def add_document(filename, chunks, size):
    with get_conn() as conn:
        cursor = conn.cursor()
        uploaded_at = datetime.now().isoformat()
        cursor.execute("INSERT INTO documents (filename, chunks, size, uploaded_at) VALUES (?, ?, ?, ?)", (filename, chunks, size, uploaded_at))
        doc_id = cursor.lastrowid
    return doc_id

def get_documents():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY id DESC")
        rows = cursor.fetchall()
    return [{"id": r["id"], "filename": r["filename"], "chunks": r["chunks"], "size": r["size"], "uploaded_at": r["uploaded_at"]} for r in rows]

def delete_document(doc_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

# 数据库初始化已移至 _ensure_db()，首次 get_conn() 时自动执行

# ========== 对话分支操作 ==========
def get_last_ai_message():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='assistant' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    return {"id": row["id"], "content": row["content"]} if row else None

def reroll_last_ai_message():
    """删除最后一条 AI 消息，用于重新生成。返回被删除前的用户消息"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            return None
        cursor.execute("DELETE FROM chat_history WHERE role='assistant' AND id > ?", (user_row["id"],))
    return user_row["content"] if user_row else None

def archive_message(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_history SET archived = 1 WHERE id = ?", (msg_id,))