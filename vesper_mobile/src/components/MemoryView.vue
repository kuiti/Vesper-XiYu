<template>
  <div class="panel-view">
    <div class="panel-header">
      <h2>记忆</h2>
    </div>

    <!-- Relationship -->
    <div v-if="relationship.intimacy || relationship.trust" class="memory-section">
      <div class="section-title">关系</div>
      <div class="rel-bars">
        <div class="rel-bar">
          <div class="rel-label">
            <span>亲密度</span>
            <span class="rel-value">{{ Math.round(relationship.intimacy || 0) }}</span>
          </div>
          <div class="rel-track">
            <div class="rel-fill intimacy" :style="{ width: Math.min(100, relationship.intimacy || 0) + '%' }"></div>
          </div>
        </div>
        <div class="rel-bar">
          <div class="rel-label">
            <span>信任度</span>
            <span class="rel-value">{{ Math.round(relationship.trust || 0) }}</span>
          </div>
          <div class="rel-track">
            <div class="rel-fill trust" :style="{ width: Math.min(100, relationship.trust || 0) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- User Profile -->
    <div class="memory-section">
      <div class="section-title">用户画像</div>
      <div v-if="Object.keys(profile).length" class="profile-grid">
        <div v-for="(v, k) in profile" :key="k" class="profile-item">
          <span class="profile-key">{{ k }}</span>
          <span class="profile-val">{{ typeof v === 'object' ? JSON.stringify(v) : v }}</span>
        </div>
      </div>
      <div v-else class="empty-msg">暂无画像数据</div>
    </div>

    <!-- Shared Moments -->
    <div class="memory-section">
      <div class="section-title">共同回忆</div>
      <div v-for="m in moments" :key="m.id" class="moment-card">
        <div class="moment-type">{{ m.moment_type }}</div>
        <div class="moment-text">{{ m.text }}</div>
      </div>
      <div v-if="!moments.length" class="empty-msg">暂无共同回忆</div>
    </div>

    <!-- Episodes -->
    <div class="memory-section">
      <div class="section-title">情景记忆</div>
      <div v-for="e in episodes" :key="e.id" class="episode-card" @click="toggleEpisode(e)">
        <div class="episode-header">
          <span class="episode-date">{{ (e.start_time || '').slice(0, 10) }}</span>
          <span class="episode-emotion">{{ e.emotion || '' }}</span>
        </div>
        <div class="episode-topic">{{ e.topic_summary }}</div>
        <div v-if="e._expanded && e.key_points" class="episode-detail">
          <div v-for="(kp, i) in parseKeyPoints(e.key_points)" :key="i" class="key-point">{{ kp }}</div>
        </div>
      </div>
      <div v-if="!episodes.length" class="empty-msg">暂无情景记忆</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/appStore.js'
import api from '../api.js'

const app = useAppStore()
const profile = ref({})
const moments = ref([])
const episodes = ref([])
const relationship = ref({})

function toggleEpisode(e) {
  e._expanded = !e._expanded
}

function parseKeyPoints(kp) {
  if (Array.isArray(kp)) return kp
  if (typeof kp === 'string') {
    try { return JSON.parse(kp) } catch { return [kp] }
  }
  return []
}

onMounted(async () => {
  try {
    const res = await api.get('/memory/vault')
    profile.value = res.data?.profile || {}
  } catch {}
  try {
    const res = await api.get('/episodes/timeline', { params: { days: 14 } })
    episodes.value = (res.data || []).map(e => ({ ...e, _expanded: false }))
  } catch {}
  try {
    const res = await api.get('/shared-moments/')
    moments.value = res.data || []
  } catch {}
  try {
    const res = await api.get('/relationship/')
    relationship.value = res.data || {}
  } catch {}
})
</script>
