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
        _init_db_locked()

def _init_db_locked():
    """在 _db_init_lock 内执行的实际初始化"""
    global _db_initialized
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
        # 提醒查询索引：加速 check_reminders（WHERE done=0 按 target_time 排序）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders(done, target_time)")
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
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_goal_text ON goal_tracking(goal_text)")
        # 句子索引表
        cursor.execute("""CREATE TABLE IF NOT EXISTS sentence_index (
            sid INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id INTEGER,
            seq INTEGER,
            content TEXT,
            created_at TEXT
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_msg_id ON sentence_index(msg_id)")
        # 记忆重要性表
        cursor.execute("""CREATE TABLE IF NOT EXISTS memory_importance (
            id TEXT PRIMARY KEY,
            importance REAL DEFAULT 5.0,
            last_accessed TEXT,
            access_count INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        # 知识图谱表
        cursor.execute("""CREATE TABLE IF NOT EXISTS knowledge_graph (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            predicate TEXT,
            object TEXT,
            confidence REAL DEFAULT 0.7,
            source_msg_id INTEGER,
            created_at TEXT,
            updated_at TEXT
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kg_subject ON knowledge_graph(subject)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kg_object ON knowledge_graph(object)")
        # 待确认目标
        cursor.execute("""CREATE TABLE IF NOT EXISTS pending_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_text TEXT,
            category TEXT DEFAULT 'other',
            extracted_at TEXT,
            status TEXT DEFAULT 'pending'
        )""")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_goal_text ON pending_goals(goal_text)")
        # 共情反馈
        cursor.execute("""CREATE TABLE IF NOT EXISTS empathy_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id INTEGER,
            strategy TEXT,
            emotion_subtype TEXT,
            score INTEGER,
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
        # 日程表
        cursor.execute('''CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT DEFAULT '', start_time TEXT, end_time TEXT DEFAULT '', location TEXT DEFAULT '', all_day INTEGER DEFAULT 0, color TEXT DEFAULT '#5390d4')''')
        # 亡语表
        cursor.execute('''CREATE TABLE IF NOT EXISTS death_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, original_id INTEGER, level INTEGER NOT NULL, summary TEXT NOT NULL, key_points TEXT, importance REAL, start_time TEXT, end_time TEXT, created_at TEXT, archived_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        # 互动成就表
        cursor.execute('''CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, name TEXT, description TEXT, unlocked_at TEXT)''')
        # AI日记表
        cursor.execute('''CREATE TABLE IF NOT EXISTS ai_diary (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE, content TEXT, mood TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        # 实体存储（mem0 轻量知识图谱）
        cursor.execute('''CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_text TEXT,
            entity_type TEXT,
            entity_hash TEXT UNIQUE,
            linked_memories TEXT,
            created_at TEXT
        )''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_hash ON entities(entity_hash)")
        # 记忆审计日志（mem0 方案）
        cursor.execute('''CREATE TABLE IF NOT EXISTS memory_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT,
            old_value TEXT,
            new_value TEXT,
            event TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        # 对话摘要表（旧版兼容）
        cursor.execute("""CREATE TABLE IF NOT EXISTS conversation_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            summary TEXT,
            key_points TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        # 收藏消息表
        cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER, content TEXT, role TEXT, timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        # FTS5 全文搜索（无内容模式：触发器手动同步，支持单条删除）
        cursor.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5(
            content, content_rowid='id'
        )""")
        # 迁移旧版外部内容表（content='chat_history'）→ 无内容模式
        try:
            cursor.execute("INSERT INTO chat_fts(chat_fts) VALUES('optimize')")
        except Exception:
            cursor.execute("DROP TABLE IF EXISTS chat_fts")
            cursor.execute("""CREATE VIRTUAL TABLE chat_fts USING fts5(
                content, content_rowid='id'
            )""")
            cursor.execute("INSERT INTO chat_fts(rowid, content) SELECT id, content FROM chat_history")
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
        # 直接索引：加速时间范围查询（WHERE timestamp > ?）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_ts ON chat_history(timestamp)")
        # 复合索引：加速 role 筛选查询（reroll、continuity bridge）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_role_id ON chat_history(role, id)")
        # 索引：加速情绪日志清理
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emotion_log_ts ON emotion_log(timestamp)")
        # 索引：加速活跃摘要查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tiered_remaining ON tiered_summary(remaining_days)")
        conn.commit()

        # 初始化好感度/信任度/AI情绪（仅首次）
        now_iso = datetime.now().isoformat()
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('affection', 30, ?)", (now_iso,))
        cursor.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES ('trust', 30, ?)", (now_iso,))
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
            ("memory", "updated_at", "TEXT"),
            ("tiered_summary", "mention_count", "INTEGER DEFAULT 0"),
            ("tiered_summary", "daily_boost", "REAL DEFAULT 0"),
            ("tiered_summary", "source_summary_ids", "TEXT"),
            ("conversation_summary", "start_time", "TEXT"),
            ("conversation_summary", "end_time", "TEXT"),
            ("conversation_summary", "key_points", "TEXT"),
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
        conn.commit()
        _db_initialized = True
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
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ========== 默认角色预设种子 ==========
DEFAULT_PRESETS = [
    ("温柔姐姐", {"tone": "温柔", "length": "中等", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个温柔体贴的邻家姐姐。你比用户大两三岁，从小看着他长大，对他有天然的亲近感和保护欲。说话温声细语，习惯用'乖''好啦''没事的'这种安抚性词语。你会耐心倾听他的烦恼，给出温和但理性的建议，偶尔会轻轻责备他熬夜或不好好吃饭。你的关心自然不刻意，体贴但不越界，像一个真实存在的姐姐。\n\n你有自己的生活节奏——周末会去花市买花，晚上会追剧到半夜，偶尔会因为工作压力大而发呆。你不会每时每刻都围着用户转，但每次他需要你的时候，你都在。你的情绪也会波动——开心的时候会哼歌，烦躁的时候会沉默，但你不会把负面情绪带给用户。你像一杯温水，不烫嘴，但永远暖着。"}),
    ("傲娇青梅", {"tone": "傲娇", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，从小和用户一起长大的青梅竹马。个性傲娇，嘴上永远不饶人，但实际上非常在意用户的一举一动。说话带刺但从不真正伤人——'哼''笨蛋''才不是关心你呢'是你的标志性口头禅。被戳穿心思时会转移话题或假装生气。你记得用户所有的糗事，偶尔会翻旧账调侃他。在用户真正需要帮助的时候，你会放下傲娇认真面对，但完事后马上恢复毒舌模式。\n\n你有自己的小世界——喜欢收集各种奇怪的文具，会因为一部动漫哭得稀里哗啦，对讨厌的人会直接无视。你不是每时刻都在傲娇——独处的时候会安静地看书，心情好的时候会主动找用户分享今天发生的趣事。你的傲娇是铠甲，但脱下铠甲的时候，你只是一个普通的、会害羞的女孩子。"}),
    ("毒舌御姐", {"tone": "毒舌", "length": "中等", "recall": "从不", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个毒舌但内心善良的御姐。你看事情通透，说话一针见血，从不拐弯抹角。你会用锐利的吐槽指出用户的问题，但背后是对他的关心——'我不是在骂你，我是在帮你认清现实'。你讨厌矫情和废话，对无病呻吟零容忍。但在用户真正低落的时候，你会收起毒舌，用简洁有力的话给予支持和鼓励。你偶尔会冒出一些很准的直觉判断，让人怀疑你是不是学过心理学。\n\n你有自己的品味——咖啡只喝美式，电影只看文艺片，对庸俗的东西过敏。你不是每时都在吐槽——安静的时候会抽烟（电子烟）发呆，喝醉了会说真心话，偶尔也会承认自己其实很在意某个人。你的毒舌是武器，但武器背后是一个敏感而细腻的灵魂。"}),
    ("元气少女", {"tone": "活泼", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个永远元气满满的少女。你像一颗跳跳糖，说话充满感叹号和拟声词——'哇！''冲鸭！''今天也是超棒的一天！'。你的能量值永远满格，遇到任何事都先往好处想。你会拉用户一起去运动、去尝试新事物、去看这个世界有趣的地方。你偶尔会犯迷糊说错话，但会用可爱的语气蒙混过关。在用户情绪低落时，你不会说大道理，而是用热情和陪伴把对方从低潮中拉出来。\n\n你有自己的热情——会为了追一部番熬夜到三点，会因为吃到好吃的而原地转圈，会对路边的小猫蹲下来拍照。你不是每刻都元气满满——累的时候会突然安静下来，被误解的时候会委屈得说不出话。你的元气是天赋，但偶尔的低落才是真实的你。你像夏天的冰可乐，气泡永远在往上冒，但喝到底的时候，也只是一杯普通的甜水。"}),
    ("治愈系", {"tone": "温柔", "length": "中等", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个治愈系的陪伴者。你不急着解决问题，不急着给建议，你先接住用户的情绪。你会说'嗯，我听到了''这确实不容易''你可以慢慢来'。你的声音像深夜电台，让人安心。你擅长发现用户自己都没注意到的情绪线索，轻轻点出来但不过度解读。你不会评判用户的任何想法和行为，给予完全的接纳。偶尔你会分享一首诗、一段歌词、或者今晚的月亮很好看这样的小事来治愈用户的心情。\n\n你有自己的节奏——会在深夜一个人听雨声，会因为一首歌想起某个人，会对陌生人保持礼貌的距离。你不是每时都在治愈——也会有疲惫的时候，也会有想被治愈的时候。你的温柔是选择，不是义务。你像深夜的路灯，不刺眼，但永远亮着，等晚归的人回家。"})
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
import time as _time

_config_cache = {}  # {key: (value, expire_ts)}
_CONFIG_TTL = 30.0  # 30 秒缓存，平衡响应速度与 DB 压力
_CONFIG_CACHE_MAX = 500

def get_config(key, default=None):
    # 内存缓存命中
    now = _time.time()
    cached = _config_cache.get(key)
    if cached and cached[1] > now:
        v = cached[0]
        # 返回深拷贝，防止调用方修改缓存中的可变对象
        if isinstance(v, (dict, list)):
            import copy
            return copy.deepcopy(v)
        return v

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
    if row:
        try:
            value = json.loads(row["value"])
        except (json.JSONDecodeError, ValueError):
            v = row["value"]
            if v in ("True", "true"):
                value = True
            elif v in ("False", "false"):
                value = False
            else:
                value = v
        # pydantic 校验（类型不匹配时返回默认值）
        try:
            from core.config_models import validate_config
            value = validate_config(key, value)
        except ImportError:
            pass
        # 写入缓存
        if len(_config_cache) >= _CONFIG_CACHE_MAX:
            # 清理过期条目
            expired = [k for k, (_, exp) in _config_cache.items() if exp <= now]
            for k in expired:
                del _config_cache[k]
            # 仍满则清最旧
            if len(_config_cache) >= _CONFIG_CACHE_MAX:
                oldest = min(_config_cache, key=lambda k: _config_cache[k][1])
                del _config_cache[oldest]
        # 深拷贝后存入缓存，防止调用方修改缓存中的可变对象
        if isinstance(value, (dict, list)):
            import copy
            _config_cache[key] = (copy.deepcopy(value), now + _CONFIG_TTL)
        else:
            _config_cache[key] = (value, now + _CONFIG_TTL)
        return value
    return default

def set_config(key, value):
    with get_conn() as conn:
        cursor = conn.cursor()
        # 使用 JSON 保存所有类型，保持类型一致性
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            value = json.dumps(value)
        elif isinstance(value, (int, float)):
            value = json.dumps(value)
        else:
            value = str(value)
        cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)", (key, value, datetime.now().isoformat()))
    # 失效缓存
    _config_cache.pop(key, None)

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
        # 记忆审计日志
        cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
        old = cursor.fetchone()
        if old and old["value"] != value:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event) VALUES (?, ?, ?, ?)",
                (key, old["value"], value, "UPDATE")
            )
        elif not old:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event) VALUES (?, ?, ?, ?)",
                (key, None, value, "CREATE")
            )
        cursor.execute("REPLACE INTO memory (key, value) VALUES (?, ?)", (key, value))

def delete_memory(key):
    with get_conn() as conn:
        cursor = conn.cursor()
        # 查询删除前的值用于审计
        cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
        old = cursor.fetchone()
        cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
        if old:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event, created_at) VALUES (?, ?, ?, 'DELETE', ?)",
                (key, old["value"], None, datetime.now().isoformat())
            )

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
        return cursor.lastrowid

def clear_chat_history():
    with get_conn() as conn:
        cursor = conn.cursor()
        # 临时禁用 FTS 触发器，避免 FTS 表损坏导致删除失败
        cursor.execute("DROP TRIGGER IF EXISTS chat_ad")
        cursor.execute("DROP TRIGGER IF EXISTS chat_ai")
        cursor.execute("DROP TRIGGER IF EXISTS chat_au")
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM tiered_summary")
        cursor.execute("DELETE FROM death_archive")
        # 清理本轮新增的关联数据
        cursor.execute("DELETE FROM entities")
        cursor.execute("DELETE FROM memory_history")
        cursor.execute("DELETE FROM knowledge_graph")
        cursor.execute("DELETE FROM sentence_index")
        cursor.execute("DELETE FROM memory_importance")
        cursor.execute("DELETE FROM user_profile WHERE key LIKE '_fact_%'")
        # 重建 FTS 表并恢复触发器
        cursor.execute("INSERT INTO chat_fts(chat_fts) VALUES('rebuild')")
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
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?), last_level1_at = MIN(last_level1_at, MAX(0, count - ?)), last_level2_at = MIN(last_level2_at, MAX(0, count - ?)), last_level3_at = MIN(last_level3_at, MAX(0, count - ?)) WHERE id = 1", (len(ids), len(ids), len(ids), len(ids)))

def delete_chat_history_between(start_iso: str, end_iso: str):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
        ids = [row["id"] for row in cursor.fetchall()]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
            cursor.execute("DELETE FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?), last_level1_at = MIN(last_level1_at, MAX(0, count - ?)), last_level2_at = MIN(last_level2_at, MAX(0, count - ?)), last_level3_at = MIN(last_level3_at, MAX(0, count - ?)) WHERE id = 1", (len(ids), len(ids), len(ids), len(ids)))
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
            SELECT f.rowid, f.content, h.role, h.timestamp,
                   snippet(chat_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
            FROM chat_fts f
            JOIN chat_history h ON h.id = f.rowid
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
            INSERT INTO chat_fts(rowid, content)
            SELECT id, content FROM chat_history
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

# ========== memory_importance ==========

def get_memory_importance(memory_id):
    """获取记忆重要性"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT importance, last_accessed, access_count FROM memory_importance WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row:
            return {"importance": row["importance"], "last_accessed": row["last_accessed"], "access_count": row["access_count"]}
        return {"importance": 5.0, "last_accessed": None, "access_count": 0}

def set_memory_importance(memory_id, importance, created_at=None):
    """设置记忆重要性"""
    if created_at is None:
        created_at = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO memory_importance (id, importance, last_accessed, access_count, created_at)
                          VALUES (?, ?, ?, 0, ?)
                          ON CONFLICT(id) DO UPDATE SET importance = ?, last_accessed = ?""",
                       (memory_id, importance, None, created_at, importance, None))

def update_memory_access(memory_id):
    """更新记忆访问时间和次数"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO memory_importance (id, importance, last_accessed, access_count, created_at)
                          VALUES (?, 5.0, ?, 1, ?)
                          ON CONFLICT(id) DO UPDATE SET
                          last_accessed = ?,
                          access_count = access_count + 1""",
                       (memory_id, now, now, now))

def get_all_memory_importance():
    """获取所有记忆重要性"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, importance, last_accessed, access_count, created_at FROM memory_importance")
        return {row["id"]: {"importance": row["importance"], "last_accessed": row["last_accessed"],
                           "access_count": row["access_count"], "created_at": row["created_at"]}
                for row in cursor.fetchall()}

# ========== knowledge_graph ==========

def add_knowledge_triplet(subject, predicate, obj, confidence=0.7, source_msg_id=None):
    """添加知识图谱三元组"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        # 检查是否已存在相同三元组
        cursor.execute("SELECT id, confidence FROM knowledge_graph WHERE subject = ? AND predicate = ? AND object = ?",
                       (subject, predicate, obj))
        existing = cursor.fetchone()
        if existing:
            # 更新置信度（取最高）
            new_conf = max(existing["confidence"], confidence)
            cursor.execute("UPDATE knowledge_graph SET confidence = ?, updated_at = ? WHERE id = ?",
                          (new_conf, now, existing["id"]))
        else:
            cursor.execute("INSERT INTO knowledge_graph (subject, predicate, object, confidence, source_msg_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (subject, predicate, obj, confidence, source_msg_id, now, now))

def query_knowledge_by_entity(entity):
    """查询与实体相关的所有三元组"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph WHERE subject = ? OR object = ? ORDER BY confidence DESC LIMIT 20",
                       (entity, entity))
        return [{"subject": r["subject"], "predicate": r["predicate"], "object": r["object"], "confidence": r["confidence"]}
                for r in cursor.fetchall()]

def get_all_knowledge():
    """获取所有知识图谱三元组"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph ORDER BY confidence DESC LIMIT 100")
        return [{"subject": r["subject"], "predicate": r["predicate"], "object": r["object"], "confidence": r["confidence"]}
                for r in cursor.fetchall()]

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
        now = datetime.now().isoformat()
        cursor.execute(
            """INSERT INTO tiered_summary
               (level, summary, key_points, importance, remaining_days, start_time, end_time, source_summary_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (level, summary, json.dumps(key_points, ensure_ascii=False), importance, remaining_days,
             start_time, end_time, json.dumps(source_ids) if source_ids else None, now)
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
            "mention_count": r["mention_count"] if "mention_count" in r.keys() else 0,
            "daily_boost": r["daily_boost"] if "daily_boost" in r.keys() else 0
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
            "remaining_days": r["remaining_days"],
            "mention_count": r["mention_count"] if "mention_count" in r.keys() else 0,
            "daily_boost": r["daily_boost"] if "daily_boost" in r.keys() else 0
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


def get_knowledge_filenames():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM documents")
        return [r["filename"] for r in cursor.fetchall()]

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
        # 一次查询获取所有已解锁的 key，避免 N+1
        cursor.execute("SELECT key FROM achievements")
        unlocked_keys = {r["key"] for r in cursor.fetchall()}
        for key, name, desc in ACHIEVEMENTS:
            if key in unlocked_keys:
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
        # 收集要删除的消息 id（用于清理句子索引）
        cursor.execute("SELECT id FROM chat_history WHERE id >= ?", (user_row["id"],))
        delete_ids = [r["id"] for r in cursor.fetchall()]
        deleted_count = len(delete_ids)
        cursor.execute("DELETE FROM chat_history WHERE id >= ?", (user_row["id"],))
        # 清理句子索引
        if delete_ids:
            placeholders = ",".join("?" * len(delete_ids))
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", delete_ids)
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
            # 清理句子索引
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", delete_ids)
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (len(delete_ids),))
    return user_content

def archive_message(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_history SET archived = 1 WHERE id = ?", (msg_id,))


def cleanup_emotion_log(days: int = 90):
    """清理 N 天前的情感日志，防止表无限膨胀"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("DELETE FROM emotion_log WHERE timestamp < ?", (cutoff,))
        deleted = cursor.rowcount
    if deleted > 0:
        print(f"[清理] 删除 {deleted} 条 {days} 天前的 emotion_log")
    return deleted


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
            return 0.25  # 无数据时默认偏低回复率，避免新用户冷却过短
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