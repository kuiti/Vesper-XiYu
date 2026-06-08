// stores/global.js — 全局辅助数据（旧 App.vue 的零散状态）
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api.js'

export const useGlobalStore = defineStore('global', () => {
  const relationship = ref({})
  const emotionTrend = ref([])
  const assistantAvatarUrl = ref('')
  const userAvatarUrl = ref('')
  const ipCity = ref('')
  const ipCityShort = ref('')
  const conversationDays = ref(0)
  const totalMessages = ref(0)
  const timelineDates = ref([])
  const todayLearning = ref(null)

  async function loadAll() {
    await Promise.allSettled([
      loadRelationship(),
      loadEmotionTrend(),
      loadAvatars(),
      loadIpLocation(),
      loadTimelineDates(),
      loadTodayLearning(),
    ])
  }

  async function loadRelationship() {
    try { const r = await api.get('/relationship/'); relationship.value = r.data } catch (e) {}
  }
  async function loadEmotionTrend() {
    try { const r = await api.get('/emotion/trend?days=14'); emotionTrend.value = r.data || [] } catch (e) {}
  }
  async function loadAvatars() {
    try { const r = await api.get('/avatar/assistant'); if (r.data?.url) assistantAvatarUrl.value = r.data.url } catch (e) {}
    try { const r = await api.get('/avatar/user'); if (r.data?.url) userAvatarUrl.value = r.data.url } catch (e) {}
  }
  async function loadIpLocation() {
    try { const r = await api.get('/location/ip'); if (r.data?.city) { ipCity.value = r.data.city; ipCityShort.value = r.data.city } } catch (e) {}
  }
  async function loadTimelineDates() {
    try { const r = await api.get('/chat/history/dates'); const months = r.data?.months || []; timelineDates.value = months.flatMap(m => (m.dates || []).map(d => d.date)) } catch (e) {}
  }
  async function loadTodayLearning() {
    try { const r = await api.get('/memory/today-learning'); if (r.data?.has_new) todayLearning.value = r.data } catch (e) {}
  }

  return {
    relationship, emotionTrend, assistantAvatarUrl, userAvatarUrl,
    ipCity, ipCityShort, conversationDays, totalMessages,
    timelineDates, todayLearning,
    loadAll,
  }
})
