"""Root-level fixtures: prevent tests from touching the real database.

Session-scoped setup patches all DB connection factories ONCE at import time.
This avoids the module-caching issue where function-scoped monkeypatches don't
propagate to already-imported modules.
"""

import sqlite3
from contextlib import contextmanager

# ── Build persistent in-memory databases ──

_main_conn = sqlite3.connect(":memory:")
_main_conn.row_factory = sqlite3.Row
_main_conn.execute("PRAGMA journal_mode=WAL")
_main_conn.execute("PRAGMA busy_timeout=10000")
_main_conn.execute("PRAGMA synchronous=NORMAL")

_chat_conns: dict[int, sqlite3.Connection] = {}


def _ensure_main_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp TEXT, parent_id INTEGER, branch_id TEXT, archived INTEGER DEFAULT 0, character_id INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS user_profile (key TEXT PRIMARY KEY, value TEXT, confidence REAL, extracted_at TEXT);
        CREATE TABLE IF NOT EXISTS tiered_summary (id INTEGER PRIMARY KEY AUTOINCREMENT, level INTEGER, summary TEXT, key_points TEXT, importance REAL, remaining_days REAL, start_time TEXT, end_time TEXT, created_at TEXT, is_active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS summary_msg_counter (id INTEGER PRIMARY KEY CHECK (id = 1), count INTEGER DEFAULT 0, last_level1_at INTEGER DEFAULT 0, last_level2_at INTEGER DEFAULT 0, last_level3_at INTEGER DEFAULT 0);
        INSERT OR IGNORE INTO summary_msg_counter (id) VALUES (1);
        CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, done INTEGER DEFAULT 0, created TEXT);
        CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, created TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS countdowns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, target_date TEXT);
        CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, checked INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, date TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, target_time TEXT, level INTEGER DEFAULT 2, done INTEGER DEFAULT 0, last_reminded TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS presets (name TEXT PRIMARY KEY, data TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, chunks INTEGER, size INTEGER, uploaded_at TEXT);
        CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY AUTOINCREMENT, fact_text TEXT NOT NULL, category TEXT DEFAULT 'personal', importance REAL DEFAULT 0.5, confidence REAL DEFAULT 0.7, source TEXT DEFAULT '', extracted_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS emotion_daily (date TEXT PRIMARY KEY, score REAL DEFAULT 0, positive_count INTEGER DEFAULT 0, negative_count INTEGER DEFAULT 0, neutral_count INTEGER DEFAULT 0, total_messages INTEGER DEFAULT 0, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS relationship (key TEXT PRIMARY KEY, value REAL DEFAULT 50, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS demand_patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, trigger_context TEXT, demand_level TEXT, emotion_analysis TEXT, latent_need TEXT, frequency INTEGER DEFAULT 1, last_matched TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS goal_tracking (id INTEGER PRIMARY KEY AUTOINCREMENT, goal_text TEXT, category TEXT, status TEXT DEFAULT 'active', first_mentioned TEXT, last_mentioned TEXT, last_followed_up TEXT, follow_up_count INTEGER DEFAULT 0, source_summary_id INTEGER, created_at TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_goal_text ON goal_tracking(goal_text);
        CREATE TABLE IF NOT EXISTS sentence_index (sid INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER DEFAULT 0, msg_id INTEGER, seq INTEGER, content TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS memory_importance (id TEXT PRIMARY KEY, importance REAL DEFAULT 5.0, last_accessed TEXT, access_count INTEGER DEFAULT 0, ignored_count INTEGER DEFAULT 0, created_at TEXT);
        CREATE TABLE IF NOT EXISTS knowledge_graph (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, predicate TEXT, object TEXT, confidence REAL DEFAULT 0.7, source_msg_id INTEGER, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS pending_goals (id INTEGER PRIMARY KEY AUTOINCREMENT, goal_text TEXT, category TEXT DEFAULT 'other', extracted_at TEXT, status TEXT DEFAULT 'pending');
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_goal_text ON pending_goals(goal_text);
        CREATE TABLE IF NOT EXISTS empathy_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER, strategy TEXT, emotion_subtype TEXT, score INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS emotion_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, event_type TEXT, affection_delta REAL, trust_delta REAL, affection_after REAL, trust_after REAL, ai_emotion_after TEXT, trigger_detail TEXT, reason TEXT);
        CREATE TABLE IF NOT EXISTS user_activity_stats (hour INTEGER PRIMARY KEY, message_count INTEGER DEFAULT 0, last_updated TEXT);
        CREATE TABLE IF NOT EXISTS proactive_response_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, trigger_type TEXT, content TEXT, responded INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS proactive_flags (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT DEFAULT '', start_time TEXT, end_time TEXT DEFAULT '', location TEXT DEFAULT '', all_day INTEGER DEFAULT 0, color TEXT DEFAULT '#5390d4');
        CREATE TABLE IF NOT EXISTS death_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, original_id INTEGER, level INTEGER NOT NULL, summary TEXT NOT NULL, key_points TEXT, importance REAL, start_time TEXT, end_time TEXT, created_at TEXT, archived_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, name TEXT, description TEXT, unlocked_at TEXT);
        CREATE TABLE IF NOT EXISTS ai_diary (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT UNIQUE, content TEXT, mood TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS lorebook (id INTEGER PRIMARY KEY AUTOINCREMENT, keys TEXT NOT NULL DEFAULT '[]', content TEXT NOT NULL DEFAULT '', priority INTEGER NOT NULL DEFAULT 5, position TEXT NOT NULL DEFAULT 'after_persona', logic TEXT NOT NULL DEFAULT 'AND_ANY', group_name TEXT NOT NULL DEFAULT '', probability INTEGER NOT NULL DEFAULT 100, sticky INTEGER NOT NULL DEFAULT 0, cooldown INTEGER NOT NULL DEFAULT 0, scope TEXT NOT NULL DEFAULT 'global', character_name TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS user_personas (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', avatar TEXT NOT NULL DEFAULT '', is_default INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS characters_v2 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT '', personality TEXT DEFAULT '', scenario TEXT DEFAULT '', first_mes TEXT DEFAULT '', mes_example TEXT DEFAULT '', system_prompt TEXT DEFAULT '', post_history_instructions TEXT DEFAULT '', creator_notes TEXT DEFAULT '', tags TEXT DEFAULT '', avatar TEXT DEFAULT '', card_data TEXT DEFAULT '', voice TEXT DEFAULT NULL, is_active INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS entities (id INTEGER PRIMARY KEY AUTOINCREMENT, entity_text TEXT, entity_type TEXT, entity_hash TEXT UNIQUE, linked_memories TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS memory_history (id INTEGER PRIMARY KEY AUTOINCREMENT, memory_key TEXT, old_value TEXT, new_value TEXT, event TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS conversation_summary (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, summary TEXT, key_points TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER, content TEXT, role TEXT, timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, emotion_summary TEXT, topic_summary TEXT, key_events TEXT, user_message_count INTEGER DEFAULT 0, ai_message_count INTEGER DEFAULT 0, importance REAL DEFAULT 0.5, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS consolidation_log (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER DEFAULT 0, consolidated_at TEXT, source_count INTEGER, target_count INTEGER, details TEXT);
        CREATE TABLE IF NOT EXISTS feedback_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, category TEXT DEFAULT 'behavior', source TEXT DEFAULT 'feedback_command', created_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS correction_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_message TEXT, ai_wrong_reply TEXT, corrected_fact TEXT NOT NULL, trigger_keywords TEXT DEFAULT '[]', wrong_pattern TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_applied TEXT, apply_count INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS mention_weights (phrase TEXT PRIMARY KEY, count INTEGER DEFAULT 1, weight REAL DEFAULT 0.0, first_mentioned TEXT, last_mentioned TEXT, decayed_at TEXT);
        CREATE TABLE IF NOT EXISTS user_conclusions (id INTEGER PRIMARY KEY AUTOINCREMENT, conclusion TEXT NOT NULL, category TEXT DEFAULT 'behavior', confidence REAL DEFAULT 0.7, evidence TEXT, source_episodes TEXT, status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS user_vocabulary (id INTEGER PRIMARY KEY AUTOINCREMENT, phrase TEXT NOT NULL, meaning TEXT, use_count INTEGER DEFAULT 1, last_used TEXT, created_at TEXT);
    """)
    conn.execute("INSERT OR IGNORE INTO characters_v2 (id, name) VALUES (1, 'test_char_1')")
    conn.execute("INSERT OR IGNORE INTO characters_v2 (id, name) VALUES (2, 'test_char_2')")
    from datetime import datetime
    now = datetime.now().isoformat()
    for k, v in [('affection', 30), ('trust', 30), ('ai_emotion', 'neutral'), ('recent_negative_count', 0)]:
        conn.execute("INSERT OR IGNORE INTO relationship (key, value, updated_at) VALUES (?, ?, ?)", (k, str(v), now))


    # FTS5 virtual tables（与 _init_db_locked 一致）
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5(content, content_rowid='id')")
    except Exception:
        pass  # FTS5 may not be available
    try:
        conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
            topic_summary, emotion_summary, key_events, content='episodes', content_rowid='id'
        )""")
    except Exception:
        pass

_ensure_main_schema(_main_conn)

# ── Patch all DB factories ──

def _mock_get_conn():
    return _main_conn


def _mock_get_chat_conn(character_id=0):
    if character_id not in _chat_conns:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        from core.db import _init_chat_schema
        _init_chat_schema(conn)
        _chat_conns[character_id] = conn
    return _chat_conns[character_id]


def _mock_get_char_profile_conn(character_id):
    return _mock_get_chat_conn(character_id)


# Override all connection factories at the module level
import core.db as _db_mod
_db_mod.get_conn = _mock_get_conn
_db_mod.get_chat_conn = _mock_get_chat_conn
_db_mod.get_char_profile_conn = _mock_get_char_profile_conn
_db_mod.DB_FILE = ":memory:"


# ── Test-state reset per test ──

import pytest


@pytest.fixture(autouse=True)
def _clear_test_state():
    """Before each test, clear per-character connections and reset tables."""
    _chat_conns.clear()
    for tbl in (
        "chat_history", "user_profile", "facts", "summary_msg_counter",
        "memory", "tiered_summary", "emotion_daily", "emotion_log",
        "relationship", "knowledge_graph", "correction_memory",
        "feedback_memory", "mention_weights", "user_conclusions",
        "user_vocabulary", "empathy_feedback", "goal_tracking",
        "conversation_summary", "episodes", "consolidation_log",
        "sentence_index", "memory_importance", "death_archive",
    ):
        try:
            _main_conn.execute(f"DELETE FROM {tbl}")
        except Exception:
            pass
    _main_conn.execute("INSERT OR IGNORE INTO summary_msg_counter (id) VALUES (1)")
