<template>
  <div class="panel-view">
    <div class="panel-title">/memory</div>

    <div class="setting-group">
      <div class="setting-label">User Profile</div>
      <div v-for="(v, k) in profile" :key="k" class="setting-row">
        <span class="setting-name">{{ k }}</span>
        <span class="setting-value">{{ v }}</span>
      </div>
      <div v-if="!Object.keys(profile).length" style="color: var(--text-muted); font-size: 13px;">No profile data yet</div>
    </div>

    <div class="setting-group">
      <div class="setting-label">Shared Moments</div>
      <div v-for="m in moments" :key="m.id" class="card" style="margin-bottom: 8px;">
        <div class="card-title">{{ m.moment_type }}</div>
        <div class="card-desc">{{ m.text }}</div>
      </div>
      <div v-if="!moments.length" style="color: var(--text-muted); font-size: 13px;">No shared moments yet</div>
    </div>

    <div class="setting-group">
      <div class="setting-label">Episodes</div>
      <div v-for="e in episodes" :key="e.id" class="card" style="margin-bottom: 8px;">
        <div class="card-title">{{ (e.start_time || '').slice(0, 10) }}</div>
        <div class="card-desc">{{ e.topic_summary }}</div>
      </div>
      <div v-if="!episodes.length" style="color: var(--text-muted); font-size: 13px;">No episodes yet</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api.js'

const profile = ref({})
const moments = ref([])
const episodes = ref([])

onMounted(async () => {
  try {
    const res = await api.get('/memory/vault')
    profile.value = res.data?.profile || {}
  } catch {}
  try {
    const res = await api.get('/episodes/timeline', { params: { days: 14 } })
    episodes.value = res.data || []
  } catch {}
  try {
    const res = await api.get('/shared-moments/')
    moments.value = res.data || []
  } catch {}
})
</script>
