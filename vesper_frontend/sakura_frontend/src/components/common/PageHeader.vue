<template>
  <div class="page-header">
    <div class="ph-bar"></div>
    <div class="ph-text">
      <h2>{{ title }}</h2>
      <p v-if="desc">{{ desc }}</p>
    </div>
  </div>
</template>

<script>
export default {
  props: { title: String, desc: String },
}
</script>

<style scoped>
.page-header { display: flex; align-items: center; gap: 12px; padding: 24px 28px 16px; flex-shrink: 0; }
.ph-bar { width: 3px; height: 22px; background: var(--accent-primary); border-radius: 2px; flex-shrink: 0; }
.ph-text h2 { font-size: 17px; font-weight: 600; color: var(--text-primary); margin: 0; letter-spacing: -.01em; }
.ph-text p { font-size: 12px; color: var(--text-secondary); margin: 3px 0 0; line-height: 1.4; }
</style>
