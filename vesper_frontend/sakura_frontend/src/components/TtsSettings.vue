<template>
  <div class="sc-pane">
    <div class="card"><h3>语音朗读（TTS）</h3>
      <label class="switch"><input type="checkbox" :checked="ttsEnabled" @change="$emit('update:ttsEnabled', $event.target.checked); $emit('save-voice')"> 启用语音合成</label>
      <label class="field-label" style="margin-top:8px">引擎</label>
      <select :value="ttsEngine" @change="$emit('update:ttsEngine', $event.target.value); $emit('engine-change')" class="input">
        <option value="off">关闭</option><option value="edge">Edge TTS</option><option value="openai">OpenAI TTS</option>
        <option value="xiaomi">小米 MiMo TTS</option><option value="volcano">火山引擎</option>
        <option value="baidu">百度</option><option value="aliyun">阿里云</option>
        <option value="fish_audio">Fish Audio</option><option value="spark">讯飞</option>
        <option value="cosyvoice">CosyVoice</option><option value="gpt_sovits">GPT-SoVITS</option>
      </select>
      <p class="hint" v-if="ttsEngineStatus" :class="ttsEngineStatus==='ok'?'hint-ok':'hint-err'">引擎状态: {{ ttsEngineStatus }}</p>
    </div>
    <div v-if="ttsEngine==='edge'" class="card"><h3>Edge TTS</h3>
      <select :value="ttsVoice" @change="$emit('update:ttsVoice', $event.target.value); $emit('save-voice')" class="input">
        <option value="xiaoyi">小艺</option><option value="xiaoxiao">小晓</option><option value="yunxi">云希</option><option value="yunjian">云健</option>
      </select>
    </div>
    <div v-if="['openai','volcano','baidu','aliyun','fish_audio','spark'].includes(ttsEngine)" class="card">
      <h3>{{ {openai:'OpenAI',volcano:'火山引擎',baidu:'百度',aliyun:'阿里云',fish_audio:'Fish Audio',spark:'讯飞'}[ttsEngine] }} TTS</h3>
      <label class="field-label">API Key</label><input :value="ttsApiKey" @input="$emit('update:ttsApiKey', $event.target.value)" class="input" type="password">
      <label class="field-label" style="margin-top:8px">音色</label><input :value="ttsVoice" @input="$emit('update:ttsVoice', $event.target.value)" class="input">
      <div style="margin-top:8px"><button class="btn" @click="$emit('save-voice')">保存</button></div>
    </div>
    <div v-if="['cosyvoice','gpt_sovits'].includes(ttsEngine)" class="card">
      <h3>{{ {cosyvoice:'CosyVoice',gpt_sovits:'GPT-SoVITS'}[ttsEngine] }} 本地</h3>
      <label class="field-label">服务地址</label><input :value="ttsServerUrl" @input="$emit('update:ttsServerUrl', $event.target.value)" class="input">
      <label class="field-label" style="margin-top:8px">音色</label><input :value="ttsVoice" @input="$emit('update:ttsVoice', $event.target.value)" class="input">
      <div style="margin-top:8px"><button class="btn" @click="$emit('save-voice')">保存</button></div>
    </div>
    <div v-if="ttsEngine==='xiaomi'" class="card"><h3>小米 MiMo TTS</h3>
      <div style="display:flex;gap:8px">
        <input :value="ttsApiKey" @input="$emit('update:ttsApiKey', $event.target.value)" class="input" type="password" style="flex:1">
        <button class="btn" @click="$emit('save-voice')">确认</button>
        <button class="btn-s" @click="$emit('test-xiaomi')" :disabled="testingXiaomi">{{ testingXiaomi?'...':'测试' }}</button>
      </div>
      <p v-if="xiaomiTestMsg" :class="xiaomiTestOk?'hint-ok':'hint-err'" style="font-size:11px;margin-top:4px">{{ xiaomiTestMsg }}</p>
      <label class="field-label" style="margin-top:8px">模式</label>
      <select :value="ttsCloneMode" @change="$emit('update:ttsCloneMode', $event.target.value); $emit('clone-mode-change')" class="input">
        <option value="preset">预置音色</option><option value="clone">声音克隆</option>
      </select>
      <div v-if="ttsCloneMode==='preset'" style="margin-top:8px">
        <select :value="ttsVoice" @change="$emit('update:ttsVoice', $event.target.value); $emit('save-voice')" class="input">
          <option value="冰糖">冰糖</option><option value="茉莉">茉莉</option><option value="苏打">苏打</option><option value="白桦">白桦</option>
        </select>
      </div>
      <div v-if="ttsCloneMode==='clone'" style="margin-top:8px">
        <input type="file" accept=".wav,.mp3" @change="$emit('upload-clone-audio', $event)" class="input" style="padding:4px">
        <p v-if="ttsCloneStatus" :class="ttsCloneStatus==='ok'?'hint-ok':'hint-err'" style="font-size:11px">{{ ttsCloneStatusMsg }}</p>
      </div>
    </div>
    <div class="card"><h3>语音输入与播放</h3>
      <label class="switch"><input type="checkbox" :checked="sttEnabled" @change="$emit('update:sttEnabled', $event.target.checked); $emit('save-voice')"> 语音输入</label>
      <label class="switch" style="margin-top:6px"><input type="checkbox" :checked="autoPlay" @change="$emit('update:autoPlay', $event.target.checked); $emit('save-voice')"> 自动播放</label>
    </div>
  </div>
</template>
<script>
export default {
  props: {
    ttsEnabled: Boolean, ttsEngine: String, ttsVoice: String, ttsApiKey: String,
    ttsApiUrl: String, ttsServerUrl: String, ttsEngineStatus: String,
    ttsCloneMode: String, ttsCloneStatus: String, ttsCloneStatusMsg: String,
    sttEnabled: Boolean, autoPlay: Boolean,
    testingXiaomi: Boolean, xiaomiTestMsg: String, xiaomiTestOk: Boolean,
  },
  emits: ['update:ttsEnabled','update:ttsEngine','update:ttsVoice','update:ttsApiKey',
          'update:ttsApiUrl','update:ttsServerUrl','update:ttsCloneMode','update:sttEnabled','update:autoPlay',
          'save-voice','engine-change','clone-mode-change','test-xiaomi','upload-clone-audio'],
}
</script>
<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border-default); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint-ok { color: #4caf50; font-size: 12px; }
.hint-err { color: #e74c3c; font-size: 12px; }
.field-label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.input { width: 100%; padding: 6px 10px; background: var(--surface-app); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); font-size: 13px; outline: none; box-sizing: border-box; }
.btn { padding: 7px 16px; background: var(--accent-primary); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.switch { display: block; font-size: 13px; color: var(--text-primary); margin: 4px 0; cursor: pointer; }
.switch input { margin-right: 6px; }
</style>