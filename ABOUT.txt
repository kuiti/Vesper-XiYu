Vesper —— 你的本地 AI 桌面伴侣
================================

Vesper 是一个开源的本地 AI 桌面聊天应用。它运行在你的 Windows 电脑上，
无需云端服务（除 AI 模型 API 外），所有对话数据完全由你掌控。


## 特性

  ● 本地运行 —— 自带 Python 运行时，下载即用，无需安装任何环境
  ● 流式对话 —— AI 回复逐句呈现，像真人聊天一样自然
  ● 三层记忆 —— 短期上下文 + 对话摘要 + 向量检索，AI 记得你说过什么
  ● 工具集成 —— 天气查询、IP 定位、联网搜索、待办、笔记、提醒
  ● 深/亮双主题 —— 可自定义配色，聊天气泡风格
  ● 数据可移植 —— 一键导出/导入全部聊天记录
  ● 离线可用 —— 除 AI 模型 API 外，所有功能本地运行


## 技术栈

  ● 后端：Python 3.10 + FastAPI + SQLite + ChromaDB 向量数据库
  ● 前端：Vue 3 + Vite
  ● 桌面壳：pywebview (Edge WebView2)
  ● AI 模型：DeepSeek Chat API（可替换为任何 OpenAI 兼容接口）
  ● 嵌入模型：paraphrase-multilingual-MiniLM-L12-v2（本地运行）


## 快速开始

  1. 下载 Vesper.exe
  2. 双击运行
  3. 在设置中填入 DeepSeek API Key（或任意 OpenAI 兼容 API）
  4. 开始聊天


## 项目结构

  vesper_backend/
  ├── main.py           # FastAPI 入口
  ├── launcher.py       # 桌面启动器
  ├── api/              # 17 个 API 路由模块
  │   ├── chat.py       # WebSocket 流式聊天
  │   ├── history.py    # 聊天记录
  │   ├── settings.py   # 设置管理
  │   ├── memory.py     # 手动记忆
  │   ├── summary.py    # 对话摘要
  │   ├── rag.py        # 向量索引
  │   ├── search.py     # 全文搜索
  │   ├── todos.py      # 待办事项
  │   ├── notes.py      # 笔记
  │   ├── reminders.py  # 提醒
  │   ├── location.py   # 天气/定位
  │   └── ...
  ├── core/
  │   ├── db.py         # SQLite 数据库
  │   ├── vector_store.py # ChromaDB 向量存储
  │   └── prompt_builder.py # 提示词构建
  ├── frontend/         # 前端静态文件
  └── config.json       # 配置文件

  vesper_frontend/
  └── src/
      ├── App.vue       # 主界面
      ├── api.js        # API 封装
      └── components/   # 子组件


## 配置

  编辑 config.json 或通过设置面板修改：

  {
    "api_key": "",           // DeepSeek API Key
    "model_mode": "auto",    // 模型模式
    "personality": {         // AI 性格
      "tone": "冷静",        // 语气：冷静/活泼/温柔/毒舌/傲娇
      "length": "短",        // 回复长度：极短/短/中等/长/详细
      "recall_past": "从不"  // 回忆过去对话
    },
    "custom_system_prompt": ""  // 自定义人设（留空使用默认）
  }


## 开源协议

  MIT License —— 你可以自由使用、修改、分发本项目。
  只需保留原始版权声明。


## 致谢

  Vesper 从 "佐仓" (Sakura) 项目分叉而来，去除了语音模块和所有个人信息，
  全面重命名为 Vesper，保持了一个干净的开源起点。

  本项目使用以下开源技术：
  - FastAPI (MIT)
  - Vue.js (MIT)
  - ChromaDB (Apache 2.0)
  - sentence-transformers (Apache 2.0)
  - pywebview (BSD)
  - DeepSeek API
