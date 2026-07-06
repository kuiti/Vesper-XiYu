# 代码审计报告 — 断链检查

审计时间: 2026-06-12
范围: `sakura_backend/` + `sakura_frontend/`

---

## CRITICAL — 孤儿组件（定义了但从未被引用）

| # | 文件 | 描述 |
|---|------|------|
| 1 | `sakura_frontend/src/components/SearchPanel.vue` | 整个组件从未被任何文件 import，也未在任何模板中使用。**死代码** |
| 2 | `sakura_frontend/src/components/settings/LocationSettings.vue` | 从未被 import 或使用。其所有 `$emit` 事件（save-amap-key, test-amap, locate-ip 等）无父组件监听。**死代码** |
| 3 | `sakura_frontend/src/components/settings/PrivacySettings.vue` | 从未被 import 或使用。其所有 `$emit` 事件（toggle-pin, save-pin 等）无父组件监听。**死代码** |
| 4 | `sakura_backend/core/db/goal.py` | 空模块，导出零个函数。`from .goal import *` 是无操作。 |

---

## HIGH — 断掉的 emit 链

| # | 文件:行号 | 描述 |
|---|-----------|------|
| 1 | `components/settings/ChatSettings.vue:4` | `$emit("save-cfg")` — 无父组件处理 |
| 2 | `components/settings/ChatSettings.vue:19` | `$emit("upd-phrase")` / `$emit("del-phrase")` / `$emit("add-phrase")` — 无父组件处理 |
| 3 | `components/settings/ChatSettings.vue` (多处) | 共 8 个 emit 事件无 handler |

> **说明**: ChatSettings.vue 虽被 import，但其 emit 事件未被父组件监听。LocationSettings.vue 和 PrivacySettings.vue 的 emit 问题属于孤儿组件附带问题。

---

## HIGH — 后端未使用的导入（api/ 和 core/ 聚焦）

### api/chat.py — 集中了最多未使用的导入
| 行号 | 导入 | 说明 |
|------|------|------|
| 8 | `reroll_last_ai_message` | 从 core.db 导入但从未调用 |
| 8 | `reroll_from_message` | 从 core.db 导入但从未调用 |
| 8 | `update_reminder_last_reminded` | 从 core.db 导入但从未调用 |
| 22 | `search_similar` | 从 core.vector_store 导入但从未调用 |
| 22 | `search_knowledge_similar` | 从 core.vector_store 导入但从未调用 |
| 26 | `_check_achievements` | 从 api.chat_tasks 导入但从未调用 |
| 42 | `weather_scheduler`, `_push_weather`, `_broadcast_weather` | 从 api.weather_push 导入但从未调用 |

### api/ 其他文件
| 文件:行号 | 导入 |
|-----------|------|
| `avatar.py:2` | `import shutil` (未使用) |
| `characters.py:7` | `from fastapi import Form` (未使用) |
| `chat_loops.py:7` | `import time` (未使用) |
| `chat_loops.py:10` | `from core.db import get_reminders` (未使用) |
| `chat_manage.py:3` | `from core.db import get_db_connection` (未使用) |
| `chat_tasks.py:11` | `import threading` (未使用) |
| `cloud.py:7` | `import os` (未使用) |
| `countdowns.py:2` | `from core.db import delete_countdown` (未使用) |
| `knowledge.py:1` | `from fastapi import Form` (未使用) |
| `migrate.py:5` | 7 个 db 函数全部未使用 (get_config, add_chat_message, add_todo, add_note, add_countdown, add_reminder, clear_chat_history) |
| `notes.py:2` | `from core.db import delete_note` (未使用) |
| `proactive.py:13` | `from datetime import timedelta` (未使用) |
| `reminders.py:3` | `from core.db import delete_reminder` (未使用) |
| `report.py:3` | `from datetime import timedelta` (未使用) |
| `sentiment.py:3` | `import json` (未使用) |
| `sentiment.py:6` | `from core.db import get_config` (未使用) |
| `split_sentences.py:11` | `import json` (未使用) |
| `summary.py:2` | `get_config`, `set_config`, `get_messages_since_last_tiered_summary` (全部未使用) |
| `todos.py:2` | `from core.db import delete_todo` (未使用) |
| `tts.py:4` | `import re` (未使用) |
| `tts.py:16` | `from core.tts import _strip_markdown` (未使用) |
| `intent.py:74` | `from core.weather import WMO_WEATHER` (未使用) |

### core/ 文件
| 文件:行号 | 导入 |
|-----------|------|
| `character_card.py:15` | `import os` (未使用) |
| `character_card.py:19` | `import hashlib` (未使用) |
| `demand_analyzer.py:9` | `import json` (未使用) |
| `demand_analyzer.py:11` | `from core.db import get_config` (未使用) |
| `diary_utils.py:4` | `get_config`, `save_diary_entry` (未使用) |
| `goal_tracker.py:7` | `import json` (未使用) |
| `goal_tracker.py:9` | `from core.db import get_config` (未使用) |
| `knowledge_graph.py:4` | `from core.db import get_conn` (未使用) |
| `memory_utils.py:2` | `from core.db import get_config` (未使用) |
| `prompt_pipeline.py:14-19` | `json`, `timedelta`, `Optional`, 以及 6 个 persona_data 导入 (全部未使用) |
| `db/chat.py:3` | `import json` (未使用) |
| `db/cleanup.py:3-4` | `sqlite3`, `timedelta` (未使用) |
| `db/misc.py:3` | `import json` (未使用) |
| `tts/aliyun.py:2` | `import base64` (未使用) |
| `tts/baidu.py:2` | `import base64` (未使用) |

> **排除项**: `from __future__ import annotations` 和 `from __future__` 是合法的模块级指令，不影响运行时。`core/vector_store/__init__.py` 中的大量导入属于 **re-export** 模式（供外部 `from core.vector_store import xxx`），非误报但需注意是否真的有调用方。

---

## MEDIUM — 后端空 except 块（吞掉异常，调试困难）

| 文件:行号 | 说明 |
|-----------|------|
| `api/avatar.py:82` | `except: pass` |
| `api/chat.py:221` | `except: pass` |
| `api/chat_loops.py:34, 108, 135` | 3 处 `except: pass` |
| `api/chat_tasks.py:272` | `except: pass` |
| `api/greeting.py:197` | `except: pass` |
| `api/memory.py:28` | `except: pass` |
| `api/proactive.py:352, 360` | 2 处 `except: pass` |
| `core/profile_builder.py:223, 246, 265, 316, 350` | 5 处 `except: pass` |
| `core/prompt_pipeline.py:393` | `except: pass` |
| `core/relationship.py:431` | `except: pass` |
| `core/db/config.py:49` | `except: pass` |
| `core/db/__init__.py:340` | `except: pass` (schema migration, 可接受) |

**合计**: 19 处后端空 except 块

---

## MEDIUM — 前端空 catch 块

| 文件:行号 | 说明 |
|-----------|------|
| `App.vue:254` | `catch (e) {}` — 导出聊天失败时静默吞错 |
| `components/TodayLearning.vue:43` | `catch (e) {}` |

---

## MEDIUM — 前端缺失 await 的 API 调用

| 文件:行号 | 说明 |
|-----------|------|
| `CharactersView.vue:84-85` | `api.get('/characters/')` 和 `api.get('/characters/current')` — 可能在 `Promise.all` 中，但缺少 `await` |
| `InsightPanel.vue:83-84, 95-96` | 4 个 `api.get()` 调用在 `Promise.all` 中但缺 `await` |
| `Game2048.vue:87` | `api.post(...)` 缺 `await`（有 `.catch` 处理） |
| `Minesweeper.vue:99` | `api.post(...)` 缺 `await`（有 `.catch` 处理） |
| `SnakeGame.vue:88` | `api.post(...)` 缺 `await`（有 `.catch` 处理） |

> **说明**: Game2048/Minesweeper/SnakeGame 的 fire-and-forget 模式（`.catch(() => {})`）是可接受的，因为不需要等待结果。CharactersView 和 InsightPanel 需要进一步确认上下文。

---

## LOW — 孤儿 DB 函数（仅在自身文件内调用，无外部调用方）

| 模块:函数 | 说明 |
|-----------|------|
| `chat.py:rebuild_fts_index` | 仅在 chat.py 内部引用 |
| `chat.py:get_last_ai_message` | 仅在 chat.py 内部引用 |
| `summary.py:get_active_summary` | 仅在 summary.py 内部引用 |
| `summary.py:get_active_keypoints` | 仅在 summary.py 内部引用 |
| `summary.py:merge_keypoints` | 仅在 summary.py 内部引用 |
| `summary.py:get_messages_since_last_summary` | 仅在 summary.py 内部引用 |
| `summary.py:decrement_msg_counter` | 仅在 summary.py 内部引用 |
| `tools.py:toggle_todo` | 仅在 tools.py 内部引用 |
| `emotion.py:get_proactive_cooldown_minutes` | 仅在 emotion.py 内部引用 |
| `misc.py:get_achievements` | 仅在 misc.py 内部引用 |
| `misc.py:get_all_achievement_defs` | 仅在 misc.py 内部引用 |

> **说明**: 这些函数通过 `from .xxx import *` 被 re-export 到 `core.db` 命名空间，但实际上没有外部模块调用它们。可能是为未来功能预留的，也可能是遗留代码。

---

## LOW — 未使用的 CSS 变量（themes.css 中定义但未被任何 `<style>` 引用）

去重后的唯一变量列表：
- `--surface-elevated`
- `--text-disabled`
- `--accent-hover`
- `--accent-secondary`
- `--bubble-user-text`
- `--bubble-assistant-text`
- `--border-light`
- `--status-warning`
- `--status-info`
- `--cb` / `--ub`
- `--gap-xs` / `--gap-sm` / `--gap-md` / `--gap-lg` / `--gap-xl` / `--gap-2xl` / `--gap-3xl`

**合计**: 18 个唯一 CSS 变量未被使用

---

## 未发现问题的区域

| 检查项 | 结果 |
|--------|------|
| **未注册的路由** | ✅ 所有 `api/*.py` 中的 34 个 router 均在 `main.py` 的 `_ALL_ROUTERS` 中注册 |
| **未使用的 Pinia store** | ✅ 3 个 store (useChatStore, useSettingsStore, useUiStore) 均有调用方 |
| **未注册的组件** | ✅ 所有被 import 的 .vue 组件均在 `components:{}` 中注册（或在 `<script setup>` 中自动注册） |
| **后端缺 await** | ✅ 未发现明显遗漏 |
| **前端未处理的 Promise** | ✅ 未发现 `.then()` 缺 `.catch()` |

---

## 严重程度统计

| 级别 | 数量 | 说明 |
|------|------|------|
| CRITICAL | 4 | 孤儿组件(3) + 空模块(1) |
| HIGH | 6 | 断 emit 链(1组) + 关键未使用导入(5组) |
| MEDIUM | 28 | 空 except/catch(21) + 缺 await(5+组) |
| LOW | 29 | 孤儿 DB 函数(11) + 未用 CSS 变量(18) |

---

## 建议优先修复

1. **删除或整合孤儿组件**: `SearchPanel.vue`、`LocationSettings.vue`、`PrivacySettings.vue` — 如不再需要应删除
2. **清理 `api/chat.py` 的 10 个未使用导入** — 最大文件的导入膨胀会拖慢启动
3. **修复 `api/migrate.py`** — 7 个 db 函数导入全部未使用，说明迁移逻辑可能未完成
4. **审查 `core/profile_builder.py`** — 5 处空 except 块，可能导致配置解析错误被静默吞掉
5. **清理 themes.css** — 18 个未使用的 CSS 变量增加了维护负担