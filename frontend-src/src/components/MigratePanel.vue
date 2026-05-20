<template>
  <div class="migrate-panel">
    <div class="section">
      <h4>导出备份</h4>
      <p class="desc">打包所有数据（聊天记录、设置、人设、记忆、待办、笔记等）为一个文件</p>
      <button @click="doExport" :disabled="exporting" class="btn-primary">
        {{ exporting ? '导出中...' : '下载备份文件' }}
      </button>
    </div>

    <hr />

    <div class="section">
      <h4>导入恢复</h4>
      <p class="desc">选择之前导出的备份文件，恢复所有数据到当前电脑</p>
      <input type="file" ref="fileInput" accept=".json" @change="doImport" style="display:none" />
      <button @click="$refs.fileInput.click()" :disabled="importing" class="btn-primary">
        {{ importing ? '恢复中...' : '选择备份文件并恢复' }}
      </button>
      <div v-if="importResult" :class="['result', importResult.status]">{{ importResult.message }}</div>
      <div v-if="importResult && importResult.status === 'ok'" class="restored-detail">
        <div v-for="(v, k) in importResult.restored" :key="k">{{ k }}: {{ v }}</div>
      </div>
    </div>

    <hr />

    <div class="section">
      <h4>包含内容</h4>
      <ul>
        <li>聊天记录</li>
        <li>API 密钥 & 设置</li>
        <li>角色人设 & 预设</li>
        <li>记忆键值对</li>
        <li>对话摘要</li>
        <li>待办 / 笔记 / 倒计时 / 提醒</li>
        <li>向量记忆库（导入后需手动重建）</li>
      </ul>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      exporting: false,
      importing: false,
      importResult: null
    }
  },
  methods: {
    async doExport() {
      this.exporting = true
      try {
        const res = await api.get('/migrate/export', { responseType: 'blob' })
        const url = URL.createObjectURL(new Blob([res.data]))
        const a = document.createElement('a')
        a.href = url
        const now = new Date().toISOString().slice(0,10)
        a.download = `vesper_backup_${now}.json`
        a.click()
        URL.revokeObjectURL(url)
      } catch (err) {
        console.error('导出失败', err)
        alert('导出失败')
      } finally {
        this.exporting = false
      }
    },
    async doImport(e) {
      const file = e.target.files[0]
      if (!file) return
      if (!confirm(`确定要导入 "${file.name}" 吗？当前数据将被覆盖！`)) {
        this.$refs.fileInput.value = ''
        return
      }
      this.importing = true
      this.importResult = null
      try {
        const formData = new FormData()
        formData.append('file', file)
        const res = await api.post('/migrate/import', formData)
        this.importResult = res.data
        if (res.data.status === 'ok') {
          alert('数据恢复成功！页面将刷新。')
          location.reload()
        }
      } catch (err) {
        console.error('导入失败', err)
        this.importResult = { status: 'error', message: '导入失败' }
      } finally {
        this.importing = false
        this.$refs.fileInput.value = ''
      }
    }
  }
}
</script>

<style scoped>
.migrate-panel { padding: 8px; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 6px 0; color: #4e89ae; font-size: 14px; }
.desc { font-size: 12px; color: #7f8c8d; margin: 0 0 10px 0; }
hr { border: none; border-top: 1px solid #2c3e50; margin: 12px 0; }
.btn-primary { width: 100%; padding: 10px; background: #4e89ae; border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { opacity: .5; cursor: wait; }
.result { margin-top: 8px; padding: 8px; border-radius: 6px; font-size: 13px; }
.result.ok { background: #4caf5022; color: #4caf50; }
.result.error { background: #e74c3c22; color: #e74c3c; }
.restored-detail { margin-top: 6px; font-size: 11px; color: #7f8c8d; }
.restored-detail div { padding: 2px 0; }
ul { font-size: 12px; color: #bdc3c7; padding-left: 16px; }
ul li { margin-bottom: 3px; }
</style>
