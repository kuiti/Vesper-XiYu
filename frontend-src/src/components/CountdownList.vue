<template>
  <div class="countdown-list">
    <div class="add-item">
      <input v-model="newName" placeholder="名称" />
      <input type="date" v-model="newDate" />
      <button @click="addCountdown">+</button>
    </div>
    <div class="items">
      <div v-for="item in items" :key="item.id" class="item">
        <span>{{ item.name }}</span>
        <span>{{ daysRemaining(item.target) }}天</span>
        <button @click="deleteItem(item.id)">🗑️</button>
      </div>
      <div v-if="!items.length" class="empty">暂无倒计时</div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      items: [],
      newName: '',
      newDate: ''
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      try {
        const res = await api.get('/countdowns/')
        this.items = res.data
      } catch (err) {
        console.error('加载倒计时失败', err)
      }
    },
    daysRemaining(targetDate) {
      const days = Math.ceil((new Date(targetDate) - new Date()) / (1000 * 60 * 60 * 24))
      return days >= 0 ? days : 0
    },
    async addCountdown() {
      if (!this.newName || !this.newDate) return
      try {
        await api.post('/countdowns/', {
          name: this.newName,
          target_date: this.newDate
        })
        this.newName = ''
        this.newDate = ''
        await this.load()
      } catch (err) {
        console.error('添加失败', err)
      }
    },
    async deleteItem(id) {
      if (!confirm('删除此倒计时？')) return
      try {
        await api.delete(`/countdowns/${id}`)
        await this.load()
      } catch (err) {
        console.error('删除失败', err)
      }
    }
  }
}
</script>

<style scoped>
.countdown-list { padding: 8px; }
.add-item { display: flex; gap: 8px; margin-bottom: 12px; }
.add-item input { flex: 1; padding: 6px; border-radius: 6px; background: #1a1a2e; color: white; border: 1px solid #2c3e50; }
.add-item button { background: #4e89ae; border: none; color: white; border-radius: 6px; cursor: pointer; padding: 0 12px; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 6px; background: #16213e; border-radius: 6px; margin-bottom: 6px; }
.item span { color: white; }
.item button { background: none; border: none; color: #e74c3c; cursor: pointer; }
.empty { text-align: center; color: #7f8c8d; font-size: 13px; padding: 12px; }
</style>