// stores/ui.js — UI 全局状态（弹窗、通知、布局）
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // Naive UI 的 useDialog / useMessage 在 setup 外不可用，
  // 所以暴露注册函数，由 App.vue 在 mount 时注入
  let _dialog = null
  let _message = null

  function registerDialog(d) { _dialog = d }
  function registerMessage(m) { _message = m }

  // 确认弹窗（替代 window.confirm）
  function confirm(options) {
    if (!_dialog) return Promise.resolve(false)
    return new Promise(resolve => {
      _dialog.warning({
        title: options.title || '确认操作',
        content: options.content || '',
        positiveText: options.confirmText || '确定',
        negativeText: options.cancelText || '取消',
        onPositiveClick: () => resolve(true),
        onNegativeClick: () => resolve(false),
        onClose: () => resolve(false),
      })
    })
  }

  // 通知提示（替代 alert）
  function notify(options) {
    if (!_message) return
    const type = options.type || 'info'
    const fn = _message[type] || _message.info
    fn(options.content || '', { duration: options.duration || 3000 })
  }

  // 便捷方法
  const alert = (content, duration) => notify({ type: 'warning', content, duration })
  const success = (content, duration) => notify({ type: 'success', content, duration })
  const error = (content, duration) => notify({ type: 'error', content, duration })

  // 侧栏状态
  const sidebarOpen = ref(true)
  function toggleSidebar() { sidebarOpen.value = !sidebarOpen.value }

  return {
    registerDialog, registerMessage,
    confirm, notify, alert, success, error,
    sidebarOpen, toggleSidebar,
  }
})
