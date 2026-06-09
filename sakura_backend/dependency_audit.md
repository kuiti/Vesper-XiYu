# 依赖使用审计报告

扫描范围：sakura_backend/ 全部 .py 文件
对照：requirements-cloud.txt

## 结论

| 包名 | 状态 | 说明 |
|------|------|------|
| fastapi | ✅ USED | 直接 import |
| uvicorn | ✅ USED | 直接 import |
| pydantic | ✅ USED | 直接 import |
| python-multipart | ⚠️ 间接依赖 | 不直接 import，但 FastAPI 的 UploadFile 需要它（7 个文件用到 UploadFile） |
| httpx | ✅ USED | 直接 import |
| chromadb | ✅ USED | 直接 import |
| openai | ❌ UNUSED | 无任何 import，llm_provider.py 用 httpx 直接调 API |
| apscheduler | ✅ USED | 直接 import |
| edge-tts | ✅ USED | 直接 import |
| pycryptodome | ❌ UNUSED | crypto.py 实际用的是 `cryptography` 包（AESGCM/PBKDF2），不是 pycryptodome |
| aiofiles | ❌ UNUSED | 无任何 import |
| requests | ✅ USED | 直接 import |
| jieba | ✅ USED | 直接 import |

## 建议操作

1. **移除 `openai`** — 项目用 httpx 直接调 OpenAI 兼容 API，不需要 openai SDK
2. **移除 `pycryptodome`** — 替换为 `cryptography`（crypto.py 已在用）
3. **移除 `aiofiles`** — 无任何使用
4. **新增 `cryptography`** — crypto.py 依赖但未在 requirements 中声明
5. **保留 `python-multipart`** — 虽不直接 import，但 FastAPI 文件上传运行时必需