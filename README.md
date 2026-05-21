# 夕语（Vesper）—— 本地 AI 陪伴桌面应用

夕语是一个开源的本地 AI 桌面聊天应用，使用 Python + Vue 构建，数据完全本地掌控。

> **不想装 Python？** 下载[打包版](https://github.com/kuiti/Vesper/releases)双击即用，零环境依赖。

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（64位） |
| Python | 3.10+（源码版需要） |
| 内存 | 4GB（推荐 8GB） |
| 磁盘 | 500MB（EXE）/ 200MB（源码） |
| 网络 | 需要（AI API + 天气） |
| WebView2 | Windows 10/11 自带 |

---

## 安装方式

### 方式一：EXE 一键运行（推荐新手）

1. 从 [Releases](https://github.com/kuiti/Vesper/releases) 下载 `Vesper.exe`
2. 双击运行
3. 首次启动自动创建数据目录
4. 在设置中配置 API Key
5. 开始聊天

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

> `sentence-transformers` 首次运行会自动下载模型（~100MB），需等待几分钟。

#### 第四步：配置 API Key

用记事本打开 `config.json`，填入你的 API Key：

```json
{
  "api_key": "你的密钥填在这里"
}
```

支持的 API（OpenAI 兼容接口均可）：
- [DeepSeek](https://platform.deepseek.com/) — 便宜好用
- [MiMo](https://100t.xiaomimimo.com/) — 100T token 免费额度
- [OpenAI](https://platform.openai.com/)
- 任何兼容 `/v1/chat/completions` 的接口

#### 第五步：启动

```bash
python launcher.py
```

首次启动会自动创建数据库。窗口弹出后即可使用。

---

## 功能一览

### 智能聊天
- 流式输出，实时显示
- 支持 Markdown 渲染
- 上下文记忆（短期 + 摘要 + 向量检索）

### 智能问候
- **对话尾巴**：根据上次聊天内容问候（"昨晚睡得好吗？"）
- **时间关怀**：7 个时段不同问候风格
- **主动交互**：长时间未聊天时主动关心

### 天气关怀
- 每天 7:00/12:00/19:00 自动推送天气
- 聊天窗口卡片显示
- 系统通知（窗口最小化时）

### 主题系统
- 🌙 **暗色**：深色背景，护眼
- ☀ **亮色**：浅色背景，清爽
- 🌸 **樱花粉**：粉色系，温暖
- ✨ **夕语**：青紫星光，神秘优雅

### 生活工具
- 待办清单
- 提醒事项（7 级智能提醒）
- 笔记（全文搜索）
- 倒计时

### 情感系统
- AI 情感追踪
- 好感度 / 信任度
- 9 种情绪状态

### 数据管理
- 聊天记录导出
- 知识库 RAG 检索
- 用户画像
- 数据备份/恢复

### 系统托盘
- 关闭窗口 → 后台运行
- 双击托盘 → 恢复窗口
- 右键托盘 → 退出

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Enter | 发送消息 |
| Shift+Enter | 换行 |
| 双击消息 | 复制内容 |
| 右键消息 | 上下文菜单 |

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
├── api/                 # API 路由
│   ├── chat.py          # WebSocket 聊天
│   ├── greeting.py      # 智能问候
│   ├── settings.py      # 设置管理
│   ├── emotion.py       # 情感系统
│   ├── relationship.py  # 关系系统
│   └── ...
├── core/                # 核心模块
│   ├── db.py            # SQLite 数据库
│   ├── weather.py       # 天气服务
│   ├── emotion_tracker.py # 情感追踪
│   ├── relationship.py  # 关系管理
│   ├── reminder_ai.py   # 智能提醒
│   └── ...
├── frontend/            # 前端静态文件（构建产物）
└── frontend-src/        # 前端源码（Vue 3 + Vite）
```

---

## 常见问题

**Q: 启动后白屏？**
A: 确保 WebView2 已安装。Windows 10/11 通常自带，如缺失可从[微软官网](https://developer.microsoft.com/microsoft-edge/webview2/)下载。

**Q: API 连接失败？**
A: 检查 API Key 是否正确，网络是否正常。可在设置中测试连接。

**Q: 天气不推送？**
A: 确保已在设置中开启「每日天气推送」，并配置了正确的城市。

**Q: 如何完全退出？**
A: 右键系统托盘图标 → 退出。

**Q: 模型下载失败或很慢？**
A: 设置 HuggingFace 镜像：
```bash
set HF_ENDPOINT=https://hf-mirror.com
```

**Q: 提示 `ModuleNotFoundError`？**
A: 没装依赖或虚拟环境没激活。确认执行了 `pip install -r requirements.txt`。

---

## 更新日志

### v0.3.0（2026-05-21）
- 新增天气关怀系统
- 新增 4 个主题（暗色、亮色、樱花粉、夕语星光）
- 新增对话尾巴问候
- 新增时间关怀增强
- 新增情感追踪 + 关系系统
- 新增系统托盘后台运行
- 新增命名管道单实例检测
- 移除语音功能（将在未来版本重新实现）
- 改名：佐仓 → 夕语

### v0.2.0
- 代码注释完善
- 前端关键修复
- 打包版重建

### v0.1.0
- 初始开源版本

---

## 技术栈

- **后端**：Python 3.10 + FastAPI + SQLite
- **前端**：Vue 3 + Vite
- **桌面**：pywebview (WebView2)
- **AI**：OpenAI 兼容 API
- **向量**：ChromaDB + sentence-transformers

---

## 开源协议

MIT License — 自由使用、修改、分发。

---

## 致谢

夕语从「佐仓」(Sakura) 项目分叉而来，感谢原项目的启发。
