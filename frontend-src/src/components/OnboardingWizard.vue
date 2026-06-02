<template>
  <div class="onboarding-overlay">
    <div class="onboarding-card">
      <!-- 步骤指示器 -->
      <div class="steps">
        <div v-for="(s, i) in steps" :key="i" :class="['step', { active: i === currentStep, done: i < currentStep }]">
          <span class="step-num">{{ i + 1 }}</span>
          <span class="step-label">{{ s }}</span>
        </div>
      </div>

      <!-- Step 1: 取名字 -->
      <div v-if="currentStep === 0" class="step-content">
        <h2>取个名字</h2>
        <p class="desc">给你们起个名字吧，之后可以随时改</p>
        <div class="field">
          <label>AI 的名字</label>
          <input v-model="aiNameInput" placeholder="夕语">
        </div>
        <div class="field">
          <label>你的名字</label>
          <input v-model="userNameInput" placeholder="彦祖">
        </div>
      </div>

      <!-- Step 2: 选角色 -->
      <div v-if="currentStep === 1" class="step-content">
        <h2>选择 AI 角色</h2>
        <p class="desc">每个角色有不同的性格和说话风格，之后可以随时在设置中切换</p>
        <div class="preset-grid">
          <div v-for="p in presets" :key="p.name" :class="['preset-card', { selected: selectedPreset === p.name }]" @click="selectedPreset = p.name">
            <div class="preset-name">{{ p.name }}</div>
            <div class="preset-tone">{{ getToneEmoji(p.data.tone) }} {{ p.data.tone }}</div>
            <div class="preset-desc">{{ getPresetDesc(p) }}</div>
          </div>
        </div>
        <div v-if="selectedPreset" class="preset-preview">
          <div class="preview-header">已选择「{{ selectedPreset }}」，试着这样说话：</div>
          <div class="preview-dialog">{{ getPresetPreview(selectedPreset) }}</div>
        </div>
        <div class="custom-role-section">
          <div class="custom-role-header" @click="showCustomRole = !showCustomRole">
            <span class="custom-role-toggle">{{ showCustomRole ? '▼' : '▶' }} 或者，自定义一个独一无二的角色</span>
            <span class="custom-role-hint">每个角色都可以有自己的脾气和故事</span>
          </div>
          <div v-if="showCustomRole" class="custom-role-content">
            <div class="field">
              <label>角色名称</label>
              <input v-model="customRoleName" placeholder="给角色起个名字">
            </div>
            <div class="field">
              <label>性格描述</label>
              <textarea v-model="customRolePersonality" placeholder="例如：温柔体贴，偶尔毒舌，喜欢用颜文字&#10;越详细AI越能演出你想要的性格" rows="4"></textarea>
            </div>
            <div class="field">
              <label>说话风格</label>
              <select v-model="customRoleTone">
                <option value="">-- 选择语气 --</option>
                <option value="冷静">冷静</option>
                <option value="活泼">活泼</option>
                <option value="温柔">温柔</option>
                <option value="毒舌">毒舌</option>
                <option value="傲娇">傲娇</option>
                <option value="自由">自由</option>
              </select>
            </div>
            <div class="custom-role-note">自定义角色会覆盖上方预设选择</div>
          </div>
        </div>
      </div>

      <!-- Step 3: 选关系 -->
      <div v-if="currentStep === 2" class="step-content">
        <h2>选择关系类型</h2>
        <p class="desc">决定你和{{ aiNameInput || '夕语' }}的初始关系，之后可以随时在设置中切换</p>
        <div class="foundation-grid">
          <div v-for="(info, type) in foundationTypes" :key="type" :class="['foundation-card', { selected: selectedFoundation === type }]" @click="selectedFoundation = type">
            <div class="foundation-name">{{ type }}</div>
            <div class="foundation-values">好感: {{ info.default_affection }} | 信任: {{ info.default_trust }}</div>
          </div>
        </div>
      </div>

      <!-- Step 4: 配 API -->
      <div v-if="currentStep === 3" class="step-content">
        <h2>配置 AI 接口</h2>
        <p class="desc">支持云端和本地模型，之后可以随时修改</p>
        <div class="field"><label>提供商</label><select v-model="provider" @change="onProviderChange"><option value="deepseek">DeepSeek</option><option value="qwen">通义千问</option><option value="moonshot">Moonshot</option><option value="zhipu">智谱 GLM</option><option value="openai">OpenAI</option><option value="ollama">Ollama (本地)</option><option value="custom">自定义</option></select></div>
        <div class="field"><label>API 地址</label><input v-model="baseUrl" placeholder="https://api.deepseek.com/v1"></div>
        <div class="field" v-if="provider !== 'ollama'"><label>API Key</label><input type="password" v-model="apiKey" placeholder="sk-..."></div>
        <div class="field" v-if="provider === 'ollama'"><div class="ollama-note">本地模型无需 API Key，确保 Ollama 已启动</div></div>
        <button class="btn-test" @click="testConnection" :disabled="testing">{{ testing ? '测试中...' : '测试连接' }}</button>
        <span :class="testStatus">{{ testMsg }}</span>
      </div>

      <!-- Step 5: 功能介绍 -->
      <div v-if="currentStep === 4" class="step-content">
        <h2>准备就绪</h2>
        <p class="desc">来看看{{ aiNameInput || '夕语' }}能做什么</p>
        <div class="feature-list">
          <div class="feature-item"><div><strong>AI 聊天</strong><p>流式回复，情感感知，角色扮演</p></div></div>
          <div class="feature-item"><div><strong>长期记忆</strong><p>记住你的喜好和说过的重要事情</p></div></div>
          <div class="feature-item"><div><strong>生活工具</strong><p>待办清单、提醒事项、笔记、倒计时</p></div></div>
          <div class="feature-item"><div><strong>天气关怀</strong><p>每天三次天气推送</p></div></div>
        </div>
        <button class="btn-start" @click="finish">开始使用</button>
      </div>

      <!-- 底部按钮 -->
      <div class="onboarding-footer">
        <button v-if="currentStep > 0" class="btn-back" @click="currentStep--">上一步</button>
        <span class="spacer"></span>
        <button v-if="currentStep < 4" class="btn-next" @click="goNext">下一步</button>
        <button class="btn-skip" @click="skip">跳过全部</button>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'

export default {
  name: 'OnboardingWizard',
  props: { aiName: { type: String, default: '夕语' } },
  emits: ['completed'],
  data() {
    return {
      currentStep: 0,
      steps: ['取名字', '选角色', '选关系', '配 API', '开始'],
      aiNameInput: '夕语',
      userNameInput: '彦祖',
      selectedPreset: '',
      selectedFoundation: '空白',
      provider: 'deepseek',
      baseUrl: 'https://api.deepseek.com/v1',
      apiKey: '',
      testing: false,
      testStatus: '',
      testMsg: '',
      presets: [],
      foundationTypes: {},
      // 自定义角色
      showCustomRole: false,
      customRoleName: '',
      customRolePersonality: '',
      customRoleTone: '',
    }
  },
  async mounted() {
    try {
      const res = await api.get('/settings/presets')
      const data = res.data || {}
      // 过滤掉"沉稳大叔"预设
      const filtered = Object.entries(data).filter(([name]) => name !== '沉稳大叔')
      this.presets = filtered.map(([name, d]) => ({ name, data: d, icon: '' }))
    } catch (e) { /* 预设加载失败不阻塞 */ }
    try {
      const res = await api.get('/settings/foundation-types')
      this.foundationTypes = res.data || {}
    } catch (e) { /* 基石类型加载失败不阻塞 */ }
  },
  methods: {
    onProviderChange() {
      const m = {
        deepseek: { url: 'https://api.deepseek.com/v1' },
        qwen: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
        moonshot: { url: 'https://api.moonshot.cn/v1' },
        zhipu: { url: 'https://open.bigmodel.cn/api/paas/v4' },
        openai: { url: 'https://api.openai.com/v1' },
        ollama: { url: 'http://localhost:11434/v1' },
        custom: { url: '' }
      }[this.provider]
      if (m) this.baseUrl = m.url
    },
    async testConnection() {
      this.testing = true; this.testStatus = ''; this.testMsg = ''
      try {
        // 先保存 API Key 和配置
        await api.post('/settings/', { key: 'api_provider', value: this.provider })
        await api.post('/settings/', { key: 'api_base_url', value: this.baseUrl })
        if (this.apiKey && this.provider !== 'ollama') {
          await api.post('/settings/', { key: 'api_key', value: this.apiKey })
        }
        // 测试连接
        const res = await api.get('/test/deepseek')
        this.testStatus = res.data.ok ? 'ok' : 'fail'
        this.testMsg = res.data.message || (res.data.ok ? '连接成功' : '连接失败')
      } catch (e) {
        this.testStatus = 'fail'; this.testMsg = '连接失败: ' + (e.message || '未知错误')
      } finally { this.testing = false }
    },
    goNext() {
      this.currentStep++
    },
    getToneEmoji(tone) {
      const m = { '冷静': '🧊', '活泼': '🎉', '温柔': '🌸', '毒舌': '🌶️', '傲娇': '😤', '自由': '🎭' }
      return m[tone] || '💬'
    },
    getPresetDesc(p) {
      const m = {
        '傲娇': '嘴上不承认但心里在乎你',
        '温柔': '软软的，会关心你的日常',
        '毒舌': '说话带刺但其实是关心',
        '活泼': '元气满满，像永远有用不完的精力',
        '自由': '想到什么说什么，不受拘束',
        '冷静': '理性分析，沉稳可靠',
        '沉稳大叔': '成熟稳重，偶尔说教'
      }
      return m[p.name] || (p.data.custom_system_prompt || '').slice(0, 40)
    },
    getPresetPreview(name) {
      const m = {
        '傲娇': '"…哼，才不是因为你才这样的。不过你今天记得吃饭了吗？"',
        '温柔': '"今天天气不错呢～要不要一起去散个步？记得多穿点哦。"',
        '毒舌': '"又熬夜？你以为自己是铁打的啊。去睡觉，现在。"',
        '活泼': '"耶！你终于来了！我等你好久啦～今天有什么好玩的？"',
        '自由': '"啊，今天心情不错，想吃火锅。你呢，有什么新鲜事？"',
        '冷静': '"我分析了一下你最近的作息，建议调整到23点前入睡。"',
        '沉稳大叔': '"年轻人，这个道理嘛，我活了这么多年才明白……"'
      }
      return m[name] || '试着聊聊天吧，AI会用你选择的性格来回应你'
    },
    async skip() {
      try { await api.post('/settings/onboarding-complete') } catch (e) {}
      this.$emit('completed')
    },
    async finish() {
      try {
        // 保存名字
        if (this.aiNameInput) {
          await api.post('/settings/', { key: 'ai_name', value: this.aiNameInput })
        }
        if (this.userNameInput) {
          await api.post('/settings/', { key: 'user_name', value: this.userNameInput })
        }
        // 保存角色预设（自定义角色优先）
        if (this.showCustomRole && (this.customRoleName || this.customRolePersonality)) {
          // 自定义角色
          if (this.customRoleName) {
            await api.post('/settings/', { key: 'ai_name', value: this.customRoleName })
          }
          if (this.customRoleTone) {
            await api.post('/settings/', { key: 'personality_tone', value: this.customRoleTone })
          }
          if (this.customRolePersonality) {
            await api.post('/settings/', { key: 'custom_system_prompt', value: this.customRolePersonality })
          }
        } else if (this.selectedPreset) {
          // 预设角色
          const preset = this.presets.find(p => p.name === this.selectedPreset)
          if (preset) {
            await api.post('/settings/', { key: 'personality_tone', value: preset.data.tone })
            await api.post('/settings/', { key: 'length_level', value: preset.data.length })
            await api.post('/settings/', { key: 'recall_past', value: preset.data.recall })
            await api.post('/settings/', { key: 'allow_emotion', value: preset.data.allow_emotion !== false })
            if (preset.data.custom_system_prompt) {
              await api.post('/settings/', { key: 'custom_system_prompt', value: preset.data.custom_system_prompt })
            }
          }
        }
        // 保存基石类型
        if (this.selectedFoundation && this.selectedFoundation !== '空白') {
          await api.post('/settings/foundation', { foundation_type: this.selectedFoundation })
        }
        // 保存 API 配置
        await api.post('/settings/', { key: 'api_provider', value: this.provider })
        await api.post('/settings/', { key: 'api_base_url', value: this.baseUrl })
        if (this.apiKey && this.provider !== 'ollama') {
          await api.post('/settings/', { key: 'api_key', value: this.apiKey })
        }
        await api.post('/settings/onboarding-complete')
      } catch (e) { /* 部分保存失败不阻塞 */ }
      this.$emit('completed')
    }
  }
}
</script>

<style scoped>
.onboarding-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.85); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.onboarding-card { background: var(--sb, #161b22); border: 1px solid var(--border, #30363d); border-radius: 16px; padding: 32px; width: 600px; max-width: 95vw; max-height: 85vh; overflow-y: auto; color: var(--tc, #e6edf3); }
.steps { display: flex; gap: 8px; margin-bottom: 24px; }
.step { flex: 1; text-align: center; opacity: .4; transition: opacity .2s; }
.step.active, .step.done { opacity: 1; }
.step-num { display: inline-flex; width: 28px; height: 28px; border-radius: 50%; background: var(--border, #30363d); align-items: center; justify-content: center; font-size: 13px; margin-right: 6px; }
.step.active .step-num { background: var(--p, #5390d4); }
.step.done .step-num { background: #2ea043; }
.step-label { font-size: 13px; }
.step-content { min-height: 280px; }
.step-content h2 { margin: 0 0 8px; font-size: 20px; }
.desc { color: var(--tc2, #8b949e); font-size: 13px; margin-bottom: 16px; }
.preset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.preset-card { border: 2px solid var(--border, #30363d); border-radius: 12px; padding: 16px 10px; text-align: center; cursor: pointer; transition: all .15s; }
.preset-card:hover { border-color: var(--tc2, #8b949e); }
.preset-card.selected { border-color: var(--p, #5390d4); background: rgba(83,144,212,.1); }
.preset-icon { font-size: 32px; margin-bottom: 8px; }
.preset-name { font-size: 15px; font-weight: 600; }
.preset-tone { font-size: 12px; color: var(--tc2, #8b949e); margin-top: 4px; }
.preset-desc { font-size: 11px; color: var(--tc2, #8b949e); margin-top: 6px; opacity: .7; line-height: 1.4; }
/* 预设预览 */
.preset-preview { margin-top: 14px; padding: 12px; background: rgba(83,144,212,.08); border-radius: 10px; border: 1px solid rgba(83,144,212,.2); }
.preview-header { font-size: 12px; color: var(--p, #5390d4); margin-bottom: 8px; }
.preview-dialog { font-size: 13px; color: var(--tc, #e6edf3); font-style: italic; line-height: 1.5; }
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 13px; margin-bottom: 4px; color: var(--tc2, #8b949e); }
.field input, .field select { width: 100%; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border, #30363d); background: var(--bg, #0d1117); color: var(--tc, #e6edf3); font-size: 13px; box-sizing: border-box; }
.ollama-note { font-size: 12px; color: var(--tc2, #8b949e); padding: 8px; background: rgba(83,144,212,.08); border-radius: 6px; }
.btn-test { background: var(--border, #30363d); color: var(--tc, #e6edf3); border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; margin-right: 8px; }
.btn-test:hover { background: var(--tc2, #8b949e); }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #f85149; font-size: 12px; }
.feature-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }
.feature-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px; background: rgba(255,255,255,.03); border-radius: 8px; }
.feature-item strong { font-size: 14px; }
.feature-item p { margin: 2px 0 0; font-size: 12px; color: var(--tc2, #8b949e); }
.feat-icon { font-size: 24px; flex-shrink: 0; }
.btn-start { width: 100%; padding: 12px; background: var(--p, #5390d4); color: #fff; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: 600; }
.btn-start:hover { filter: brightness(1.1); }
.onboarding-footer { display: flex; align-items: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border, #30363d); }
.btn-back, .btn-skip { background: transparent; color: var(--tc2, #8b949e); border: 1px solid var(--border, #30363d); padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-next { background: var(--p, #5390d4); color: #fff; border: none; padding: 6px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.spacer { flex: 1; }
.foundation-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.foundation-card { border: 2px solid var(--border, #30363d); border-radius: 12px; padding: 12px 8px; text-align: center; cursor: pointer; transition: all .15s; }
.foundation-card:hover { border-color: var(--tc2, #8b949e); }
.foundation-card.selected { border-color: var(--p, #5390d4); background: rgba(83,144,212,.1); }
.foundation-name { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.foundation-values { font-size: 11px; color: var(--tc2, #8b949e); }
/* 自定义角色区域 */
.custom-role-section { margin-top: 16px; border: 1px solid var(--border, #30363d); border-radius: 10px; overflow: hidden; }
.custom-role-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; cursor: pointer; background: rgba(255,255,255,.02); }
.custom-role-header:hover { background: rgba(255,255,255,.04); }
.custom-role-toggle { font-size: 13px; font-weight: 600; color: var(--tc, #e6edf3); }
.custom-role-hint { font-size: 11px; color: var(--tc2, #8b949e); }
.custom-role-content { padding: 14px; border-top: 1px solid var(--border, #30363d); }
.custom-role-content .field { margin-bottom: 10px; }
.custom-role-content .field label { display: block; font-size: 12px; color: var(--tc2, #8b949e); margin-bottom: 4px; }
.custom-role-content .field input, .custom-role-content .field textarea, .custom-role-content .field select { width: 100%; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border, #30363d); background: var(--bg, #0d1117); color: var(--tc, #e6edf3); font-size: 13px; box-sizing: border-box; font-family: inherit; }
.custom-role-content textarea { resize: vertical; min-height: 60px; }
.custom-role-note { font-size: 11px; color: var(--tc2, #8b949e); opacity: .7; margin-top: 8px; }
</style>
