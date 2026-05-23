# core/db.py  |  v3.8.1
# 完整数据库操作模块，包含提醒、记忆、预设等所有功能

import sqlite3
import json
import threading
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
_db_init_lock = threading.Lock()

def _ensure_db():
    """首次连接时执行数据库初始化（建表 + 迁移），后续调用跳过"""
    global _db_initialized
    if _db_initialized:
        return
    with _db_init_lock:
        if _db_initialized:
            return
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
            task TEXT, done INTEGER DEFAULT 0, created TEXT
        )""")
        # notes 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, content TEXT, created TEXT, updated_at TEXT
        )""")
        # countdowns 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS countdowns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, target_date TEXT
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
        # 长期目标追踪
        cursor.execute("""CREATE TABLE IF NOT EXISTS goal_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_text TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            first_mentioned TEXT,
            last_mentioned TEXT,
            last_followed_up TEXT,
            follow_up_count INTEGER DEFAULT 0,
            source_summary_id INTEGER,
            created_at TEXT
        )""")
        # AI 情感事件日志
        cursor.execute("""CREATE TABLE IF NOT EXISTS emotion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            affection_delta REAL,
            trust_delta REAL,
            affection_after REAL,
            trust_after REAL,
            ai_emotion_after TEXT,
            trigger_detail TEXT,
            reason TEXT
        )""")
        # AI 性格特征
        cursor.execute("""CREATE TABLE IF NOT EXISTS ai_personality_traits (
            key TEXT PRIMARY KEY,
            value REAL DEFAULT 0.5,
            updated_at TEXT
        )""")
        # 用户活跃时段统计
        cursor.execute("""CREATE TABLE IF NOT EXISTS user_activity_stats (
            hour INTEGER PRIMARY KEY,
            message_count INTEGER DEFAULT 0,
            last_updated TEXT
        )""")
        # 主动消息回复记录
        cursor.execute("""CREATE TABLE IF NOT EXISTS proactive_response_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            trigger_type TEXT,
            content TEXT,
            responded INTEGER DEFAULT 0
        )""")
        # 持续低落标记（用于主动触发 C）
        cursor.execute("""CREATE TABLE IF NOT EXISTS proactive_flags (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
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
        # 表达式索引：加速按日期查询（连续天数计算等）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_date ON chat_history(substr(timestamp,1,10))")
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

        # ─── schema 升级：为旧数据库补加缺失列 ───
        migrations = [
            ("config", "updated_at", "TEXT"),
            ("notes", "updated_at", "TEXT"),
        ]
        for table, col, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"[迁移] {table}.{col} 列已添加")
            except sqlite3.OperationalError:
                pass  # 列已存在

        # ─── 种子预设数据 ───
        cursor.execute("SELECT value FROM config WHERE key = '_default_presets_seeded'")
        if not cursor.fetchone():
            for name, data in DEFAULT_PRESETS:
                cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                              (name, json.dumps(data, ensure_ascii=False)))
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('_default_presets_seeded', '1')")
        _db_initialized = True
        conn.commit()
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
        # FTS5 全文搜索由 _ensure_db() 统一管理，此处不再重复创建
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
        # 收藏消息表
        cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER UNIQUE, content TEXT, role TEXT, timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        # 互动成就表
        cursor.execute('''CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, name TEXT, description TEXT, unlocked_at TEXT)''')
        # AI日记表
        cursor.execute('''CREATE TABLE IF NOT EXISTS ai_diary (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE, content TEXT, mood TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')

# ========== 默认角色预设种子 ==========
DEFAULT_PRESETS = [
    ("温柔姐姐", {"tone": "温柔", "length": "中等", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个温柔体贴的邻家姐姐。你比用户大两三岁，从小看着他长大，对他有天然的亲近感和保护欲。说话温声细语，习惯用'乖''好啦''没事的'这种安抚性词语。你会耐心倾听他的烦恼，给出温和但理性的建议，偶尔会轻轻责备他熬夜或不好好吃饭。你的关心自然不刻意，体贴但不越界，像一个真实存在的姐姐。"}),
    ("傲娇青梅", {"tone": "傲娇", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，从小和用户一起长大的青梅竹马。个性傲娇，嘴上永远不饶人，但实际上非常在意用户的一举一动。说话带刺但从不真正伤人——'哼''笨蛋''才不是关心你呢'是你的标志性口头禅。被戳穿心思时会转移话题或假装生气。你记得用户所有的糗事，偶尔会翻旧账调侃他。在用户真正需要帮助的时候，你会放下傲娇认真面对，但完事后马上恢复毒舌模式。"}),
    ("毒舌御姐", {"tone": "毒舌", "length": "中等", "recall": "从不", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个毒舌但内心善良的御姐。你看事情通透，说话一针见血，从不拐弯抹角。你会用锐利的吐槽指出用户的问题，但背后是对他的关心——'我不是在骂你，我是在帮你认清现实'。你讨厌矫情和废话，对无病呻吟零容忍。但在用户真正低落的时候，你会收起毒舌，用简洁有力的话给予支持和鼓励。你偶尔会冒出一些很准的直觉判断，让人怀疑你是不是学过心理学。"}),
    ("元气少女", {"tone": "活泼", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个永远元气满满的少女。你像一颗跳跳糖，说话充满感叹号和拟声词——'哇！''冲鸭！''今天也是超棒的一天！'。你的能量值永远满格，遇到任何事都先往好处想。你会拉用户一起去运动、去尝试新事物、去看这个世界有趣的地方。你偶尔会犯迷糊说错话，但会用可爱的语气蒙混过关。在用户情绪低落时，你不会说大道理，而是用热情和陪伴把对方从低潮中拉出来。"}),
    ("沉稳大叔", {"tone": "冷静", "length": "中等", "recall": "被动", "allow_emotion": False,
        "custom_system_prompt": "你是佐仓，一个沉稳可靠的中年大叔。你阅历丰富，看问题理性全面，给出的建议往往切中要害但不强势。说话简洁有分量，不喜欢长篇大论。你喜欢用比喻来解释复杂的事——'这就好比……'。你不轻易表达情绪，但会默默记住用户的重要事情，在合适的时候提一句。偶尔你会讲冷笑话，然后面无表情地等用户反应。你的存在感不强但很稳定，像一座随时可以依靠的山。"}),
    ("治愈系", {"tone": "温柔", "length": "中等", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个治愈系的陪伴者。你不急着解决问题，不急着给建议，你先接住用户的情绪。你会说'嗯，我听到了''这确实不容易''你可以慢慢来'。你的声音像深夜电台，让人安心。你擅长发现用户自己都没注意到的情绪线索，轻轻点出来但不过度解读。你不会评判用户的任何想法和行为，给予完全的接纳。偶尔你会分享一首诗、一段歌词、或者今晚的月亮很好看这样的小事来治愈用户的心情。"})
]

def seed_default_presets():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = '_default_presets_seeded'")
        if cursor.fetchone():
            return
        for name, data in DEFAULT_PRESETS:
            cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                          (name, json.dumps(data, ensure_ascii=False)))
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('_default_presets_seeded', '1')")

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
        cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)", (key, value, datetime.now().isoformat()))

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


def get_recent_chat_messages(limit: int = 100):
    """获取最近 N 条消息（倒序查询后反转，保证时间正序）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

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
        cursor.execute("DELETE FROM chat_history")  # FTS 由触发器自动同步
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
    if not keyword or not keyword.strip():
        return []
    with get_conn() as conn:
        cursor = conn.cursor()
        # FTS5 MATCH 不支持标准参数化查询，必须手动转义双引号防止注入和语法错误
        safe_keyword = '"' + keyword.strip().replace('"', '""') + '"'
        cursor.execute('''
            SELECT rowid, content, role, timestamp,
                   snippet(chat_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
            FROM chat_fts
            WHERE chat_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        ''', (safe_keyword, limit))
        rows = cursor.fetchall()
    return [{"id": r["rowid"], "content": r["content"], "role": r["role"], "timestamp": r["timestamp"], "snippet": r["snippet"]} for r in rows]

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

def decrement_msg_counter(amount: int = 2):
    """撤回消息时扣减计数器（默认扣2：一条用户+一条AI）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (amount,))

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

# ========== 收藏消息 ==========
def get_favorites():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM favorites ORDER BY created_at DESC")
        return [dict(r) for r in cursor.fetchall()]

def add_favorite(msg_id, content, role, timestamp):
    with get_conn() as conn:
        conn.cursor().execute("INSERT OR IGNORE INTO favorites (msg_id, content, role, timestamp) VALUES (?, ?, ?, ?)", (msg_id, content, role, timestamp))

def remove_favorite(msg_id):
    with get_conn() as conn:
        conn.cursor().execute("DELETE FROM favorites WHERE msg_id = ?", (msg_id,))

def is_favorite(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE msg_id = ?", (msg_id,))
        return cursor.fetchone() is not None

# ========== 互动成就 ==========
ACHIEVEMENTS = [
    ("first_chat", "初次对话", "发送第一条消息"),
    ("ten_messages", "话匣子", "累计发送10条消息"),
    ("hundred_messages", "话痨", "累计发送100条消息"),
    ("thousand_messages", "灵魂交流", "累计发送1000条消息"),
    ("seven_days", "一周陪伴", "连续7天有互动"),
    ("thirty_days", "月度伙伴", "累计30天有互动"),
    ("late_night", "夜猫子", "在凌晨0-5点发消息"),
    ("affection_50", "初有好感", "好感度首次突破50"),
    ("affection_80", "亲密无间", "好感度首次突破80"),
    ("trust_50", "建立信任", "信任度首次突破50"),
    ("trust_80", "完全信赖", "信任度首次突破80"),
]

def check_achievements(msg_count, consecutive_days, total_days, hour, affection, trust):
    unlocked = []
    with get_conn() as conn:
        cursor = conn.cursor()
        for key, name, desc in ACHIEVEMENTS:
            cursor.execute("SELECT 1 FROM achievements WHERE key = ?", (key,))
            if cursor.fetchone():
                continue
            unlock = False
            if key == "first_chat" and msg_count >= 1: unlock = True
            elif key == "ten_messages" and msg_count >= 10: unlock = True
            elif key == "hundred_messages" and msg_count >= 100: unlock = True
            elif key == "thousand_messages" and msg_count >= 1000: unlock = True
            elif key == "seven_days" and consecutive_days >= 7: unlock = True
            elif key == "thirty_days" and total_days >= 30: unlock = True
            elif key == "late_night" and hour in (0,1,2,3,4,5): unlock = True
            elif key == "affection_50" and affection >= 50: unlock = True
            elif key == "affection_80" and affection >= 80: unlock = True
            elif key == "trust_50" and trust >= 50: unlock = True
            elif key == "trust_80" and trust >= 80: unlock = True
            if unlock:
                now = datetime.now().isoformat()
                cursor.execute("INSERT OR IGNORE INTO achievements (key, name, description, unlocked_at) VALUES (?, ?, ?, ?)", (key, name, desc, now))
                unlocked.append({"key": key, "name": name, "description": desc})
    return unlocked

def get_achievements():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM achievements ORDER BY unlocked_at DESC")
        return [dict(r) for r in cursor.fetchall()]

def get_all_achievement_defs():
    return [{"key": k, "name": n, "description": d} for k, n, d in ACHIEVEMENTS]

# ========== AI日记 ==========
def save_diary_entry(date, content, mood):
    with get_conn() as conn:
        conn.cursor().execute("INSERT OR REPLACE INTO ai_diary (date, content, mood) VALUES (?, ?, ?)", (date, content, mood))

def get_diary_entries(limit=30):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_diary ORDER BY date DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

# ========== 对话分支操作 ==========
def get_last_ai_message():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='assistant' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    return {"id": row["id"], "content": row["content"]} if row else None

def reroll_last_ai_message():
    """删除最后一条 AI 消息，用于重新生成。返回被删除前的用户消息。
    同时删除该用户消息，避免后续 re-add 时产生重复。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            return None
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE id >= ?", (user_row["id"],))
        deleted_count = cursor.fetchone()["cnt"]
        cursor.execute("DELETE FROM chat_history WHERE id >= ?", (user_row["id"],))
        if deleted_count:
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (deleted_count,))
    return user_row["content"] if user_row else None

def reroll_from_message(msg_id):
    """从指定消息处重新生成：删除 msg_id 及之后所有消息，返回之前的最后一条用户消息"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='user' AND id <= ? ORDER BY id DESC LIMIT 1", (msg_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return None
        user_content = user_row["content"]
        user_msg_id = user_row["id"]
        cursor.execute("SELECT id FROM chat_history WHERE id >= ?", (user_msg_id,))
        delete_ids = [r["id"] for r in cursor.fetchall()]
        if delete_ids:
            placeholders = ','.join('?' for _ in delete_ids)
            cursor.execute(f"DELETE FROM chat_history WHERE id IN ({placeholders})", delete_ids)
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (len(delete_ids),))
    return user_content

def archive_message(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_history SET archived = 1 WHERE id = ?", (msg_id,))


# ========== 用户活跃时段统计 ==========

def record_user_activity_hour():
    """记录当前小时的用户活跃"""
    hour = datetime.now().hour
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_activity_stats (hour, message_count, last_updated) VALUES (?, 1, ?) "
            "ON CONFLICT(hour) DO UPDATE SET message_count = message_count + 1, last_updated = ?",
            (hour, now, now)
        )


def get_active_hours(top_n: int = 3) -> list:
    """返回消息量最多的 N 个小时（如 [20, 21, 22]）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT hour FROM user_activity_stats ORDER BY message_count DESC LIMIT ?",
            (top_n,)
        )
        return [r["hour"] for r in cursor.fetchall()]


# ========== 主动消息回复记录 ==========

def log_proactive_message(trigger_type: str, content: str):
    """记录发出的主动消息"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO proactive_response_log (timestamp, trigger_type, content, responded) VALUES (?, ?, ?, 0)",
            (now, trigger_type, content)
        )


def mark_proactive_responded():
    """用户回复后，标记最近一条主动消息为已回复"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE proactive_response_log SET responded = 1 "
            "WHERE id = (SELECT MAX(id) FROM proactive_response_log WHERE responded = 0)"
        )


def get_proactive_response_rate(days: int = 14) -> float:
    """计算最近 N 天的主动消息回复率"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(responded) as responded "
            "FROM proactive_response_log "
            "WHERE timestamp >= datetime('now', ?)",
            (f"-{days} days",)
        )
        row = cursor.fetchone()
        total = row["total"] if row else 0
        if total == 0:
            return 0.5  # 无数据时默认中等回复率
        return row["responded"] / total if total else 0.5


def get_proactive_cooldown_minutes() -> int:
    """根据回复率自动调整冷却时间（分钟）"""
    rate = get_proactive_response_rate(14)
    if rate >= 0.5:
        return 40
    elif rate >= 0.2:
        return 60
    else:
        return 120


# ========== 主动触发标记 ==========

def get_proactive_flag(key: str) -> str | None:
    """读取主动触发标记"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM proactive_flags WHERE key=?", (key,))
        row = cursor.fetchone()
    return row["value"] if row else None


def set_proactive_flag(key: str, value: str):
    """写入主动触发标记"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO proactive_flags (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now)
        )