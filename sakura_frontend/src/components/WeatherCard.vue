<template>
  <div class="weather-card">
    <div class="weather-header">
      <span class="weather-icon">{{ weatherIcon }}</span>
      <span class="weather-temp">{{ data.temp }}度</span>
      <span class="weather-desc">{{ data.weather }}</span>
    </div>
    <div class="weather-body">
      <div class="weather-detail">
        <span v-if="data.feels_like != null">体感 {{ data.feels_like }}度</span>
        <span v-if="data.humidity != null">湿度 {{ data.humidity }}%</span>
        <span v-if="data.wind_speed != null">
          {{ data.wind_direction || '' }}{{ data.wind_direction ? '风 ' : '' }}{{ data.wind_speed }}km/h
        </span>
      </div>
      <div v-if="data.forecast && data.forecast.length" class="weather-forecast">
        <div v-for="f in data.forecast" :key="f.label" class="forecast-item">
          <span class="forecast-label">{{ f.label }}</span>
          <span class="forecast-weather">{{ f.weather }}</span>
          <span class="forecast-temp">{{ f.low }}~{{ f.high }}度</span>
        </div>
      </div>
      <div v-if="data.suggestion" class="weather-suggestion">
        {{ data.suggestion }}
      </div>
    </div>
    <div class="weather-footer">
      <span class="weather-city">{{ data.city }}</span>
      <span class="weather-time">{{ pushTimeLabel }}</span>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    data: { type: Object, required: true }
  },
  computed: {
    weatherIcon() {
      const w = (this.data.weather || '').toString()
      if (w.includes('晴')) return '晴'
      if (w.includes('雷')) return '雷'
      if (w.includes('云') || w.includes('阴')) return '阴'
      if (w.includes('雨')) return '雨'
      if (w.includes('雪')) return '雪'
      if (w.includes('雾')) return '雾'
      if (w.includes('霾')) return '霾'
      if (w.includes('沙') || w.includes('尘')) return '沙'
      return '晴'
    },
    pushTimeLabel() {
      const h = this.data.push_hour
      if (h === 7) return '早安'
      if (h === 12) return '午安'
      if (h === 19) return '晚安'
      return ''
    }
  }
}
</script>

<style scoped>
.weather-card {
  background: linear-gradient(135deg, var(--ab, rgba(255,255,255,.06)), var(--bg, rgba(255,255,255,.02)));
  border: 1px solid var(--border, rgba(255,255,255,.08));
  border-radius: 14px;
  padding: 16px 20px;
  max-width: 320px;
  color: var(--tc, #ecf0f1);
}
.weather-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.weather-icon { font-size: 28px; }
.weather-temp { font-size: 24px; font-weight: 600; }
.weather-desc { font-size: 14px; color: var(--tc2, #bdc3c7); }
.weather-body { font-size: 13px; }
.weather-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--tc3, #999);
  margin-bottom: 8px;
}
.weather-forecast {
  background: var(--ab, rgba(255,255,255,.04));
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
}
.forecast-item {
  display: flex;
  gap: 12px;
  font-size: 12px;
  padding: 3px 0;
}
.forecast-label { color: var(--tc3, #888); width: 36px; }
.forecast-weather { color: var(--tc2, #bdc3c7); flex: 1; }
.forecast-temp { color: var(--tc3, #999); }
.weather-suggestion {
  color: var(--pink, #e8929b);
  font-size: 12px;
  font-style: italic;
  margin-top: 4px;
}
.weather-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--tc3, #666);
}
</style>
