# 前端 — 统一页面布局（剩余视图）

## 项目位置
`H:\my_cc_ai\sakura_frontend\`

## 构建验证
```bash
npm run build
```

---

## 已完成
- PageHeader.vue 通用页面头组件
- 公共页面样式（.page-view / .page-body / .page-card）
- 页面切换 fade 过渡动画
- ToolsView / StatsView / MemoryView / GamesView 已更新

## 剩余

### P0：更新 DiaryView、CharactersView、HistoryView

三个文件都在 `src/components/` 下，每个 170-200 行。

**改动模式**（每个文件一样）：

1. 添加 import：`import PageHeader from './common/PageHeader.vue'`
2. 在 `components` 中注册 PageHeader
3. 模板改为：
```html
<template>
  <div class="page-view">
    <PageHeader icon="EMOJI" title="标题" desc="描述" />
    <div class="page-body">
      <!-- 原有内容，div 用 page-card 类名 -->
    </div>
  </div>
</template>
```
4. 删掉原有的顶端 `<h2>` 标题
5. 删掉 scoped style 中重复的 `.xxx-view { padding: 20px; overflow-y: auto; }` 等基础样式（已被 .page-view 覆盖）
6. 将原有的 `.card` 类改为 `.page-card`（或直接用 `.page-card` 替换）
7. `.btn` / `.btn-s` / `.hint` / `.ok` / `.fail` 样式已在全局定义，可以删掉 scoped 中的副本

**具体 icon 建议**：
- DiaryView → 📔
- CharactersView → 👤
- HistoryView → 📜

**验证**：`npm run build` 通过。
