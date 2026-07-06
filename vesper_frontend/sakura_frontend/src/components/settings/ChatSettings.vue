<template>
  <div class="sc-pane">
    <div class="card"><h3>字体大小</h3>
      <div class="field"><input type="range" min="10" max="20" :value="chatFontSize" @input="$emit('update:chatFontSize', Number($event.target.value))" @change="$emit('save-cfg', 'chat_font_size', chatFontSize)"><span style="margin-left:8px;font-size:13px;color:var(--tc2)">{{ chatFontSize }}px</span></div>
    </div>
    <div class="card"><h3>分句模式</h3><p class="hint">智能分句：按标点自动断句，短于12字的句子会自动合并避免刷屏。分隔符分句：AI 主动用分隔符控制断句位置。逐字显示：模拟打字效果逐字弹出。连续输出：一次性显示全部回复。</p>
      <select :value="sentenceMode" @change="$emit('update:sentenceMode', $event.target.value); $emit('save-cfg', 'sentence_mode', $event.target.value)"><option value="auto">智能分句</option><option value="delimiter">分隔符分句</option><option value="typewriter">逐字显示</option><option value="raw">连续输出</option></select>
    </div>
    <div class="card"><h3>主动频率</h3><p class="hint">AI 在你沉默后主动发起话题的间隔。关闭：不主动说话；低：约 3 小时；中：约 40-120 分钟（根据你回复率自动调整）；高：约 30 分钟。深夜 23:00-7:00 不打扰。</p>
      <select :value="proactiveFreq" @change="$emit('update:proactiveFreq', $event.target.value); $emit('save-cfg', 'proactive_frequency', $event.target.value)"><option value="off">关闭</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select>
    </div>
    <div class="card"><h3>主动风格</h3><p class="hint">AI 主动找你说话时的语气。温暖关怀：像朋友一样关心近况再自然聊开；幽默调侃：带俏皮玩笑让人会心一笑；简洁直接：控制在15字以内说重点；自由发挥：由 AI 自行决定语气。主动消息会自动融入天气和位置信息。</p>
      <select :value="proactiveStyle" @change="$emit('update:proactiveStyle', $event.target.value); $emit('save-cfg', 'proactive_style', $event.target.value)"><option value="warm">温暖关怀</option><option value="humorous">幽默调侃</option><option value="concise">简洁直接</option><option value="free">自由发挥</option></select>
    </div>
    <div class="card"><h3>关系模式</h3><p class="hint">快速模式好感度/信任度变化更快；长期模式每日有上限。好感度与信任度互相牵制——信任高了好感涨得快，反之亦然。聊天频率和情绪质量也会影响性格演化。</p>
      <select :value="relMode" @change="$emit('update:relMode', $event.target.value); $emit('save-cfg', 'relationship_mode', $event.target.value)"><option value="fast">快速</option><option value="long_term">长期</option></select>
    </div>
    <div class="card"><h3>快捷短语</h3>
      <div v-for="(p, i) in quickPhrases" :key="i" class="phrase-row"><input :value="p" @input="$emit('upd-phrase', i, $event.target.value)"><button class="btn-s" @click="$emit('del-phrase', i)">x</button></div>
      <button class="btn-s" @click="$emit('add-phrase')">+ 添加</button>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    chatFontSize: Number,
    sentenceMode: String,
    proactiveFreq: String,
    proactiveStyle: String,
    relMode: String,
    quickPhrases: Array,
  },
  emits: ['update:chatFontSize', 'update:sentenceMode', 'update:proactiveFreq', 'update:proactiveStyle', 'update:relMode', 'save-cfg', 'add-phrase', 'upd-phrase', 'del-phrase'],
}
</script>