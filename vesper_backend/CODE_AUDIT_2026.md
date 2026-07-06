# 夕语后端 (sakura_backend) 代码审计报告

**审计日期**: 2026-06-26  
**项目版本**: 5.0.0  
**技术栈**: Python 3.10+, FastAPI, SQLite, WebSocket, ChromaDB, Sentence-Transformers  

---

## 一、项目概览

夕语后端是一个基于 FastAPI 的 AI 聊天伴侣后端服务，主要功能包括：
- WebSocket 实时对话
- 多 LLM Provider 支持（DeepSeek、OpenAI、Ollama 等）
- 情感分析与关系追踪
- 向量记忆检索 (RAG)
- TTS/STT 语音交互
- 角色卡系统（兼容酒馆 chara_card_v2 规范）
- MCP 工具调用框架
- 桌面端 + 云端双模式部署

**代码规模**: 约 50+ Python 模块，API 层约 48 个路由模块，Core 层约 50+ 核心模块

---

## 二、严重安全问题 (Critical)

### 2.1 🔴 任意代码执行 — `code_runner.py`

```python
# core/code_runner.py
def run_python(code: str, timeout: int = 5) -> str:
    """运行 Python 代码片段（超时5秒）"""
    with tempfile.NamedTemporaryFile(...) as f:
        f.write(code)
        subprocess.run(['python', f.name], ...)
```

**问题**: 
- 无任何沙箱隔离，直接 `subprocess.run` 执行任意 Python 代码
- 无文件系统/网络限制，攻击者可读写任意文件、发起网络请求
- 无 import 限制，可导入 `os`、`subprocess`、`socket` 等危险模块
- 虽有 5 秒超时，但足以执行破坏性操作

**风险等级**: **严重 (Critical)** — 如果该功能被 LLM 工具调用或 API 暴露，可导致远程代码执行 (RCE)

**建议**:
- 若非必要，移除此模块
- 如需保留，使用 `RestrictedPython` 或 Docker 容器沙箱
- 限制可用的内置函数和 import

### 2.2 🔴 远程依赖安装端点 — `api/rag.py`

```python
@router.post("/install")
async def rag_install():
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "sentence-transformers", "chromadb"],
        ...
    )
```

**问题**:
- 暴露了一个 HTTP 端点允许远程执行 `pip install`
- 虽然云端模式有检查，但本地模式下完全开放
- 攻击者可通过 SSRF 或本地网络访问安装恶意包

**风险等级**: **严重 (Critical)**

**建议**: 移除此端点，依赖安装应仅通过 CLI 或部署脚本完成

### 2.3 🔴 本地模式完全无认证

```python
# core/auth.py
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = _get_token()
        if not token:
            return await call_next(request)  # 本地模式，不验证
```

**问题**: 默认本地模式下所有 API 端点完全无认证，包括：
- `/settings/` — 读写所有配置（含 API Key）
- `/export/chat` — 导出全部聊天记录
- `/settings/full-reset` — 删除所有数据
- `/push/send` — 发送推送通知
- WebSocket 连接无限制

**风险等级**: **高 (High)** — 同一网络下的任何设备均可访问

**建议**: 本地模式也应启用基础认证（如 PIN 码，config.json 中已有 `pin_code` 字段但未使用）

---

## 三、高风险安全问题 (High)

### 3.1 🟠 API Key 明文存储

```python
# config.json
"api_key": ""
# settings.py 允许前端直接设置 api_key
_SETTINGS_WHITELIST = {... "api_key", ...}
```

**问题**:
- API Key 以明文存储在 SQLite `config` 表中
- 前端可通过 `/settings/` 直接读写 API Key
- `/settings/` GET 端点虽然返回 `has_api_key` 布尔值，但 `api_key` 本身仍可通过数据库直接读取
- 虽有 `core/crypto.py` 加密模块，但未被用于加密 API Key

**建议**: 使用 `core/crypto.py` 中的 AES-256-GCM 加密存储 API Key，读取时解密

### 3.2 🟠 SQL 注入风险 — 动态表名拼接

```python
# api/settings.py - full_reset
for table in ["countdowns", "goal_tracking", ...]:
    cursor.execute(f"DELETE FROM {table}")

# core/db/__init__.py - migrations
cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
```

**问题**: 多处使用 f-string 拼接 SQL 语句中的表名和列名。虽然当前值来自硬编码列表，但这种模式容易在未来扩展时引入注入风险。

**建议**: 
- 对动态表名/列名添加白名单校验
- 使用 `sqlite3` 的标识符引用（方括号或双引号）

### 3.3 🟠 路径遍历防护不完整

```python
# main.py - SPA fallback
raw = os.path.join(FRONTEND_DIR, full_path)
real = os.path.realpath(raw)
if not real.startswith(os.path.realpath(FRONTEND_DIR) + os.sep):
    return JSONResponse({"detail": "Not Found"}, 404)
```

**正面**: SPA fallback 中正确使用了 `os.path.realpath` + 前缀检查，防护较好。

**问题**: 
- `api/vision.py` 中文件上传使用 `os.path.basename` 但未校验文件扩展名与 content_type 的一致性
- `data/avatars` 目录通过 `StaticFiles` 挂载，无访问控制

### 3.4 🟠 WebSocket 连接数限制可被绕过

```python
_MAX_WS_CONNECTIONS = 20
# 但 _active_websockets 使用 asyncio.Lock，在高并发下可能存在竞态条件
```

### 3.5 🟠 Push 推送端点无认证

```python
@router.post("/send")
async def send(title: str, body: str):
    # 无任何认证检查
    return {"status": "ok", "sent": len(_subscriptions)}
```

**问题**: 推送发送端点无认证，任何人可发送推送通知。

---

## 四、中等风险问题 (Medium)

### 4.1 🟡 配置缓存线程安全

```python
# core/db/config.py
_config_cache = {}
_config_cache_lock = threading.Lock()

def get_config(key, default=None):
    with _config_cache_lock:
        ...
    with get_conn() as conn:  # 锁已释放后访问 DB
        ...
    # 再次无锁写入缓存
    _config_cache[key] = (value, now + _CONFIG_TTL)
```

**问题**: 缓存读取在锁内，但 DB 查询和缓存写入在锁外，存在竞态条件：多个线程可能同时查询 DB 并写入缓存。

### 4.2 🟡 数据库连接池管理

```python
# core/db/__init__.py
_CHAT_CONNS: dict = {}
_MAX_CONNS = 20

def get_chat_conn(character_id: int = 0):
    # 永不关闭的持久连接
    conn = sqlite3.connect(path, timeout=10)
    _CHAT_CONNS[path] = conn
```

**问题**:
- 角色聊天库和画像库使用持久连接，永不关闭（仅在达到上限时淘汰最旧的）
- SQLite 的 WAL 模式下长期持有连接可能导致 WAL 文件膨胀
- 连接未设置 `PRAGMA synchronous=NORMAL`（主库设置了，但聊天库未设置）

### 4.3 🟡 FTS5 触发器可能存在性能问题

```sql
CREATE TRIGGER IF NOT EXISTS chat_ai AFTER INSERT ON chat_history BEGIN
    INSERT INTO chat_fts(rowid, content) VALUES (new.id, new.content);
END
```

**问题**: 每次插入 chat_history 都会同步写入 FTS 索引，在高频对话时可能成为瓶颈。

### 4.4 🟡 硬编码的默认端口和地址

```python
_cors_origins = ["http://127.0.0.1:8060", "http://127.0.0.1:8061", ...]
```

**问题**: CORS origins 硬编码了多个端口，应通过环境变量或配置文件统一管理。

### 4.5 🟡 全局状态过多

项目大量使用模块级全局变量：
- `_active_websockets` — 活跃连接
- `_config_cache` — 配置缓存
- `_CHAT_CONNS` — 数据库连接池
- `_PROFILE_CONNS` — 画像库连接池
- `_login_attempts` — 登录尝试
- `_subscriptions` — 推送订阅（内存存储，重启丢失）
- `_diary_scheduler_started` — 调度器状态

这使得测试困难、状态管理复杂，且在多进程部署下无法工作。

---

## 五、代码质量问题

### 5.1 命名风格不一致

变量命名混合使用了多种风格：
- 单字母缩写: `sp`, `dc`, `de`, `kh`, `rag`, `pc`, `fc`, `pn`, `tt`, `ekw`, `bu`
- 完整命名: `sentiment_result`, `intent_type`, `consecutive_negative`
- 混合缩写: `_clean_dsml`, `_calc_consecutive_days`

**建议**: 统一使用有意义的完整命名，提高可读性

### 5.2 函数过长

`ChatSession._build_and_send()` 方法约 120 行，`ChatSession._process_reply()` 约 100 行，`_init_db_locked()` 约 200 行。应拆分为更小的职责单一的函数。

### 5.3 异常处理过于宽泛

```python
except Exception:
    pass  # 多处出现

except Exception as e:
    logger.warning(f"...: {e}")
    pass  # pass 是多余的
```

**建议**: 
- 记录具体的异常类型
- 使用 `silent_exc()` 统一处理（项目已有此工具但未一致使用）
- 移除多余的 `pass`

### 5.4 缺少类型注解

大量函数缺少参数和返回值类型注解，特别是：
- `db/` 子模块的所有 CRUD 函数
- `api/` 路由处理函数
- `core/` 核心模块

### 5.5 `config.json` 已过时

项目已将配置迁移到 SQLite `config` 表，但 `config.json` 仍存在于项目根目录，包含敏感信息（pin_code、api_key 字段），容易造成混淆。

---

## 六、架构问题

### 6.1 缺少分层架构

API 层（`api/`）直接调用数据库层（`core/db/`），缺少 Service 层：
```
api/chat_session.py → core/db/get_conn() → 直接 SQL
```

**建议**: 引入 Service 层封装业务逻辑，API 层仅负责请求/响应处理。

### 6.2 WebSocket 端点过于集中

所有对话功能通过单一 `/ws/chat` WebSocket 端点处理，消息类型通过 JSON `type` 字段区分。这导致：
- 单个文件 956 行
- 职责过多（聊天、命令、反馈、工具调用）
- 难以扩展和测试

### 6.3 循环导入风险

多处使用延迟导入（函数内 `import`）来避免循环导入：
```python
async def _handle_chat_message(self):
    from core.character_card import CharacterCard  # 函数内导入
```

这表明模块间依赖关系复杂，应重新组织模块结构。

---

## 七、数据库设计

### 7.1 正面评价
- 使用 WAL 模式提高并发性能
- 合理的索引设计（时间戳、角色、FTS5 全文搜索）
- 参数化查询防止 SQL 注入
- 数据库文件权限设置（`chmod 600`）

### 7.2 问题
- 单一 SQLite 文件包含 30+ 张表，数据量增长后可能成为瓶颈
- 缺少数据库备份机制
- Schema 迁移使用 ALTER TABLE ADD COLUMN，无版本管理
- `config` 表使用 key-value 模式存储所有配置，缺乏结构化

---

## 八、测试覆盖

### 8.1 正面评价
- 有 16 个测试文件覆盖核心模块
- `conftest.py` 正确使用内存数据库隔离测试
- 使用 `monkeypatch` 避免测试污染生产数据

### 8.2 问题
- 缺少 API 集成测试（无 `TestClient` 测试路由）
- 缺少 WebSocket 端点测试
- 缺少安全性测试（认证、授权、注入）
- 缺少 `code_runner.py` 的安全测试

---

## 九、依赖管理

### 9.1 正面评价
- `requirements-cloud.txt` 分离了云端和本地依赖
- 依赖版本有最低版本约束

### 9.2 问题
- 缺少 `requirements.txt`（本地完整依赖）
- 缺少版本锁定文件（`requirements.lock` 或 `poetry.lock`）
- `pycryptodome` 和 `cryptography` 同时出现在不同地方（crypto.py 用 cryptography，requirements 用 pycryptodome）

---

## 十、安全亮点 (正面)

1. **SSRF 防护** (`core/security.py`): 完整的内网地址检测，包括 DNS 解析后验证
2. **认证中间件**: 使用 `hmac.compare_digest` 防止时序攻击
3. **登录限流**: 5 次/5 分钟的暴力破解防护
4. **WebSocket 认证**: 支持 Protocol Header 和 Query Param 两种方式
5. **路径遍历防护**: `validate_path_within` 和 `_sanitize_char_name` 函数
6. **配置白名单**: 前端只能修改白名单内的配置键
7. **SPA 路径安全**: 使用 `os.path.realpath` 防止目录遍历
8. **加密模块**: `core/crypto.py` 实现了 AES-256-GCM + PBKDF2（但未被充分利用）
9. **输入校验**: Pydantic 模型用于 API 请求验证
10. **速率限制**: WebSocket 消息速率限制（10 条/10 秒）

---

## 十一、改进建议优先级

### P0 — 立即修复
1. 移除或沙箱化 `code_runner.py`
2. 移除 `/rag/install` 远程安装端点
3. 本地模式启用基础认证（PIN 码）
4. API Key 加密存储

### P1 — 短期修复
5. SQL 动态表名添加白名单校验
6. Push 端点添加认证
7. 补充 API 集成测试和安全测试
8. 统一异常处理模式

### P2 — 中期改进
9. 引入 Service 层分离业务逻辑
10. 重构 ChatSession，拆分为更小的职责单元
11. 消除全局状态，引入依赖注入
12. 添加数据库备份机制
13. 补充类型注解

### P3 — 长期规划
14. 考虑从 SQLite 迁移到 PostgreSQL（如需多用户/多进程）
15. 引入 CI/CD 流水线和自动化安全扫描
16. 添加 API 版本管理
17. 编写完整的 API 文档（OpenAPI schema 已自动生成但需补充描述）

---

## 十二、总结

夕语后端在功能实现上相当丰富，代码量大但组织相对清晰。安全方面有 SSRF 防护、认证中间件、输入校验等良好实践，但仍存在 **代码执行端点**、**远程包安装**、**本地无认证** 等严重问题需要优先修复。代码质量方面，命名不一致、函数过长、异常处理粗糙是主要短板。建议按优先级逐步改进，特别关注 P0 级别的安全问题。