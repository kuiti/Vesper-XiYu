// stores/uiStore.js — UI 全局状态：导航、对话框、锁屏、成就弹窗
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    activeView: 'chat',  // chat | tools | diary | games | stats | memory | characters | settings | history
    showOnboarding: false,
    showLockScreen: false,
    needLogin: false,
    pinEnabled: false,
    pinCode: '',
    showEmojiPicker: false,
    showContextMenu: false,
    ctxMenuX: 0,
    ctxMenuY: 0,
    ctxTargetMsg: null,
    confirmDialog: { show: false, msg: '', resolve: null },
    achievementPopup: null,
    gameToast: null,
    _toastTimer: null,
    _achieveTimer: null,
  }),

  actions: {
    /** 切换当前视图 */
    navigate(view) {
      this.activeView = view
      this.showContextMenu = false
    },

    /** 显示确认对话框，返回 Promise<boolean> */
    showConfirm(msg) {
      return new Promise(resolve => {
        this.confirmDialog = { show: true, msg, resolve }
      })
    },

    /** 关闭确认对话框并返回结果 */
    resolveConfirm(result) {
      if (this.confirmDialog.resolve) {
        this.confirmDialog.resolve(result)
      }
      this.confirmDialog = { show: false, msg: '', resolve: null }
    },

    /** 显示成就弹窗（5 秒后自动消失） */
    showAchievement(data) {
      this.achievementPopup = data
      clearTimeout(this._achieveTimer)
      this._achieveTimer = setTimeout(() => { this.achievementPopup = null }, 5000)
    },

    /** 显示 toast 提示（自动消失，时长与内容长度相关） */
    showToast(content) {
      this.gameToast = content
      clearTimeout(this._toastTimer)
      const dur = Math.min(10000, Math.max(3000, (content || '').length * 80))
      this._toastTimer = setTimeout(() => { this.gameToast = null }, dur)
    },

    /** 根据 pin 设置决定是否显示锁屏 */
    maybeShowLockScreen(pinEnabled, pinCode) {
      if (pinEnabled && pinCode) {
        this.showLockScreen = true
      }
    },

    /** 解锁，返回 true/false */
    unlock(pin) {
      if (pin === this.pinCode) {
        this.showLockScreen = false
        return true
      }
      return false
    },
  },
})