# 代码审计修复

## 🔴 P0：清理孤儿组件

**文件操作**：
1. 删除 `sakura_frontend/src/components/SearchPanel.vue`（完全未被引用）
2. 用 `LocationSettings.vue` 替换 SettingsView 中 location 区域的 inline 代码
3. 用 `PrivacySettings.vue` 替换 SettingsView 中 privacy 区域的 inline 代码

**具体**：
- `SettingsView.vue` 中，找到 `v-else-if="activeCat==='location'"` 的 div，替换为 `<LocationSettings />` 组件
- 找到 `v-else-if="activeCat==='privacy'"` 的 div，替换为 `<PrivacySettings />` 组件
- 添加 import 和 components 注册

## 🟡 P1：修复 ChatSettings.vue 的 emit 断链

**文件**：`SettingsView.vue`

ChatSettings.vue 发出的 8 个事件在 SettingsView 中没有监听器：

| 事件 | 期望的处理 |
|------|-----------|
| `save-cfg` | 调用 `saveCfg(key, value)` |
| `upd-phrase` | 更新短语列表 |
| `del-phrase` | 删除短语 |
| `add-phrase` | 添加短语 |
| `clear-today-learning` | 清除今日学习 |

在 SettingsView 中，找到 `<ChatSettings ...>` 的调用处，补上缺失的事件监听器。

## 🟡 P2：清理未使用 import

**方法**：对以下文件逐行检查并删除未使用的 import：

```
api/avatar.py:2     → 删除 import shutil
api/chat_loops.py:7 → 删除 import time
api/chat_manage.py:3 → 删除 from core.db import get_db_connection
api/cloud.py:7      → 删除 import os
api/countdowns.py:2 → 删除 from core.db import delete_countdown
api/knowledge.py:1  → 删除 from fastapi import Form
api/notes.py:2      → 删除 from core.db import delete_note
api/proactive.py:13 → 删除 from datetime import timedelta
api/reminders.py:3  → 删除 from core.db import delete_reminder
api/report.py:3     → 删除 from datetime import timedelta
api/sentiment.py:3  → 删除 import json
api/sentiment.py:6  → 删除 from core.db import get_config
api/split_sentences.py:11 → 删除 import json
api/summary.py:2     → 删除未使用的 get_config, set_config
api/todos.py:2      → 删除 from core.db import delete_todo
api/tts.py:4        → 删除 import re
api/tts.py:16       → 删除 from core.tts import _strip_markdown
api/intent.py:74    → 删除 from core.weather import WMO_WEATHER
```

**注意**：不要删 `from __future__ import annotations`。

## 🟢 P3：修复空 except 块

**文件**：以下 19 处 `except: pass` 改为 `except Exception: silent_exc("ctx", e)`：

- api/avatar.py:82, api/chat.py:221, api/chat_loops.py:34,108,135
- api/chat_tasks.py:272, api/greeting.py:197, api/memory.py:28
- api/proactive.py:352,360
- core/profile_builder.py:223,246,265,316,350
- core/prompt_pipeline.py:393, core/relationship.py:431
- core/db/config.py:49, core/db/__init__.py:340

注意：确保 import `from core.retry import silent_exc` 在每个文件中存在。

## 验证
```bash
cd H:/my_cc_ai/sakura_frontend && npm run build
cd H:/my_cc_ai/sakura_backend && python -m pytest tests/ -v
```
