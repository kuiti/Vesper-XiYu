<template>
  <div class="cs-card">
    <div class="cs-head" @click="open = !open" role="button" tabindex="0" @keydown.enter="open = !open">
      <span class="cs-arrow">▶</span>
      <span class="cs-title">{{ title }}</span>
      <span class="cs-count" v-if="count !== undefined">{{ count }}</span>
    </div>
    <div class="cs-body" v-show="open">
      <slot />
    </div>
  </div>
</template>

<script>
export default {
  props: { title: String, count: Number, defaultOpen: { type: Boolean, default: true } },
  data() { return { open: this.defaultOpen } },
}
</script>

<style scoped>
.cs-card { background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 10px; overflow: hidden; }
.cs-card + .cs-card { margin-top: 10px; }
.cs-head { display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 14px 16px; user-select: none; -webkit-user-select: none; transition: background .1s; }
.cs-head:hover { background: var(--accent-muted); }
.cs-arrow { font-size: 8px; color: var(--text-secondary); transition: transform .15s; opacity: .5; flex-shrink: 0; }
.cs-open .cs-arrow { transform: rotate(90deg); opacity: .8; }
.cs-title { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.cs-count { margin-left: auto; font-size: 11px; color: var(--text-secondary); opacity: .6; }
.cs-body { padding: 0 16px 14px; }
</style>
