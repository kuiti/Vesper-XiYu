<template>
  <div class="sc-pane">
    <div class="card"><h3>基本信息</h3>
      <div class="field"><label>AI 名字</label><input :value="aiName" @change="$emit('update:aiName', $event.target.value); $emit('save-cfg', 'ai_name', $event.target.value)"></div>
      <div class="field"><label>你的名字</label><input :value="userName" @change="$emit('update:userName', $event.target.value); $emit('save-cfg', 'user_name', $event.target.value)"></div>
    </div>
    <div class="card"><h3>头像</h3>
      <div class="avatar-section"><div class="avatar-preview"><img :src="assistantAvatarUrl" class="avatar-img"><span class="avatar-label">AI 头像</span></div><div class="avatar-actions"><button class="btn-s" @click="$refs.aiAvatarInput.click()">本地上传</button><input type="file" ref="aiAvatarInput" accept="image/*" style="display:none" @change="$emit('upload-avatar', 'assistant', $event)"><input :value="aiAvatarUrlLocal" @input="$emit('update:aiAvatarUrlLocal', $event.target.value)" placeholder="或输入URL" class="url-input"><button class="btn-s" @click="$emit('upload-avatar-url', 'assistant')" :disabled="!aiAvatarUrlLocal">导入</button></div></div>
      <div class="avatar-section"><div class="avatar-preview"><img :src="userAvatarUrl" class="avatar-img"><span class="avatar-label">用户头像</span></div><div class="avatar-actions"><button class="btn-s" @click="$refs.userAvatarInput.click()">本地上传</button><input type="file" ref="userAvatarInput" accept="image/*" style="display:none" @change="$emit('upload-avatar', 'user', $event)"><input :value="userAvatarUrlLocal" @input="$emit('update:userAvatarUrlLocal', $event.target.value)" placeholder="或输入URL" class="url-input"><button class="btn-s" @click="$emit('upload-avatar-url', 'user')" :disabled="!userAvatarUrlLocal">导入</button></div></div>
    </div>
    <div class="card"><h3>关系状态</h3>
      <div class="rel-item"><span class="rel-label">好感度</span><div class="rel-bar"><div class="rel-fill affection" :style="{width: (relationship.affection || 30) + '%'}"></div></div><span class="rel-value">{{ relationship.affection || 30 }}</span></div>
      <div class="rel-item"><span class="rel-label">信任度</span><div class="rel-bar"><div class="rel-fill trust" :style="{width: (relationship.trust || 30) + '%'}"></div></div><span class="rel-value">{{ relationship.trust || 30 }}</span></div>
      <div class="rel-item"><span class="rel-label">AI 状态</span><span class="ai-emotion-tag">{{ relationship.ai_emotion_label || '平静' }}</span><span class="ai-emotion-desc">{{ relationship.ai_emotion_description || '正常状态' }}</span></div>
    </div>
    <div class="card"><h3>性格设置</h3>
      <div class="field"><label>语气</label><select :value="tone" @change="$emit('update:tone', $event.target.value); $emit('save-cfg', 'personality_tone', $event.target.value)"><option value="冷静">冷静</option><option value="活泼">活泼</option><option value="温柔">温柔</option><option value="毒舌">毒舌</option><option value="傲娇">傲娇</option><option value="自由">自由</option></select></div>
      <div class="field"><label>回复长度</label><select :value="length" @change="$emit('update:length', $event.target.value); $emit('save-cfg', 'length_level', $event.target.value)"><option value="极短">极短（一句话）</option><option value="短">短（两三句）</option><option value="中等">中等（一段话）</option><option value="长">长（详细展开）</option><option value="详细">非常详细</option><option value="自由发挥">自由发挥</option><option value="不限">不限</option></select></div>
      <div class="field"><label>记忆回调</label><select :value="recall" @change="$emit('update:recall', $event.target.value); $emit('save-cfg', 'recall_past', $event.target.value)"><option value="从不">从不</option><option value="被动">被动</option></select><p class="hint">控制 AI 是否在对话中主动提及过去的记忆。</p></div>
      <label class="switch"><input type="checkbox" :checked="allowEmotion" @change="$emit('update:allowEmotion', $event.target.checked); $emit('save-cfg', 'allow_emotion', $event.target.checked)"> 允许使用颜文字</label>
    </div>
    <div class="card"><h3>自定义提示词</h3>
      <textarea :value="customPrompt" @change="$emit('update:customPrompt', $event.target.value); $emit('save-cfg', 'custom_system_prompt', $event.target.value)" rows="10" placeholder="留空则使用默认人设" style="min-height:200px;resize:vertical"></textarea>
    </div>
    <div class="card"><h3>设定背景板</h3><p class="hint">记录你为 AI 设定的背景信息。</p>
      <textarea :value="aiBackground" @change="$emit('update:aiBackground', $event.target.value); $emit('save-cfg', 'ai_background', $event.target.value)" rows="5" placeholder="例如：外号：小仓" style="min-height:100px;resize:vertical"></textarea>
    </div>
    <div class="card"><h3>关系类型</h3><p class="hint">选择你和 AI 的关系类型，会影响人设和说话风格。</p>
      <select :value="foundationType" @change="$emit('update:foundationType', $event.target.value); $emit('foundation-change')">
        <option value="空白">空白（默认）</option>
        <option v-for="(info, type) in foundationTypes" :key="type" :value="type">{{ type }} (好感:{{ info.default_affection }} 信任:{{ info.default_trust }})</option>
      </select>
      <div v-if="pendingFoundation" class="foundation-confirm">
        <p>是否将好感度和信任度重置为「{{ pendingFoundation }}」的默认值？</p>
        <label><input type="checkbox" :checked="resetFoundationValues" @change="$emit('update:resetFoundationValues', $event.target.checked)"> 重置好感/信任</label>
        <div class="btn-row">
          <button class="btn" @click="$emit('confirm-foundation')">确认</button>
          <button class="btn btn-secondary" @click="$emit('cancel-foundation')">取消</button>
        </div>
      </div>
    </div>
    <div class="card"><h3>角色预设</h3>
      <div class="btn-row"><input :value="presetName" @input="$emit('update:presetName', $event.target.value)" placeholder="预设名称"><button class="btn" @click="$emit('save-preset')">保存当前</button></div>
      <div class="preset-list"><div v-for="(d, name) in presets" :key="name" class="preset-item" @click="$emit('load-preset', name, d)">{{ name }}<span class="preset-del" @click.stop="$emit('delete-preset', name)">&times;</span></div></div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    aiName: String, userName: String, tone: String, length: String, recall: String,
    allowEmotion: Boolean, customPrompt: String, aiBackground: String,
    assistantAvatarUrl: String, userAvatarUrl: String,
    aiAvatarUrlLocal: String, userAvatarUrlLocal: String,
    relationship: { type: Object, default: () => ({}) },
    foundationType: String, foundationTypes: { type: Object, default: () => ({}) },
    pendingFoundation: String, resetFoundationValues: Boolean,
    presetName: String, presets: { type: Object, default: () => ({}) },
  },
  emits: ['update:aiName', 'update:userName', 'update:tone', 'update:length',
          'update:recall', 'update:allowEmotion', 'update:customPrompt', 'update:aiBackground',
          'update:aiAvatarUrlLocal', 'update:userAvatarUrlLocal', 'update:foundationType',
          'update:resetFoundationValues', 'update:presetName',
          'save-cfg', 'upload-avatar', 'upload-avatar-url', 'foundation-change',
          'confirm-foundation', 'cancel-foundation', 'save-preset', 'load-preset', 'delete-preset'],
}
</script>

<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--tc2); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--tc2); margin-bottom: 4px; }
.field input, .field select, textarea { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.field select { width: 100%; }
textarea { resize: vertical; }
.btn { padding: 7px 16px; background: var(--p); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); cursor: pointer; font-size: 12px; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.switch { display: block; font-size: 13px; color: var(--tc); margin: 4px 0; cursor: pointer; }
.switch input { margin-right: 6px; }
.rel-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; }
.rel-label { color: var(--tc2); min-width: 50px; font-size: 12px; }
.rel-bar { flex: 1; height: 8px; background: rgba(255,255,255,.08); border-radius: 4px; overflow: hidden; }
.rel-fill { height: 100%; border-radius: 4px; transition: width .5s; }
.rel-fill.affection { background: linear-gradient(90deg, #f0a0b0, #e8929b); }
.rel-fill.trust { background: linear-gradient(90deg, #5390d4, #4ecdc4); }
.rel-value { color: var(--tc); min-width: 30px; text-align: right; font-size: 12px; }
.ai-emotion-tag { color: var(--p); font-size: 12px; }
.ai-emotion-desc { color: var(--tc2); font-size: 11px; margin-left: 8px; }
.avatar-section { display: flex; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,.03); }
.avatar-preview { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.avatar-img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); }
.avatar-label { font-size: 10px; color: var(--tc2); }
.avatar-actions { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.url-input { padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 11px; }
.foundation-confirm { margin-top: 12px; padding: 12px; background: rgba(83,144,212,.08); border-radius: 8px; border: 1px solid var(--border, #30363d); }
.foundation-confirm p { margin: 0 0 8px; font-size: 13px; }
.foundation-confirm label { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 10px; cursor: pointer; }
.btn-secondary { background: var(--border, #30363d); color: var(--tc, #e6edf3); }
.preset-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.preset-item { padding: 4px 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 4px; font-size: 12px; cursor: pointer; }
.preset-item:hover { background: rgba(255,255,255,.06); }
.preset-del { color: #e74c3c; font-size: 14px; opacity: .4; margin-left: 4px; }
.preset-del:hover { opacity: 1; }
@media (max-width: 768px) {
  .avatar-section { flex-direction: column; align-items: flex-start; }
  .btn { min-height: 44px; }
  .btn-s { min-height: 44px; }
}
</style>