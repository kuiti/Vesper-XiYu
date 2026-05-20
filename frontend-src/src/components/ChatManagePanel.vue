<template>
  <div class="chat-manage">
    <div class="section">
      <h4>快捷删除</h4>
      <div class="quick-buttons">
        <button @click="quickDelete('30min')">半小时</button>
        <button @click="quickDelete('60min')">一小时</button>
        <button @click="quickDelete('today')">今天</button>
        <button @click="quickDelete('yesterday')">昨天</button>
        <button @click="quickDelete('3days')">最近3天</button>
        <button @click="quickDelete('7days')">最近7天</button>
        <button @click="quickDelete('14days')">最近14天</button>
        <button @click="quickDelete('30days')">最近30天</button>
        <button @click="quickDelete('60days')">最近60天</button>
        <button @click="quickDelete('90days')">最近90天</button>
        <button @click="quickDelete('180days')">最近半年</button>
        <button @click="quickDelete('365days')">最近一年</button>
        <button @click="deleteAll" class="danger-btn">清除全部</button>
      </div>
    </div>
    
    <div class="section">
      <h4>自定义日期范围</h4>
      <div class="date-range">
        <input type="text" v-model="startDate" placeholder="yyyy/mm/dd" maxlength="10" @input="onDateInput">
        <span>至</span>
        <input type="text" v-model="endDate" placeholder="yyyy/mm/dd" maxlength="10" @input="onDateInput">
        <button @click="deleteRange" :disabled="!dateValid" :title="dateError">删除</button>
      </div>
      <div v-if="dateError" class="date-error">{{ dateError }}</div>
    </div>
    
    <div class="section">
      <h4>自动清理</h4>
      <div class="auto-cleanup">
        <input type="number" v-model.number="cleanupDays" min="7" max="365">
        <span>天前的记录</span>
        <button @click="saveCleanupSettings">保存</button>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  data() {
    return {
      startDate: '',
      endDate: '',
      cleanupDays: 30,
      dateError: ''
    }
  },
  computed: {
    dateValid() {
      this.dateError = ''
      const s = this.startDate.trim(), e = this.endDate.trim()
      if (!s || !e) return false
      const pat = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/
      const sm = s.match(pat), em = e.match(pat)
      if (!sm) { this.dateError = '开始日期格式应为 yyyy/mm/dd' ; return false }
      if (!em) { this.dateError = '结束日期格式应为 yyyy/mm/dd' ; return false }
      if (parseInt(sm[2]) > 12 || parseInt(em[2]) > 12) { this.dateError = '月份不能超过12' ; return false }
      if (parseInt(sm[3]) > 31 || parseInt(em[3]) > 31) { this.dateError = '日期不能超过31' ; return false }
      if (s > e) { this.dateError = '开始日期不能晚于结束日期' ; return false }
      return true
    }
  },
  mounted() {
    this.loadCleanupSettings()
  },
  methods: {
    async quickDelete(type) {
      const labels = { '30min': '半小时', '60min': '一小时', today: '今天', yesterday: '昨天', '3days': '最近3天', '7days': '最近7天', '14days': '最近14天', '30days': '最近30天', '60days': '最近60天', '90days': '最近90天', '180days': '最近半年', '365days': '最近一年' }
      if (!confirm(`确定删除${labels[type]}的记录吗？此操作同时清除AI记忆。`)) return

      try {
        if (type === '30min') {
          await api.delete('/chat/manage/recent/30')
        } else if (type === '60min') {
          await api.delete('/chat/manage/recent/60')
        } else if (type === 'today') {
          const today = new Date().toISOString().slice(0,10)
          await api.delete('/chat/manage/range', { data: { start: today, end: today } })
        } else if (type === 'yesterday') {
          const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0,10)
          await api.delete('/chat/manage/range', { data: { start: yesterday, end: yesterday } })
        } else {
          const days = parseInt(type.replace('days',''))
          await api.delete(`/chat/manage/older-than/${days}`)
        }
        this.$emit('changed')
      } catch (err) {
        console.error('删除失败', err)
        alert('删除失败')
      }
    },
    async deleteAll() {
      if (!confirm('确定清除全部聊天记录和AI记忆？此操作不可恢复！')) return
      try {
        await api.delete('/chat/manage/all')
        this.$emit('changed')
      } catch (err) {
        console.error('清除失败', err)
        alert('清除失败')
      }
    },
    onDateInput() { this.dateError = '' },
    async deleteRange() {
      if (!this.dateValid) return
      const norm = (d) => {
        const [y, m, d_] = d.trim().match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/).slice(1)
        return `${y}/${m.padStart(2,'0')}/${d_.padStart(2,'0')}`
      }
      const start = norm(this.startDate), end = norm(this.endDate)
      if (!confirm(`确定删除 ${start} 至 ${end} 的聊天记录和AI记忆吗？`)) return
      try {
        await api.delete('/chat/manage/range', { data: { start, end } })
        this.$emit('changed')
        this.startDate = ''; this.endDate = ''
        alert('已删除')
      } catch (err) {
        console.error('删除失败', err)
        alert('删除失败')
      }
    },
    async loadCleanupSettings() {
      try {
        const res = await api.get('/chat/manage/cleanup-settings')
        this.cleanupDays = res.data.auto_cleanup_days
      } catch (err) {
        console.error('加载设置失败', err)
      }
    },
    async saveCleanupSettings() {
      try {
        await api.post('/chat/manage/cleanup-settings', { days: this.cleanupDays })
        alert('自动清理设置已保存')
      } catch (err) {
        console.error('保存失败', err)
      }
    }
  }
}
</script>

<style scoped>
.chat-manage {
  padding: 10px;
}
.section {
  margin-bottom: 20px;
}
.section h4 {
  margin: 0 0 10px 0;
  color: #4e89ae;
  font-size: 14px;
}
.quick-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.quick-buttons button {
  background: #2c3e50;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  color: white;
  cursor: pointer;
  font-size: 12px;
}
.date-range { display: flex; align-items: center; gap: 8px; }
.date-range input[type="text"] { width: 100px; padding: 6px 8px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.1); font-size: 13px; font-family: monospace; text-align: center; outline: none; }
.date-range input[type="text"]:focus { border-color: #4e89ae; }
.date-error { color: #e74c3c; font-size: 11px; margin-top: 6px; }
.quick-buttons button:hover {
  background: #4e89ae;
}
.danger-btn { background: #e74c3c !important; }
.danger-btn:hover { background: #c0392b !important; }
.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.date-range input {
  padding: 6px;
  border-radius: 6px;
  border: 1px solid #2c3e50;
  background: #1a1a2e;
  color: white;
}
.date-range button {
  background: #4e89ae;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  color: white;
  cursor: pointer;
}
.auto-cleanup {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.auto-cleanup input {
  width: 80px;
  padding: 6px;
  border-radius: 6px;
  border: 1px solid #2c3e50;
  background: #1a1a2e;
  color: white;
}
.auto-cleanup button {
  background: #4e89ae;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  color: white;
  cursor: pointer;
}
</style>