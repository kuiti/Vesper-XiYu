<template>
  <div class="page-view">
    <PageHeader title="记忆" desc="长期记忆、关系图谱、AI 日记、用户画像" />
    <div class="page-body">
      <div class="mem-layout">
        <div class="page-card mem-main">
          <h3>记忆保险箱</h3>
          <MemoryVault :aiName="aiName" />
        </div>
        <div class="page-card mem-side">
          <h3>关系图</h3>
          <MemoryGraph :aiName="aiName" />
        </div>
      </div>

      <CollapsibleSection title="AI 日记" :defaultOpen="false">
        <button class="btn" @click="genDiary" :disabled="diaryGenerating">{{ diaryGenerating ? '生成中...' : '生成今日日记' }}</button>
        <div v-if="diaryContent" class="mem-diary">{{ diaryContent }}</div>
      </CollapsibleSection>

      <CollapsibleSection title="用户画像" :defaultOpen="false">
        <div style="display:flex;gap:8px;margin-bottom:8px">
          <button class="btn" @click="loadProfile" :disabled="profileLoading">{{ profileLoading ? '加载中...' : '刷新画像' }}</button>
          <button class="btn-s" @click="extractProfile" :disabled="extracting">{{ extracting ? '提取中...' : '自动提取' }}</button>
        </div>
        <div v-if="profileError" class="err">{{ profileError }}</div>
        <div v-if="profileKeys.length" class="profile-list">
          <div v-for="pk in profileKeys" :key="pk" class="profile-item">
            <span class="pk">{{ pk }}</span>
            <span class="pv">{{ profileItems[pk] }}</span>
          </div>
        </div>
        <div v-else-if="!profileLoading" class="page-hint">点击「刷新画像」查看 AI 对你的了解</div>
      </CollapsibleSection>
    </div>
  </div>
</template>

<script>
import PageHeader from './common/PageHeader.vue'
import CollapsibleSection from './common/CollapsibleSection.vue'
import MemoryVault from './MemoryVault.vue'
import MemoryGraph from './MemoryGraph.vue'
import api from '../api'

export default {
  props: { aiName: { type: String, default: '佐仓' } },
  components: { PageHeader, CollapsibleSection, MemoryVault, MemoryGraph },
  data() { return { diaryGenerating: false, diaryContent: '', profileLoading: false, extracting: false, profileItems: {}, profileError: '' } },
  computed: {
    profileKeys() { return Object.keys(this.profileItems) },
  },
  methods: {
    async genDiary() { this.diaryGenerating = true; try { const r = await api.post('/memory/diary/generate'); if (r.data.ok) this.diaryContent = r.data.content } catch (e) {} this.diaryGenerating = false },
    async loadProfile() { this.profileLoading = true; this.profileError = ''; try { const r = await api.get('/profile/'); this.profileItems = r.data.profile || {} } catch (e) { this.profileError = '加载失败' } finally { this.profileLoading = false } },
    async extractProfile() { this.extracting = true; this.profileError = ''; try { await api.post('/profile/extract'); await this.loadProfile() } catch (e) { this.profileError = '提取失败' } finally { this.extracting = false } },
  }
}
</script>

<style scoped>
.mem-layout { display: flex; gap: 16px; align-items: flex-start; }
.mem-main { flex: 1; min-width: 0; }
.mem-side { width: 340px; flex-shrink: 0; }
.profile-list { max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 3px; }
.profile-item { display: flex; gap: 8px; font-size: 12px; padding: 4px 6px; border-radius: 4px; }
.profile-item:hover { background: var(--accent-muted); }
.pk { color: var(--accent-primary); font-weight: 600; min-width: 80px; flex-shrink: 0; }
.pv { color: var(--text-primary); word-break: break-all; }
.err { color: var(--status-error); font-size: 12px; }
.mem-diary { margin-top: 8px; padding: 10px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
@media (max-width: 900px) { .mem-layout { flex-direction: column; } .mem-side { width: auto; } }
</style>
