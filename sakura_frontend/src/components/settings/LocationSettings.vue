<template>
  <div class="sc-pane">
    <div class="card"><h3>高德地图 API</h3><p class="hint">用于天气查询和 GPS 精确定位。在高德开放平台免费申请 Web服务 Key 后填入。</p>
      <div class="field"><label>API Key (Web服务)</label><div class="btn-row"><input :value="amapKey" @input="$emit('update:amapKey', $event.target.value)" placeholder="输入高德 Web服务 Key"><button class="btn" @click="$emit('save-amap-key')">保存</button><button class="btn-s" @click="$emit('test-amap')" :disabled="testingAmap">{{ testingAmap ? '...' : '测试' }}</button></div><div v-if="amapTestMsg" class="field" style="margin-top:4px"><span :class="amapTestOk ? 'ok' : 'fail'">{{ amapTestMsg }}</span></div></div>
    </div>
    <div class="card"><h3>定位方式</h3><p class="hint">IP 定位写入手动城市（不会覆盖 GPS 结果）。GPS 精确定位精度更高，首次使用需浏览器授权。已授权过的重启后不再询问。</p>
      <div class="btn-row"><button class="btn" @click="$emit('locate-ip')" :disabled="!!locating">{{ locating === 'ip' ? '定位中...' : 'IP 定位' }}</button><button class="btn" @click="$emit('locate-gps')" :disabled="!!locating">{{ locating === 'gps' ? '定位中...' : 'GPS 精确定位' }}</button><button class="btn-s" @click="$emit('reset-location')">重置权限</button></div>
      <div v-if="locateResult" class="field" style="margin-top:8px"><span :class="locateOk ? 'ok' : 'fail'">{{ locateResult }}</span></div>
    </div>
    <div class="card"><h3>手动选择</h3><p class="hint">当前定位：{{ currentLocation || '未获取' }}（精确城市优先于手动城市，GPS结果覆盖IP结果）</p>
      <div class="field"><label>省份</label><select :value="selProvince" @change="$emit('update:selProvince', $event.target.value); $emit('load-cities')"><option value="">{{ currentProvince || '-- 自动检测 --' }}</option><option v-for="p in provinces" :key="p.adcode" :value="p.adcode">{{ p.name }}</option></select></div>
      <div class="field"><label>城市</label><select :value="selCity" @change="$emit('update:selCity', $event.target.value); $emit('save-manual-city')"><option value="">{{ currentManualCity || '-- 选择城市 --' }}</option><option v-for="c in cities" :key="c.adcode" :value="c.adcode">{{ c.name }}</option></select></div>
    </div>
    <div class="card"><h3>大模型联网天气</h3>
      <label class="switch"><input type="checkbox" :checked="enableLlmWeather" @change="$emit('update:enableLlmWeather', $event.target.checked); $emit('save-cfg', 'enable_llm_weather_search', $event.target.checked)"> 使用大模型联网查询天气</label>
      <p class="hint">勾选后天气查询跳过 Open-Meteo，由大模型自行搜索天气信息。仅大模型支持联网时生效。</p>
      <div style="margin-top:12px">
        <button class="btn" @click="$emit('test-weather')" :disabled="testingWeather">{{ testingWeather ? '测试中...' : '测试天气源' }}</button>
      </div>
      <div v-if="weatherTestResults" style="margin-top:10px">
        <div v-for="r in weatherTestResults.sources" :key="r.source" :style="{color: r.ok ? '#4caf84' : '#e05570', fontSize:'13px', marginBottom:'4px'}">
          {{ r.ok ? '✓' : '✗' }} {{ r.source }}：{{ r.reason }}
          <div v-if="r.preview" style="color:var(--tc2);font-size:12px;margin-left:18px">{{ r.preview }}</div>
        </div>
        <div style="font-size:12px;color:var(--tc2);margin-top:4px">{{ weatherTestResults.summary }}</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    amapKey: String,
    enableLlmWeather: Boolean,
    testingAmap: Boolean,
    amapTestMsg: String,
    amapTestOk: Boolean,
    locating: [Boolean, String],
    locateResult: String,
    locateOk: Boolean,
    testingWeather: Boolean,
    weatherTestResults: Object,
    currentLocation: String,
    currentProvince: String,
    currentManualCity: String,
    provinces: Array,
    cities: Array,
    selProvince: String,
    selCity: String,
  },
  emits: [
    'update:amapKey', 'update:enableLlmWeather', 'update:selProvince', 'update:selCity',
    'save-amap-key', 'test-amap', 'locate-ip', 'locate-gps', 'reset-location',
    'load-cities', 'save-manual-city', 'test-weather', 'save-cfg',
  ],
}
</script>