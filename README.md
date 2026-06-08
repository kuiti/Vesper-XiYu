# 夕语 (Vesper) — 有感情的 AI 伴侣

> v1.0.0

**长期记忆 · 情感演化 · 角色扮演 · 本地隐私优先**

---

## 简介

夕语是一个运行在本地电脑上的 AI 桌面伴侣。所有数据存在你自己电脑上，不上传任何服务器。

**核心理念：** 长期记忆 + 情感 + 人设 + 陪伴 + 功能性 + 温度感

---

## 功能

- 💬 **智能对话** — 支持 DeepSeek / OpenAI / Ollama 等多种后端
- 🧠 **长期记忆** — 向量语义搜索 + 关键词回退，记住你们的过去
- 😊 **情感系统** — AI 有情绪波动，会因互动而改变
- 👤 **角色卡** — 切换不同人设，支持 SillyTavern 兼容格式
- 📝 **待办·笔记·提醒·日程** — 生活管理工具
- 📊 **统计·报告·日记** — AI 自动生成
- 🎮 **小游戏** — 五子棋、2048、扫雷、贪吃蛇
- 🎤 **语音输入 / 朗读** — TTS / STT
- ☁️ **云端同步** — 加密备份到 WebDAV

---

## 快速开始

### 打包版（推荐）

下载 `Vesper_v1.0.0_windows_x64.zip`，解压后双击 `Vesper/Vesper.exe` 即可。

首次使用：
1. 在设置页配置 API Key（支持 DeepSeek / OpenAI / Ollama）
2. 如需向量搜索，在设置页点击「安装向量引擎」

### 源码运行

```bash
# 后端
cd vesper_backend
pip install -r requirements.txt
python main.py

# 前端（需先装 Node.js）
cd frontend-src
npm install
npm run build
# 或开发模式: npm run dev
```

---

## 技术栈

- **后端：** Python 3.10+ / FastAPI / SQLite / ChromaDB
- **前端：** Vue 3 / Vite
- **桌面壳：** pywebview (WebView2)
- **打包：** PyInstaller

---

## 更新日志

### v1.0.0 (2026-06-08)
- ✨ 全新架构：5-in-1 后端融合（角色卡 + 多后端 + 向量记忆 + 提示词管道 + 安全层）
- 🔧 修复 40+ 个 bug（聊天删除、重置、缓存同步等）
- 🎨 夕语青紫主题
- 🖼️ 默认双头像
- 📦 打包版：285MB（不含 torch）

### v0.6.0 (2026-05-26)
- 天气关怀、主题系统增强

### v0.5.0 (2026-05-25)
- 情感演化、目标追踪

---

## License

MIT
