<template>
  <div class="sc-pane">
    <div class="card"><h3>主题</h3>
      <div class="theme-row">
        <button v-for="t in themeList" :key="t.id" :class="['theme-btn', { active: themeLocal===t.id }]" @click="$emit('set-theme', t.id)" :style="t.id===themeLocal ? {background:'var(--accent-primary)', color:'#fff', borderColor:'var(--accent-primary)'} : {}">{{ t.label }}</button>
      </div>
    </div>
    <div class="card"><h3>聊天背景</h3>
      <div class="field"><label>本地上传</label><div class="bg-row"><button class="btn-s" @click="$refs.bgFileInput.click()">选择图片</button><input type="file" ref="bgFileInput" accept="image/*" style="display:none" @change="$emit('upload-bg', $event)"><span v-if="bgUploadMsg" class="ok" style="font-size:11px">{{ bgUploadMsg }}</span></div></div>
      <div class="field"><label>图片 URL</label><div class="bg-row"><input :value="chatBgImage" @change="$emit('update:chatBgImage', $event.target.value); $emit('save-cfg', 'chat_bg_image', $event.target.value)" placeholder="留空为纯色"><button class="btn-s" @click="$emit('clear-bg')">清除</button></div></div>
      <div class="field"><label>透明度</label><input type="range" min="0" max="100" :value="bgOpacity" @change="$emit('update:bgOpacity', +$event.target.value); $emit('save-bg-style')"></div>
      <div class="field"><label>模糊度</label><input type="range" min="0" max="20" :value="bgBlur" @change="$emit('update:bgBlur', +$event.target.value); $emit('save-bg-style')"></div>
      <div class="field"><label>显示模式</label><select :value="bgMode" @change="$emit('update:bgMode', $event.target.value); $emit('save-bg-style')"><option value="cover">拉伸</option><option value="contain">完整</option><option value="repeat">平铺</option><option value="center">居中</option></select></div>
    </div>
    <div class="card"><h3>向量记忆引擎</h3>
      <p class="hint">将聊天记录和知识库文档转为语义向量索引。首次使用需下载 ~420MB 模型。</p>
      <div v-if="ragStatus === 'ready'" class="ok" style="margin-bottom:6px">已就绪 · {{ ragCount }} 条向量</div>
      <div v-else-if="ragStatus === 'installed'" style="color:var(--tc2);font-size:12px;margin-bottom:6px">已安装，启动时自动加载</div>
      <div v-else style="color:#f39c12;font-size:12px;margin-bottom:6px">未安装 · <button class="btn-s" @click="$emit('install-rag')" :disabled="installingRag">{{ installingRag ? '安装中...' : '点击安装' }}</button></div>
      <button class="btn-s" @click="$emit('rebuild-rag')" :disabled="rebuildingRag">{{ rebuildingRag ? '重建中...' : '重建向量索引' }}</button>
      <div v-if="ragMsg" :class="ragMsgOk ? 'ok' : 'fail'" style="margin-top:6px;font-size:11px">{{ ragMsg }}</div>
    </div>
  </div>
</template>
<script>
export default {
  props: {
    themeLocal: String, chatBgImage: String, bgOpacity: Number, bgBlur: Number, bgMode: String,
    bgUploadMsg: String, ragStatus: String, ragCount: Number, ragMsg: String, ragMsgOk: Boolean,
    installingRag: Boolean, rebuildingRag: Boolean,
  },
  emits: ['set-theme','upload-bg','clear-bg','save-cfg','save-bg-style',
          'install-rag','rebuild-rag',
          'update:chatBgImage','update:bgOpacity','update:bgBlur','update:bgMode'],
  computed: {
    themeList() {
      return [
        { id: 'dark', label: '暗色' },
        { id: 'light', label: '亮色' },
        { id: 'sakura', label: '樱花' },
        { id: 'vesper', label: '夕语' },
        { id: 'ocean', label: '深海' },
        { id: 'forest', label: '森林' },
        { id: 'sunset', label: '日落' },
        { id: 'mono', label: '单色' },
        { id: 'candy', label: '甜系' },
        { id: 'nord', label: '北欧' },
      ]
    },
  },
}
</script>
<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border-default); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--text-secondary); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.field input, .field select { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border-default); background: var(--surface-app); color: var(--text-primary); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.theme-row { display: flex; gap: 6px; flex-wrap: wrap; }
.theme-btn { flex: 1; padding: 8px; background: rgba(255,255,255,.03); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-secondary); cursor: pointer; font-size: 12px; min-width: 50px; }
.theme-btn.active { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
</style>
