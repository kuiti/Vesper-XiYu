import os

data_vue = r'''<template>
  <div class="sc-pane">
    <div class="card"><h3>收藏列表</h3>
      <div v-for="f in favorites" :key="f.id" class="fav-item">
        <span class="fav-role">{{ f.role === 'user' ? userName : aiName }}</span>
        <span class="fav-content">{{ f.content?.slice(0, 80) }}</span>
        <button class="btn-s" @click="$emit('del-fav', f.msg_id)">取消收藏</button>
      </div>
      <div v-if="!favorites.length" class="empty">暂无收藏</div>
    </div>
    <div class="card"><h3>导出</h3>
      <div class="btn-row">
        <button class="btn" @click="$emit('export-chat', 'json')">JSON</button>
        <button class="btn" @click="$emit('export-chat', 'txt')">TXT</button>
        <button class="btn" @click="$emit('export-chat', 'md')">Markdown</button>
      </div>
    </div>
    <div class="card"><h3>聊天管理</h3><ChatManagePanel @changed="$emit('load-favorites')" /></div>
    <div class="card"><h3>数据迁移</h3><MigratePanel /></div>
    <div class="card"><h3>云端同步</h3>
      <div class="cloud-panel">
        <div class="cloud-row"><label>服务器地址</label><input :value="cloudUrl" @input="$emit('update:cloudUrl', $event.target.value)" /></div>
        <div class="cloud-row"><label>用户名</label><input :value="cloudUser" @input="$emit('update:cloudUser', $event.target.value)" /></div>
        <div class="cloud-row"><label>密码</label><input :value="cloudPass" @input="$emit('update:cloudPass', $event.target.value)" type="password" /></div>
        <div class="cloud-actions">
          <button class="btn" @click="$emit('save-cloud-cfg')">保存</button>
          <button class="btn-s" @click="$emit('test-cloud')">测试</button>
          <button class="btn" @click="$emit('cloud-upload')" :disabled="cloudUploading">{{ cloudUploading ? '上传中...' : '上传' }}</button>
        </div>
        <div v-if="cloudMsg" :class="cloudMsgOk ? 'ok' : 'fail'">{{ cloudMsg }}</div>
      </div>
    </div>
    <div class="card"><h3>重置</h3>
      <div class="btn-row">
        <button class="btn-s" @click="$emit('reset-relationship')">重置关系</button>
        <button class="btn-s" @click="$emit('reset-memory')">重置摘要</button>
        <button class="btn-s danger" @click="$emit('full-reset')">完全重置</button>
      </div>
    </div>
  </div>
</template>
<script>
import ChatManagePanel from './ChatManagePanel.vue'
import MigratePanel from './MigratePanel.vue'
export default {
  components: { ChatManagePanel, MigratePanel },
  props: {
    aiName: String, userName: String,
    favorites: { type: Array, default: () => [] },
    cloudUrl: String, cloudUser: String, cloudPass: String, cloudPhrase: String,
    cloudMsg: String, cloudMsgOk: Boolean, cloudUploading: Boolean,
  },
  emits: ['del-fav','export-chat','load-favorites','save-cloud-cfg','test-cloud','cloud-upload',
          'reset-relationship','reset-memory','full-reset',
          'update:cloudUrl','update:cloudUser','update:cloudPass'],
}
</script>
<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.btn { padding: 7px 16px; background: var(--p); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); cursor: pointer; font-size: 12px; }
.btn-s.danger { color: #f85149; border-color: #f85149; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.fav-item { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,.03); font-size: 12px; }
.fav-role { color: var(--p); white-space: nowrap; min-width: 30px; }
.fav-content { flex: 1; color: var(--tc); }
.empty { color: var(--tc2); font-size: 12px; padding: 10px; }
.cloud-panel { display: flex; flex-direction: column; gap: 8px; }
.cloud-row { display: flex; align-items: center; gap: 8px; }
.cloud-row label { font-size: 12px; color: var(--tc2); min-width: 80px; }
.cloud-row input { flex: 1; padding: 6px 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--tc); font-size: 12px; }
.cloud-actions { display: flex; gap: 8px; margin-top: 4px; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
</style>
'''

appearance_vue = r'''<template>
  <div class="sc-pane">
    <div class="card"><h3>主题</h3>
      <div class="theme-row">
        <button :class="['theme-btn', { active: themeLocal==='dark' }]" @click="$emit('set-theme', 'dark')">暗色</button>
        <button :class="['theme-btn', { active: themeLocal==='light' }]" @click="$emit('set-theme', 'light')">亮色</button>
        <button :class="['theme-btn', { active: themeLocal==='sakura' }]" @click="$emit('set-theme', 'sakura')">樱花</button>
        <button :class="['theme-btn', { active: themeLocal==='vesper' }]" @click="$emit('set-theme', 'vesper')">夕语</button>
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
}
</script>
<style scoped>
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--tc2); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--tc2); margin-bottom: 4px; }
.field input, .field select { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); cursor: pointer; font-size: 12px; }
.theme-row { display: flex; gap: 6px; flex-wrap: wrap; }
.theme-btn { flex: 1; padding: 8px; background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 6px; color: var(--tc2); cursor: pointer; font-size: 12px; min-width: 50px; }
.theme-btn.active { background: var(--p); color: #fff; border-color: var(--p); }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
</style>
'''

with open('DataSettings.vue', 'w', encoding='utf-8') as f:
    f.write(data_vue.strip() + '\n')
print('DataSettings.vue created', os.path.getsize('DataSettings.vue'), 'bytes')

with open('AppearanceSettings.vue', 'w', encoding='utf-8') as f:
    f.write(appearance_vue.strip() + '\n')
print('AppearanceSettings.vue created', os.path.getsize('AppearanceSettings.vue'), 'bytes')