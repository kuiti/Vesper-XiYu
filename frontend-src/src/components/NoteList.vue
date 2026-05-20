<template>
  <div class="note-list">
    <div class="add-note">
      <input v-model="newTitle" placeholder="标题" style="flex:2">
      <input v-model="newContent" placeholder="内容" style="flex:3">
      <button @click="addNote">+</button>
    </div>
    <div class="items">
      <div v-for="note in notes" :key="note.id" class="note-item">
        <div class="note-title">{{ note.title }}</div>
        <div class="note-content">{{ note.content }}</div>
        <button @click="deleteNote(note.id)">🗑️</button>
      </div>
      <div v-if="!notes.length" class="empty">暂无笔记</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      notes: [],
      newTitle: '',
      newContent: ''
    }
  },
  mounted() {
    this.loadNotes()
  },
  methods: {
    async loadNotes() {
      try {
        const res = await api.get('/notes/')
        this.notes = res.data
      } catch (err) {
        console.error('加载笔记失败', err)
      }
    },
    async addNote() {
      if (!this.newTitle.trim() || !this.newContent.trim()) return
      try {
        await api.post('/notes/', {
          title: this.newTitle,
          content: this.newContent
        })
        this.newTitle = ''
        this.newContent = ''
        await this.loadNotes()
      } catch (err) {
        console.error('添加笔记失败', err)
      }
    },
    async deleteNote(id) {
      try {
        await api.delete(`/notes/${id}`)
        await this.loadNotes()
      } catch (err) {
        console.error('删除笔记失败', err)
      }
    }
  }
}
</script>

<style scoped>
.note-list {
  padding: 10px;
}
.add-note {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.add-note input {
  padding: 6px;
  border-radius: 8px;
  border: 1px solid #2c3e50;
  background: #1a1a2e;
  color: white;
}
.add-note button {
  background: #4e89ae;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  width: 32px;
}
.note-item {
  background: #16213e;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
  position: relative;
}
.note-title {
  font-weight: bold;
  color: #4e89ae;
  margin-bottom: 4px;
}
.note-content {
  font-size: 14px;
  color: #ecf0f1;
}
.note-item button {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
}
.empty {
  color: #7f8c8d;
  text-align: center;
  font-size: 14px;
}
</style>