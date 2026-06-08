<template>
  <div class="note-list">
    <div class="add-note">
      <input v-model="newTitle" placeholder="标题" class="title-input">
      <textarea v-model="newContent" placeholder="内容…想写多少写多少" class="content-input" rows="8"></textarea>
      <button @click="addNote" class="add-btn">保存笔记</button>
    </div>
    <div class="items">
      <div v-for="note in notes" :key="note.id" class="note-item">
        <div class="note-header">
          <div class="note-title">{{ note.title }}</div>
          <button @click="deleteNote(note.id)" class="del-btn">删除</button>
        </div>
        <div class="note-content">{{ note.content }}</div>
      </div>
      <div v-if="!notes.length" class="empty">暂无笔记，写一篇吧</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'

export default {
  inject: { showConfirm: { default: () => async (msg) => await showConfirm({ content: msg }) } },
  data() {
    return { notes: [], newTitle: '', newContent: '' }
  },
  mounted() { this.loadNotes() },
  methods: {
    async loadNotes() {
      try { const res = await api.get('/notes/'); this.notes = Array.isArray(res.data) ? res.data : [] } catch (err) { console.error(err) }
    },
    async addNote() {
      if (!this.newTitle.trim() || !this.newContent.trim()) return
      try {
        await api.post('/notes/', { title: this.newTitle.trim(), content: this.newContent.trim() })
        this.newTitle = ''; this.newContent = ''
        await this.loadNotes()
      } catch (err) { console.error(err) }
    },
    async deleteNote(id) {
      if (!await this.showConfirm('删除此笔记？')) return
      try { await api.delete(`/notes/${id}`); await this.loadNotes() } catch (err) { console.error(err) }
    }
  }
}
</script>

<style scoped>
.note-list { padding: 10px; }
.add-note { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.title-input { padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 15px; font-weight: 600; }
.content-input { padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 14px; line-height: 1.7; resize: vertical; min-height: 160px; font-family: inherit; }
.add-btn { align-self: flex-end; background: var(--p); border: none; border-radius: 8px; color: #fff; cursor: pointer; padding: 8px 20px; font-size: 14px; }
.note-item { background: var(--sb); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
.note-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.note-title { font-weight: 600; color: var(--p); font-size: 15px; }
.note-content { font-size: 14px; color: var(--tc); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.note-header .del-btn { background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 13px; opacity: .4; transition: opacity .15s; }
.note-header .del-btn:hover { opacity: 1; color: #e74c3c; }
.empty { color: var(--tc2); text-align: center; font-size: 14px; padding: 30px; }
</style>
