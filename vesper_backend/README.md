# 夕语 Vesper — AI 聊天伴侣

夕语是一个开源的本地 AI 桌面聊天应用。运行在你的 Windows 电脑上，**无需云端服务**（除 AI 模型 API 外），所有对话数据完全由你掌控。

> **当前为源码版本**，打包版（EXE 一键运行）待后续发布。

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（64位） |
| Python | 3.10+ |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | ~500MB |
| 网络 | 需要（AI API 调用 + 天气等外部服务） |
| WebView2 | Windows 10/11 已自带 |

---

## 快速开始

### 1. 克隆

```bash
git clone https://github.com/kuiti/Vesper-XiYu.git
cd Vesper-XiYu
```

### 2. 虚拟环境

```bash
python -m venv venv

# PowerShell:
venv\Scripts\activate
# CMD:
venv\Scripts\activate.bat
```

### 3. 安装依赖

```bash
pip install -r requirements-cloud.txt
```

### 4. 获取 API Key

夕语本身免费，但 AI 对话需要调用大模型 API。推荐 **DeepSeek**（国内可用，性价比最高）：

1. 打开 https://platform.deepseek.com/
2. 注册 -> API Keys -> 创建
3. 复制保存

> 也支持 OpenAI、Ollama、Azure 等任何 OpenAI 兼容接口。

### 5. 启动

```bash
python launcher.py
```

首次启动会自动创建 `data/` 目录，在设置面板填入 API Key 即可开始聊天。

---

## 核心特性

### 角色扮演引擎

- **完整角色隔离** —— 每个角色拥有独立的人格（OCEAN 五维）、关系系统（好感度/信任度）、记忆、知识图谱
- **SillyTavern V3 兼容角色卡** —— 导入/导出 character card
- **时间模式** —— 支持真实时间 / 固定时间 / 相对时间 / 无时间四种模式

### 三层记忆系统

- **短期**：最近 50 条消息上下文
- **中期**：三级生命周期摘要（10/50/100 条消息触发，自动压缩）
- **长期**：ChromaDB 向量语义检索 + BM25 关键词回退
- **记忆分类** —— FACT / EMOTION / PREFERENCE / EVENT / HABIT / RELATIONSHIP
- **TempMemory 管道** —— 对话暂存 → 后台 LLM 批量巩固为正式记忆

### 情感与关系系统

- **12 种情绪状态**：狂喜 / 开心 / 满足 / 平静 / 谨慎 / 冷漠 / 烦躁 / 受伤 / 不信任 / 敌意 / 被背叛 / 怨恨
- **双轨关系**：好感度（-100~100） + 信任度（-100~100），默认 30
- **性格演化**：5+ 条每日演化规则，根据对话内容持续调整
- **情感趋势**：14 天情绪分数曲线

### 提示词管道系统

33 个注册 Pipeline 组件，按职责分为三层：

- **System 层**：身份定义、情境设定、行为规则
- **Dynamic 层**：用户画像、记忆上下文、知识图谱、关系状态
- **Instruction 层**：对话约束、格式指令、工具定义

### 知识管理

- **知识库 RAG** —— 上传文档自动分块向量化，对话中自然引用
- **知识图谱** —— 自动从对话中提取实体关系三元组，跨角色隔离
- **纠错记忆** —— AI 记住用户的纠正反馈，避免重复犯错

### 主动交互

- **多条件触发**：活跃时段、长时未聊、连续负面情绪、目标跟进
- **每日问候**：7 个时段不同风格，根据聊天历史个性化
- **小惊喜**：随机触发暖心冷知识/短诗

### 生活工具

| 功能 | 说明 |
|------|------|
| 倒计时 | 实时更新天数 |
| 习惯追踪 | 日常打卡 |
| 目标追踪 | 长期目标跟进 |
| 成就系统 | 连续天数/里程碑 |

### 数据管理

- 导出/导入备份（JSON）
- 云端加密同步（WebDAV）
- 聊天记录全文搜索（FTS5）
- 按时间范围清理

---

## 项目结构

```
├── launcher.py              # 桌面启动器（系统托盘 + WebView2）
├── main.py                  # FastAPI 入口
├── cloud_server.py          # 云端部署入口（无 GUI）
├── config.json              # 默认配置
├── Vesper.spec              # PyInstaller 打包配置
├── requirements-cloud.txt   # Python 依赖
├── pytest.ini               # 测试配置
├── api/                     # API 路由
│   ├── chat_session.py      # WebSocket 流式聊天（核心）
│   ├── characters.py        # 角色卡管理
│   ├── greeting.py          # 智能问候 + 主动交互
│   ├── sentiment.py         # 情感分析
│   ├── proactive.py         # 主动触发引擎
│   ├── emotion.py           # 情感趋势 API
│   ├── relationship.py      # 关系系统 API
│   ├── memory.py            # 记忆管理 API
│   ├── knowledge.py         # 知识库 CRUD
│   ├── settings.py          # 设置 API
│   └── ...                  # 50+ 端点模块
├── core/                    # 核心引擎
│   ├── db/                  # SQLite 连接管理 + schema（主库+角色库）
│   │   ├── __init__.py      # 建表、迁移、get_chat_conn
│   │   ├── chat.py          # 聊天记录 CRUD + FTS5
│   │   ├── config.py        # 配置读写（per-character）
│   │   ├── entity.py        # 实体+知识图谱+记忆重要性
│   │   ├── emotion.py       # 情绪日志+活跃统计
│   │   ├── memory.py        # memory 表 CRUD
│   │   ├── misc.py          # 文档管理
│   │   ├── summary.py       # 摘要表 CRUD
│   │   ├── tools.py         # 工具调用记录
│   │   ├── cleanup.py       # 数据清理
│   │   └── goal.py          # 目标表
│   ├── llm_client.py        # 统一 LLM API 调用
│   ├── llm_provider.py      # 多后端抽象层（OpenAI/Ollama/DeepSeek/Azure）
│   ├── prompt_pipeline.py   # 33 管道提示词引擎
│   ├── prompt_builder.py    # 系统提示词构建
│   ├── memory_provider.py   # 统一记忆接口 + TempMemory
│   ├── emotion_evolution.py # 情绪演化 + OCEAN 人格
│   ├── relationship.py      # 好感度/信任度 + 里程碑
│   ├── character_card.py    # 角色卡引擎（V2/V3）
│   ├── vector_store/        # ChromaDB + BM25 语义检索
│   │   ├── model.py         # embedding 模型加载
│   │   ├── search.py        # 混合搜索 + MMR
│   │   ├── knowledge.py     # 文档分块 + 向量化
│   │   ├── memory.py        # 记忆向量管理
│   │   ├── bm25.py          # BM25 中文关键词索引
│   │   └── utils.py         # 工具函数
│   ├── knowledge_graph.py   # 实体关系三元组提取
│   ├── consistency_checker.py # 三层回复一致性检查
│   ├── correction_memory.py # 纠错记忆
│   ├── feedback_memory.py   # 行为反馈
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── episodic_memory.py   # 情景记忆管理
│   ├── summary_engine.py    # 三级生命周期摘要
│   ├── tag_parser.py        # DSML 标签解析
│   ├── mcp_tools.py         # MCP 工具注册表
│   ├── security.py          # SQL 注入/路径穿越防护
│   ├── retry.py             # 异常安全辅助
│   ├── lorebook.py          # lorebook 管理
│   ├── profile_builder.py   # 用户画像构建
│   ├── conclusion_engine.py # 用户行为结论分析
│   ├── mention_tracker.py   # 提及权重追踪
│   ├── easter_eggs.py       # 彩蛋检测
│   ├── shared_memory.py     # 共同经历检测
│   ├── memory_curation.py   # 记忆整理
│   ├── memory_consolidation.py # 记忆合并
│   ├── goal_tracker.py      # 目标追踪
│   ├── quick_reply.py       # 快捷回复
│   ├── token_counter.py     # token 计数
│   ├── story_arc.py         # 故事弧
│   ├── plugin_loader.py     # 插件加载器
│   ├── user_persona.py      # 用户分身管理
│   ├── tts/                 # TTS 适配器（多引擎）
│   └── ...                  # 80+ 核心模块
├── launcher/                # 桌面启动器模块
│   ├── __init__.py          # 启动逻辑（单实例+WebView2+系统托盘）
│   ├── process.py           # 进程管理
│   ├── window.py            # 窗口管理
│   ├── tray.py              # 系统托盘
│   ├── lock.py              # 互斥锁
│   ├── weather.py           # 天气推送
│   └── _shared.py           # 共享变量
├── frontend/                # Vue 3 前端构建产物（当前 UI）
├── frontend_old/            # 旧版前端
├── static/                  # 静态资源（备用前端）
├── mcp_servers/             # MCP 服务器
│   ├── sqlite_server.py     # 数据库 MCP
│   ├── screen_server.py     # 截图 MCP
│   └── web_fetch.py         # 网页抓取 MCP
├── plugins/                 # 插件目录
│   └── example.py           # 插件示例
├── tests/                   # pytest 测试（366+ 测试用例）
└── data/                    # 运行后自动创建（DB/向量/日志）
```

---

## 技术架构

| 层面 | 技术栈 |
|------|--------|
| 后端 | FastAPI + SQLite WAL + APScheduler |
| 前端 | Vue 3 + Vite + WebView2 |
| 向量存储 | ChromaDB + paraphrase-multilingual-MiniLM-L12-v2 |
| 全文搜索 | SQLite FTS5 |
| LLM 适配 | OpenAI / DeepSeek / Ollama / Azure |
| 打包 | PyInstaller |

### 核心设计理念

- **完全本地优先** —— 所有数据存本地，API Key 自行管理
- **角色即个体** —— 每个角色有独立人格、记忆、关系，零串扰
- **渐进式记忆** —— TempMemory → 批量巩固 → 分类存储 → 语义检索
- **三层管道** —— System/Dynamic/Instruction 分层注入，清晰可扩展

---

## 开源协议

MIT License
