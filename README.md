# 夕语（Vesper）—— 你的本地 AI 桌面伴侣

夕语是一个开源的本地 AI 桌面聊天应用。运行在你的 Windows 电脑上，**无需云端服务**（除 AI 模型 API 外），所有对话数据完全由你掌控。

> **v1.0.0 已发布** — 全新架构，全面升级。**不想装 Python？** 下载[打包版](#方式一exe-一键运行推荐新手)双击即用，零环境依赖。

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（64位） |
| Python | 3.10+（仅源码版需要） |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | ~1GB（EXE）/ ~500MB（源码版） |
| 网络 | 需要（AI API 调用 + 天气等外部服务） |
| WebView2 | Windows 10/11 已自带，Win7 需手动安装 |

---

## 安装方式

### 方式一：EXE 一键运行（推荐新手）

#### 第一步：下载

从 [Releases](https://github.com/kuiti/Vesper-XiYu/releases) 下载最新版 `Vesper_v1.0.0_windows_x64.zip`。

#### 第二步：解压

解压到任意目录（建议 `D:\Vesper\` 或桌面），解压后结构：

```
Vesper/
├── Vesper.exe        -- 双击启动
├── _internal/        -- 程序依赖（不要动）
└── data/             -- 运行后自动创建
```

#### 第三步：获取 API Key

夕语本身免费且离线运行，但 AI 对话需要调用大模型 API。推荐 **DeepSeek**（国内可用，性价比最高）：

1. 打开 https://platform.deepseek.com/
2. 注册并登录
3. 左侧菜单「API Keys」->「创建 API Key」
4. 复制保存（**只显示一次！**）

> 也支持 OpenAI、Ollama 本地模型等任何 OpenAI 兼容接口。

#### 第四步：配置

启动 Vesper.exe，在设置面板填入 API Key，或首次引导时直接填写。

#### 第五步：开始使用

双击 `Vesper.exe`。

- 首次启动会自动创建 `data/` 目录（聊天记录、数据库等）
- 窗口出现后即可开始聊天

---

### 方式二：源码运行（推荐开发者）

#### 第一步：克隆项目

```bash
git clone https://github.com/kuiti/Vesper-XiYu.git
cd Vesper-XiYu
```

#### 第二步：创建虚拟环境

```bash
python -m venv venv
```

激活虚拟环境：

```bash
# Windows PowerShell:
venv\Scripts\activate

# Windows CMD:
venv\Scripts\activate.bat
```

#### 第三步：安装依赖

```bash
pip install -r requirements.txt
```

#### 第四步：启动

```bash
python launcher.py
```

#### 构建前端（可选，如需修改 UI）

```bash
cd frontend-src
npm install
npm run build
```

---

## 功能一览

### 智能聊天

- **流式输出** —— AI 回复逐字呈现，支持 Markdown 渲染
- **三层记忆系统**
  - 短期：最近 35 条消息上下文
  - 中期：三级生命周期摘要（10/50/100 条触发）
  - 长期：向量语义检索（ChromaDB），关键词回退
- **多后端支持** —— DeepSeek / OpenAI / Ollama 一键切换
- **角色卡系统** —— 切换不同人设，支持 SillyTavern 兼容格式

### 问候与主动交互

- **对话尾巴**：根据上次聊天内容自然问候
- **时间关怀**：7 个时段不同问候风格
- **主动交互**：多条件触发（连续负面情绪、长时未聊、目标跟进、提醒到期等）
- **深夜免打扰**：23:00-7:00 不主动推送

### 天气关怀

- 每天 7:00 / 12:00 / 19:00 自动推送天气提醒
- 数据源：Open-Meteo（免费，无需 API Key）+ 高德天气备用

### 情感与关系系统

- **情感追踪**：每日情绪分数累计，14 天趋势曲线
- **好感度 / 信任度**：双轨制关系系统
- **9 种情绪状态**：狂喜/开心/满足/平静/谨慎/冷漠/烦躁/受伤/不信任
- **性格演化**：5 条每日演化规则

### 主题系统

| 主题 | 风格 |
|------|------|
| 暗色 | 深蓝灰，护眼 |
| 亮色 | 象牙白暖色调 |
| 樱花粉 | 粉蓝暖色调 |
| 夕语 | 青紫星空（默认） |

### 生活工具

- **待办清单** —— 添加/勾选/删除
- **提醒事项** —— 7 级优先级，AI 温柔提醒文案
- **笔记** —— 全文搜索
- **倒计时** —— 实时更新天数
- **日程管理** —— 日历视图
- **目标追踪** —— 长期目标跟进

### AI 记忆管理

- **用户画像** —— AI 自动提取你的昵称、爱好、习惯
- **记忆保险箱** —— 查看/删除 AI 记住的关于你的信息
- **知识库 RAG** —— 上传文档，本地向量索引
- **知识图谱** —— 实体关系提取
- **对话摘要** —— 三级摘要系统，可查看/重置

### 数据管理

- **导出备份** —— 一键导出所有数据为 JSON
- **导入恢复** —— 从备份恢复全部数据
- **云端同步** —— 加密备份到 WebDAV 服务器
- **聊天管理** —— 按时间范围删除、自动清理
- **全文搜索** —— 搜索历史聊天记录（FTS5）

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Enter | 发送消息 |
| Shift + Enter | 换行 |
| Escape | 关闭弹窗/面板 |
| 右键消息 | 上下文菜单 |

---

## 常见问题

**Q: 启动后白屏？**
A: Windows 10/11 自带 WebView2。如缺失可从[微软官网](https://developer.microsoft.com/microsoft-edge/webview2/)下载安装。

**Q: API 连接失败？**
A: 检查 API Key 是否正确，网络是否正常。在设置面板可点击「测试连接」。

**Q: AI 回复很慢？**
A: DeepSeek 免费版有速率限制。改用付费 API 或切换 API 提供商。

**Q: 聊天记录在哪里？**
A: `data/chat_history.db`（SQLite 格式），可用任何 SQLite 工具查看。

**Q: 如何备份？**
A: 方法一：复制整个 Vesper 文件夹。方法二：设置面板 ->「导出备份」。

**Q: 如何升级？**
A: 下载新版本 zip，解压覆盖旧文件。`data/` 目录不会被覆盖。

**Q: 向量模型下载失败？**
A: 设置面板点击「安装向量引擎」，代码已默认使用国内镜像（hf-mirror.com）。

**Q: 提示 `ModuleNotFoundError`？**
A: 源码版需确认虚拟环境已激活且执行了 `pip install -r requirements.txt`。打包版不存在此问题。

---

## 项目结构

```
vesper_backend/              # 后端
├── launcher.py              # 桌面启动器（系统托盘 + 单实例 + WebView2）
├── main.py                  # FastAPI 入口 + 路由注册
├── Vesper.spec              # PyInstaller 打包配置
├── requirements.txt         # Python 依赖
├── api/                     # API 路由模块
│   ├── chat.py              # WebSocket 流式聊天
│   ├── greeting.py          # 智能问候 + 主动交互
│   ├── sentiment.py         # 情感分析
│   ├── proactive.py         # 主动交互触发引擎
│   ├── characters.py        # 角色卡管理
│   └── ...
├── core/                    # 核心模块
│   ├── db.py                # SQLite 数据库（WAL 模式 + FTS5）
│   ├── llm_client.py        # 统一 LLM API 调用
│   ├── llm_provider.py      # 多后端抽象层
│   ├── prompt_pipeline.py   # 提示词管道引擎
│   ├── summary_engine.py    # 三级生命周期摘要引擎
│   ├── emotion_evolution.py # 情绪演化引擎
│   ├── relationship.py      # 好感度/信任度关系系统
│   ├── vector_store.py      # ChromaDB 向量存储
│   ├── character_card.py    # 角色卡引擎
│   └── ...
├── frontend/                # 前端静态文件（构建产物）
├── frontend-src/            # 前端源码（Vue 3 + Vite）
└── data/                    # 运行后自动创建
```

---

## 更新日志

### v1.0.0 (2026-06-08) —— 全新架构

- **5-in-1 后端融合**：角色卡系统（SillyTavern V3 兼容）、多 LLM 后端抽象（OpenAI/Ollama）、向量记忆（ChromaDB + 语义搜索）、提示词管道引擎（20 种 pipe）、安全层（SSRF/SQL注入防护）
- **全新前端面板**：角色卡管理、用户画像、云端同步
- **修复 40+ 个 bug**：聊天删除级联清理、重置缓存同步、config 读写一致性、路由前缀统一等
- **向量模型镜像**：默认国内镜像（hf-mirror.com），解决下载失败问题
- **默认双头像**：内置 AI 头像 + 用户头像

### v0.6.0 (2026-05-26)

- AI 设定背景板，联网搜索二选一，天气三级容错
- 修复 10+ 项 bug

### v0.5.0 (2026-05-25)

- 24 项 Bug 修复，好感度/信任度双向牵制
- 性格演化门槛降低，主动消息融入天气和位置

### v0.4.0 (2026-05-23)

- 86 项 Bug 修复，全量代码审计

### v0.3.0

- 首次对外发布，天气关怀 + 4 主题 + 系统托盘 + 情感追踪

---

## 开源协议

MIT License —— 自由使用、修改、分发。
