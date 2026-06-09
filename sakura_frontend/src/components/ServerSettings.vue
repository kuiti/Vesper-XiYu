<template>
  <div class="sc-pane">
    <div class="card"><h3>云端服务器连接</h3><p class="hint">连接到云端部署的佐仓后端。本地使用请留空。</p>
      <div class="field"><label>服务器地址</label><input :value="serverHost" @input="$emit('update:serverHost', $event.target.value)" placeholder="47.98.120.186（留空=本地模式）"></div>
      <div class="field"><label>端口</label><input :value="serverPort" @input="$emit('update:serverPort', $event.target.value)" placeholder="18060"></div>
      <div class="field"><label>访问令牌</label><input type="password" :value="serverToken" @input="$emit('update:serverToken', $event.target.value)" placeholder="输入云端 Token"></div>
      <div class="btn-row">
        <button class="btn" @click="$emit('save-server')">保存并连接</button>
        <button class="btn-s" @click="$emit('test-server')" :disabled="testingServer">{{ testingServer ? '...' : '测试连接' }}</button>
        <span v-if="serverTestMsg" :class="serverTestOk ? 'ok' : 'fail'">{{ serverTestMsg }}</span>
      </div>
      <p class="hint" style="margin-top:8px">当前模式：{{ serverHost ? '☁️ 云端' : '💻 本地' }}</p>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    serverHost: { type: String, default: '' },
    serverPort: { type: String, default: '8060' },
    serverToken: { type: String, default: '' },
    testingServer: { type: Boolean, default: false },
    serverTestMsg: { type: String, default: '' },
    serverTestOk: { type: Boolean, default: false },
  },
  emits: ['update:serverHost', 'update:serverPort', 'update:serverToken', 'save-server', 'test-server'],
}
</script>

<style scoped>
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--tc2); margin-bottom: 4px; }
.field input { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.hint { font-size: 11px; color: var(--tc2); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.btn { padding: 7px 16px; background: var(--p); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); cursor: pointer; font-size: 12px; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
</style>