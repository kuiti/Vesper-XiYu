<template>
  <div class="settings-page">
    <div class="set-tabs">
      <div v-for="tab in tabs" :key="tab.id" :class="['tab', { on: activeTab === tab.id }]" @click="activeTab = tab.id">{{ tab.label }}</div>
    </div>

    <!-- 人设 -->
    <div v-show="activeTab === 'persona'" class="set-body">
      <div class="card"><h4>头像</h4><div class="desc">你和 AI 的头像</div>
        <div class="avatar-row">
          <div class="avatar-item"><div class="avatar-circle ai">佐</div><label>上传头像</label></div>
          <div class="avatar-item"><div class="avatar-circle user"><i class="ri-user-line"></i></div><label>用户头像</label></div>
        </div>
      </div>
      <div class="card"><h4>名称与称呼</h4><div class="desc">你的 AI 伙伴的名字</div><div class="fld"><label>AI 名字</label><input v-model="aiName"></div><div class="fld"><label>你的名字</label><input v-model="userName"></div></div>
      <div class="card"><h4>性格与语气</h4><div class="desc">AI 的表达方式</div>
        <div class="fld"><label>语气</label><select v-model="tone"><option>温柔</option><option selected>冷静</option><option>活泼</option><option>毒舌</option><option>傲娇</option><option>治愈系</option><option>自由</option></select></div>
        <div class="fld"><label>回复长度</label><select v-model="length"><option>极短</option><option selected>短</option><option>中等</option><option>长</option><option>详细</option><option>自由发挥</option><option>不限</option></select></div>
        <div class="fld"><label>记忆回调</label><select v-model="recall"><option selected>从不</option><option>被动</option><option>主动</option></select></div>
      </div>
      <div class="card"><h4>基石设定</h4><div class="desc">两人关系的核心基调</div><div class="fld"><label>关系类型</label><select v-model="foundation"><option>空白</option><option selected>亲密稳固</option><option>青梅竹马</option><option>新婚燕尔</option><option>爱恨交织</option><option>破镜重圆</option><option>单相思</option><option>暗恋成真</option><option>对手</option><option>主仆</option><option>契约关系</option><option>救命恩人</option><option>仇人</option><option>陌生人</option></select></div></div>
      <div class="card"><h4>自定义提示词</h4><div class="desc">覆盖 AI 的默认人格设定</div><textarea v-model="customPrompt" placeholder="输入自定义提示词..."></textarea></div>
    </div>

    <!-- 模型 -->
    <div v-show="activeTab === 'llm'" class="set-body">
      <div class="card"><h4>LLM 服务商</h4><div class="desc">选择 AI 模型提供商</div>
        <div class="fld"><label>服务商</label><select v-model="provider"><option selected>DeepSeek</option><option>OpenAI</option><option>Ollama（本地）</option><option>Claude</option></select></div>
        <div class="fld"><label>模型</label><input v-model="model"></div>
        <div class="fld"><label>API 地址</label><input v-model="apiBase"></div>
        <div class="fld"><label>API Key</label><input type="password" v-model="apiKey"></div>
      </div>
      <div class="card"><h4>联网搜索</h4><div class="fld"><label>搜索策略</label><select><option>关闭</option><option selected>DuckDuckGo</option></select></div></div>
      <div class="card"><h4>定位城市</h4><div class="desc">用于天气推送</div><div class="fld"><label>城市</label><input v-model="city" placeholder="自动定位或手动输入"></div></div>
    </div>

    <!-- 主题 -->
    <div v-show="activeTab === 'theme'" class="set-body">
      <div class="card"><h4>主题外观</h4><div class="fld"><label>主题</label><select v-model="theme"><option selected>深色</option><option>浅色</option><option>佐仓（樱花）</option><option>夕语（星光）</option></select></div><div class="fld"><label>字体大小</label><select v-model="fontSize"><option>小 12px</option><option selected>中 14px</option><option>大 16px</option></select></div></div>
      <div class="card"><h4>聊天背景</h4><div class="desc">背景图片 URL 或本地上传</div><input v-model="bgImage" placeholder="输入图片 URL" style="width:100%;padding:8px 12px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);outline:none;margin-bottom:8px"><div style="display:flex;gap:8px;align-items:center"><span style="font-size:12px;color:var(--text-muted)">透明度</span><input type="range" min="0" max="100" v-model="bgOpacity" style="flex:1;accent-color:var(--primary)"></div></div>
    </div>

    <!-- 语音 -->
    <div v-show="activeTab === 'voice'" class="set-body">
      <div class="card"><h4>语音朗读 (TTS)</h4><div class="fld"><label>启用</label><select v-model="ttsEnabled"><option selected>开启</option><option>关闭</option></select></div>
        <div class="fld"><label>引擎</label><select v-model="ttsEngine"><option selected>小米 MiMo TTS</option><option>Edge TTS</option></select></div>
        <div style="font-size:11px;color:var(--text-muted);margin:4px 0">引擎状态: <span style="color:var(--accent)">● OK</span></div>
        <div class="fld"><label>API Key</label><input type="password" v-model="ttsKey"></div>
        <div class="fld"><label>音色</label><select><option selected>茉莉（中文女声）</option></select></div>
      </div>
      <div class="card"><h4>语音输入 (STT)</h4><div class="fld"><label>启用</label><select><option selected>开启</option><option>关闭</option></select></div></div>
    </div>

    <!-- 通知 -->
    <div v-show="activeTab === 'notif'" class="set-body">
      <div class="card"><h4>系统通知</h4><div class="desc">Windows 桌面推送</div><div class="fld"><label>启用</label><select><option selected>开启</option><option>关闭</option></select></div></div>
      <div class="card"><h4>天气关怀</h4><div class="desc">每天 7:00 / 12:00 / 19:00 推送天气</div><div class="fld"><label>推送</label><select><option selected>开启</option><option>关闭</option></select></div></div>
      <div class="card"><h4>主动消息</h4><div class="fld"><label>频率</label><select v-model="proactiveFreq"><option>关闭</option><option>低（约 3h）</option><option selected>中（自动）</option><option>高（约 30min）</option></select></div><div class="fld"><label>风格</label><select v-model="proactiveStyle"><option>温暖关怀</option><option>幽默调侃</option><option>简洁直接</option><option selected>自由发挥</option></select></div></div>
      <div class="card"><h4>通知风格</h4><div class="desc">影响天气推送和主动问候的文案语气</div><div class="fld"><label>风格</label><select v-model="notifStyle"><option>温暖</option><option>随意</option><option>幽默</option><option>简洁</option><option>傲娇</option><option selected>自由</option></select></div></div>
      <div class="card"><h4>分句模式</h4><div class="fld"><label>模式</label><select v-model="sentenceMode"><option selected>智能分句</option><option>分隔符分句</option><option>逐字显示</option><option>连续输出</option></select></div></div>
      <div class="card"><h4>关系模式</h4><div class="desc">快速：变化更快。长期：每日有上限。</div><div class="fld"><label>模式</label><select v-model="relationMode"><option selected>快速</option><option>长期</option></select></div></div>
    </div>

    <!-- 记忆 -->
    <div v-show="activeTab === 'memory'" class="set-body">
      <div class="card"><h4>向量记忆引擎</h4><div class="desc">语义搜索增强</div><div class="fld"><label>嵌入模型</label><select><option selected>paraphrase-multilingual-MiniLM-L12-v2</option></select></div><div class="fld"><label>状态</label><span style="font-size:12px;color:var(--accent)">● 已加载</span></div></div>
      <div class="card"><h4>同步设置</h4><div class="fld"><label>自动同步</label><select><option selected>开启</option><option>关闭</option></select></div><div class="fld"><label>同步频率</label><select><option>每 10 条</option><option selected>每 50 条</option></select></div><div class="fld"><label>检索数量</label><select><option>3 条</option><option selected>5 条</option><option>10 条</option></select></div></div>
    </div>

    <!-- 角色卡 -->
    <div v-show="activeTab === 'chars'" class="set-body">
      <div class="card"><h4>当前角色</h4><div class="current-char"><div class="char-avatar">佐</div><div><div style="font-weight:600">{{ aiName }}</div><div style="font-size:11px;color:var(--text-muted)">{{ tone }} · {{ foundation }}</div></div></div></div>
      <div class="card"><h4>角色库</h4><div v-for="c in characterList" :key="c.name" class="char-row"><div class="char-avatar sm" :style="{ background: c.color }">{{ c.init }}</div><div style="flex:1"><div>{{ c.name }}</div><div style="font-size:10px;color:var(--text-muted)">{{ c.desc }}</div></div><button class="btn-s">{{ c.active ? '使用中' : '应用' }}</button></div></div>
      <div class="card"><h4>导入/导出</h4><div class="desc">PNG/JSON 角色卡（SillyTavern 兼容）</div><div class="btn-row"><button class="btn">导入角色卡</button><button class="btn-s">导出当前</button></div></div>
    </div>

    <!-- 提示词 -->
    <div v-show="activeTab === 'prompt'" class="set-body">
      <div class="card"><h4>模块开关</h4><div class="desc">控制 AI 提示词的组成部分</div>
        <div v-for="m in moduleList" :key="m.key" class="fld"><label>{{ m.label }}</label><select><option selected>开启</option><option>关闭</option></select></div>
      </div>
      <div class="card"><h4>Token 预算</h4><div class="fld"><label>动态内容上限</label><select><option>2000</option><option selected>3500</option><option>5000</option></select></div></div>
    </div>

    <!-- 数据 -->
    <div v-show="activeTab === 'data'" class="set-body">
      <div class="card"><h4>导出记录</h4><div class="btn-row"><button class="btn" @click="exportChat('json')">JSON</button><button class="btn-s" @click="exportChat('txt')">TXT</button><button class="btn-s" @click="exportChat('md')">Markdown</button></div></div>
      <div class="card"><h4>数据迁移</h4><button class="btn-s">导入备份</button></div>
      <div class="card"><h4>自动清理</h4><div class="fld"><label>保留天数</label><select v-model="cleanupDays"><option>关闭</option><option selected>30 天</option><option>60 天</option><option>90 天</option></select></div></div>
      <div class="card"><h4>危险操作</h4><div class="btn-row"><button class="btn-s" @click="resetRel">重置好感度</button><button class="btn-s" @click="resetMem">重置记忆</button><button class="btn danger" @click="fullReset">完全重置</button></div></div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useSettingsStore } from '../stores/settings.js'
import { showConfirm, alert as showAlert } from '../utils/dialog.js'
import api from '../api.js'

export default {
  setup() {
    const settings = useSettingsStore()
    const activeTab = ref('persona')
    const tabs = [
      { id: 'persona', label: '人设' }, { id: 'llm', label: '模型' },
      { id: 'theme', label: '主题' }, { id: 'voice', label: '语音' },
      { id: 'notif', label: '通知' }, { id: 'memory', label: '记忆' },
      { id: 'chars', label: '角色卡' }, { id: 'prompt', label: '提示词' },
      { id: 'data', label: '数据' },
    ]
    const aiName = ref('佐仓'); const userName = ref('用户')
    const tone = ref('冷静'); const length = ref('短'); const recall = ref('从不')
    const foundation = ref('亲密稳固'); const customPrompt = ref('')
    const provider = ref('DeepSeek'); const model = ref('deepseek-chat')
    const apiBase = ref('https://api.deepseek.com/v1'); const apiKey = ref('')
    const theme = ref('深色'); const fontSize = ref('中 14px')
    const bgImage = ref(''); const bgOpacity = ref(80)
    const ttsEnabled = ref('开启'); const ttsEngine = ref('小米 MiMo TTS'); const ttsKey = ref('')
    const city = ref('')
    const proactiveFreq = ref('中（自动）'); const proactiveStyle = ref('自由发挥')
    const notifStyle = ref('自由'); const sentenceMode = ref('智能分句')
    const relationMode = ref('快速'); const cleanupDays = ref('30 天')

    const characterList = ref([
      { name: '佐仓', desc: '默认 · 当前使用', color: 'var(--primary)', init: '佐', active: true },
      { name: '温柔姐姐', desc: '预设', color: 'hsl(260,30%,55%)', init: '姐', active: false },
      { name: '傲娇青梅', desc: '预设', color: 'hsl(0,30%,50%)', init: '傲', active: false },
    ])

    const moduleList = [
      { key: 'iron', label: '铁律（防幻觉）' }, { key: 'rules', label: '聊天规则' },
      { key: 'persona', label: '人设' }, { key: 'summary', label: '用户摘要' },
      { key: 'kb', label: '知识库' }, { key: 'kg', label: '知识图谱' },
      { key: 'schedule', label: '日程' }, { key: 'quirks', label: '随机口癖' },
      { key: 'continuity', label: '对话连续感' },
    ]

    function exportChat(fmt) {
      api.get(`/export/chat?format=${fmt}`).then(r => {
        const blob = new Blob([r.data.content], { type: 'text/plain' })
        const url = URL.createObjectURL(blob); const a = document.createElement('a')
        a.href = url; a.download = r.data.filename; a.click(); URL.revokeObjectURL(url)
      }).catch(() => showAlert('导出失败'))
    }

    async function resetRel() {
      if (!await showConfirm({ content: '重置好感度和信任度？' })) return
      try { await api.post('/relationship/reset'); showAlert('已重置') } catch (e) { showAlert('重置失败') }
    }
    async function resetMem() {
      if (!await showConfirm({ content: '重置摘要记忆？' })) return
      try { await api.post('/summary/reset'); showAlert('已重置') } catch (e) { showAlert('重置失败') }
    }
    async function fullReset() {
      if (!await showConfirm({ content: '确定完全重置？此操作不可撤销！' })) return
      try { await api.post('/settings/full-reset') } catch (e) { showAlert('重置失败') }
      window.location.reload()
    }

    return {
      activeTab, tabs, aiName, userName, tone, length, recall, foundation, customPrompt,
      provider, model, apiBase, apiKey, theme, fontSize, bgImage, bgOpacity,
      ttsEnabled, ttsEngine, ttsKey, city,
      proactiveFreq, proactiveStyle, notifStyle, sentenceMode, relationMode, cleanupDays,
      characterList, moduleList, exportChat, resetRel, resetMem, fullReset,
    }
  }
}
</script>

<style scoped>
.settings-page { display: flex; flex-direction: column; height: 100%; }
.set-tabs { display: flex; gap: 4px; padding: 10px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0; overflow-x: auto; }
.set-tabs .tab { padding: 5px 12px; border-radius: 5px; font-size: 12px; color: var(--text-muted); cursor: pointer; white-space: nowrap; }
.set-tabs .tab:hover { background: var(--bg-card); color: var(--text); }
.set-tabs .tab.on { background: var(--bg-card); color: var(--text); }
.set-body { flex: 1; padding: 20px; overflow-y: auto; }
.card { background: var(--bg-card); border-radius: 10px; border: 1px solid var(--border); padding: 20px; margin-bottom: 12px; }
.card h4 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.card .desc { font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }
.fld { display: flex; align-items: center; justify-content: space-between; padding: 7px 0; border-top: 1px solid var(--border); }
.fld label { font-size: 13px; }
.fld input, .fld select { padding: 5px 10px; background: var(--bg-base); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; outline: none; width: 200px; font-family: inherit; }
.fld input:focus { border-color: var(--primary); }
textarea { width: 100%; padding: 10px; background: var(--bg-base); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; outline: none; font-family: inherit; min-height: 80px; resize: vertical; }
textarea:focus { border-color: var(--primary); }
.avatar-row { display: flex; gap: 20px; }
.avatar-item { text-align: center; }
.avatar-circle { width: 56px; height: 56px; border-radius: 50%; margin: 0 auto 6px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #fff; cursor: pointer; }
.avatar-circle.ai { background: var(--primary); }
.avatar-circle.user { background: var(--bg-elevated); border: 2px dashed var(--border); font-size: 18px; color: var(--text-dim); }
.avatar-item label { font-size: 11px; color: var(--text-muted); cursor: pointer; }
.current-char { display: flex; align-items: center; gap: 14px; padding: 8px 0; }
.char-avatar { width: 48px; height: 48px; border-radius: 50%; background: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 20px; color: #fff; }
.char-avatar.sm { width: 36px; height: 36px; font-size: 14px; }
.char-row { display: flex; align-items: center; gap: 12px; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.char-row:hover { background: var(--bg-elevated); }
.btn-row { display: flex; gap: 8px; flex-wrap: wrap; }
.btn { padding: 7px 16px; background: var(--primary); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; font-family: inherit; }
.btn-s { padding: 7px 14px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; color: var(--text); cursor: pointer; font-size: 12px; font-family: inherit; }
.btn.danger { border-color: hsl(0,65%,55%); color: hsl(0,65%,55%); }
.btn:hover { filter: brightness(1.1); }
</style>
