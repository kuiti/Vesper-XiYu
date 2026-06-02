<template>
  <transition name="tl-slide">
    <div v-if="show" class="tl-side-card">
      <div class="tl-header">今天了解到的你</div>
      <div v-if="data" class="tl-items">
        <span v-for="p in data.new_profile" :key="p.key" class="tl-chip">{{ p.key }}: {{ p.value }}</span>
        <span v-if="!data.new_profile?.length" class="tl-empty">暂无新发现</span>
      </div>
      <button class="tl-close" @click="dismiss">×</button>
    </div>
  </transition>
</template>

<script>
export default {
  props: { data: { type: Object, default: () => ({ new_profile: [], new_summaries: [] }) } },
  emits: ['close'],
  data() { return { show: false, _dismissed: false } },
  mounted() {
    const hash = JSON.stringify(this.data?.new_profile || [])
    const lastHash = localStorage.getItem('tl_last_hash') || ''
    if (hash && hash !== lastHash && (this.data?.new_profile || []).some(p => !/游戏|2048|扫雷|贪吃蛇|得分|最高分/.test(p.key + p.value))) {
      setTimeout(() => { this.show = true }, 2000)
    }
  },
  methods: {
    dismiss() {
      this.show = false
      localStorage.setItem('tl_last_hash', JSON.stringify(this.data?.new_profile || []))
      this.$emit('close')
    }
  }
}
</script>

<style scoped>
.tl-side-card {
  position: fixed; right: 16px; top: 60px; width: 240px; max-height: 70vh; overflow-y: auto;
  padding: 14px; background: var(--sb); border: 1px solid var(--border); border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,.3); z-index: 100; animation: tlIn .3s ease;
}
@keyframes tlIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
.tl-header { font-size: 12px; color: var(--tc2); margin-bottom: 8px; font-weight: 500; }
.tl-items { display: flex; flex-wrap: wrap; gap: 6px; }
.tl-chip { padding: 3px 10px; background: rgba(255,255,255,.04); border-radius: 10px; font-size: 11px; color: var(--tc); }
.tl-empty { font-size: 11px; color: var(--tc2); opacity: .6; }
.tl-close { position: absolute; top: 8px; right: 10px; background: none; border: none; color: var(--tc2); cursor: pointer; font-size: 16px; }
</style>
