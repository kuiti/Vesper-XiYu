# Vesper 打包版说明

面向**没有 Python 环境的普通用户**，下载解压双击即可运行。

## 下载

前往 [GitHub Releases](../../releases) 下载 `Vesper_vX.X.X_windows_x64.zip`。

## 使用方式

1. 解压到任意文件夹
2. 双击 `Vesper.exe`
3. 在设置中填入 API Key
4. 开始聊天

## 优势

| 优势 | 说明 |
|------|------|
| **零环境依赖** | 无需安装 Python、Node.js、任何运行时 |
| **解压即用** | 下载 zip → 解压 → 双击 exe，三步完成 |
| **自包含** | Python 运行时、所有依赖包、前端文件全部内置 |
| **快速启动** | --onedir 模式，不解压到临时目录，冷启动更快 |
| **跨机携带** | 整个文件夹复制到 U 盘即可在任意 Windows 电脑运行 |
| **无需网络** | 仅 AI 对话需 API 网络，软件本身完全离线 |
| **自动回退** | 如果 WebView2 不可用，自动打开系统浏览器 |

## 缺陷与限制

| 缺陷 | 说明 |
|------|------|
| **体积大** | 约 900MB（含 PyTorch、ChromaDB、sentence-transformers） |
| **仅 Windows** | 打包版仅支持 Windows 10/11，macOS/Linux 请用源码版 |
| **首次需联网** | 首次运行需下载 Embedding 模型（~100MB） |
| **WebView2 依赖** | Windows 10 需手动安装 Edge WebView2 Runtime |
| **更新不便** | 每次更新需重新下载整个压缩包 |
| **杀软误报** | PyInstaller 打包的 exe 可能被部分杀软误报 |

## 适用场景

| 场景 | 推荐 |
|------|:--:|
| 想快速体验，不想装 Python | ✅ |
| 公司电脑无管理员权限装不了软件 | ✅ |
| 给非技术朋友分享 | ✅ |
| 日常长期使用 | ✅ |
| 需要修改源码/二次开发 | ❌ → 用[源码版](../README.md) |
| macOS / Linux 用户 | ❌ → 用[源码版](../README.md) |

## 技术信息

- 打包工具：PyInstaller 6.x
- 打包模式：`--onedir`（文件夹模式，非单文件）
- Python 版本：3.10.11
- WebView2：Edge Chromium 内核
