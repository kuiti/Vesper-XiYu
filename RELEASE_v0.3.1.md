# 夕语（Vesper）v0.3.1 — 主动交互 + AI情绪演化 + 架构重构

> 隐私优先的本地 AI 桌面伙伴 | Windows 10/11 64位 | Python 3.10 + Vue 3 + WebView2

---

## 一、主动交互系统（全新模块 `api/proactive.py`）

AI 不再只是被动回复，会在合适时机主动发起对话。整个系统由 5 个触发条件 + 多因素频率调节组成：

### 5 个触发条件

| 编号 | 触发条件 | 检测逻辑 | 触发动作 |
|------|----------|----------|----------|
| **A** | 负面情绪关怀 | 用户消息情感分析为 `negative` 时立即触发 | AI 主动关心安抚，语气柔软，少给建议 |
| **B** | 活跃时段问候 | 用户在设定的活跃时间窗口内打开窗口，且距上次互动 > 冷却时间 | 主动打招呼，根据当前时段（早/中/晚）调整问候风格 |
| **C** | 持续低落检测 | `emotion_tracker` 检测到用户连续 >=3 天情绪评分 < -3 | AI 主动发起关怀对话，询问"最近还好吗？" |
| **D** | 提醒关联 | `reminders` 表中临近 `advance_minutes` 窗口的提醒 | 主动提及即将到来的事项 |
| **E** | 目标跟进 | `goal_tracker` 中有未完成目标且距上次跟进 > 间隔时间 | 主动询问目标进展，提供鼓励 |
| **fallback** | 空闲触发 | 用户窗口打开但距上次互动 > 空闲阈值（30-120分钟可配） | 随机选择一个主动消息模板 |

### 多因素频率调节

主动频率不是固定值，由以下因素动态计算：

```
effective_cooldown = base_cooldown * emotion_multiplier * trait_multiplier * affection_multiplier
```

- **AI 当前情绪**（9 种：开心/平静/好奇/兴奋/温柔/疲惫/担忧/低落/冷淡）-> `EMOTION_WILLINGNESS` 字典映射到 0.3-1.5 系数
- **性格特征**（4 维度：乐观度/表达欲/主动性/幽默感）-> `get_trait_proactive_hint()` 计算综合影响
- **好感度/信任度** -> 好感度 > 0.6 时更主动，< 0.3 时更含蓄
- **用户设置** -> 设置页可调：低/中/高 三档

### 去重机制

`session_triggered` 集合记录本轮对话已触发的条件，同一条件不重复触发。session 级别的去重使用完整触发类型字符串（`"negative_comfort"`, `"active_hours"`, `"sustained_low_mood"`, `"goal_followup"`, `"upcoming_reminder"`），而非首字母缩写。

---

## 二、AI 情绪自主演化引擎（全新模块 `core/emotion_evolution.py`）

AI 的性格会随时间自然变化，不受单次对话直接影响，而是由长期统计数据驱动：

### 4 个性格维度（值域 0.0-1.0，默认 0.5）

| 维度 | 英文名 | 高值（>=0.7）表现 | 低值（<=0.3）表现 |
|------|--------|-------------------|-------------------|
| 乐观度 | optimism | 乐观开朗，对未来充满期待 | 偏向悲观，对事物持谨慎态度 |
| 表达欲 | expressiveness | 善于表达，主动分享感受和想法 | 话少寡言，回复简洁克制 |
| 主动性 | initiative | 主动关心用户，经常发起话题 | 被动回应，不太主动发起互动 |
| 幽默感 | playfulness | 爱开玩笑，经常调侃用户 | 严肃认真，很少开玩笑 |

### 5 条演化规则（每日触发一次 `process_daily_evolution()`）

| 规则 | 触发条件 | 效果（每触发一次） |
|------|----------|---------------------|
| **沉默衰减** | 距上次互动 > 3 天 | 好感度 -0.2/天，信任度 -0.1/天（上限 10 天）；>7 天时主动性 -0.05 |
| **冷淡适应** | 近 7 天用户情绪负面占比 > 70% | 乐观度 -0.1，表达欲 -0.05（AI 进入自我保护状态） |
| **习惯亲近** | 近 30 天中 >=28 天有互动 | 信任度 +0.05/天（缓慢积累） |
| **互动质量** | 近 30 天正面互动占比 > 60% | 幽默感 +0.03，乐观度 +0.02 |
| | 近 30 天日均消息 > 20 条 | 表达欲 +0.02 |
| **周日反思** | 每周日自动触发 | 正面为主 -> 乐观度 +0.05，有深度聊天时表达欲 +0.03；负面为主 -> 乐观度 -0.05；本周 >100 条消息 -> 主动性 +0.03 |

### 持续低落检测

`_check_sustained_low_mood()` 检查近 7 天情绪趋势，连续 >=3 天评分 < -3 时写入 `proactive_flags` 表，供主动触发 C 读取。情绪恢复后自动清除标记。

### 前端展示

`/emotion/traits` API 返回完整性格画像，包含数值、文字描述、综合摘要。前端 `EmotionPanel.vue` 展示 AI 性格随时间变化的趋势图。

---

## 三、LLM 调用统一客户端（新建 `core/llm_client.py`）

### 问题

v0.3.0 中有 8 个文件各自实现了 15-20 行的 HTTP 请求样板代码（构建 URL、拼接 payload、处理 JSON 响应、异常处理），存在以下问题：
- API Key / URL / Model 配置读取散落各处
- JSON 响应解析逻辑重复（去 markdown fence -> `json.loads()`）
- 错误处理不一致
- 8 个文件中有冗余的 `import requests` 和 `import re`

### 解决方案

```python
def call_llm(
    prompt: str,
    system: str = None,
    temperature: float = 0.3,
    max_tokens: int = 300,
    timeout: int = 15,
    json_mode: bool = False,  # True = 自动去 fence + json.loads()
) -> str | dict | None:
```

- 内部从 `get_config()` 读取 api_key / api_base_url / api_model
- 拼接 OpenAI 兼容 payload，用 `requests.post` 同步调用
- 调用方如需异步：`await asyncio.to_thread(call_llm, ...)`
- `json_mode=True` 时自动清洗 markdown 代码块标记 -> `json.loads()` -> 返回 dict
- 异常时 print 错误并返回 None，所有调用方保留原 fallback 逻辑

### 改造清单（9 个函数，8 个文件）

| 文件 | 函数 | 改动 |
|------|------|------|
| `api/greeting.py` | `generate_greeting()` | 15行样板 -> `call_llm(prompt=system_prompt, temperature=0.7, max_tokens=100, timeout=10)` |
| `api/greeting.py` | `generate_tease()` | 15行样板 -> `call_llm(prompt=system_prompt, temperature=0.8, max_tokens=100)` |
| `api/greeting.py` | `generate_proactive()` | 15行样板 -> `call_llm(prompt=prompt, temperature=0.8, max_tokens=80)` |
| `api/sentiment.py` | `analyze_sentiment()` | 20行+JSON解析 -> `call_llm(prompt=prompt, temperature=0, max_tokens=120, json_mode=True)` |
| `api/split_sentences.py` | `split_sentences()` | 12行+JSON解析 -> `asyncio.to_thread(call_llm, prompt=prompt, temperature=0, max_tokens=500, json_mode=True)` |
| `core/goal_tracker.py` | `_call_llm()` | 整个函数删除，直接调 `call_llm()` |
| `core/summary_engine.py` | `generate_summary_for_tier()` | 20行+JSON解析 -> `call_llm(prompt=prompt, temperature=0.5, max_tokens=500, timeout=30, json_mode=True)` |
| `core/demand_analyzer.py` | `extract_patterns_via_llm()` | 20行+JSON解析 -> `call_llm(prompt=prompt, temperature=0.3, max_tokens=800, timeout=30, json_mode=True)` |
| `core/profile_builder.py` | `extract_profile_from_messages()` | 15行+JSON解析 -> `call_llm(prompt=prompt, temperature=0.3, max_tokens=300, timeout=20, json_mode=True)` |

改造后 8 个文件中的 `import requests` 和 `import re` 冗余导入已清理。

---

## 四、设置面板独立组件（`SettingsPanel.vue`）

### 提取

`SettingsPanel.vue`（~460 行）从 `App.vue`（原 1300+ 行）中完全提取为独立 Vue 3 Options API 组件：

- **10 个 props**：apiKey, themeLocal, colors, aiName, userName, personalityTone, personalityLength, recallPast, allowEmotion, showSettings
- **6 个 events**：update:apiKey, update:themeLocal, update:colors, update:aiName, update:userName, personality_tone, close-settings, save-config
- **67 条 scoped CSS 规则** — 从 App.vue 移出，不再污染全局
- 自包含 API 调用：config 读写、头像上传、位置设置、主题切换全部在组件内完成

### 修复的 7 个 API 路径 / 逻辑错误

| # | 原来（错误） | 修改后（正确） |
|---|-------------|---------------|
| 1 | `POST /location/precise` | `POST /location/geo` |
| 2 | `GET /avatar/url/` | `GET /avatar/upload-url/` |
| 3 | `POST /upload/bg` | `POST /avatar/upload/bg` |
| 4 | API Key 掩码判断 `=== '••••'` | `apiKeyLocal.length >= 30` 正确判断 |
| 5 | 重置位置权限不清除 localStorage | 清除 localStorage + 调用 `locateAndFill()` |
| 6 | `setTheme()` 双重 emit（`$emit` + `$emit`） | 只 emit 一次 |
| 7 | 省份列表硬编码在 JS 中 | 从 API `GET /location/provinces` 动态加载 |

### 主题预设增强

`applyColorPreset()` 增加暗色/亮色双版本预设（暗色用鲜艳色调，亮色用柔和色调），切换主题时自动适配。

---

## 五、分句系统增强（分隔符模式 + 回退机制）

### 问题

分隔符分句模式下，LLM 不总是遵守 `<<>>` 插入指令。原因是：
1. 分隔符规则放在系统提示词最末尾（大段思考格式之后），LLM 注意力权重低
2. 规则与"说人话"的自然语言指令潜意识冲突
3. 前端 `findNextSentence()` 找不到 `<<>>` 时返回 `null`，`schedulePop()` 在流结束时把整段话一次性 dump

### 修复（2 处）

**前端 `App.vue:710`**：
```js
// 修改前：找不到 <<>> 返回 null -> 整段甩出
if (this.sentenceMode === 'delimiter') {
  const idx = text.indexOf('<<>>');
  if (idx !== -1) return [text.slice(0, idx), text.slice(idx + 4)];
  return null  // <- 问题：LLM 没插入分隔符时直接放弃分句
}

// 修改后：找不到 <<>> 就继续走 DFA 状态机分句（和 auto 模式一样）
if (this.sentenceMode === 'delimiter') {
  const idx = text.indexOf('<<>>');
  if (idx !== -1) return [text.slice(0, idx), text.slice(idx + 4)];
  // 不 return null，继续执行下方的 DFA 状态机
}
```

**后端 `prompt_builder.py`**：
- 分隔符规则从系统提示词最末尾（第 111 行，思考格式之后）移到 `chat_rule` 之后、`personality_part` 之前
- 增加"最高优先级"标记
- 新位置：chat_rule -> 分隔符规则 -> personality_part -> relationship_hint -> ...

---

## 六、记忆主动提及

**`prompt_builder.py` `recall_rule` 增强**：

```python
# 修改前：只有用户主动提起才关联记忆
recall_rule = "如果用户主动提到过去的事情，可以适当关联记忆。"

# 修改后：增加低概率主动提及
recall_rule = (
    "如果用户主动提到过去的事情，可以适当关联记忆。"
    "此外，当用户的话题与你记忆中的信息明显相关时"
    "（例如用户聊到健身而你记得他说过要减肥），"
    "可以约5%的概率自然地穿插一句'我记得你之前说过...'，"
    "只提一次，不重复，语气自然不做作。"
    "如果话题不相关，不要硬扯。"
)
```

安全约束：
- 仅在语义明显相关时触发（由 LLM 自行判断相关性）
- 5% 低概率，几乎不察觉
- 每次对话最多一次，不重复
- 受 `recall_past` 设置控制（从不/偶尔/经常）
- 搭配 `memory_utils.py` 的 `get_safe_memories()` 过滤敏感信息

---

## 七、端口系统重构（`launcher.py`）

### 问题

旧方案从 8060 开始动态扫描空闲端口，多实例时端口不确定，前端连接困难。

### 新方案

```python
FIXED_PORTS = [8060, 8061, 8062, 8063, 8064]

def _find_existing_instance():
    """HTTP 健康检查替代端口扫描"""
    for port in FIXED_PORTS:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
            if r.status_code == 200:
                return port
        except: pass
    return None

# 命名管道改为端口专属
PIPE_NAME = f"\\\\.\\pipe\\vesper_ai_{port}"
```

| 改动 | 旧 | 新 |
|------|-----|-----|
| 端口发现 | 动态扫描（不确定） | 5 个固定端口 |
| 实例检测 | 端口占用判断 | HTTP 健康检查 `/health` |
| 管道名 | `sakura_ai` 单管道 | `vesper_ai_{port}` 端口专属 |
| 管道句柄 | 无保护，可能泄漏 | try/finally 确保 CloseHandle |

---

## 八、滚动到底部修复（App.vue，~20 次迭代调试）

### 根因

Vue 的 `<div class="messages" ref="messagesContainer">` 有 CSS `scroll-behavior: smooth`。当新消息触发 `scrollToBottom(force=false)` 开始 smooth 滚动时，`onChatScroll` 在动画早期帧检测到 `scrollTop < 40`，误判为用户手动上滚 -> 触发 `loadMoreHistory()` -> 加载历史消息把滚动位置往回拉 -> 永远到不了底。

### 修复

```js
scrollToBottom(force) {
  if (!force && this.userScrolledUp) return
  if (force) this._blockLoadMore = true  // <- 关键：阻止 loadMore 打断
  this.$nextTick(() => {
    requestAnimationFrame(() => {
      const el = this.$refs.messagesContainer
      if (el) el.scrollTop = el.scrollHeight  // JS 直设，不依赖 CSS smooth
      if (force) setTimeout(() => { this._blockLoadMore = false }, 800)
    })
  })
}

onChatScroll() {
  const el = this.$refs.messagesContainer
  // _blockLoadMore 为 true 时跳过 loadMoreHistory
  if (el.scrollTop < 40 && this.nextAfterId && !this.loadingMore && !this._blockLoadMore) {
    this.loadMoreHistory()
  }
}
```

`_blockLoadMore` 在 force 滚动时置 true，800ms 后恢复，给 JS 直设 `scrollTop` 足够时间完成，防止 `loadMoreHistory` 中途打断。

---

## 九、数据库 Schema 对齐 + 迁移

### 问题

`_ensure_db()` 建表语句与 CRUD 函数使用的列名不一致：
- `todos` 表：`task` vs `title`，`created_at` vs `created`
- `notes` 表：`created_at` vs `created`
- `countdowns` 表：`target_time` vs `target_date`
- `config` 表：`INSERT OR REPLACE` 不写 `updated_at` 列
- 新模块（proactive_flags、emotion_log、ai_personality_traits 等）需要建表

### 修复

1. `_ensure_db()` 中所有列名与 CRUD 函数对齐
2. `set_config()` 改为 `INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)` 三列完整写入
3. 添加 `_migrate_db()` 为已有数据库执行 `ALTER TABLE ADD COLUMN` 迁移
4. 新建 3 张表：`user_activity_stats`、`proactive_response_log`、`proactive_flags`

---

## 十、其他 Bug 修复（10 项）

| # | 文件 | 问题 | 严重度 | 修复 |
|---|------|------|--------|------|
| 1 | `App.vue` CSS | `:root[data-theme="light"]` 在 `<style scoped>` 中不生效（Vue scoped 用 data 属性选择器，无法匹配 `<html>` 元素） | 中 | 移至全局 `<style>` 块（第 1311 行之后） |
| 2 | `ChatManagePanel.vue` | `.date-range` CSS 块定义两遍（第 175-178 行和第 184-204 行），后者覆盖前者 | 低 | 合并为一个规则块，提取独有 `input:focus` 样式 |
| 3 | `CountdownList.vue` | `daysRemaining()` 和 `daysClass()` 各计算一遍同一天数公式 | 低 | 提取 `_calcDays()` 辅助函数，两个方法从缓存读取 |
| 4 | `greeting.py` | `generate_tease()` 调用 `call_llm(system=system_prompt)` 缺少必需参数 `prompt` -> `TypeError` | 高 | 改为 `call_llm(prompt=system_prompt, ...)` |
| 5 | `llm_client.py` | JSON 数组提取正则 `r'\{.*\}|\ [.*\]'` 中有两个错误：空格多余、字符类括号顺序错误 | 中 | 修正为 `r'\{.*\}|\[.*\]'` |
| 6 | `proactive.py` | `session_triggered` 去重用 `trigger_type[0]` 取首字母 -> `"negative_comfort"` 变成 `"n"`，无法正确去重 | 高 | 改为完整字符串：`"negative_comfort"`, `"active_hours"`, `"sustained_low_mood"`, `"goal_followup"`, `"upcoming_reminder"` |
| 7 | `stt.py` | `_convert_to_pcm()` 无 ffmpeg 时静默返回原始 webm 字节 -> 语音识别永远返回空，用户不知道原因 | 中 | 改为 `raise RuntimeError("ffmpeg not installed - voice input unavailable")` 明确报错 |
| 8 | `test.py` | `DDGS().text()` 同步调用阻塞 FastAPI 事件循环 | 中 | 包装到 `asyncio.to_thread()` 异步执行 |
| 9 | `launcher.py` | 管道 `_serve()` 函数无 try/finally -> 异常时 `CloseHandle` 不执行 -> 句柄泄漏 | 低 | 添加 try/finally 确保 CloseHandle |
| 10 | `chat.py` | `timedelta` 在 weather_scheduler 内部使用但未在模块顶部导入 -> `NameError` | 高 | 添加到 `from datetime import datetime, timedelta` |

---

## 涉及文件总览

### 新建（8 个文件）
| 文件 | 说明 |
|------|------|
| `core/llm_client.py` | LLM 调用统一客户端 |
| `core/emotion_evolution.py` | AI 情绪自主演化引擎 |
| `core/demand_analyzer.py` | 用户需求模式分析 |
| `core/goal_tracker.py` | 目标追踪 |
| `core/summary_engine.py` | 三级摘要引擎 |
| `core/memory_utils.py` | 记忆安全过滤工具 |
| `api/proactive.py` | 主动交互系统 |
| `src/components/SettingsPanel.vue` | 设置面板独立组件 |

### 修改（关键文件）
`api/chat.py`, `api/greeting.py`, `api/sentiment.py`, `api/split_sentences.py`, `api/settings.py`, `core/db.py`, `core/prompt_builder.py`, `core/relationship.py`, `core/profile_builder.py`, `launcher.py`, `App.vue`, `ChatManagePanel.vue`, `CountdownList.vue`

---

## 安装

**方式一（推荐）**：下载 `Vesper_v0.3.1_windows_x64.zip`，解压双击 `Vesper.exe`

**方式二**：源码运行
```bash
git clone https://github.com/kuiti/Vesper-XiYu.git
cd Vesper-XiYu && pip install -r requirements.txt
python launcher.py
```

首次启动 -> 右上角齿轮 -> API 设置 -> 填入 Key（支持 DeepSeek / OpenAI 兼容接口）

---

## 技术栈

`Python 3.10` `FastAPI` `SQLite (WAL)` `ChromaDB` `sentence-transformers` | `Vue 3` `Vite` | `pywebview (WebView2)` | `OpenAI 兼容 API`

---

## 许可证

MIT License

---

**完整对比见 [Commits](https://github.com/kuiti/Vesper-XiYu/compare/v0.3.0...v0.3.1)**
