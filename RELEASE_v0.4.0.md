# Vesper（夕语） v0.4.0 Release Notes

## 概述

v0.4.0 是夕语项目的一次重大稳定性更新。来自"佐仓"母项目的 **86 项 Bug 修复**已全部同步，全量审计了 89 个源代码文件，致命/高危/中危级别问题全部清零。

**代码版本**: 5.0.0  
**发布日期**: 2026-05-23

---

## 致命修复 (3 项)

| 问题 | 影响 |
|------|------|
| 空 key 删除记忆时会清空全部对话摘要表 | 用户在 MemoryVault 中删除摘要时，若不传 key 参数，整个摘要表被 `LIKE '%%'` 匹配清空 |
| `recall_past` 设置完全无效 | 设置面板"回忆过去"选项，存储用的键名是 `recall`，读取时却查 `recall_past`，永远返回默认值"从不" |
| MemoryVault 删除摘要时截断前 20 字 | `.slice(0,20)` 导致前缀相同的摘要被误删，或完全删不到目标 |

## 高危修复 (14 项)

### 后端
| 问题 | 影响 |
|------|------|
| AI 日记生成同步阻塞整个事件循环 15 秒 | `call_llm` 同步调用阻塞 asyncio，日记生成期间所有请求无响应 |
| 主动消息 idle 触发器无防重复 | 用户空闲超过 30 分钟后，每次 poll 都触发新消息，造成刷屏 |
| 新用户无响应率数据时 `None >= 0.5` 崩溃 | `get_proactive_response_rate()` 返回 None 被直接比较，抛出 TypeError |
| 情绪每日记录 SELECT-then-INSERT 竞态 | 并发记录同日情绪时，两条请求同时读到"无记录"，都尝试 INSERT 导致 IntegrityError |
| 提醒内容含花括号 `{}` 崩溃 | `template.format(content=content)` 把用户内容中的花括号当作占位符解析 |

### 前端
| 问题 | 影响 |
|------|------|
| ChatManagePanel 日期校验有副作用 | computed 属性内修改 dateError，违反 Vue 响应式原则 |
| 倒计时面板无定时刷新 | 面板打开后倒计时数字永远不变，需手动刷新 |
| 倒计时时区偏移 | `new Date("2024-12-25")` 按 UTC 解析，亚洲用户提前一天归零 |
| 知识库上传无大小限制 | 可上传 GB 级文件耗尽磁盘空间 |
| MemoryGraph/HistoryPanel 组件销毁后异步回调泄漏 | 组件销毁后 API 回调仍在写 `this.xxx` |
| MemoryVault 删除无确认弹窗 | 误点直接丢失记忆数据 |
| StatsPanel/TodayLearning 空数据导致模板崩溃 | API 返回 null 时 `Cannot read properties of null` |

## 中危修复 (24 项)

- **身份混淆**: `_is_emotional_question` 把含"你"字的正常问题判定为情绪问题，阻断知识搜索
- **状态机卡死**: `split_sentences.py` 短括号动作后状态不重置，导致后续文本合并异常
- **TOCTOU 竞态**: STT 模型加载无锁，并发请求可能创建多个模型实例
- **文件泄漏**: Vision 上传超大图片被拒绝后，已写磁盘的部分文件未清理
- **缓存竞态**: `profile_builder` 全局缓存无锁保护
- **0 值被当作假值**: WeatherCard 0°C、0% 湿度被 `v-if` 隐藏，倒计时、天气建议中的 0 值判断同样问题
- **上传**: 知识库无大小限制、迁移导入 blob URL 过早释放、api.js 无上传超时
- **Vue 规范**: LockScreen 用 Function prop 而非 emit、SearchPanel 无请求取消、多处缺少 null 守卫
- **阈值边缘**: 摘要触发计数在恰好 10/50/100 时显示异常

## 技术升级

- 所有 Python 文件版本号统一为 `5.0.0`
- PyInstaller spec 隐式导入列表从 3 项扩展到 50 项，覆盖所有 API 和 Core 模块
- 数据库建表（favorites）移到初始化流程中，消除启动时 try/except 建表
- LLM 调用增加 3 次重试机制，含退避延迟
- JSON 解析增强：支持 markdown fence 内提取 + 非贪婪正则

---

## 从 v0.3.1 升级

**数据兼容**：v0.3.1 的 chat_history.db 可直接复制到 v0.4.0 的 `data/` 目录使用。

**配置文件不变**：`config.json` 格式完全相同，无需修改。

**打包版升级**: 替换旧文件夹即可，数据目录 `data/` 可保留。

**源码版升级**: 替换 `api/` 和 `core/` 目录中所有 `.py` 文件，重新 `pip install -r requirements.txt`。
