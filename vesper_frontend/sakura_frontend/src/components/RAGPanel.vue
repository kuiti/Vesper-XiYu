<template>
  <div class="rag-panel">
    <div class="status-row">
      <span class="label">模型状态</span>
      <span :class="['badge', modelLoaded ? 'ok' : 'fail']">{{ modelLoaded ? '已加载' : '未加载' }}</span>
    </div>
    <div class="status-row">
      <span class="label">向量数量</span>
      <span class="badge">{{ vectorCount }}</span>
    </div>
    <button @click="rebuildIndex" :disabled="loading">
      {{ loading ? '重建中...' : '重建向量索引' }}
    </button>
    <p class="hint">{{ modelLoaded ? '语义记忆已就绪，对话时自动检索历史' : '模型加载失败，请检查网络或重启后端' }}</p>
  </div>
</template>

<script>
import api from '../api'

export default {
  data() {
    return {
      loading: false,
      modelLoaded: false,
      vectorCount: 0,
      _statusTimer: null,
      _unmounted: false
    }
  },
  mounted() {
    this.loadStatus()
  },
  beforeUnmount() {
    this._unmounted = true
    if (this._statusTimer) { clearTimeout(this._statusTimer); this._statusTimer = null }
  },
  methods: {
    async loadStatus() {
      try {
        const res = await api.get('/rag/status')
        this.modelLoaded = res.data.model_loaded
        this.vectorCount = res.data.vector_count
      } catch (err) {
        console.error('RAG状态获取失败', err)
      }
    },
    async rebuildIndex() {
      this.loading = true
      try {
        await api.post('/rag/rebuild')
        alert('索引重建已开始，请稍等几分钟（后台运行）')
        if (!this._unmounted) this._statusTimer = setTimeout(() => this.loadStatus(), 5000)
      } catch (err) {
        console.error('重建失败', err)
        alert('重建失败，请检查后端日志')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.rag-panel { padding: 10px; }
.status-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; margin-bottom: 6px; background: rgba(255,255,255,.03); border-radius: 6px; font-size: 13px; }
.label { color: var(--text-secondary); }
.badge { padding: 2px 10px; border-radius: 10px; font-size: 11px; background: rgba(255,255,255,.08); color: var(--text-primary); }
.badge.ok { background: #4caf5033; color: #4caf50; }
.badge.fail { background: #e74c3c33; color: #e74c3c; }
button { width: 100%; padding: 8px; margin-top: 10px; background: var(--accent-primary); border: none; border-radius: 6px; color: #fff; cursor: pointer; }
button:disabled { background: var(--border-default); }
.hint { font-size: 12px; color: var(--text-secondary); margin-top: 8px; text-align: center; }
</style>