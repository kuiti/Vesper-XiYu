<template>
  <div class="sc-pane">
    <div class="card"><h3>隐私锁</h3><p class="hint">启动时需要输入密码才能进入聊天界面。忘记密码时输错3次后可重置。</p>
      <label class="switch"><input type="checkbox" :checked="pinEnabled" @change="$emit('toggle-pin')"> 启用 PIN 锁</label>
      <div v-if="pinEnabled" class="field" style="margin-top:8px"><label>密码</label><input type="password" :value="pinCode" @input="$emit('update:pinCode', $event.target.value)" @change="$emit('save-pin')"></div>
    </div>
    <div class="card"><h3>通知</h3>
      <label class="switch"><input type="checkbox" :checked="useSysNotify" @change="$emit('update:useSysNotify', $event.target.checked); $emit('save-cfg', 'use_system_notification', $event.target.checked)"> 系统通知</label><p class="hint">Windows 桌面推送。提醒到期、AI 主动问候时弹窗。</p>
      <label class="switch"><input type="checkbox" :checked="useWeather" @change="$emit('update:useWeather', $event.target.checked); $emit('save-cfg', 'use_weather_care', $event.target.checked)"> 天气关怀</label><p class="hint">每天 7:00 / 12:00 / 19:00 自动推送当地天气，主动问候也会提及天气。定位城市可在「定位」设置中修改。</p>
      <label class="switch"><input type="checkbox" :checked="showTray" @change="$emit('update:showTray', $event.target.checked); $emit('save-cfg', 'show_tray_notification', $event.target.checked)"> 托盘提示</label><p class="hint">最小化到托盘时显示气泡提示。</p>
      <div class="field" style="margin-top:8px"><label>通知风格</label><select :value="notifyStyle" @change="$emit('update:notifyStyle', $event.target.value); $emit('save-cfg', 'notification_style', $event.target.value)"><option value="warm">温暖</option><option value="casual">随意</option><option value="humorous">幽默</option><option value="concise">简洁</option><option value="tsundere">傲娇</option><option value="free">自由</option></select><p class="hint">影响天气推送和主动问候的文案语气。温暖偏向关怀口吻，随意更口语化，幽默带俏皮玩笑，简洁只说重点，傲娇口是心非，自由由AI自行决定。</p></div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    pinEnabled: Boolean,
    pinCode: String,
    useSysNotify: Boolean,
    useWeather: Boolean,
    showTray: Boolean,
    notifyStyle: String,
  },
  emits: [
    'update:pinCode', 'update:useSysNotify', 'update:useWeather', 'update:showTray', 'update:notifyStyle',
    'toggle-pin', 'save-pin', 'save-cfg',
  ],
}
</script>