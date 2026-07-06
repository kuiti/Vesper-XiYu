<template>
  <div class="sc-pane">
    <div class="card"><h3>AI 接口配置</h3>
      <div class="field"><label>提供商</label><select :value="provider" @change="$emit('update:provider', $event.target.value); $emit('provider-change')"><option value="deepseek">DeepSeek</option><option value="mimo">MiMo</option><option value="qwen">通义千问</option><option value="moonshot">Moonshot</option><option value="zhipu">智谱</option><option value="openai">OpenAI</option><option value="siliconflow">硅基流动</option><option value="baidu">百度千帆</option><option value="doubao">字节豆包</option><option value="ollama">Ollama (本地)</option><option value="custom">自定义</option></select></div>
      <div class="field"><label>API 地址</label><input :value="apiBaseUrl" @input="$emit('update:apiBaseUrl', $event.target.value)" placeholder="https://api.deepseek.com/v1"></div>
      <div class="field"><label>模型</label><div class="btn-row"><input :value="apiModel" @input="$emit('update:apiModel', $event.target.value)" placeholder="deepseek-chat" style="flex:1"><button class="btn-s" @click="$emit('fetch-models')" :disabled="fetchingModels">{{ fetchingModels ? '...' : '获取' }}</button></div></div>
      <div class="field"><label>备选模型</label><input :value="fallbackModels" @input="$emit('update:fallbackModels', $event.target.value)" @change="$emit('save-cfg', 'fallback_models', fallbackModels)" placeholder="gpt-4o,claude-sonnet-4-6（主模型失败时自动切换）"></div>
      <div class="field"><label>API Key</label><input type="password" :value="apiKey" @input="$emit('update:apiKey', $event.target.value)" placeholder="sk-..."></div>
      <div class="btn-row"><button class="btn" @click="$emit('save-api')">保存</button><button class="btn-s" @click="$emit('test-api')" :disabled="testingApi">{{ testingApi ? '...' : '测试连接' }}</button><span v-if="testMsg" :class="testOk ? 'ok' : 'fail'">{{ testMsg }}</span></div>
      <div v-if="availableModels.length" class="field" style="margin-top:8px"><label>可用模型</label><select :value="apiModel" @change="$emit('update:apiModel', $event.target.value)"><option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option></select></div>
    </div>
    <div class="card"><h3>联网搜索</h3><p class="hint">选择搜索方式。大模型模式由 AI 自行判断是否需要联网；DuckDuckGo 仅在识别到搜索意图时调用。仅大模型支持联网时生效。</p>
      <select :value="searchProvider" @change="$emit('update:searchProvider', $event.target.value); $emit('save-cfg', 'search_provider', $event.target.value)"><option value="off">关闭</option><option value="llm">大模型</option><option value="ddg">DuckDuckGo</option></select>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    provider: String, apiBaseUrl: String, apiModel: String, apiKey: String,
    searchProvider: String, fallbackModels: { type: String, default: '' },
    testingApi: Boolean, testMsg: String, testOk: Boolean,
    fetchingModels: Boolean, availableModels: { type: Array, default: () => [] },
  },
  emits: ['update:provider', 'update:apiBaseUrl', 'update:apiModel', 'update:apiKey',
          'update:searchProvider', 'update:fallbackModels',
          'provider-change', 'save-api', 'test-api', 'fetch-models', 'save-cfg'],
}
</script>

<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border-default); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.field input, .field select { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.btn { padding: 7px 16px; background: var(--accent-primary); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
</style>