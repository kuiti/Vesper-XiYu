<template>
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
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border-default); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.btn { padding: 7px 16px; background: var(--accent-primary); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border-default); border-radius: 4px; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.btn-s.danger { color: #f85149; border-color: #f85149; }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.fav-item { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,.03); font-size: 12px; }
.fav-role { color: var(--accent-primary); white-space: nowrap; min-width: 30px; }
.fav-content { flex: 1; color: var(--text-primary); }
.empty { color: var(--text-secondary); font-size: 12px; padding: 10px; }
.cloud-panel { display: flex; flex-direction: column; gap: 8px; }
.cloud-row { display: flex; align-items: center; gap: 8px; }
.cloud-row label { font-size: 12px; color: var(--text-secondary); min-width: 80px; }
.cloud-row input { flex: 1; padding: 6px 8px; background: var(--surface-app); border: 1px solid var(--border-default); border-radius: 6px; color: var(--text-primary); font-size: 12px; }
.cloud-actions { display: flex; gap: 8px; margin-top: 4px; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
</style>
