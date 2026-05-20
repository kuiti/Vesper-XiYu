# Vesper —— 本地 AI 陪伴桌面应用

Vesper 是一个开源的本地 AI 桌面聊天应用，使用 Python + Vue 构建，数据完全本地掌控。

## 环境要求

- **Windows 10/11**（macOS 也可运行）
- **Python 3.10+** → [官网下载](https://www.python.org/downloads/)
- **Edge WebView2 Runtime** → Win11 已内置，Win10 点此[安装](https://developer.microsoft.com/microsoft-edge/webview2/)
- **Git** → [下载](https://git-scm.com/download/win)

## 安装运行（保姆级）

### 第一步：克隆项目

打开终端（PowerShell 或 CMD），执行：

```bash
git clone https://github.com/kuiti/Vesper.git
cd Vesper
```

### 第二步：创建虚拟环境

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

### 第三步：安装依赖

```bash
pip install -r requirements.txt
```

> `sentence-transformers` 首次运行会自动下载模型（~100MB），需等待几分钟。

### 第四步：配置 API Key

用记事本打开 `config.json`，填入你的 API Key：

```json
{
  "api_key": "你的密钥填在这里",
  ...
}
```

支持的 API（OpenAI 兼容接口均可）：
- [DeepSeek](https://platform.deepseek.com/) — 便宜好用
- [MiMo](https://100t.xiaomimimo.com/) — 100T token 免费额度
- [OpenAI](https://platform.openai.com/)
- 任何兼容 `/v1/chat/completions` 的接口

### 第五步：启动

```bash
python launcher.py
```

首次启动会自动创建数据库、下载模型。窗口弹出后即可使用。

> 如果窗口没出来，会自动用浏览器打开 `http://127.0.0.1:XXXX/`。

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 流式聊天 | AI 回复逐句呈现，支持 Markdown |
| 三层记忆 | 短期上下文 + 对话摘要 + 向量检索 |
| 待办事项 | 创建、管理待办 |
| 笔记 | 记录笔记，支持全文搜索 |
| 倒计时 | 事件倒计时 |
| 提醒 | 定时提醒 |
| 联网搜索 | DuckDuckGo 搜索 |
| 天气 | 高德天气（需配置 amap_key） |
| 数据导出 | 一键备份/恢复全部数据 |
| 暗色主题 | 可自定义配色 |

---

## 从源码构建前端

如果你修改了前端代码（`frontend-src/`），需要重新构建：

```bash
cd frontend-src
npm install
npm run build
```

构建产物在 `dist/`，将其内容复制到 `frontend/` 替换即可。

---

## 项目结构

```
vesper_backend/
├── launcher.py          # 桌面启动器（入口）
├── main.py              # FastAPI 后端
├── config.json          # 用户配置
├── requirements.txt     # Python 依赖列表
├── README.md            # 本文件
├── api/                 # API 路由（17个模块）
│   ├── chat.py          # WebSocket 聊天
│   ├── memory.py        # 记忆系统
│   ├── rag.py           # 向量检索
│   └── ...
├── core/                # 核心模块
│   ├── db.py            # SQLite 数据库
│   ├── prompt_builder.py # 提示词构建
│   └── vector_store.py  # ChromaDB 向量存储
├── frontend/            # 前端静态文件（构建产物）
└── frontend-src/        # 前端源码（Vue 3 + Vite）
```

---

## 常见问题

**Q: 提示 `ModuleNotFoundError: No module named 'xxx'`**

A: 没装依赖或虚拟环境没激活。确认执行了 `pip install -r requirements.txt`。

**Q: 发送消息后没回复**

A: 检查 `config.json` 中 `api_key` 是否正确，网络是否通畅。

**Q: 模型下载失败或很慢**

A: 设置 HuggingFace 镜像：
```bash
set HF_ENDPOINT=https://hf-mirror.com
```

**Q: WebView2 报错**

A: Win10 需要手动安装 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。

**Q: 端口被占用**

A: 程序自动分配空闲端口，一般不会冲突。

---

## 开源协议

MIT License — 自由使用、修改、分发。
