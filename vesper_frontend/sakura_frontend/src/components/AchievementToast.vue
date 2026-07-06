<template>
  <div class="ach-toast">
    <span class="ach-name">{{ data.name }}</span>
    <span class="ach-desc">{{ data.description }}</span>
  </div>
</template>

<script>
export default { props: { data: Object } }
</script>

<style scoped>
.ach-toast { position: fixed; top: 16px; left: 50%; transform: translateX(-50%); z-index: 3000; background: var(--surface-sidebar); border: 1px solid var(--border-default); border-radius: 8px; padding: 12px 24px; display: flex; gap: 12px; align-items: center; color: var(--text-primary); animation: achIn .4s ease; box-shadow: 0 4px 16px rgba(0,0,0,.4); }
.ach-name { font-size: 14px; font-weight: 600; white-space: nowrap; }
.ach-desc { font-size: 12px; color: var(--text-secondary); }
@keyframes achIn { from { opacity: 0; transform: translateX(-50%) translateY(-12px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
</style>
