# Sakura Frontend 审计报告

**审计日期：** 2026-06-12  
**技术栈：** Vue 3.5 + Pinia 3 + Vite 8 + TypeScript (部分) + Vitest  
**项目性质：** PWA 单页聊天应用，AI 伴侣"佐仓"的前端界面

---

## 一、项目概览

| 维度 | 详情 |
|------|------|
| 框架 | Vue 3 (Options API 为主) |
| 状态管理 | Pinia 3 (3 个 Store) |
| 构建工具 | Vite 8 |
| HTTP 客户端 | Axios 1.16 |
| 测试框架 | Vitest 4 + @vue/test-utils 2 |
| 类型系统 | TypeScript（部分，`strict: false`） |
| 组件数量 | ~45 个 `.vue` 文件 |
| 生产依赖 | 仅 3 个（axios, pinia, vue） |

### 文件结构

```
sakura_frontend/
├── index.html           # 入口 HTML，加载 config.js + sw.js
├── vite.config.js       # Vite 配置
├── tsconfig.json        # TypeScript 配置
├── package.json         # 依赖声明
├── public/
│   ├── sw.js            # Service Worker
│   ├── manifest.json    # PWA Manifest
│   ├── config.js        # 运行时配置（.gitignore 排除）
│   └── icons/           # 应用图标
├── src/
│   ├── main.js          # 应用入口
│   ├── api.ts           # Axios 实例 + WebSocket 工厂
│   ├── App.vue          # 根组件（336 行）
│   ├── themes.css       # 10 套主题 CSS 变量
│   ├── env.d.ts         # 类型声明
│   ├── stores/          # Pinia Store
│   │   ├── chatStore.js    # 聊天 + WebSocket + 打字机
│   │   ├── settingsStore.js # 设置 + 主题
│   │   └── uiStore.js      # UI 状态 + 锁屏 + 确认框
│   ├── components/      # 45 个 Vue 组件
│   │   ├── settings/    # 设置子组件 (3 个)
│   │   ├── chat/        # 聊天相关组件
│   │   ├── common/      # 通用组件 (2 个)
│   │   └── *.vue        # 其他页面级组件
│   └── __tests__/       # 测试文件 (3 个)
```

---

## 二、安全审计

### 🔴 严重 (Critical)

#### 2.1 API Token 明文存储于 localStorage

**位置：** `src/api.ts:28`，`src/components/LoginView.vue:54`

```typescript
// api.ts
token: localStorage.getItem('sakura_api_token') || cfg.apiToken || '',

// LoginView.vue
localStorage.setItem('sakura_api_token', this.token)
```

**风险：** 任何 XSS 漏洞都可直接读取 Token。localStorage 无过期机制，Token 一旦泄露可永久使用。

**建议：**
- 使用 `httpOnly` Cookie 存储 Token（需后端配合）
- 若必须用 localStorage，至少对 Token 进行加密/混淆
- 缩短 Token 有效期，实现自动刷新机制

#### 2.2 WebSocket Token 通过 URL 查询参数传递

**位置：** `src/api.ts:72`

```typescript
const url = c.token ? `${base}${path}${sep}token=${encodeURIComponent(c.token)}` : `${base}${path}`
```

**风险：** URL 中的 Token 会出现在：
- 浏览器历史记录
- 服务器访问日志
- 代理/CDN 日志
- WebSocket 握手请求的 Referer 头

**建议：** 在 WebSocket `onopen` 后通过首条消息发送 Token 认证，或使用 Sec-WebSocket-Protocol 头。

### 🟠 高危 (High)

#### 2.3 PIN 码明文存储和比较

**位置：** `src/stores/uiStore.js:11,69-70`

```javascript
pinCode: '',           // 明文存储
unlock(pin) {
  if (pin === this.pinCode) {  // 明文比较
```

**风险：** PIN 码以明文形式存在于：
- Pinia Store 内存中
- 后端 settings API（可能也明文存储）
- 无暴力破解保护（前端可无限重试，仅靠 UI 层面的 3 次重置逻辑）

**建议：**
- 前端仅做基本输入校验，实际验证交给后端
- 后端使用 bcrypt/argon2 哈希存储
- 加入速率限制和账户锁定机制

#### 2.4 XSS 风险：用户输入未经转义

**位置：** `src/App.vue:109` (chatBgImage URL 直接注入 CSS)

```javascript
if (this.chatBgImage && /^(https?:\/\/|\/)[^\s'"()]+\.(jpg|jpeg|png|webp|gif)(\?[^\s'"()]*)?$/i.test(this.chatBgImage)) {
  bg = `url("${this.chatBgImage}")`
}
```

虽然有正则校验，但 `url()` 中的引号转义不够充分。更广泛地，聊天消息中的 HTML 内容（如天气卡片 `__WEATHER_CARD__`）可能包含用户可控数据。

**建议：** 所有用户生成内容必须经过 DOMPurify 或类似库过滤。

#### 2.5 无 Content Security Policy (CSP)

**位置：** `index.html`

HTML 中没有 CSP meta 标签，也无迹象表明后端设置了 CSP 响应头。

**风险：** 一旦存在 XSS 漏洞，攻击者可以：
- 注入任意脚本
- 连接任意外部服务器
- 读取 localStorage 中的 Token

**建议：** 添加严格 CSP 策略，限制 script-src、connect-src、style-src 等。

### 🟡 中危 (Medium)

#### 2.6 外部脚本加载 `config.js`

**位置：** `index.html:18`

```html
<script src="/config.js"></script>
```

`config.js` 在 `.gitignore` 中，但运行时通过 `<script>` 标签直接加载。如果 CDN/部署被劫持，可注入恶意代码。

**建议：** 使用 SRI (Subresource Integrity) 或将配置内联到构建产物中。

#### 2.7 错误信息泄露

**位置：** 多处 `catch (e) {}` 和 `console.error`

```javascript
// chatStore.js:54
try { data = JSON.parse(event.data) } catch (e) { return }

// App.vue:162
} catch (e) {}
```

空 catch 块吞掉了所有错误，调试困难。同时 `console.error` 在生产环境可能泄露敏感信息。

**建议：** 实现统一的错误上报机制，生产环境禁用 `console.error` 输出。

---

## 三、代码质量审计

### 3.1 TypeScript 使用不一致

**问题：** 项目混用 TypeScript 和 JavaScript：
- `api.ts`、`env.d.ts` 使用 TypeScript
- 所有 Store（`.js`）、组件（`.vue`）、`main.js` 使用 JavaScript
- `tsconfig.json` 中 `strict: false`、`checkJs: false`

**影响：** TypeScript 的类型安全优势几乎完全丧失。

**建议：**
1. 将 `strict` 设为 `true`
2. 将 Store 文件改为 `.ts`
3. 逐步为组件添加类型注解

### 3.2 App.vue 过于臃肿

**位置：** `src/App.vue` — 336 行

根组件承担了过多职责：
- 15 个组件注册
- 15+ 个异步数据加载方法
- WebSocket 回调注入
- 键盘快捷键处理
- 全局样式定义（80+ 行 CSS）
- 聊天消息发送逻辑
- 游戏事件处理
- 导出功能

**建议：** 拆分为：
- `AppLayout.vue` — 布局容器
- `AppInitializer.vue` — 初始化逻辑（composable）
- 各功能模块提取为独立 composable（`useLocation`、`useAvatars` 等）

### 3.3 Options API vs Composition API

**现状：** 全部组件使用 Options API。

**影响：**
- 代码复用困难（mixin 模式已弃用）
- 类型推断弱
- 逻辑分散在 `data`、`computed`、`methods`、`mounted` 等选项中

**建议：** 新组件使用 `<script setup>` + Composition API，逐步迁移旧组件。

### 3.4 Store 中的回调注入模式

**位置：** `src/stores/chatStore.js:30-37`，`src/App.vue:122-147`

```javascript
// chatStore.js state
_onGreeting: null,
_onProactive: null,
_onWeather: null,
// ...7 个回调

// App.vue mounted
chatStore._onGreeting = (data) => { ... }
chatStore._onProactive = (data) => { ... }
```

**问题：** 
- Store 应该是纯粹的状态容器，不应持有组件引用
- 回调函数引用了 `$refs`，破坏了 Store 的可测试性
- 隐式依赖关系难以追踪

**建议：** 使用 Pinia 插件或事件总线，或改为在 Store 中 emit 事件，由组件自行监听。

### 3.5 魔法数字和字符串

**示例：**

```javascript
// chatStore.js
setTimeout(() => { ... }, 500)        // 冷却时间
setTimeout(() => { ... }, 60000)      // 流超时
this.pendingReply.length < 50000      // 最大回复长度

// App.vue
setInterval(() => { ... }, 300000)    // 位置刷新间隔
setTimeout(() => { ... }, 8000)       // 断连提示时长
.slice(-35)                           // 历史消息条数
```

**建议：** 提取为命名常量或配置文件。

### 3.6 空 catch 块泛滥

**统计：** 项目中约有 **15+** 处空 catch 块 `catch (e) {}`。

```javascript
// App.vue
try { ... } catch (e) {}  // 至少 8 处
// stores
} catch (e) {}             // 至少 4 处
```

**建议：** 至少记录错误日志，关键路径应有用户提示。

---

## 四、性能审计

### 4.1 无路由级别的代码分割

**现状：** 所有 ~45 个组件在 `App.vue` 中通过 `v-if`/`v-show` 切换，无懒加载。

**影响：** 
- 首屏加载需下载全部组件代码
- 打包产物可能较大

**建议：**
- 使用 `defineAsyncComponent` 或 Vue Router 实现懒加载
- 大型组件（如 GamesView 包含 3 个游戏）应独立 chunk

### 4.2 频繁的 localStorage 访问

**位置：** `src/api.ts:15-33`

```typescript
function _getConfig(): ServerConfig {
  // 每次请求都读取 5 次 localStorage
  localStorage.getItem('sakura_config_ver')
  localStorage.getItem('sakura_server_host')
  // ...
}
```

每个 HTTP 请求的拦截器都会调用 `_getConfig()`，触发 5 次 `localStorage.getItem`。

**建议：** 缓存配置到内存变量，仅在配置变更时更新。

### 4.3 CSS 主题文件体积

**位置：** `src/themes.css` — 178 行，10 套主题

每套主题包含完整的变量声明，用户通常只使用 1 套。

**建议：** 
- 运行时按需加载主题 CSS
- 或保持现状但添加 CSS minification（Vite 默认会做）

### 4.4 WebSocket 重连策略

**位置：** `src/stores/chatStore.js:265-273`

```javascript
const delay = Math.min(30000, 1000 * Math.pow(2, this.wsReconnectAttempts))
```

指数退避最大 30 秒，合理。但缺少：
- 最大重连次数限制
- 页面不可见时暂停重连
- 网络状态检测（`navigator.onLine`）

---

## 五、测试审计

### 5.1 测试覆盖率极低

| 文件 | 行数 | 测试内容 |
|------|------|----------|
| `api.test.ts` | 15 行 | 仅测试 `getBaseUrl` 和 `getToken` 返回类型 |
| `stores.test.js` | 130 行 | Store 默认值 + 基本 action |
| `ChatSettings.test.ts` | 50 行 | 组件渲染 + 1 个 emit 测试 |

**未覆盖的关键逻辑：**
- ❌ WebSocket 连接/断连/重连
- ❌ 消息发送/接收/流式处理
- ❌ 打字机效果（`_twTick`、`_twPush`）
- ❌ 分句调度（`schedulePop`）
- ❌ 认证流程（LoginView）
- ❌ 锁屏功能
- ❌ 主题切换
- ❌ 错误处理路径
- ❌ 历史消息加载/分页

### 5.2 测试质量

```javascript
// stores.test.js - 仅测试默认值
it('has correct defaults', () => {
  const c = useChatStore()
  expect(c.ws).toBeNull()
  expect(c.wsReady).toBe(false)
  // ...
})
```

测试仅验证初始状态，未测试状态变更和副作用。

**建议：** 优先补充：
1. WebSocket 消息处理的单元测试
2. 认证流程的集成测试
3. 关键用户路径的 E2E 测试

---

## 六、PWA 审计

### 6.1 Service Worker 形同虚设

**位置：** `public/sw.js`

```javascript
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
```

SW 仅透传所有请求，不做任何缓存。在 activate 时还清除所有缓存。

**影响：** 无离线支持，PWA 安装后无法离线使用。

**建议：** 
- 实现 Cache-First 策略缓存静态资源
- 使用 Network-First 策略处理 API 请求
- 或移除 SW 注册（避免误导用户）

### 6.2 Manifest 配置

`manifest.json` 基本完整，但缺少：
- `scope` 字段
- `screenshots` 字段（增强安装提示）
- `shortcuts` 字段（快速操作）

---

## 七、依赖审计

### 7.1 生产依赖

| 包名 | 版本 | 安全性 | 备注 |
|------|------|--------|------|
| vue | ^3.5.32 | ✅ 安全 | 最新稳定版 |
| pinia | ^3.0.4 | ✅ 安全 | Vue 官方状态管理 |
| axios | ^1.16.1 | ✅ 安全 | 主流 HTTP 客户端 |

**优点：** 依赖精简，仅 3 个生产依赖，攻击面小。

### 7.2 开发依赖

| 包名 | 版本 | 备注 |
|------|------|------|
| vite | ^8.0.8 | 最新版本 |
| @vitejs/plugin-vue | ^6.0.6 | |
| vitest | ^4.1.8 | |
| @vue/test-utils | ^2.4.11 | |
| jsdom | ^29.1.1 | |
| vite-plugin-vue-devtools | ^8.1.1 | ⚠️ 生产构建应排除 |

### 7.3 缺失的工具链

- ❌ **无 ESLint** — 无代码风格和错误检查
- ❌ **无 Prettier** — 无代码格式化
- ❌ **无 Husky/lint-staged** — 无 Git hooks
- ❌ **无 Dependency Cruiser** — 无依赖关系检查

---

## 八、可访问性审计

### 8.1 无障碍性问题

- ❌ 大量使用 `<div>` 而非语义化标签（`<nav>`、`<main>`、`<section>`）
- ❌ 确认对话框无 `role="dialog"` 和 `aria-*` 属性
- ❌ 按钮缺乏 `aria-label`（如 `x` 删除按钮）
- ❌ 颜色对比度未测试
- ❌ 键盘导航支持有限（仅 Ctrl+数字切换视图）

### 8.2 移动端适配

- ✅ viewport meta 设置了 `maximum-scale=1.0, user-scalable=no`
- ✅ 有 `@media (max-width: 768px)` 响应式样式
- ⚠️ `user-scalable=no` 阻止缩放，影响视障用户

---

## 九、架构建议

### 9.1 推荐的重构路线图

**阶段一：安全加固（紧急）**
1. Token 存储改为 httpOnly Cookie
2. WebSocket 认证改为首条消息
3. 添加 CSP 头
4. 实现输入消毒

**阶段二：TypeScript 迁移**
1. 启用 `strict: true`
2. Store 文件改为 `.ts`
3. 组件添加类型注解

**阶段三：架构优化**
1. App.vue 拆分
2. 引入 Vue Router 实现路由级别的代码分割
3. 回调注入模式改为事件驱动
4. 提取 composables

**阶段四：质量保障**
1. 添加 ESLint + Prettier
2. 补充核心路径测试
3. 添加 E2E 测试
4. 实现真正的 SW 缓存策略

### 9.2 目标架构

```
src/
├── main.ts
├── router/           # Vue Router
├── composables/      # 可复用逻辑
│   ├── useWebSocket.ts
│   ├── useLocation.ts
│   └── useAuth.ts
├── stores/           # Pinia (TypeScript)
├── views/            # 页面级组件（懒加载）
├── components/       # 通用组件
├── utils/            # 工具函数
├── types/            # 类型定义
└── assets/           # 静态资源
```

---

## 十、审计总结

### 评分卡

| 维度 | 评分 | 说明 |
|------|------|------|
| 安全性 | **3/10** | Token 明文存储、无 CSP、XSS 风险 |
| 代码质量 | **5/10** | 结构清晰但 TS 使用不充分，App.vue 臃肿 |
| 性能 | **6/10** | 依赖精简但无懒加载，localStorage 频繁读取 |
| 测试 | **2/10** | 覆盖率极低，核心逻辑未测试 |
| 可维护性 | **5/10** | Store 设计合理但回调注入模式不佳 |
| 无障碍 | **3/10** | 语义化不足，缺乏 ARIA |
| PWA | **2/10** | SW 形同虚设，无离线能力 |
| 依赖管理 | **7/10** | 依赖精简安全，但缺少工具链 |

### 优先修复项

1. 🔴 **Token 安全存储** — 最高优先级
2. 🔴 **WebSocket 认证方式** — 最高优先级  
3. 🟠 **添加 CSP** — 高优先级
4. 🟠 **输入消毒** — 高优先级
5. 🟡 **补充核心测试** — 中优先级
6. 🟡 **App.vue 拆分** — 中优先级
7. 🟢 **TypeScript 严格模式** — 低优先级
8. 🟢 **ESLint 配置** — 低优先级

### 正面评价

- ✅ 依赖极其精简（仅 3 个生产依赖）
- ✅ Pinia Store 职责划分清晰
- ✅ 主题系统设计良好（CSS 变量 + 10 套预设）
- ✅ WebSocket 指数退避重连
- ✅ 分句/打字机效果实现精巧
- ✅ 配置版本管理（CONFIG_VERSION）避免缓存不一致
- ✅ `.gitignore` 正确排除了敏感的 `config.js`