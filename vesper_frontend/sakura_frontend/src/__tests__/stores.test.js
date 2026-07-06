import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUiStore } from '../stores/uiStore'
import { useSettingsStore } from '../stores/settingsStore'
import { useChatStore } from '../stores/chatStore'

describe('uiStore', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('has correct defaults', () => {
    const ui = useUiStore()
    expect(ui.activeView).toBe('chat')
    expect(ui.showOnboarding).toBe(false)
    expect(ui.showLockScreen).toBe(false)
    expect(ui.needLogin).toBe(false)
    expect(ui.gameToast).toBeNull()
  })

  it('navigate changes activeView', () => {
    const ui = useUiStore()
    ui.navigate('settings')
    expect(ui.activeView).toBe('settings')
  })

  it('navigate closes context menu', () => {
    const ui = useUiStore()
    ui.showContextMenu = true
    ui.navigate('tools')
    expect(ui.showContextMenu).toBe(false)
  })

  it('showConfirm returns Promise', () => {
    const ui = useUiStore()
    const p = ui.showConfirm('test?')
    expect(p).toBeInstanceOf(Promise)
    expect(ui.confirmDialog.show).toBe(true)
    expect(ui.confirmDialog.msg).toBe('test?')
    ui.resolveConfirm(true)
  })

  it('resolveConfirm closes dialog', () => {
    const ui = useUiStore()
    ui.showConfirm('are you sure?')
    ui.resolveConfirm(false)
    expect(ui.confirmDialog.show).toBe(false)
  })

  it('unlock succeeds with correct pin', () => {
    const ui = useUiStore()
    ui.pinCode = '1234'
    expect(ui.unlock('1234')).toBe(true)
    expect(ui.showLockScreen).toBe(false)
  })

  it('unlock fails with wrong pin', () => {
    const ui = useUiStore()
    ui.pinCode = '1234'
    expect(ui.unlock('0000')).toBe(false)
  })
})

describe('settingsStore', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('has correct defaults', () => {
    const s = useSettingsStore()
    expect(s.aiNameLocal).toBe('佐仓')
    expect(s.currentTheme).toBe('dark')
    expect(s.chatFontSize).toBe(14)
    expect(s.sentenceMode).toBe('auto')
    expect(s.quickPhrases).toEqual([])
  })

  it('applySetting updates theme', () => {
    const s = useSettingsStore()
    s.applySetting('theme', 'sakura')
    expect(s.currentTheme).toBe('sakura')
    expect(s.themeLocal).toBe('sakura')
  })

  it('applySetting updates aiName', () => {
    const s = useSettingsStore()
    s.applySetting('ai_name', '小雪')
    expect(s.aiNameLocal).toBe('小雪')
  })

  it('applySetting updates bg_style', () => {
    const s = useSettingsStore()
    s.applySetting('bg_style', { opacity: 0.5, blur: 10, mode: 'contain' })
    expect(s.bgOpacity).toBe(0.5)
    expect(s.bgBlur).toBe(10)
    expect(s.bgMode).toBe('contain')
  })

  it('_resolveTheme rejects invalid', () => {
    const s = useSettingsStore()
    expect(s._resolveTheme('invalid')).toBe('dark')
    expect(s._resolveTheme('vesper')).toBe('vesper')
  })
})

describe('chatStore', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('has correct defaults', () => {
    const c = useChatStore()
    expect(c.ws).toBeNull()
    expect(c.wsReady).toBe(false)
    expect(c.messages).toEqual([])
    expect(c.isStreaming).toBe(false)
    expect(c.pendingReply).toBe('')
    expect(c.totalMessages).toBe(0)
  })

  it('sendMessage returns false when not connected', () => {
    const c = useChatStore()
    expect(c.sendMessage('hello')).toBe(false)
  })

  it('stopTypewriter clears state', () => {
    const c = useChatStore()
    c.isStreaming = true
    c._twActive = true
    c._twQueue = ['test']
    c.stopTypewriter()
    expect(c.isStreaming).toBe(false)
    expect(c._twActive).toBe(false)
    expect(c._twQueue).toEqual([])
  })
})