<template>
  <div class="weather-card" v-if="data">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
      <span style="font-size: 20px;">{{ data.weather }}</span>
      <span style="font-size: 18px; font-weight: 600;">{{ data.temp }}C</span>
    </div>
    <div style="font-size: 12px; color: var(--text-secondary);">
      {{ data.city }} | {{ data.wind }} | {{ data.humidity }}%
    </div>
  </div>
</template>

<script setup>
defineProps({ data: Object })
</script>

<style scoped>
.weather-card {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  max-width: 280px;
}
</style>
