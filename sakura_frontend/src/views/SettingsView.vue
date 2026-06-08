// views/SettingsView.vue — 设置页（从旧组件迁移中）
<template>
  <div style="padding:24px;color:var(--tc2,#7b8ca0);font-size:14px">
    <h2 style="margin-bottom:16px;color:var(--tc,#e2e8f0)">设置</h2>
    <p>设置页面正在迁移中，请暂时使用旧版界面。</p>
    <n-button @click="router.push({name:'chat'})" style="margin-top:12px">返回聊天</n-button>
  </div>
</template>

<script setup>
import { NButton } from 'naive-ui'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
