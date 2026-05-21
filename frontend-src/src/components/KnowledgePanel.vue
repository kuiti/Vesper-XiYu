<template>
  <div class="knowledge-panel">
    <div class="add-row">
      <input type="file" ref="fileInput" accept=".txt,.md,.pdf" @change="onFilePicked" style="display:none">
      <button class="btn-s" @click="$refs.fileInput.click()" :disabled="uploading">
        {{ uploading ? '上传中...' : '选择文件 (.txt/.md/.pdf)' }}
      </button>
    </div>
    <div v-if="error" class="error-msg">{{ error }}</div>
    <div v-if="docs.length" class="doc-list">
      <div v-for="doc in docs" :key="doc.id" class="doc-row">
        <span class="doc-name">{{ doc.filename }}</span>
        <span class="doc-meta">{{ doc.chunks }}块 | {{ fmtSize(doc.size) }}</span>
        <button class="btn-s btn-danger" @click="removeDoc(doc.id)">删除</button>
      </div>
    </div>
    <div v-else class="empty-hint">暂无文档</div>
    <div class="model-status" :class="{ ready: modelReady }">
      {{ modelReady ? '模型已就绪' : '模型加载中，上传后稍后自动索引' }}
    </div>
  </div>
</template>

<script>
import api from '../api.js'
export default {
  data() { return { docs: [], modelReady: false, uploading: false, error: '' } },
  mounted() { this.loadDocs() },
  methods: {
    async loadDocs() {
      try { const res = await api.get('/knowledge/'); this.docs = res.data.documents; this.modelReady = res.data.model_ready } catch (e) { console.error(e) }
    },
    async onFilePicked(e) {
      const file = e.target.files[0]; if (!file) return
      this.uploading = true; this.error = ''
      const form = new FormData(); form.append('file', file)
      try {
        const res = await api.post('/knowledge/upload', form)
        if (res.data.status === 'ok') this.loadDocs()
        else this.error = res.data.message
      } catch (err) { this.error = '上传失败' }
      finally { this.uploading = false; e.target.value = '' }
    },
    async removeDoc(id) {
      try { await api.delete(`/knowledge/${id}`); this.loadDocs() } catch (err) { console.error(err) }
    },
    fmtSize(bytes) { if (!bytes) return '0B'; const u = ['B','KB','MB']; let i = 0, s = bytes; while (s >= 1024 && i < 2) { s /= 1024; i++ }; return s.toFixed(1) + u[i] }
  }
}
</script>

<style scoped>
.knowledge-panel { display: flex; flex-direction: column; gap: 8px; }
.add-row { display: flex; gap: 8px; }
.doc-list { display: flex; flex-direction: column; gap: 4px; max-height: 200px; overflow-y: auto; }
.doc-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: rgba(255,255,255,.03); border-radius: 6px; }
.doc-name { flex: 1; font-size: 12px; color: #ccc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-meta { font-size: 11px; color: #7f8c8d; flex-shrink: 0; }
.error-msg { color: #e74c3c; font-size: 12px; }
.empty-hint { color: #7f8c8d; text-align: center; font-size: 12px; padding: 8px; }
.model-status { font-size: 11px; color: #f39c12; }
.model-status.ready { color: #4caf50; }
</style>
