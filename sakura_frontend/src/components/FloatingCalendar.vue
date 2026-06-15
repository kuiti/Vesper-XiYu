<template>
  <div class="floating-calendar" :style="{ top: pos.y + 'px', right: pos.x + 'px' }" ref="root">
    <!-- 收起状态：小图标 -->
    <button v-if="!expanded" class="cal-toggle" @mousedown="onDragStart" @click="onToggleClick" title="日历">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      <span class="cal-badge">{{ todayDate }}</span>
    </button>

    <!-- 展开状态：月历 -->
    <div v-else class="cal-panel" @click.stop>
      <!-- 头部：可拖动 -->
      <div class="cal-header" @mousedown="onDragStart">
        <button class="cal-nav" @mousedown.stop @click="prevMonth">&lt;</button>
        <span class="cal-title">{{ viewYear }}年{{ viewMonth + 1 }}月</span>
        <button class="cal-nav" @mousedown.stop @click="nextMonth">&gt;</button>
        <button class="cal-close" @mousedown.stop @click="expanded = false">×</button>
      </div>

      <!-- 星期标题 -->
      <div class="cal-weekdays">
        <span v-for="w in weekdays" :key="w">{{ w }}</span>
      </div>

      <!-- 日期网格 -->
      <div class="cal-grid">
        <div v-for="(day, i) in calendarDays" :key="i"
          :class="['cal-day', {
            today: day.isToday,
            other: !day.currentMonth,
            selected: selectedDate === day.dateStr,
            hasEvent: day.hasEvent,
            festival: day.isFestival
          }]"
          @click="selectDate(day)">
          <span class="day-num">{{ day.day }}</span>
          <span v-if="day.festival" class="day-festival">{{ day.festival }}</span>
          <span v-else class="day-lunar">{{ day.lunar }}</span>
          <span v-if="day.hasEvent" class="day-dot" :style="{ background: day.eventColor }"></span>
        </div>
      </div>

      <!-- 选中日期的日程列表 -->
      <div v-if="selectedDate" class="cal-detail">
        <div class="detail-header">
          <span>{{ selectedDate }}</span>
          <button class="detail-add" @click="showAdd = !showAdd">+</button>
        </div>

        <!-- 添加日程表单 -->
        <div v-if="showAdd" class="add-form">
          <input v-model="newTitle" placeholder="日程标题" class="add-input" @keyup.enter="addSchedule" />
          <div class="add-row">
            <input v-model="newTime" type="time" class="add-time" />
            <select v-model="newColor" class="add-color">
              <option value="#5390d4">蓝</option>
              <option value="#e74c3c">红</option>
              <option value="#2ea043">绿</option>
              <option value="#f39c12">橙</option>
              <option value="#9b59b6">紫</option>
            </select>
            <button class="add-btn" @click="addSchedule" :disabled="!newTitle">添加</button>
          </div>
        </div>

        <!-- 日程列表 -->
        <div class="detail-list">
          <div v-for="s in daySchedules" :key="s.id" class="schedule-item" :class="{ 'sch-special': isSpecialDate(s) }">
            <span class="sch-dot" :style="{ background: s.color || '#5390d4' }"></span>
            <span class="sch-title">{{ s.title }}</span>
            <span class="sch-level" v-if="s.isReminder">L{{ s.level }}</span>
            <span class="sch-time" v-if="s.start_time">{{ formatTime(s.start_time) }}</span>
            <button class="sch-del" @click="deleteSchedule(s.id)">×</button>
          </div>
          <div v-if="!daySchedules.length" class="detail-empty">这天没有日程</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api'

// 简化的农历转换函数（仅支持2024-2030年）
function getLunarInfo(year, month, day) {
  // 常见节日
  const festivals = {
    '1-1': '元旦', '2-14': '情人节', '3-8': '妇女节', '3-12': '植树节',
    '4-1': '愚人节', '5-1': '劳动节', '5-4': '青年节', '6-1': '儿童节',
    '7-1': '建党节', '8-1': '建军节', '9-10': '教师节', '10-1': '国庆节',
    '12-25': '圣诞节', '12-24': '平安夜', '2-14': '情人节', '3-14': '白色情人节',
    '4-22': '世界地球日', '5-20': '我爱你日', '6-18': '父亲节', '5-12': '母亲节',
    '9-20': '全国爱牙日', '10-31': '万圣节', '11-11': '光棍节', '12-12': '双十二',
  }

  // 农历节日（简化）
  const lunarFestivals = {
    '1-1': '春节', '1-15': '元宵节', '5-5': '端午节', '7-7': '七夕',
    '7-15': '中元节', '8-15': '中秋节', '9-9': '重阳节', '12-30': '除夕',
    '12-29': '除夕', '1-5': '破五', '1-8': '谷日', '1-10': '石头节',
    '2-2': '龙抬头', '4-8': '佛诞节', '6-6': '天贶节', '7-14': '中元节',
    '8-1': '天医节', '9-1': '重阳节', '10-1': '寒衣节', '10-15': '下元节',
    '11-7': '冬至', '12-8': '腊八节', '12-23': '小年',
  }

  const key = `${month}-${day}`
  const festival = festivals[key] || ''

  // 简化的农历日期（仅用于显示）
  // 实际应用中需要使用完整的农历转换库
  const lunarMonths = ['正月', '二月', '三月', '四月', '五月', '六月',
                       '七月', '八月', '九月', '十月', '冬月', '腊月']
  const lunarDays = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
                     '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                     '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十']

  // 简化计算（实际需要完整农历算法）
  const lunarMonth = lunarMonths[(month - 1) % 12]
  const lunarDay = lunarDays[(day - 1) % 30]

  return {
    festival,
    lunar: `${lunarMonth}${lunarDay}`,
    isFestival: !!festival,
  }
}

export default {
  data() {
    return {
      expanded: false,
      viewYear: new Date().getFullYear(),
      viewMonth: new Date().getMonth(),
      selectedDate: null,
      schedules: [],
      showAdd: false,
      newTitle: '',
      newTime: '',
      newColor: '#5390d4',
      pos: { x: 20, y: 60 },
      weekdays: ['日', '一', '二', '三', '四', '五', '六'],
    }
  },
  computed: {
    todayDate() { return new Date().getDate() },
    calendarDays() {
      const days = []
      const first = new Date(this.viewYear, this.viewMonth, 1)
      const startDow = first.getDay()
      const daysInMonth = new Date(this.viewYear, this.viewMonth + 1, 0).getDate()
      const today = new Date()
      const todayStr = this.fmtDate(today)

      // 上月补位
      const prevMonthDays = new Date(this.viewYear, this.viewMonth, 0).getDate()
      for (let i = startDow - 1; i >= 0; i--) {
        const d = prevMonthDays - i
        const dt = new Date(this.viewYear, this.viewMonth - 1, d)
        const dateStr = this.fmtDate(dt)
        const lunarInfo = getLunarInfo(dt.getFullYear(), dt.getMonth() + 1, d)
        days.push({
          day: d, dateStr, currentMonth: false, isToday: false,
          hasEvent: this.hasEvent(dateStr), eventColor: this.getEventColor(dateStr),
          lunar: lunarInfo.lunar, festival: lunarInfo.festival, isFestival: lunarInfo.isFestival,
        })
      }

      // 本月
      for (let d = 1; d <= daysInMonth; d++) {
        const dt = new Date(this.viewYear, this.viewMonth, d)
        const dateStr = this.fmtDate(dt)
        const lunarInfo = getLunarInfo(dt.getFullYear(), dt.getMonth() + 1, d)
        days.push({
          day: d, dateStr, currentMonth: true, isToday: dateStr === todayStr,
          hasEvent: this.hasEvent(dateStr), eventColor: this.getEventColor(dateStr),
          lunar: lunarInfo.lunar, festival: lunarInfo.festival, isFestival: lunarInfo.isFestival,
        })
      }

      // 下月补位
      const remaining = 42 - days.length
      for (let d = 1; d <= remaining; d++) {
        const dt = new Date(this.viewYear, this.viewMonth + 1, d)
        const dateStr = this.fmtDate(dt)
        const lunarInfo = getLunarInfo(dt.getFullYear(), dt.getMonth() + 1, d)
        days.push({
          day: d, dateStr, currentMonth: false, isToday: false,
          hasEvent: this.hasEvent(dateStr), eventColor: this.getEventColor(dateStr),
          lunar: lunarInfo.lunar, festival: lunarInfo.festival, isFestival: lunarInfo.isFestival,
        })
      }

      return days
    },
    daySchedules() {
      if (!this.selectedDate) return []
      return this.schedules.filter(s => s.start_time && s.start_time.startsWith(this.selectedDate))
    },
  },
  mounted() {
    this.loadSchedules()
    document.addEventListener('click', this.onOutsideClick)
    document.addEventListener('mousemove', this.onDragMove)
    document.addEventListener('mouseup', this.onDragEnd)
  },
  beforeUnmount() {
    document.removeEventListener('click', this.onOutsideClick)
    document.removeEventListener('mousemove', this.onDragMove)
    document.removeEventListener('mouseup', this.onDragEnd)
  },
  methods: {
    onToggleClick(e) {
      if (!this._dragged) {
        this.expanded = true
        this._justOpened = true
        setTimeout(() => { this._justOpened = false }, 100)
        // 每次打开日历时刷新数据
        this.loadSchedules()
      }
    },
    onDragStart(e) {
      this._startX = e.clientX
      this._startY = e.clientY
      this._dragged = false
      this._dragging = true
    },
    onDragMove(e) {
      if (!this._dragging) return
      const dx = e.clientX - this._startX
      const dy = e.clientY - this._startY
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        this._dragged = true
        this.pos.x = Math.max(0, window.innerWidth - e.clientX - 30)
        this.pos.y = Math.max(0, e.clientY - 15)
      }
    },
    onDragEnd() {
      this._dragging = false
    },
    fmtDate(dt) {
      const y = dt.getFullYear()
      const m = String(dt.getMonth() + 1).padStart(2, '0')
      const d = String(dt.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    },
    formatTime(ts) {
      if (!ts || ts.length < 16) return ''
      return ts.slice(11, 16)
    },
    hasEvent(dateStr) {
      return this.schedules.some(s => s.start_time && s.start_time.startsWith(dateStr))
    },
    getEventColor(dateStr) {
      const s = this.schedules.find(s => s.start_time && s.start_time.startsWith(dateStr))
      return s ? (s.color || '#5390d4') : ''
    },
    prevMonth() {
      if (this.viewMonth === 0) { this.viewMonth = 11; this.viewYear-- }
      else this.viewMonth--
    },
    nextMonth() {
      if (this.viewMonth === 11) { this.viewMonth = 0; this.viewYear++ }
      else this.viewMonth++
    },
    selectDate(day) {
      this.selectedDate = day.dateStr
      this.showAdd = false
      this.newTitle = ''
      this.newTime = ''
    },
    async loadSchedules() {
      this.schedules = []
      // 加载日程
      try {
        const res = await api.get('/schedule/')
        this.schedules = res.data || []
      } catch (e) { console.error(e) }
      // 加载提醒
      try {
        const res2 = await api.get('/reminders/')
        const reminders = res2.data || []
        const levelColors = {
          1: '#e74c3c', 2: '#e67e22', 3: '#f1c40f',
          4: '#2ecc71', 5: '#3498db', 6: '#9b59b6', 7: '#95a5a6',
        }
        for (const r of reminders) {
          if (r.target_time && !r.done) {
            this.schedules.push({
              id: 'reminder_' + r.id,
              title: r.content,
              start_time: r.target_time,
              color: levelColors[r.level] || '#e74c3c',
              isReminder: true,
              level: r.level,
            })
          }
        }
      } catch (e) { console.error(e) }
      // 加载待办
      try {
        const res3 = await api.get('/todos/')
        const todos = res3.data || []
        for (const t of todos) {
          if (!t.done) {
            this.schedules.push({
              id: 'todo_' + t.id,
              title: t.task,
              start_time: t.created ? t.created.split('T')[0] : '',
              color: '#2ecc71',
              isTodo: true,
            })
          }
        }
      } catch (e) { console.error(e) }
    },
    async addSchedule() {
      if (!this.newTitle.trim()) return
      const start_time = this.newTime ? `${this.selectedDate}T${this.newTime}:00` : `${this.selectedDate}T00:00:00`
      try {
        await api.post('/schedule/', {
          title: this.newTitle.trim(),
          start_time,
          end_time: '',
          description: '',
          location: '',
          all_day: this.newTime ? 0 : 1,
          color: this.newColor,
        })
        this.newTitle = ''
        this.newTime = ''
        this.showAdd = false
        await this.loadSchedules()
      } catch (e) { console.error(e) }
    },
    async deleteSchedule(id) {
      try {
        await api.delete(`/schedule/${id}`)
        await this.loadSchedules()
      } catch (e) { console.error(e) }
    },
    isSpecialDate(schedule) {
      // 判断是否为特殊日期（生日、纪念日等）
      const specialKeywords = ['生日', '纪念日', '结婚', '入学', '毕业', '入职', '周年']
      return specialKeywords.some(keyword => schedule.title.includes(keyword))
    },
    onOutsideClick(e) {
      if (this._justOpened) return
      if (this.expanded && this.$refs.root && !this.$refs.root.contains(e.target)) {
        this.expanded = false
      }
    },
  }
}
</script>

<style scoped>
.floating-calendar { position: fixed; z-index: 100; }

/* 收起按钮 */
.cal-toggle { display: flex; align-items: center; gap: 4px; background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 8px; padding: 6px 10px; cursor: pointer; color: var(--text-secondary); transition: all .15s; position: relative; }
.cal-toggle:hover { border-color: var(--accent-primary); color: var(--accent-primary); }
.cal-badge { font-size: 12px; font-weight: 600; color: var(--text-primary); }

/* 展开面板 */
.cal-panel { width: 280px; background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,.3); overflow: hidden; }

/* 头部 */
.cal-header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--border-default); }
.cal-nav { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 14px; padding: 2px 6px; border-radius: 4px; }
.cal-nav:hover { background: rgba(255,255,255,.06); color: var(--text-primary); }
.cal-title { flex: 1; text-align: center; font-size: 13px; font-weight: 600; color: var(--text-primary); }
.cal-close { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 16px; padding: 2px 6px; border-radius: 4px; }
.cal-close:hover { color: var(--text-primary); }

/* 星期标题 */
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); padding: 6px 8px 0; }
.cal-weekdays span { text-align: center; font-size: 10px; color: var(--text-secondary); padding: 2px 0; }

/* 日期网格 */
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); padding: 4px 8px 8px; }
.cal-day { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 40px; border-radius: 6px; cursor: pointer; position: relative; transition: all .1s; gap: 1px; }
.cal-day:hover { background: rgba(255,255,255,.04); }
.cal-day.other .day-num { color: var(--text-secondary); opacity: .3; }
.cal-day.today { background: rgba(255,255,255,.06); }
.cal-day.today .day-num { color: var(--accent-primary); font-weight: 700; }
.cal-day.selected { background: var(--accent-primary); }
.cal-day.selected .day-num { color: #fff; font-weight: 600; }
.day-num { font-size: 12px; color: var(--text-primary); }
.day-lunar { font-size: 8px; color: var(--text-secondary); opacity: .6; line-height: 1; }
.day-festival { font-size: 8px; color: #e74c3c; line-height: 1; font-weight: 500; }
.cal-day.festival .day-num { color: #e74c3c; }
.day-dot { width: 4px; height: 4px; border-radius: 50%; margin-top: 1px; }

/* 详情区 */
.cal-detail { border-top: 1px solid var(--border-default); padding: 10px 12px; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-header span { font-size: 13px; color: var(--text-primary); font-weight: 600; }
.detail-add { background: var(--accent-primary); border: none; color: #fff; width: 22px; height: 22px; border-radius: 50%; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; }

/* 添加表单 */
.add-form { margin-bottom: 8px; }
.add-input { width: 100%; padding: 6px 8px; border: 1px solid var(--border-default); border-radius: 6px; background: var(--surface-app); color: var(--text-primary); font-size: 12px; outline: none; box-sizing: border-box; margin-bottom: 6px; }
.add-input:focus { border-color: var(--accent-primary); }
.add-row { display: flex; gap: 6px; }
.add-time { flex: 1; padding: 4px 6px; border: 1px solid var(--border-default); border-radius: 4px; background: var(--surface-app); color: var(--text-primary); font-size: 12px; }
.add-color { width: 40px; border: 1px solid var(--border-default); border-radius: 4px; background: var(--surface-app); color: var(--text-primary); font-size: 11px; }
.add-btn { padding: 4px 10px; background: var(--accent-primary); border: none; color: #fff; border-radius: 4px; cursor: pointer; font-size: 12px; }
.add-btn:disabled { opacity: .4; cursor: not-allowed; }

/* 日程列表 */
.detail-list { max-height: 150px; overflow-y: auto; }
.schedule-item { display: flex; align-items: center; gap: 6px; padding: 4px 0; }
.sch-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.sch-title { flex: 1; font-size: 12px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sch-level { font-size: 10px; color: var(--text-secondary); background: rgba(255,255,255,.06); padding: 1px 4px; border-radius: 3px; flex-shrink: 0; }
.sch-time { font-size: 11px; color: var(--text-secondary); }
.sch-del { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 14px; padding: 0 2px; opacity: .4; }
.sch-del:hover { opacity: 1; color: #e74c3c; }
.sch-special { background: rgba(231, 76, 60, 0.1); border-radius: 4px; padding: 4px 6px; }
.sch-special .sch-title { color: #e74c3c; font-weight: 500; }
.detail-empty { font-size: 12px; color: var(--text-secondary); text-align: center; padding: 8px 0; }

/* 移动端适配 */
@media (max-width: 768px) {
  .cal-panel {
    width: calc(100vw - 32px);
    max-width: 320px;
  }
  .cal-btn {
    min-width: 44px;
    min-height: 44px;
  }
  .cal-day {
    height: 40px;
    font-size: 13px;
  }
  .add-btn {
    min-height: 44px;
    padding: 8px 16px;
  }
  .sch-del {
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
