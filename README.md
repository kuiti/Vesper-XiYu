# 夕语（Vesper）—— 你的本地 AI 桌面伴侣

夕语是一个开源的本地 AI 桌面聊天应用。运行在你的 Windows 电脑上，**无需云端服务**（除 AI 模型 API 外），所有对话数据完全由你掌控。

> **不想装 Python？** 下载[打包版](#方式一exe-一键运行推荐新手)双击即用，零环境依赖。

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（64位） |
| Python | 3.10+（仅源码版需要） |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | ~2GB（EXE 含模型）/ ~500MB（源码版） |
| 网络 | 需要（AI API 调用 + 天气等外部服务） |
| WebView2 | Windows 10/11 已自带，Win7 需手动安装 |

---

## 安装方式

### 方式一：EXE 一键运行（推荐新手）

#### 第一步：下载

从 [Releases](https://github.com/kuiti/Vesper/releases) 下载最新版 `Vesper_v0.4.0_windows_x64.zip`。

#### 第二步：解压

解压到任意目录（建议 `D:\Vesper\` 或桌面），解压后结构：

```
Vesper/
├── Vesper.exe        ← 双击启动
├── _internal/        ← 程序依赖（不要动）
├── config.json       ← 配置文件
└── frontend/         ← 界面文件
```

#### 第三步：获取 API Key

夕语本身免费且离线运行，但 AI 对话需要调用大模型 API。推荐 **DeepSeek**（国内可用，性价比最高）：

1. 打开 https://platform.deepseek.com/
2. 注册并登录
3. 左侧菜单「API Keys」→「创建 API Key」
4. 复制保存（**只显示一次！**）

> 也支持 OpenAI、Ollama 本地模型、MiMo 等任何 OpenAI 兼容接口。

#### 第四步：配置

用记事本打开 `config.json`，找到：

```json
"api_key": "",
```

填入你的 API Key：

```json
"api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
```

#### 第五步：双击启动

双击 `Vesper.exe`。

- 首次启动会自动创建 `data/` 目录（聊天记录、数据库、头像）
- 首次启动也会创建 `data/webview2_data/`（Edge WebView2 缓存）
- 窗口出现后即可开始聊天

---

### 方式二：源码运行（推荐开发者）

#### 第一步：克隆项目

```bash
git clone https://github.com/kuiti/Vesper.git
cd Vesper
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

> `sentence-transformers` 首次运行会自动下载嵌入模型（~100MB），需要几分钟。如果下载慢，设置镜像：
> ```bash
> set HF_ENDPOINT=https://hf-mirror.com
> ```

#### 第四步：配置 API Key

用记事本打开 `config.json`，填入 API Key：

```json
{
  "api_key": "你的密钥填在这里"
}
```

#### 第五步：启动

```bash
python launcher.py
```

---

## 功能一览

### 智能聊天
- **流式输出** —— AI 回复逐句呈现，支持 Markdown 渲染
- **三层记忆系统**
  - 短期：最近 35 条消息上下文
  - 中期：三级生命周期摘要（10/50/100 条触发）
  - 长期：ChromaDB 向量语义检索
- **重生成** —— 右键消息可重新生成 AI 回复
- **收藏** —— 右键消息可收藏/取消收藏

### 智能问候 & 主动交互
- **对话尾巴**：根据上次聊天内容自然问候（"昨晚睡得好吗？"）
- **时间关怀**：7 个时段不同问候风格
- **主动交互**：多条件触发（连续负面情绪、长时未聊、目标跟进、提醒到期等）
- **深夜免打扰**：23:00-7:00 不主动推送

### 天气关怀
- 每天 7:00 / 12:00 / 19:00 自动推送
- 聊天窗口卡片显示（温度、体感、湿度、风力、穿衣建议）
- 系统通知（窗口最小化时通过托盘弹出）
- 数据源：Open-Meteo（免费，无需 API Key）+ 高德天气备用

### 情感 & 关系系统
- **AI 情感追踪**：每日情绪分数累计，14 天趋势曲线
- **好感度 / 信任度**：双轨制关系系统
- **9 种 AI 情绪状态**：狂喜/开心/满足/平静/谨慎/冷漠/烦躁/受伤/不信任
- **关系模式**：快速模式 / 长期模式
- **性格演化**：5 条每日演化规则（乐观度/表达欲/主动性/调皮度）

### 主题系统
| 主题 | 风格 | 适合 |
|------|------|------|
| 🌙 暗色 | 深蓝灰，护眼 | 夜间使用 |
| ☀ 亮色 | 象牙白暖色调 | 白天使用 |
| 🌸 樱花粉 | 粉蓝暖色调 | 温暖心情 |
| ✨ 夕语 | 青紫星空 | 默认推荐 |

### 生活工具
- **待办清单** —— 添加/勾选/删除
- **提醒事项** —— 7 级优先级，AI 温柔提醒文案
- **笔记** —— 全文搜索
- **倒计时** —— 实时更新天数
- **收藏消息** —— 重要对话一键收藏

### AI 记忆管理
- **用户画像** —— AI 自动提取你的昵称、爱好、习惯
- **记忆保险箱** —— 查看/删除 AI 记住的关于你的信息
- **知识库 RAG** —— 上传 .txt/.md/.pdf，本地向量索引
- **对话摘要** —— 三级摘要系统，可查看/重置

### 数据管理
- **导出备份** —— 一键导出所有数据为 JSON
- **导入恢复** —— 从备份恢复全部数据
- **聊天管理** —— 按时间范围删除、自动清理
- **全文搜索** —— 搜索历史聊天记录

### 系统托盘
- 关闭窗口 → 最小化到托盘，后台继续运行
- 双击托盘图标 → 恢复窗口
- 右键托盘 → 显示窗口 / 退出
- 再次启动 → 自动激活已有窗口（单实例）

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Enter | 发送消息 |
| Shift + Enter | 换行 |
| Ctrl + 1~9 | 切换面板 |
| Escape | 关闭弹窗/面板 |
| 右键消息 | 上下文菜单 |

---

## 配置详解

所有配置可在设置面板（齿轮图标）修改，也可直接编辑 `config.json`：

### 基础配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | AI 模型 API Key | 空 |
| `api_base_url` | API 地址 | `https://api.deepseek.com/v1` |
| `api_model` | 模型名称 | `deepseek-chat` |
| `ai_name` | AI 名字 | Vesper |
| `user_name` | 你的名字 | （自定义） |

### AI 人设

| 配置项 | 选项 | 说明 |
|--------|------|------|
| `personality.tone` | 冷静/活泼/温柔/毒舌/傲娇 | AI 语气风格 |
| `personality.length` | 极短/短/中等/长/详细 | 回复长度 |
| `personality.recall_past` | 从不/偶尔/经常/总是 | 回忆过去对话的频率 |
| `personality.allow_emotion` | true/false | 是否在回答中表达情绪 |
| `custom_system_prompt` | 任意文本 | 自定义人设提示词 |

### 更换 API 提供商

**OpenAI:**
```json
"api_base_url": "https://api.openai.com/v1",
"api_model": "gpt-4o",
```

**Ollama 本地模型（无需 API Key）:**
```json
"api_base_url": "http://localhost:11434/v1",
"api_model": "qwen2.5:7b",
"api_key": "ollama",
```

**MiMo（100T Token 免费额度）:**
```json
"api_base_url": "https://100t.xiaomimimo.com/v1",
"api_key": "你的 MiMo Token",
```

---

## 常见问题

**Q: 启动后白屏？**
A: Windows 10/11 自带 WebView2。如缺失可从[微软官网](https://developer.microsoft.com/microsoft-edge/webview2/)下载安装。

**Q: API 连接失败？**
A: 检查 `api_key` 是否正确，网络是否正常。在设置面板可点击「测试连接」。

**Q: AI 回复很慢？**
A: DeepSeek 免费版有速率限制。改用付费 API 或切换 API 提供商。

**Q: 聊天记录在哪里？**
A: `data/chat_history.db`（SQLite 格式），可用任何 SQLite 工具查看。

**Q: 如何备份？**
A: 方法一：复制整个 Vesper 文件夹。方法二：设置面板 →「导出备份」。

**Q: 如何升级？**
A: 下载新版本 zip，解压覆盖旧文件。`data/` 目录（聊天记录）不会被覆盖。

**Q: 如何完全退出？**
A: 右键系统托盘图标 → 退出。直接关窗口只是最小化到托盘。

**Q: 向量模型下载失败？**
A: 设置 HuggingFace 镜像后重启：
```bash
set HF_ENDPOINT=https://hf-mirror.com
```

**Q: 提示 `ModuleNotFoundError`？**
A: 源码版需确认虚拟环境已激活且执行了 `pip install -r requirements.txt`。打包版不存在此问题。

**Q: 支持 macOS/Linux 吗？**
A: 当前仅支持 Windows。macOS/Linux 用户可用源码版运行（需自行适配 WebView）。

---

## 从源码构建前端

如果你修改了前端源码（`vesper_frontend/`），需要重新构建：

```bash
cd vesper_frontend
npm install
npm run build
```

构建产物在 `dist/`，复制到 `vesper_backend/frontend/` 替换即可。

### 打包 EXE

```bash
cd vesper_backend
pip install pyinstaller
python -m PyInstaller Vesper.spec
```

输出在 `dist/Vesper/` 目录。

---

## 项目结构

```
vesper_backend/              # 后端
├── launcher.py              # 桌面启动器（系统托盘 + 单实例 + WebView2）
├── main.py                  # FastAPI 入口 + 路由注册
├── Vesper.spec              # PyInstaller 打包配置
├── config.json              # 用户配置模板
├── requirements.txt         # Python 依赖
├── api/                     # 38 个 API 路由模块
│   ├── chat.py              # WebSocket 流式聊天（核心）
│   ├── greeting.py          # 智能问候 + 主动交互
│   ├── sentiment.py         # 情感分析
│   ├── proactive.py         # 主动交互触发引擎
│   ├── intent.py            # 意图识别（天气/搜索/定位）
│   └── ...
├── core/                    # 18 个核心模块
│   ├── db.py                # SQLite 数据库（WAL 模式 + FTS5）
│   ├── llm_client.py        # 统一 LLM API 调用（重试 + JSON 解析）
│   ├── prompt_builder.py    # 提示词构建
│   ├── summary_engine.py    # 三级生命周期摘要引擎
│   ├── emotion_evolution.py # 情绪演化引擎
│   ├── relationship.py      # 好感度/信任度关系状态机
│   ├── vector_store.py      # ChromaDB 向量存储
│   └── ...
├── frontend/                # 前端静态文件（构建产物）
├── frontend-src/ → ../vesper_frontend/  # 前端源码（Vue 3）
└── data/                    # 运行后自动创建（聊天记录等）
```

---

## 更新日志

### v0.4.0（2026-05-23）—— 重大稳定性更新

- **86 项 Bug 修复**来自母项目"佐仓"的全量代码审计
- 修复 3 项致命 Bug：空 key 删全表、recall_past 设置无效、MemoryVault 截断误删
- 修复 14 项高危 Bug：asyncio 阻塞、主动消息刷屏、竞态条件、模板崩溃、前端内存泄漏等
- 修复 24 项中危 Bug：状态机卡死、null 守卫、TOCTOU 竞态、0 值判断、请求取消等
- 全量审计 89 个源文件（后端 57 + 前端 32），代码版本统一为 5.0.0
- LLM 调用增加 3 次重试机制 + JSON 解析增强
- PyInstaller 打包配置完善（50+ 隐式导入）

详见 [RELEASE_v0.4.0.md](RELEASE_v0.4.0.md)

### v0.3.1
- 首次对外发布
- 天气关怀系统 + 4 主题 + 系统托盘 + 情感追踪
- 语音功能暂移除

### v0.2.0
- 代码注释完善 + 前端关键修复

### v0.1.0
- 初始开源版本

---

## 开源协议

MIT License —— 自由使用、修改、分发。保留原始版权声明即可。

---

## 致谢

夕语从「佐仓」(Sakura) 项目脱敏而来。

本项目使用以下开源技术：
- [FastAPI](https://github.com/tiangolo/fastapi) (MIT)
- [Vue.js](https://github.com/vuejs/core) (MIT)
- [ChromaDB](https://github.com/chroma-core/chroma) (Apache 2.0)
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers) (Apache 2.0)
- [pywebview](https://github.com/r0x0r/pywebview) (BSD)
- [pystray](https://github.com/moses-palmer/pystray) (LGPL)
- [DeepSeek](https://platform.deepseek.com/)
- [Open-Meteo](https://open-meteo.com/) — 免费天气 API
