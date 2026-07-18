# Vesper（夕语）— AI 角色扮演聊天引擎

夕语是一个**本地优先**的 AI 角色扮演聊天应用。每个角色拥有独立人格、记忆、情感和关系，像真人一样与你长期相处。

> **开源版（源码）** | 打包版（EXE）待后续发布

---

## 设计哲学

夕语不是"套壳聊天 UI"，而是一个**角色扮演引擎**——从底层数据库隔离到顶层提示词管道，全部围绕"让角色活起来"设计。

| 理念 | 实现 |
|------|------|
| **长期记忆** | 三层记忆（短期上下文 → 中期摘要 → 长期向量检索），跨会话持久化 |
| **真实情感** | 12 种情绪状态 + OCEAN 五维人格 + 好感度/信任度双轨关系，每日演化 |
| **角色独立** | 每个角色独享 SQLite 数据库 + ChromaDB 集合，零串扰 |
| **主动陪伴** | 空闲问候、情绪关怀、小惊喜、周期性主动互动 |
| **功能完备** | 知识库 RAG、知识图谱、纠错记忆、数据导入导出、全文搜索 |
| **温度感** | 不是冷冰冰的工具，是有记忆、有情绪、会成长的陪伴者 |

---

## 快速开始

### 环境要求

- Windows 10/11（64 位）
- Python 3.10+
- 内存 4GB+（推荐 8GB）
- AI API Key（DeepSeek 推荐，国内可用）

### 安装

```bash
git clone https://github.com/kuiti/Vesper-XiYu.git
cd Vesper-XiYu
python -m venv venv
venv\Scripts\activate
pip install -r requirements-cloud.txt
```

### 获取 API Key

1. 打开 [platform.deepseek.com](https://platform.deepseek.com/)
2. 注册 → API Keys → 创建
3. 复制保存

> 也支持 OpenAI / Ollama / Azure 等任何 OpenAI 兼容接口。

### 启动

```bash
python launcher.py
```

首次启动自动创建 `data/` 目录，在设置面板填入 API Key 即可开始聊天。

---

## 核心系统

### 角色引擎

- **角色卡**：兼容 SillyTavern V2/V3 规范，一键导入社区角色卡
- **独立人格**：OCEAN 五维（开放性/尽责性/外向性/宜人性/神经质）
- **时间感知**：真实时间 / 固定时间 / 相对时间 / 无时间四种模式
- **完整隔离**：每个角色独立的数据库、向量集合、配置、记忆、关系

### 记忆系统

| 层级 | 容量 | 机制 |
|------|------|------|
| 短期 | 最近对话 | 上下文窗口直接注入 |
| 中期 | 50/100/150 条消息 | 三级生命周期摘要，自动衰减归档 |
| 长期 | 全量 | ChromaDB 语义向量 + BM25 关键词混合检索 |
| 巩固 | 每 8 轮 | TempMemory 暂存 → 后台 LLM 批量提取事实 → 分类存储 |

### 情感与关系

- **12 种情绪**：狂喜 → 开心 → 满足 → 平静 → 谨慎 → 冷漠 → 烦躁 → 受伤 → 不信任 → 敌意 → 被背叛 → 怨恨
- **双轨关系**：好感度（-100~100）+ 信任度（-100~100）
- **每日演化**：沉默衰减、冷适应、习惯亲近、反讽惩罚等规则
- **里程碑**：好感度/信任度跨阈值时触发关系阶段变化

### 提示词管道

33 个管道组件，按注入区域分层：

```
静态前缀层 (5 pipes):
  IronRule → FactRule → ChatRule → TimeRule → Identity

动态注入层 (24 pipes):
  Persona → PersonalityTrait → Thinking → CustomContext →
  Continuity → WorkMemory → Onboarding → EpisodicMemory →
  EntityContext → FactsContext → Correction → Conclusion →
  Vocabulary → Opinion → Summaries → Schedule → RAG →
  KnowledgeBase → KnowledgeGraph → Quirk → Pattern →
  UserSummary → DepthHint → UserPersona

深度插入层 (4 pipes):
  PostHistory (depth:0) → DepthHint (depth:1) →
  PersonalityTrait (depth:2) → Continuity (depth:4)
```

### 知识管理

- **知识库 RAG**：上传文档自动分块向量化，对话中按需检索引用
- **知识图谱**：自动提取实体关系三元组（subject-predicate-object），跨角色隔离
- **纠错记忆**：AI 记住你的纠正，避免重复犯错
- **用户画像**：自动构建你的偏好、习惯、事件等结构化认知

### 数据管理

- 全量导出/导入（JSON 备份）
- 云端加密同步（WebDAV）
- FTS5 全文搜索
- 按时间范围清理 + 完全重置

---

## 项目结构

```
vesper_backend/
├── launcher.py              # 桌面启动入口
├── main.py                  # FastAPI 应用（140 条路由）
├── cloud_server.py          # 云端部署入口（无 GUI）
├── Vesper.spec              # PyInstaller 打包配置
│
├── api/                     # 46 个 API 路由模块
│   ├── chat_session.py      # WebSocket 流式聊天（核心，~1200 行）
│   ├── chat_loops.py        # 后台循环（主动消息/日记调度）
│   ├── chat_tasks.py        # 后台任务（DSML 清理/情绪演化/RAG 构建）
│   ├── chat_fallback.py     # 三阶段 LLM 降级（非流式 → 缓存 → 错误）
│   ├── chat_commands.py     # 命令处理（/reroll /welcome 等）
│   ├── chat_parser.py       # 思考标签解析器
│   ├── greeting.py          # 智能问候 + 主动交互生成
│   ├── proactive.py         # 主动触发引擎
│   ├── characters.py        # 角色卡管理
│   ├── memory.py            # 记忆管理 API
│   ├── knowledge.py         # 知识库 CRUD
│   ├── settings.py          # 设置 + 完全重置
│   ├── migrate.py           # 全量导出/导入（V2）
│   ├── favorites.py         # 收藏消息
│   ├── emotion.py           # 情感趋势 API
│   ├── relationship.py      # 关系系统 API
│   ├── profile.py           # 用户画像 API
│   ├── history.py           # 会话管理
│   ├── search.py            # 全文搜索
│   ├── summary.py           # 摘要 API
│   ├── stats.py             # 统计概览
│   ├── report.py            # 月度报告
│   └── ...                  # TTS/STT/Vision/Cloud 等
│
├── core/                    # 75 个核心引擎模块
│   ├── db/                  # 数据库层（主库 + 角色独立库）
│   │   ├── __init__.py      # 建表/迁移/连接池（60+ 表）
│   │   ├── chat.py          # 聊天记录 CRUD + FTS5
│   │   ├── config.py        # 三级配置解析（角色→全局→默认）
│   │   ├── entity.py        # 实体/知识图谱/记忆重要性
│   │   ├── emotion.py       # 情绪日志/活跃统计
│   │   ├── memory.py        # 键值记忆 CRUD
│   │   ├── misc.py          # 收藏/日记/文档
│   │   ├── summary.py       # 三级摘要 + 亡语归档
│   │   ├── tools.py         # 预设模板
│   │   └── cleanup.py       # 数据清理
│   │
│   ├── prompt_pipeline.py   # 33 管道提示词引擎
│   ├── prompt_builder.py    # 系统提示词 + 动态上下文构建
│   ├── llm_client.py        # 统一 LLM 调用（流式 + 重试）
│   ├── llm_provider.py      # 多后端抽象（OpenAI/DeepSeek/Ollama/Azure）
│   ├── character_card.py    # 角色卡引擎（V2/V3 + 12 属性）
│   ├── emotion_evolution.py # 情绪演化 + OCEAN 人格每日规则
│   ├── emotion_tracker.py   # 情绪事件追踪
│   ├── emotion_patterns.py  # 情绪关键词/反讽检测
│   ├── relationship.py      # 好感度/信任度/里程碑/冷却锁
│   ├── summary_engine.py    # 三级生命周期摘要引擎
│   ├── memory_provider.py   # 统一记忆接口 + TempMemory
│   ├── memory_curation.py   # 记忆整理（每 8 轮触发）
│   ├── memory_consolidation.py # 记忆合并去重
│   ├── episodic_memory.py   # 情景记忆 + 会话归档
│   ├── vector_store/        # ChromaDB + BM25 混合检索
│   │   ├── __init__.py      # 向量重建
│   │   ├── model.py         # embedding 模型（MiniLM-L12-v2）
│   │   ├── search.py        # MMR 多样性排序
│   │   ├── knowledge.py     # 文档分块向量化 + 画像向量
│   │   ├── memory.py        # 句子/消息向量管理
│   │   ├── bm25.py          # jieba 中文关键词索引
│   │   └── utils.py         # 分句/重要性计算
│   ├── knowledge_graph.py   # 实体关系三元组提取
│   ├── lorebook.py          # 世界书管理
│   ├── profile_builder.py   # 用户画像自动构建
│   ├── conclusion_engine.py # 用户行为模式推理
│   ├── consistency_checker.py # 三层回复一致性（启发式+LLM）
│   ├── correction_memory.py # 纠错记忆
│   ├── feedback_memory.py   # 行为反馈
│   ├── shared_memory.py     # 共同经历检测
│   ├── demand_analyzer.py   # 需求模式分析（per-character）
│   ├── mention_tracker.py   # 提及权重追踪
│   ├── tag_parser.py        # DSML 标签解析
│   ├── mcp_tools.py         # MCP 函数调用工具
│   ├── plugin_loader.py     # 插件系统
│   ├── user_persona.py      # 用户分身管理
│   ├── scheduler.py         # 定时任务调度
│   ├── token_counter.py     # Token 估算
│   ├── security.py          # SQL 注入/路径穿越防护
│   ├── retry.py             # 异常安全辅助
│   └── easter_eggs.py       # 彩蛋
│
├── launcher/                # 桌面壳层（5 个模块）
│   ├── __init__.py          # 主流程（单实例锁 + WebView2 + 托盘）
│   ├── tray.py              # 系统托盘（pystray）
│   ├── lock.py              # PID 文件锁
│   ├── process.py           # 后端进程管理 + 命名管道
│   ├── window.py            # 窗口管理 + 原生通知
│   ├── weather.py           # 天气推送
│   └── _shared.py           # 共享状态
│
├── tests/                   # 450 个测试
├── frontend/                # Vue 3 前端（构建产物）
├── static/                  # 静态资源（备用前端）
├── mcp_servers/             # MCP 服务器
├── plugins/                 # 用户插件
└── data/                    # 运行时数据（自动创建）
```

---

## 技术架构

| 层面 | 技术 |
|------|------|
| 后端 | FastAPI + SQLite WAL + APScheduler |
| 前端 | Vue 3 + Vite + WebView2 |
| 桌面壳 | pywebview + pystray + winotify |
| 向量 | ChromaDB + paraphrase-multilingual-MiniLM-L12-v2 |
| 搜索 | SQLite FTS5 + BM25 (jieba) |
| LLM | OpenAI 兼容接口（DeepSeek / Ollama / Azure） |
| 打包 | PyInstaller |

### 数据库架构

```
主库 (data/vesper.db)        角色库 (data/chats/{name}/chat.db)
├── characters_v2             ├── config
├── config                    ├── chat_history + chat_sessions
├── presets                   ├── memory + memory_importance
├── lorebook                  ├── tiered_summary + death_archive
├── sentence_index            ├── emotion_daily + emotion_log
├── chat_fts (FTS5)           ├── relationship
├── demand_patterns           ├── user_profile + facts
├── shared_moments            ├── knowledge_graph + entities
├── achievements              ├── correction_memory + feedback_memory
├── schedule                  ├── ai_diary + empathy_feedback
├── proactive_*               ├── mention_weights
├── user_activity_stats       ├── user_conclusions + user_vocabulary
├── episodes + episodes_fts   ├── episodes
├── consolidation_log         ├── memory_history
└── ...                       ├── demand_patterns
                              └── ...
```

---

## 开源协议

MIT License
