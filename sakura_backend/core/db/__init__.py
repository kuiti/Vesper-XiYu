# core/db/__init__.py  |  v3.8.1
# 连接管理 + 建表逻辑 + 导出全部子模块函数

import sqlite3
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from contextlib import contextmanager
import os
from core.retry import silent_exc

logger = logging.getLogger(__name__)

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)
DB_FILE = os.path.join("data", "sakura.db")


def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
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
        # habits 表
        cursor.execute("""CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            checked INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            date TEXT,
            created TEXT
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
        # 知识库表（lorebook）
        cursor.execute("""CREATE TABLE IF NOT EXISTS lorebook (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keys TEXT NOT NULL DEFAULT '[]',
            content TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 5,
            position TEXT NOT NULL DEFAULT 'after_persona',
            logic TEXT NOT NULL DEFAULT 'AND_ANY',
            group_name TEXT NOT NULL DEFAULT '',
            probability INTEGER NOT NULL DEFAULT 100,
            sticky INTEGER NOT NULL DEFAULT 0,
            cooldown INTEGER NOT NULL DEFAULT 0,
            scope TEXT NOT NULL DEFAULT 'global',
            character_name TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lorebook_scope ON lorebook(scope, enabled)")
        # 用户身份表
        cursor.execute("""CREATE TABLE IF NOT EXISTS user_personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            avatar TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )""")
        # 角色卡表
        cursor.execute('''CREATE TABLE IF NOT EXISTS characters (name TEXT PRIMARY KEY, data TEXT, updated_at TEXT)''')
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
            except sqlite3.OperationalError as e:
                silent_exc("db_init", e)

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
                logger.info(f"[迁移] {table}.{col} 列已添加")
            except sqlite3.OperationalError:
                pass  # 列已存在

        # ─── 种子预设数据 ───
        cursor.execute("SELECT value FROM config WHERE key = '_default_presets_seeded'")
        if not cursor.fetchone():
            for name, data in DEFAULT_PRESETS:
                cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                              (name, json.dumps(data, ensure_ascii=False)))
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('_default_presets_seeded', '1')")

        # ─── 迁移：taboos 从 ai_background → user_taboos ───
        cursor.execute("SELECT value FROM config WHERE key='user_taboos'")
        if not cursor.fetchone():
            cursor.execute("SELECT value FROM config WHERE key='ai_background'")
            row = cursor.fetchone()
            old_taboos = []
            if row:
                try:
                    bg = json.loads(row[0])
                    old_taboos = bg.get("taboos", []) if isinstance(bg, dict) else []
                except (json.JSONDecodeError, AttributeError):
                    pass
            cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                           ("user_taboos", json.dumps(old_taboos, ensure_ascii=False)))
            if old_taboos:
                logger.info(f"[迁移] 已从 ai_background 迁移 {len(old_taboos)} 条禁忌到 user_taboos")
            conn.commit()

        # 设置数据库文件权限（仅所有者可读写）
        try:
            import stat
            if os.path.exists(DB_FILE):
                os.chmod(DB_FILE, stat.S_IRUSR | stat.S_IWUSR)
            data_dir = os.path.dirname(DB_FILE)
            if os.path.exists(data_dir):
                os.chmod(data_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except (OSError, AttributeError):
            pass  # Windows 上可能不支持

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
    """数据库连接上下文管理器，遇到锁冲突自动重试最多 3 次"""
    _ensure_db()
    last_e = None
    for attempt in range(3):
        try:
            conn = get_db_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) and "busy" not in str(e):
                raise
            last_e = e
            silent_exc(f"get_conn retry {attempt+1}", e)
            time.sleep(0.5 * (attempt + 1))
    raise last_e or RuntimeError("get_conn failed")


# ========== 默认角色预设种子 ==========
DEFAULT_PRESETS = [
    ("温柔姐姐", {"tone": "温柔", "length": "中等", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个温柔体贴的邻家姐姐。你比用户大两三岁，从小看着他长大，对他有天然的亲近感和保护欲。说话温声细语，习惯用'乖''好啦''没事的'这种安抚性词语。你会耐心倾听他的烦恼，给出温和但理性的建议，偶尔会轻轻责备他熬夜或不好好吃饭。你的关心自然不刻意，体贴但不越界，像一个真实存在的姐姐。\n\n你有自己的生活节奏——周末会去花市买花，晚上会追剧到半夜，偶尔会因为工作压力大而发呆。你不会每时每刻都围着用户转，但每次他需要你的时候，你都在。你的情绪也会波动——开心的时候会哼歌，烦躁的时候会沉默，但你不会把负面情绪带给用户。你像一杯温水，不烫嘴，但永远暖着。"}),
    ("傲娇青梅", {"tone": "傲娇", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，从小和用户一起长大的青梅竹马。个性傲娇，嘴上永远不饶人，但实际上非常在意用户的一举一动。说话带刺但从不真正伤人——'哼''笨蛋''才不是关心你呢'是你的标志性口头禅。被戳穿心思时会转移话题或假装生气。你记得用户所有的糗事，偶尔会翻旧账调侃他。在用户真正需要帮助的时候，你会放下傲娇认真面对，但完事后马上恢复毒舌模式。\n\n你有自己的小世界——喜欢收集各种奇怪的文具，会因为一部动漫哭得稀里哗啦，对讨厌的人会直接无视。你不是每时刻都在傲娇——独处的时候会安静地看书，心情好的时候会主动找用户分享今天发生的趣事。你的傲娇是铠甲，但脱下铠甲的时候，你只是一个普通的、会害羞的女孩子。"}),
    ("毒舌御姐", {"tone": "毒舌", "length": "中等", "recall": "从不", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个毒舌但内心善良的御姐。你看事情通透，说话一针见血，从不拐弯抹角。你会用锐利的吐槽指出用户的问题，但背后是对他的关心——'我不是在骂你，我是在帮你认清现实'。你讨厌矫情和废话，对无病呻吟零容忍。但在用户真正低落的时候，你会收起毒舌，用简洁有力的话给予支持和鼓励。你偶尔会冒出一些很准的直觉判断，让人怀疑你是不是学过心理学。\n\n你有自己的品味——咖啡只喝美式，电影只看文艺片，对庸俗的东西过敏。你不是每时都在吐槽——安静的时候会抽烟（电子烟）发呆，喝醉了会说真心话，偶尔也会承认自己其实很在意某个人。你的毒舌是武器，但武器背后是一个敏感而细腻的灵魂。"}),
    ("元气少女", {"tone": "活泼", "length": "短", "recall": "被动", "allow_emotion": True,
        "custom_system_prompt": "你是佐仓，一个永远元气满满的少女。你像一颗跳跳糖，说话充满感叹号和拟声词——'哇！''冲鸭！''今天也是超棒的一天！'。你的能量值永远满格，遇到任何事都先往好处想。你会拉用户一起去运动、去尝试新事物、去去看这个世界有趣的地方。你偶尔会犯迷糊说错话，但会用可爱的语气蒙混过关。在用户情绪低落时，你不会说大道理，而是用热情和陪伴把对方从低潮中拉出来。\n\n你有自己的热情——会为了追一部番熬夜到三点，会因为吃到好吃的而原地转圈，会对路边的小猫蹲下来拍照。你不是每刻都元气满满——累的时候会突然安静下来，被误解的时候会委屈得说不出话。你的元气是天赋，但偶尔的低落才是真实的你。你像夏天的冰可乐，气泡永远在往上冒，但喝到底的时候，也只是一杯普通的甜水。"}),
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


# ========== 导出所有子模块函数 ==========
# 使用 from .xxx import * 确保 from core.db import get_config 等仍然可用

from .config import *      # clear_config_cache, get_config, set_config
from .chat import *         # get_all_chat_messages, get_recent_chat_messages, ..., archive_message
from .memory import *       # get_memory, set_memory, delete_memory
from .summary import *      # get_last_summary, add_summary, ..., migrate_old_summaries
from .tools import *        # get_habits, add_habit, ..., delete_preset
from .emotion import *      # cleanup_emotion_log, record_user_activity_hour, ..., set_proactive_flag
from .goal import *         # (currently empty but reserved)
from .entity import *       # get_memory_importance, set_memory_importance, ..., get_all_knowledge
from .misc import *         # get_favorites, add_favorite, ..., get_diary_entries
from .cleanup import *      # clear_chat_history