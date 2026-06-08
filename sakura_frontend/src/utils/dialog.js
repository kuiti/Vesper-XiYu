// utils/dialog.js — 全局弹窗工具（旧组件 Options API 兼容）
// 在 App.vue 的 onMounted 中注入 Naive UI 实例，组件直接 import 使用
// 替代所有浏览器原生 alert()/confirm()/prompt()

let _dialog = null
let _message = null

export function initDialog(d, m) {
  _dialog = d
  _message = m
}

/** 确认弹窗 — 替代 window.confirm()，返回 Promise<boolean> */
export function showConfirm(options) {
  if (!_dialog) return Promise.resolve(window.confirm(options.content || ''))
  return new Promise(resolve => {
    _dialog.warning({
      title: options.title || '确认操作',
      content: options.content || '',
      positiveText: options.confirmText || '确定',
      negativeText: options.cancelText || '取消',
      onPositiveClick: () => resolve(true),
      onNegativeClick: () => resolve(false),
      onClose: () => resolve(false),
      maskClosable: false,
    })
  })
}

/** 提示消息 — 替代 alert()，右上角滑入 */
export function showMessage(content, type = 'warning', duration = 3000) {
  if (!_message) { alert(content); return }
  _message[type](content, { duration })
}

// 便捷方法
export const alert = (content, duration) => showMessage(content, 'warning', duration)
export const success = (content, duration) => showMessage(content, 'success', duration)
export const error = (content, duration) => showMessage(content, 'error', duration)
export const info = (content, duration) => showMessage(content, 'info', duration)
