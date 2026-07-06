<template>
  <div class="settings-view">
    <div class="settings-nav">
      <button v-for="cat in categories" :key="cat.id" :class="['sn-item', { active: activeCat === cat.id }]" @click="activeCat = cat.id">{{ cat.label }}</button>
    </div>
    <div class="settings-content">
      <Transition name="page-fade" mode="out-in">
        <ServerSettings v-if="activeCat==='server'" :key="'server'"
        :serverHost="serverHost" :serverPort="serverPort" :serverToken="serverToken"
        :testingServer="testingServer" :serverTestMsg="serverTestMsg" :serverTestOk="serverTestOk"
        @update:serverHost="serverHost=$event" @update:serverPort="serverPort=$event" @update:serverToken="serverToken=$event"
        @save-server="saveServer" @test-server="testServer" />

      <ApiSettings v-else-if="activeCat==='api'"
        :provider="provider" :apiBaseUrl="apiBaseUrl" :apiModel="apiModel" :apiKey="apiKey"
        :searchProvider="searchProvider" :fallbackModels="fallbackModels"
        :testingApi="testingApi" :testMsg="testMsg" :testOk="testOk"
        :fetchingModels="fetchingModels" :availableModels="availableModels"
        @update:provider="provider=$event" @update:apiBaseUrl="apiBaseUrl=$event" @update:apiModel="apiModel=$event"
        @update:apiKey="apiKey=$event" @update:searchProvider="searchProvider=$event" @update:fallbackModels="fallbackModels=$event"
        @provider-change="onProviderChange" @save-api="saveApi" @test-api="testApi" @fetch-models="fetchModels"
        @save-cfg="(k,v)=>saveCfg(k,v)" />

      <RoleSettings v-else-if="activeCat==='role'"
        :aiName="aiName" :userName="userName" :tone="tone" :length="length" :recall="recall"
        :allowEmotion="allowEmotion" :customPrompt="customPrompt" :aiBackground="aiBackground"
        :assistantAvatarUrl="assistantAvatarUrl" :userAvatarUrl="userAvatarUrl"
        :aiAvatarUrlLocal="aiAvatarUrlLocal" :userAvatarUrlLocal="userAvatarUrlLocal"
        :relationship="relationship" :foundationType="foundationType" :foundationTypes="foundationTypes"
        :pendingFoundation="pendingFoundation" :resetFoundationValues="resetFoundationValues"
        :presetName="presetName" :presets="presets"
        :cardDescription="cardDescription" :cardPersonality="cardPersonality" :cardScenario="cardScenario"
        @update:aiName="aiName=$event" @update:userName="userName=$event"
        @update:cardDescription="cardDescription=$event" @update:cardPersonality="cardPersonality=$event"
        @update:cardScenario="cardScenario=$event"
        @update:tone="tone=$event" @update:length="length=$event" @update:recall="recall=$event"
        @update:allowEmotion="allowEmotion=$event" @update:customPrompt="customPrompt=$event"
        @update:aiBackground="aiBackground=$event"
        @update:aiAvatarUrlLocal="aiAvatarUrlLocal=$event" @update:userAvatarUrlLocal="userAvatarUrlLocal=$event"
        @update:foundationType="foundationType=$event" @update:resetFoundationValues="resetFoundationValues=$event"
        @update:presetName="presetName=$event"
        @save-cfg="(k,v)=>saveCfg(k,v)"
        @upload-avatar="(r,e)=>uploadAvatar(r,e)" @upload-avatar-url="(r)=>uploadAvatarByUrl(r)"
        @foundation-change="onFoundationChange" @confirm-foundation="confirmFoundation"
        @cancel-foundation="cancelFoundation" @save-preset="savePreset"
        @load-preset="(n,d)=>loadPreset(n,d)" @delete-preset="(n)=>deletePreset(n)" />

      <AppearanceSettings v-else-if="activeCat==='appearance'"
        :themeLocal="themeLocal" :chatBgImage="chatBgImage" :bgOpacity="bgOpacity" :bgBlur="bgBlur" :bgMode="bgMode"
        :bgUploadMsg="bgUploadMsg" :ragStatus="ragStatus" :ragCount="ragCount" :ragMsg="ragMsg" :ragMsgOk="ragMsgOk"
        :installingRag="installingRag" :rebuildingRag="rebuildingRag"
        @set-theme="(t)=>setTheme(t)" @upload-bg="(e)=>uploadBg(e)" @clear-bg="clearBg"
        @save-cfg="(k,v)=>saveCfg(k,v)" @save-bg-style="saveBgStyle"
        @install-rag="installRag" @rebuild-rag="rebuildRag"
        @update:chatBgImage="chatBgImage=$event" @update:bgOpacity="bgOpacity=$event"
        @update:bgBlur="bgBlur=$event" @update:bgMode="bgMode=$event" />

      <!-- 聊天偏好 -->
      <div v-else-if="activeCat==='chat'" class="sc-pane">
        <div class="card"><h3>字体大小</h3>
          <div class="field"><input type="range" min="10" max="20" v-model.number="chatFontSize" @change="saveCfg('chat_font_size', chatFontSize)"><span style="margin-left:8px;font-size:13px;color:var(--tc2)">{{ chatFontSize }}px</span></div>
        </div>
        <div class="card"><h3>分句模式</h3><p class="hint">智能分句：按标点自动断句，短于12字的句子会自动合并避免刷屏。分隔符分句：AI 主动用分隔符控制断句位置。逐字显示：模拟打字效果逐字弹出。连续输出：一次性显示全部回复。</p>
          <select v-model="sentenceMode" @change="saveCfg('sentence_mode', sentenceMode)"><option value="auto">智能分句</option><option value="delimiter">分隔符分句</option><option value="typewriter">逐字显示</option><option value="raw">连续输出</option></select>
        </div>
        <div class="card"><h3>主动频率</h3><p class="hint">AI 在你沉默后主动发起话题的间隔。关闭：不主动说话；低：约 3 小时；中：约 40-120 分钟（根据你回复率自动调整）；高：约 30 分钟。深夜 23:00-7:00 不打扰。</p>
          <select v-model="proactiveFreq" @change="saveCfg('proactive_frequency', proactiveFreq)"><option value="off">关闭</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select>
        </div>
        <div class="card"><h3>主动风格</h3><p class="hint">AI 主动找你说话时的语气。温暖关怀：像朋友一样关心近况再自然聊开；幽默调侃：带俏皮玩笑让人会心一笑；简洁直接：控制在15字以内说重点；自由发挥：由 AI 自行决定语气。主动消息会自动融入天气和位置信息。</p>
          <select v-model="proactiveStyle" @change="saveCfg('proactive_style', proactiveStyle)"><option value="warm">温暖关怀</option><option value="humorous">幽默调侃</option><option value="concise">简洁直接</option><option value="free">自由发挥</option></select>
        </div>
        <div class="card"><h3>关系模式</h3><p class="hint">快速模式好感度/信任度变化更快；长期模式每日有上限。好感度与信任度互相牵制——信任高了好感涨得快，反之亦然。聊天频率和情绪质量也会影响性格演化。</p>
          <select v-model="relMode" @change="saveCfg('relationship_mode', relMode)"><option value="fast">快速</option><option value="long_term">长期</option></select>
        </div>
        <div class="card"><h3>快捷短语</h3>
          <div v-for="(p, i) in quickPhrases" :key="i" class="phrase-row"><input :value="p" @input="updPhrase(i, $event.target.value)"><button class="btn-s" @click="delPhrase(i)">x</button></div>
          <button class="btn-s" @click="addPhrase">+ 添加</button>
        </div>
      </div>

      <!-- 定位 -->
      <LocationSettings v-else-if="activeCat==='location'"
        :amapKey="amapKey" :enableLlmWeather="enableLlmWeather" :testingAmap="testingAmap"
        :amapTestMsg="amapTestMsg" :amapTestOk="amapTestOk" :locating="locating"
        :locateResult="locateResult" :locateOk="locateOk" :testingWeather="testingWeather"
        :weatherTestResults="weatherTestResults" :currentLocation="currentLocation"
        :currentProvince="currentProvince" :currentManualCity="currentManualCity"
        :provinces="provinces" :cities="cities" :selProvince="selProvince" :selCity="selCity"
        @update:amapKey="amapKey=$event" @update:enableLlmWeather="enableLlmWeather=$event"
        @update:selProvince="selProvince=$event" @update:selCity="selCity=$event"
        @save-amap-key="saveAmapKey" @test-amap="testAmap"
        @locate-ip="locateByIP" @locate-gps="preciseLocate" @reset-location="resetLocation"
        @load-cities="loadCities" @save-manual-city="saveManualCity" @test-weather="testWeather"
        @save-cfg="(k,v)=>saveCfg(k,v)" />

      <!-- 隐私与通知 -->
      <PrivacySettings v-else-if="activeCat==='privacy'"
        :pinEnabled="pinEnabled" :pinCode="pinCode"
        :useSysNotify="useSysNotify" :useWeather="useWeather"
        :showTray="showTray" :notifyStyle="notifyStyle"
        @update:pinCode="pinCode=$event" @update:useSysNotify="useSysNotify=$event"
        @update:useWeather="useWeather=$event" @update:showTray="showTray=$event"
        @update:notifyStyle="notifyStyle=$event"
        @toggle-pin="togglePin" @save-pin="savePin"
        @save-cfg="(k,v)=>saveCfg(k,v)" />

      <TtsSettings v-else-if="activeCat==='tts'"
        :ttsEnabled="ttsEnabled" :ttsEngine="ttsEngine" :ttsVoice="ttsVoice" :ttsApiKey="ttsApiKey"
        :ttsApiUrl="ttsApiUrl" :ttsServerUrl="ttsServerUrl" :ttsEngineStatus="ttsEngineStatus"
        :ttsCloneMode="ttsCloneMode" :ttsCloneStatus="ttsCloneStatus" :ttsCloneStatusMsg="ttsCloneStatusMsg"
        :sttEnabled="sttEnabled" :autoPlay="autoPlay"
        :testingXiaomi="testingXiaomi" :xiaomiTestMsg="xiaomiTestMsg" :xiaomiTestOk="xiaomiTestOk"
        @update:ttsEnabled="ttsEnabled=$event" @update:ttsEngine="ttsEngine=$event"
        @update:ttsVoice="ttsVoice=$event" @update:ttsApiKey="ttsApiKey=$event"
        @update:ttsApiUrl="ttsApiUrl=$event" @update:ttsServerUrl="ttsServerUrl=$event"
        @update:ttsCloneMode="ttsCloneMode=$event" @update:sttEnabled="sttEnabled=$event"
        @update:autoPlay="autoPlay=$event"
        @save-voice="saveVoice" @engine-change="onEngineChange" @clone-mode-change="onCloneModeChange"
        @test-xiaomi="testXiaomiTts" @upload-clone-audio="(e)=>uploadCloneAudio(e)" />

      <DataSettings v-else-if="activeCat==='data'"
        :aiName="aiName" :userName="userName" :favorites="favorites"
        :cloudBackend="cloudBackend" :cloudUrl="cloudUrl" :cloudUser="cloudUser" :cloudPass="cloudPass" :cloudPhrase="cloudPhrase"
        :cloudMsg="cloudMsg" :cloudMsgOk="cloudMsgOk" :cloudUploading="cloudUploading" :cloudLastSync="cloudLastSync"
        @update:cloudBackend="cloudBackend=$event" @update:cloudUrl="cloudUrl=$event"
        @update:cloudUser="cloudUser=$event" @update:cloudPass="cloudPass=$event"
        @del-fav="(id)=>delFav(id)" @export-chat="(f)=>$emit('export-chat',f)" @load-favorites="loadFavorites"
        @save-cloud-cfg="saveCloudCfg" @test-cloud="testCloudConn" @cloud-upload="cloudUpload"
        @reset-relationship="resetRelationship" @reset-memory="resetMemory" @full-reset="fullReset" />
      </Transition>
    </div>
  </div>
</template>

<script>
import api from '../api'
import ServerSettings from './ServerSettings.vue'
import ApiSettings from './ApiSettings.vue'
import RoleSettings from './RoleSettings.vue'
import TtsSettings from './TtsSettings.vue'
import DataSettings from './DataSettings.vue'
import AppearanceSettings from './AppearanceSettings.vue'
import LocationSettings from './settings/LocationSettings.vue'
import PrivacySettings from './settings/PrivacySettings.vue'

const PROVIDER_MAP = {
  deepseek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  mimo: { url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2-flash' },
  qwen: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  moonshot: { url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  zhipu: { url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  openai: { url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  siliconflow: { url: 'https://api.siliconflow.cn/v1', model: 'deepseek-v4-flash' },
  baidu: { url: 'https://qianfan.baidubce.com/v2', model: 'ernie-4.0' },
  doubao: { url: 'https://ark.cn-beijing.volces.com/api/v3', model: 'ep-xxx' },
  ollama: { url: 'http://localhost:11434/v1', model: '' },
  custom: { url: '', model: '' },
}

export default {
  components: { ServerSettings, ApiSettings, RoleSettings, TtsSettings, DataSettings, AppearanceSettings },
  props: { settings: Object, themeLocal: String, ipCity: String, relationship: Object, emotionTrend: Array, totalMessages: Number, conversationDays: Number, assistantAvatarUrl: String, userAvatarUrl: String },
  emits: ['config-changed', 'export-chat', 'close'],
  data() {
    return {
      activeCat: 'role',
      categories: [
        { id: 'role', label: '角色人设' },
        { id: 'appearance', label: '外观主题' },
        { id: 'chat', label: '聊天偏好' },
        { id: 'tts', label: '语音朗读' },
        { id: 'location', label: '定位' },
        { id: 'privacy', label: '隐私与通知' },
        { id: 'data', label: '数据管理' },
        { id: 'server', label: '服务器连接' },
        { id: 'api', label: 'API 接口' },
      ],
      // 服务器连接
      serverHost: '', serverPort: '8060', serverToken: '', serverProtocol: 'http',
      serverTestMsg: '', serverTestOk: false, testingServer: false,
      provider: 'deepseek', apiBaseUrl: '', apiModel: '', apiKey: '',
      searchProvider: 'ddg', testMsg: '', testOk: false, testingApi: false, fetchingModels: false, availableModels: [],
      ttsEnabled: true, sttEnabled: true, autoPlay: false, notifyStyle: 'warm',
      ttsEngine: 'off', ttsVoice: 'xiaoyi', ttsApiKey: '', ttsApiUrl: '', ttsServerUrl: 'http://127.0.0.1:9880', ttsEngineStatus: '',
      ttsCloneMode: 'preset', ttsCloneStatus: '', ttsCloneStatusMsg: '',
      testingXiaomi: false, xiaomiTestMsg: '', xiaomiTestOk: false,
      aiName: '', userName: '', tone: '冷静', length: '短', recall: '从不', allowEmotion: true,
      customPrompt: '', aiBackground: '', presets: {}, presetName: '',
      cardDescription: '', cardPersonality: '', cardScenario: '',
      foundationType: '空白', foundationTypes: {}, pendingFoundation: '', resetFoundationValues: false,
      chatBgImage: '', bgOpacity: 1, bgBlur: 0, bgMode: 'cover', bgUploadMsg: '',
      aiAvatarUrlLocal: '', userAvatarUrlLocal: '', chatFontSize: 14,
      sentenceMode: 'auto', proactiveFreq: 'medium', relMode: 'fast',
      quickPhrases: [], pinEnabled: false, pinCode: '',
      proactiveStyle: 'warm',
      useSysNotify: false, useWeather: true, showTray: true,
      favorites: [],
      amapKey: '', enableLlmWeather: false, testingWeather: false, weatherTestResults: null,
      locating: false, locateResult: '', locateOk: false, testingAmap: false, amapTestMsg: '', amapTestOk: false,
      ragStatus: '', ragCount: 0, ragMsg: '', ragMsgOk: false, installingRag: false, rebuildingRag: false,
      provinces: [], cities: [], selProvince: '', selCity: '',
      savedColorPresets: [],
      cloudBackend: 'webdav', cloudUrl: '', cloudUser: '', cloudPass: '', cloudPhrase: '',
      cloudMsg: '', cloudMsgOk: false, cloudUploading: false, cloudLastSync: '',
    }
  },
  computed: {
    currentLocation() {
      const precise = (this.settings || {}).precise_city || ''
      const manual = (this.settings || {}).manual_city || ''
      return precise || manual || this.ipCity || ''
    },
    currentProvince() {
      return (this.settings || {}).ip_location_province || ''
    },
    currentManualCity() {
      return (this.settings || {}).manual_city || ''
    }
  },
  async mounted() { this._loadServerSettings(); await this.loadFromSettings(); this.loadPresets(); this.loadFavorites(); this.loadProvinces(); this.checkRagStatus(); this.loadFoundationTypes(); this.loadCloudCfg() },
  methods: {
    // ── 服务器连接 ──
    saveServer() {
      localStorage.setItem('sakura_server_host', this.serverHost)
      localStorage.setItem('sakura_server_port', this.serverPort)
      localStorage.setItem('sakura_api_token', this.serverToken)
      localStorage.setItem('sakura_server_protocol', this.serverProtocol)
      if (this.serverHost) {
        window.__SAKURA_CONFIG__ = Object.assign({}, window.__SAKURA_CONFIG__ || {}, {
          backendHost: this.serverHost,
          backendPort: parseInt(this.serverPort) || 8060,
          apiToken: this.serverToken,
          backendProtocol: this.serverProtocol,
        })
      }
      this.serverTestMsg = '已保存，正在刷新...'
      this.serverTestOk = true
      setTimeout(() => location.reload(), 500)
    },
    async testServer() {
      this.testingServer = true; this.serverTestMsg = ''
      try {
        const host = this.serverHost || '127.0.0.1'
        const port = this.serverPort || '8060'
        const protocol = this.serverProtocol || 'http'
        const url = `${protocol}://${host}:${port}/health`
        const headers = this.serverToken ? { Authorization: `Bearer ${this.serverToken}` } : {}
        const res = await fetch(url, { headers, signal: AbortSignal.timeout(10000) })
        const data = await res.json()
        if (data.status === 'ok') { this.serverTestMsg = '✅ 连接成功'; this.serverTestOk = true }
        else { this.serverTestMsg = '❌ 响应异常'; this.serverTestOk = false }
      } catch (e) { this.serverTestMsg = '❌ 连接失败: ' + e.message; this.serverTestOk = false }
      this.testingServer = false
    },
    _loadServerSettings() {
      this.serverHost = localStorage.getItem('sakura_server_host') || ''
      this.serverPort = localStorage.getItem('sakura_server_port') || '8060'
      this.serverToken = localStorage.getItem('sakura_api_token') || ''
      this.serverProtocol = localStorage.getItem('sakura_server_protocol') || 'http'
      // 如果有云端配置，覆盖 __SAKURA_CONFIG__
      if (this.serverHost) {
        window.__SAKURA_CONFIG__ = Object.assign({}, window.__SAKURA_CONFIG__ || {}, {
          backendHost: this.serverHost,
          backendPort: parseInt(this.serverPort) || 8060,
          apiToken: this.serverToken,
          backendProtocol: this.serverProtocol,
        })
      }
    },
    _detectProvider(url) { if (!url) return 'deepseek'; if (url.includes('localhost:11434')) return 'ollama'; for (const [k, v] of Object.entries(PROVIDER_MAP)) { if (k !== 'custom' && url.includes(v.url.replace('https://','').split('/')[0])) return k } return 'custom' },
    async loadFromSettings() {
      const s = this.settings || {}
      this.provider = this._detectProvider(s.api_base_url)
      this.apiBaseUrl = s.api_base_url || ''
      this.apiModel = s.api_model || ''
      this.apiKey = s.has_api_key ? '••••••••' : ''
      this.searchProvider = s.search_provider || 'ddg'
      this.aiName = s.ai_name || '佐仓'; this.userName = s.user_name || ''
      this.tone = s.personality_tone || '冷静'; this.length = s.length_level || '短'
      this.recall = s.recall_past || '从不'; this.allowEmotion = s.allow_emotion !== false
      this.customPrompt = s.custom_system_prompt || ''
      this.aiBackground = s.ai_background || ''
      this.cardDescription = s.card_description || ''
      this.cardPersonality = s.card_personality || ''
      this.cardScenario = s.card_scenario || ''
      this.bgOpacity = s.bg_opacity !== undefined ? Number(s.bg_opacity) : 1
      this.bgBlur = s.bg_blur !== undefined ? Number(s.bg_blur) : 0
      this.chatFontSize = s.chat_font_size || 14
      this.bgMode = s.bg_mode || 'cover'
      if (s.quick_phrases) { try { this.quickPhrases = JSON.parse(s.quick_phrases) } catch (e) { this.quickPhrases = [] } }
      this.sentenceMode = s.sentence_mode || 'auto'
      this.proactiveFreq = s.proactive_frequency || 'medium'
      this.proactiveStyle = s.proactive_style || 'warm'
      this.amapKey = s.amap_key || ''
      this.enableLlmWeather = s.enable_llm_weather_search === true
      this.relMode = s.relationship_mode || 'fast'
      this.pinEnabled = s.pin_enabled === 'true' || s.pin_enabled === true
      this.pinCode = s.pin_code || ''
      this.useSysNotify = s.use_system_notification || false
      this.useWeather = s.use_weather_care !== false
      this.showTray = s.show_tray_notification !== false
      this.notifyStyle = s.notification_style || 'warm'
      this.ttsEnabled = s.tts_enabled !== false; this.sttEnabled = s.stt_enabled !== false
      this.autoPlay = s.auto_play_voice || false
      this.ttsEngine = s.tts_engine || 'off'
      this.ttsVoice = s.tts_voice || 'xiaoyi'
      this.ttsApiKey = s.tts_api_key || ''
      this.ttsApiUrl = s.tts_api_url || ''
      this.ttsServerUrl = s.tts_server_url || 'http://127.0.0.1:9880'
      // 声音克隆状态（从顶级配置读取）
      if (s.tts_clone_audio) {
        this.ttsCloneStatus = 'ok'
        this.ttsCloneStatusMsg = '已上传声音文件'
      } else {
        this.ttsCloneStatus = ''
      }
      // 从后端读取模式设置
      this.ttsCloneMode = s.tts_clone_mode || 'preset'
      this.checkEngineStatus()
    },
    async loadPresets() {
      try {
        const r = await api.get('/settings/presets')
        const all = r.data || {}
        this.presets = {}
        this.savedColorPresets = []
        for (const [k, v] of Object.entries(all)) {
          if (v && v.primary_color) {
            this.savedColorPresets.push({ name: k, primary: v.primary_color, bg: v.bg_color, sidebarBg: v.sidebar_bg, chatBg: v.chat_bg, userBubble: v.user_bubble, aiBubble: v.ai_bubble })
          } else {
            this.presets[k] = v
          }
        }
      } catch (e) {}
    },
    async loadFoundationTypes() {
      try {
        const r = await api.get('/settings/foundation-types')
        this.foundationTypes = r.data || {}
        // 从 ai_background 中读取当前 foundation_type
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          this.foundationType = bg.foundation_type || '空白'
          this._previousFoundationType = this.foundationType
        } catch (e) {
          this.foundationType = '空白'
          this._previousFoundationType = '空白'
        }
      } catch (e) {}
    },
    onFoundationChange() {
      // 暂存选择，等待用户确认
      this.pendingFoundation = this.foundationType
      this.resetFoundationValues = false
      // 恢复原来的选择（等确认后再改）
      this.foundationType = this._previousFoundationType || '空白'
    },
    async confirmFoundation() {
      try {
        await api.post('/settings/foundation', {
          foundation_type: this.pendingFoundation,
          reset_values: this.resetFoundationValues
        })
        this.foundationType = this.pendingFoundation
        this._previousFoundationType = this.pendingFoundation
        // 更新本地 aiBackground
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          bg.foundation_type = this.pendingFoundation
          if (this.pendingFoundation !== '空白') {
            delete bg.foundation  // 使用模板时清除自定义基石
          }
          this.aiBackground = JSON.stringify(bg)
        } catch (e) {}
      } catch (e) {}
      this.pendingFoundation = ''
    },
    cancelFoundation() {
      this.pendingFoundation = ''
      this.resetFoundationValues = false
    },
    async saveFoundation() {
      // 保留旧方法兼容（引导面板用）
      try {
        await api.post('/settings/foundation', { foundation_type: this.foundationType, reset_values: true })
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          bg.foundation_type = this.foundationType
          if (this.foundationType !== '空白') {
            delete bg.foundation
          }
          this.aiBackground = JSON.stringify(bg)
        } catch (e) {}
      } catch (e) {}
    },
    async loadFavorites() { try { const r = await api.get('/favorites'); this.favorites = r.data || [] } catch (e) {} },
    async saveCfg(key, value) { if (this._saveTimers?.[key]) clearTimeout(this._saveTimers[key]); this._saveTimers = this._saveTimers || {}; this._saveTimers[key] = setTimeout(async () => { try { await api.post('/settings/', { key, value }); this.$emit('config-changed', key, value) } catch (e) {} }, key === 'chat_font_size' || key === 'bg_opacity' || key === 'bg_blur' ? 200 : 50) },
    onProviderChange() { const p = PROVIDER_MAP[this.provider]; if (p) { this.apiBaseUrl = p.url; this.apiModel = p.model } },
    async saveApi() { await this.saveCfg('api_provider', this.provider); await this.saveCfg('api_base_url', this.apiBaseUrl); await this.saveCfg('api_model', this.apiModel); if (this.apiKey && this.apiKey !== '••••••••' && this.apiKey.length >= 10) await this.saveCfg('api_key', this.apiKey) },
    async testApi() { this.testingApi = true; try { const r = await api.get('/test/deepseek'); this.testOk = r.data.ok; this.testMsg = r.data.message } catch (e) { this.testOk = false; this.testMsg = '连接失败' } this.testingApi = false },
    setTheme(v) { this.$emit("config-changed", "theme", v); this.saveCfg("theme", v) },
    clearBg() { this.chatBgImage = ''; this.saveCfg('chat_bg_image', ''); this.bgUploadMsg = '' },
    async uploadBg(e) { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const r = await api.post('/avatar/upload/bg', fd); if (r.data.filename) { const url = `/avatars/${r.data.filename}`; this.chatBgImage = url; this.saveCfg('chat_bg_image', url); this.bgUploadMsg = '已上传' } } catch (err) { this.bgUploadMsg = '上传失败' } e.target.value = '' },
    saveBgStyle() { this.saveCfg('bg_opacity', this.bgOpacity); this.saveCfg('bg_blur', this.bgBlur); this.saveCfg('bg_mode', this.bgMode); this.$emit('config-changed', 'bg_style', { opacity: this.bgOpacity, blur: this.bgBlur, mode: this.bgMode }) },
    async fetchModels() { this.fetchingModels = true; try { const r = await api.get('/test/models'); this.availableModels = r.data.models || [] } catch (e) {} this.fetchingModels = false },
    saveVoice() {
      // 不传 tts_clone_audio，由上传端点单独管理
      this.saveCfg('voice', { tts_enabled: this.ttsEnabled, tts_engine: this.ttsEngine, tts_voice: this.ttsVoice, tts_api_key: this.ttsApiKey, tts_api_url: this.ttsApiUrl, tts_server_url: this.ttsServerUrl, stt_enabled: this.sttEnabled, auto_play: this.autoPlay })
    },
    onEngineChange() { this.saveVoice(); this.checkEngineStatus() },
    onCloneModeChange() {
      this.saveCfg('tts_clone_mode', this.ttsCloneMode)
      if (this.ttsCloneMode === 'preset') { this.saveVoice() }
    },
    async uploadCloneAudio(e) {
      const f = e.target.files[0]; if (!f) return
      this.ttsCloneStatus = 'uploading'; this.ttsCloneStatusMsg = '上传中...'
      try {
        const fd = new FormData(); fd.append('file', f)
        const r = await api.post('/tts/upload-voice', fd)
        if (r.data?.status === 'ok') {
          this.ttsCloneStatus = 'ok'; this.ttsCloneStatusMsg = '上传成功，声音克隆已启用'
          // 通知 App 重新加载配置
          this.$emit('config-changed', 'tts_clone_audio', r.data.path)
        }
        else { this.ttsCloneStatus = 'err'; this.ttsCloneStatusMsg = r.data?.error || '上传失败' }
      } catch (err) { this.ttsCloneStatus = 'err'; this.ttsCloneStatusMsg = '上传失败：' + (err.message || '') }
    },
    async checkEngineStatus() {
      if (this.ttsEngine === 'off') { this.ttsEngineStatus = ''; return }
      try {
        const r = await api.get('/tts/health')
        this.ttsEngineStatus = r.data?.status || 'unknown'
        this.indexttsDevice = r.data?.device || ''
      } catch (e) { this.ttsEngineStatus = 'unreachable'; this.indexttsDevice = '' }
    },
    async testXiaomiTts() {
      if (!this.ttsApiKey) { this.xiaomiTestMsg = '请先填写 API Key'; this.xiaomiTestOk = false; return }
      this.testingXiaomi = true; this.xiaomiTestMsg = '测试中...'
      try {
        const r = await api.post('/tts/tts', { text: '你好，这是测试语音。', mode: this.ttsCloneMode === 'clone' ? 'clone' : 'preset' })
        if (r.data?.success) { this.xiaomiTestMsg = `测试成功，音频时长 ${r.data.duration?.toFixed(1) || '?'}s`; this.xiaomiTestOk = true }
        else { this.xiaomiTestMsg = r.data?.error || '测试失败'; this.xiaomiTestOk = false }
      } catch (e) { this.xiaomiTestMsg = '请求失败：' + (e.response?.data?.detail || e.message); this.xiaomiTestOk = false }
      this.testingXiaomi = false
    },
    addPhrase() { this.quickPhrases.push(''); this.savePhrases() },
    updPhrase(i, v) { this.quickPhrases.splice(i, 1, v); this.savePhrases() },
    delPhrase(i) { this.quickPhrases.splice(i, 1); this.savePhrases() },
    savePhrases() { this.saveCfg('quick_phrases', JSON.stringify(this.quickPhrases)) },
    togglePin() { this.saveCfg('pin_enabled', this.pinEnabled); if (!this.pinEnabled) { this.pinCode = ''; this.saveCfg('pin_code', '') } },
    savePin() { if (this.pinCode.length === 4) this.saveCfg('pin_code', this.pinCode) },
    async savePreset() { if (!this.presetName.trim()) return; try { await api.post('/settings/presets', { name: this.presetName, data: { tone: this.tone, length: this.length, recall: this.recall, allow_emotion: this.allowEmotion, custom_system_prompt: this.customPrompt } }); await this.loadPresets() } catch (e) {} },
    async deletePreset(name) { if (!confirm(`删除预设「${name}」？`)) return; try { await api.delete(`/settings/presets/${encodeURIComponent(name)}`); await this.loadPresets() } catch (e) {} },
    async loadPreset(name, d) { if (!d) return; this.tone = d.tone || '冷静'; this.length = d.length || '短'; this.recall = d.recall || '从不'; this.allowEmotion = d.allow_emotion !== false; this.customPrompt = d.custom_system_prompt || ''; this.saveCfg('personality_tone', this.tone); this.saveCfg('length_level', this.length); this.saveCfg('recall_past', this.recall); this.saveCfg('allow_emotion', this.allowEmotion); this.saveCfg('custom_system_prompt', this.customPrompt) },
    async delFav(id) { try { await api.delete(`/favorites/${id}`); await this.loadFavorites() } catch (e) {} },
    // ── 定位 ──
    async saveAmapKey() { await this.saveCfg('amap_key', this.amapKey); this.loadProvinces() },
    async locateByIP() { this.locating = 'ip'; try { const r = await api.get('/location/ip'); if (r.data.city) { this.locateResult = `${r.data.province || ''} ${r.data.city}`; this.locateOk = true; await this.saveCfg('manual_city', r.data.city); if (r.data.province) await this.saveCfg('ip_location_province', r.data.province); this.$emit('config-changed', 'manual_city', r.data.city) } else { this.locateResult = r.data.error || '获取失败'; this.locateOk = false } } catch (e) { this.locateResult = '请求失败'; this.locateOk = false } this.locating = false },
    async preciseLocate() { this.locating = 'gps'; try { let perm = 'prompt'; try { const ps = await navigator.permissions.query({ name: 'geolocation' }); perm = ps.state } catch (e) {} if (perm === 'denied') { this.locateResult = '定位权限已被拒绝，请在浏览器设置中允许'; this.locateOk = false; this.locating = false; return } const pos = await new Promise((resolve, reject) => { navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000, maximumAge: 300000 }) }); localStorage.setItem('gps_location_granted', '1'); const r = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude }); if (r.data.city) { const loc = r.data.district ? r.data.city + '·' + r.data.district : r.data.city; this.locateResult = loc; this.locateOk = true; await this.saveCfg('precise_city', loc); if (r.data.province) await this.saveCfg('ip_location_province', r.data.province); this.$emit('config-changed', 'precise_city', loc) } else { this.locateResult = '无法解析位置'; this.locateOk = false } } catch (e) { this.locateResult = e.code === 1 ? '定位权限被拒绝' : '定位失败，请检查权限'; this.locateOk = false } this.locating = false },
    resetLocation() { try { localStorage.removeItem('gps_location_granted'); localStorage.removeItem('location_granted'); localStorage.removeItem('location_denied') } catch (e) {} this.selProvince = ''; this.selCity = ''; this.cities = []; this.locateResult = '已重置'; this.locateOk = true },
    async loadProvinces() { try { const r = await api.get('/location/provinces'); this.provinces = r.data || [] } catch (e) {} },
    async loadCities() { this.selCity = ''; this.cities = []; if (!this.selProvince) return; try { const r = await api.get(`/location/cities/${this.selProvince}`); this.cities = r.data || [] } catch (e) {} },
    async saveManualCity() { if (!this.selCity) return; const city = this.cities.find(c => c.adcode === this.selCity); if (city) { await this.saveCfg('manual_city', city.name); this.locateResult = `已选择: ${city.name}`; this.locateOk = true } },
    // ── 颜色 ──
    async testAmap() { this.testingAmap = true; try { const r = await api.get('/location/ip'); this.amapTestOk = r.data.city ? true : false; this.amapTestMsg = r.data.city ? '连接成功: ' + r.data.city : (r.data.error || '无数据') } catch (e) { this.amapTestOk = false; this.amapTestMsg = '连接失败' } this.testingAmap = false },
    async testWeather() { this.testingWeather = true; this.weatherTestResults = null; try { const r = await api.get('/test/weather'); this.weatherTestResults = r.data } catch (e) { this.weatherTestResults = { ok: false, summary: '请求失败', sources: [{source:'网络',ok:false,reason:e.message||'未知错误'}] } } this.testingWeather = false },
    async checkRagStatus() { try { const r = await api.get('/rag/status'); this.ragStatus = r.data.model_loaded ? 'ready' : (r.data.installed ? 'installed' : 'missing'); this.ragCount = r.data.total_vectors || r.data.vector_count || 0 } catch (e) {} },
    async installRag() { this.installingRag = true; this.ragMsg = '正在安装向量引擎...'; this.ragMsgOk = false; try { const r = await api.post('/rag/install'); if (r.data.ok) { this.ragMsg = r.data.msg; this.ragMsgOk = true; this.checkRagStatus() } else { this.ragMsg = r.data.error; this.ragMsgOk = false } } catch (e) { this.ragMsg = '安装失败'; this.ragMsgOk = false } this.installingRag = false },
    async rebuildRag() { this.rebuildingRag = true; this.ragMsg = '正在重建索引...'; this.ragMsgOk = false; try { await api.post('/rag/rebuild'); this.ragMsg = '重建任务已提交，稍后刷新查看进度'; this.ragMsgOk = true; setTimeout(() => this.checkRagStatus(), 5000) } catch (e) { this.ragMsg = '重建失败'; this.ragMsgOk = false } this.rebuildingRag = false },
    async resetRelationship() { if (!confirm('确定要重置好感度、信任度和AI情绪为初始值吗？')) return; try { await api.post('/relationship/reset'); alert('已重置') } catch (e) { alert('重置失败') } },
    async resetMemory() { if (!confirm('确定要重置摘要记忆吗？此操作不可撤销。')) return; try { await api.post('/summary/reset'); alert('已重置') } catch (e) { alert('重置失败') } },
    async fullReset() {
      if (!confirm('确定要完全重置吗？\n\n将清除：\n- 所有聊天记录\n- 所有倒计时\n- 所有记忆和摘要\n- 人设和性格设置\n\nAPI 设置会保留。\n\n此操作不可撤销！')) return
      try {
        await api.post('/settings/full-reset')
        localStorage.removeItem('sakura_api_token')
        location.reload()
      } catch (e) { alert('重置失败: ' + (e.message || '未知错误')) }
    },
    async uploadAvatar(role, e) { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { await api.post(`/avatar/upload/${role}`, fd); this.$emit('config-changed', 'avatar_updated'); e.target.value = '' } catch (err) { alert('上传失败') } },
    async uploadAvatarByUrl(role) { const url = role === 'assistant' ? this.aiAvatarUrlLocal : this.userAvatarUrlLocal; if (!url) return; try { await api.post(`/avatar/upload-url/${role}`, { url }); this.$emit('config-changed', 'avatar_updated'); if (role === 'assistant') this.aiAvatarUrlLocal = ''; else this.userAvatarUrlLocal = '' } catch (err) { alert('导入失败') } },
    // 云端同步
    async saveCloudCfg() {
      try {
        await api.post('/cloud/config', { backend_type: this.cloudBackend, url: this.cloudUrl, username: this.cloudUser, password: this.cloudPass, passphrase: this.cloudPhrase })
        this.cloudMsg = '配置已保存'; this.cloudMsgOk = true
        setTimeout(() => this.cloudMsg = '', 3000)
      } catch (e) { this.cloudMsg = '保存失败'; this.cloudMsgOk = false }
    },
    async testCloudConn() {
      try {
        const r = await api.post('/cloud/test')
        this.cloudMsg = r.data.message || '连接成功'; this.cloudMsgOk = r.data.status === 'ok'
      } catch (e) { this.cloudMsg = '连接失败'; this.cloudMsgOk = false }
    },
    async cloudUpload() {
      this.cloudUploading = true; this.cloudMsg = ''
      try {
        const r = await api.post('/cloud/upload', { passphrase: this.cloudPhrase })
        this.cloudMsg = r.data.status === 'ok' ? '上传成功' : (r.data.message || '上传失败')
        this.cloudMsgOk = r.data.status === 'ok'
        if (r.data.status === 'ok') { const sr = await api.get('/cloud/status'); this.cloudLastSync = sr.data.last_sync || '' }
      } catch (e) { this.cloudMsg = '上传失败'; this.cloudMsgOk = false }
      finally { this.cloudUploading = false }
    },
    async loadCloudCfg() {
      try {
        const r = await api.get('/cloud/config')
        const cfg = r.data.config || {}
        this.cloudUrl = cfg.url || ''; this.cloudUser = cfg.username || ''; this.cloudPass = cfg.password || ''
        this.cloudBackend = cfg.backend_type || 'webdav'
        const sr = await api.get('/cloud/status')
        this.cloudLastSync = sr.data.last_sync || ''
      } catch (e) {}
    },
  }
}
</script>

<style scoped>
.settings-view { display: flex; height: 100%; }
.settings-nav { width: 180px; border-right: 1px solid var(--border-default); padding: 16px 0; display: flex; flex-direction: column; gap: 2px; }
.sn-item { padding: 10px 20px; background: none; border: none; text-align: left; font-size: 13px; color: var(--text-secondary); cursor: pointer; }
.sn-item:hover { background: rgba(255,255,255,.03); color: var(--text-primary); }
.sn-item.active { background: rgba(255,255,255,.04); color: var(--accent-primary); }
.settings-content { flex: 1; overflow-y: auto; padding: 20px; }
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border-default); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.hint-ok { color: #4caf50 !important; opacity: 1 !important; }
.hint-err { color: #e74c3c !important; opacity: 1 !important; }
.field-label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.input { width: 100%; padding: 6px 10px; background: var(--surface-app); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); font-size: 13px; outline: none; box-sizing: border-box; }
.input:focus { border-color: var(--accent-primary); }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.field input, .field select, textarea { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.field select { width: 100%; }
textarea { resize: vertical; }
.btn { padding: 7px 16px; background: var(--accent-primary); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.btn-s:hover { background: rgba(255,255,255,.06); }
.btn-s.danger { color: #f85149; border-color: #f85149; }
.btn-s.danger:hover { background: rgba(248,81,73,.1); }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
.switch { display: block; font-size: 13px; color: var(--text-primary); margin: 4px 0; cursor: pointer; }
.switch input { margin-right: 6px; }
.theme-row { display: flex; gap: 6px; flex-wrap: wrap; }
.theme-btn { flex: 1; padding: 8px; background: rgba(255,255,255,.03); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-secondary); cursor: pointer; font-size: 12px; min-width: 50px; }
.theme-btn.active { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
.preset-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.preset-item { padding: 4px 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border-default); border-radius: 4px; font-size: 12px; cursor: pointer; }
.preset-item:hover { background: rgba(255,255,255,.06); }
.phrase-row { display: flex; gap: 6px; margin-bottom: 6px; }
.phrase-row input { flex: 1; padding: 5px 8px; border-radius: 4px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 12px; }
.fav-item { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,.03); font-size: 12px; }
.fav-role { color: var(--accent-primary); white-space: nowrap; min-width: 30px; }
.fav-content { flex: 1; color: var(--text-primary); }
.empty { color: var(--text-secondary); font-size: 12px; padding: 10px; }
.preset-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.preset-chip { display: flex; align-items: center; gap: 4px; padding: 4px 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border-default); border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--text-secondary); transition: border-color .15s; }
.preset-chip:hover { border-color: var(--accent-primary); color: var(--text-primary); }
.preset-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.preset-del { color: #e74c3c; font-size: 14px; opacity: .4; }
.preset-del:hover { opacity: 1; }
.loc-hint { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
.color-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.color-field label { font-size: 11px; color: var(--text-secondary); }
.color-row { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.color-swatch { width: 20px; height: 20px; border-radius: 4px; border: 1px solid var(--border-default); flex-shrink: 0; }
.color-row input[type="color"] { width: 28px; height: 20px; padding: 0; border: none; background: none; cursor: pointer; }
.rel-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; }
.rel-label { color: var(--text-secondary); min-width: 50px; font-size: 12px; }
.rel-bar { flex: 1; height: 8px; background: rgba(255,255,255,.08); border-radius: 4px; overflow: hidden; }
.rel-fill { height: 100%; border-radius: 4px; transition: width .5s; }
.rel-fill.affection { background: linear-gradient(90deg, #f0a0b0, #e8929b); }
.rel-fill.trust { background: linear-gradient(90deg, #5390d4, #4ecdc4); }
.rel-value { color: var(--text-primary); min-width: 30px; text-align: right; font-size: 12px; }
.ai-emotion-tag { color: var(--accent-primary); font-size: 12px; }
.ai-emotion-desc { color: var(--text-secondary); font-size: 11px; margin-left: 8px; }
.avatar-section { display: flex; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.03); }
.avatar-preview { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.avatar-img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border-default); }
.avatar-label { font-size: 10px; color: var(--text-secondary); }
.avatar-actions { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.url-input { padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 11px; }

/* 移动端适配 */
@media (max-width: 768px) {
  .settings-view { flex-direction: column; }
  .settings-nav {
    width: 100%;
    flex-direction: row;
    border-right: none;
    border-bottom: 1px solid var(--border-default);
    padding: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .settings-nav::-webkit-scrollbar { display: none; }
  .sn-item {
    padding: 10px 14px;
    white-space: nowrap;
    flex-shrink: 0;
    font-size: 12px;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .settings-content { padding: 12px; }
  .card { padding: 12px; }
  .avatar-section { flex-direction: column; align-items: flex-start; }
  .color-grid { grid-template-columns: 1fr; }
  .btn { min-height: 44px; }
  .btn-s { min-height: 44px; }
  .hint { font-size: 12px; }
}
.foundation-confirm { margin-top: 12px; padding: 12px; background: rgba(83,144,212,.08); border-radius: 8px; border: 1px solid var(--border, #30363d); }
.foundation-confirm p { margin: 0 0 8px; font-size: 13px; }
.foundation-confirm label { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 10px; cursor: pointer; }
.foundation-confirm .btn-row { display: flex; gap: 8px; }
.foundation-confirm .btn { padding: 6px 16px; font-size: 13px; }
.btn-secondary { background: var(--border, #30363d); color: var(--tc, #e6edf3); }
.btn-secondary:hover { background: var(--tc2, #8b949e); }
.cloud-panel { display: flex; flex-direction: column; gap: 8px; }
.cloud-row { display: flex; align-items: center; gap: 8px; }
.cloud-row label { font-size: 12px; color: var(--text-secondary); min-width: 80px; flex-shrink: 0; }
.cloud-row input, .cloud-row select { flex: 1; padding: 6px 8px; background: var(--surface-app); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); font-size: 12px; }
.cloud-actions { display: flex; gap: 8px; margin-top: 4px; }
.cloud-msg { font-size: 12px; padding: 4px 0; }
.cloud-msg.ok { color: #4caf50; }
.cloud-msg.err { color: #e74c3c; }
.cloud-last { font-size: 11px; color: var(--text-secondary); }
</style>
