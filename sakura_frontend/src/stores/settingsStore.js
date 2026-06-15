// stores/settingsStore.js — 设置状态：主题、人设、外观、聊天偏好
import { defineStore } from 'pinia'
import api from '../api'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    allSettings: {},
    currentTheme: 'dark',
    themeLocal: 'dark',
    aiNameLocal: '佐仓',
    userNameLocal: '',
    chatFontSize: 14,
    chatBgImage: '',
    bgOpacity: 1,
    bgBlur: 0,
    bgMode: 'cover',
    sentenceMode: 'auto',
    quickPhrases: [],
  }),

  actions: {
    /** 从后端加载所有设置 */
    async loadAllSettings() {
      try {
        const res = await api.get('/settings/')
        const s = res.data
        this.allSettings = s
        this.themeLocal = s.theme || 'dark'
        this.currentTheme = this._resolveTheme(this.themeLocal)
        document.documentElement.setAttribute('data-theme', this.currentTheme)
        this.aiNameLocal = s.ai_name || '佐仓'
        this.userNameLocal = s.user_name || ''
        if (s.chat_bg_image) this.chatBgImage = s.chat_bg_image
        if (s.bg_opacity !== undefined) this.bgOpacity = Number(s.bg_opacity)
        if (s.bg_blur !== undefined) this.bgBlur = Number(s.bg_blur)
        if (s.bg_mode) this.bgMode = s.bg_mode
        if (s.chat_font_size) this.chatFontSize = Number(s.chat_font_size)
        if (s.sentence_mode) this.sentenceMode = s.sentence_mode
        if (s.quick_phrases) {
          try { this.quickPhrases = JSON.parse(s.quick_phrases) } catch (e) { this.quickPhrases = [] }
        }
        return s
      } catch (e) {
        console.error('loadAllSettings failed:', e)
        return null
      }
    },

    /** 更新单个设置 + 处理副作用 */
    applySetting(key, value) {
      this.allSettings[key] = value
      if (key === 'theme') {
        this.currentTheme = this._resolveTheme(value)
        this.themeLocal = value
        document.documentElement.setAttribute('data-theme', this.currentTheme)
      } else if (key === 'ai_name') {
        this.aiNameLocal = value
      } else if (key === 'user_name') {
        this.userNameLocal = value
      } else if (key === 'quick_phrases') {
        try { this.quickPhrases = JSON.parse(value) } catch (e) { this.quickPhrases = value || [] }
      } else if (key === 'bg_style') {
        if (value.opacity !== undefined) this.bgOpacity = value.opacity
        if (value.blur !== undefined) this.bgBlur = value.blur
        if (value.mode) this.bgMode = value.mode
      } else if (key === 'chat_bg_image') {
        this.chatBgImage = value
      } else if (key === 'sentence_mode') {
        this.sentenceMode = value
      } else if (key === 'chat_font_size') {
        this.chatFontSize = Number(value)
      }
    },

    /** 主题名校验 */
    _resolveTheme(t) {
      const valid = ['dark', 'light', 'sakura', 'vesper', 'ocean', 'forest', 'sunset', 'mono', 'candy', 'nord']
      return valid.includes(t) ? t : 'dark'
    },
  },
})