<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchCharacters, updateCharacter } from '../utils/api.js'
import { useChat } from '../stores/chatStore.js'

const props = defineProps({ id: String })
const router = useRouter()
const chat = useChat()

const cid = computed(() => parseInt(props.id))
const char = computed(() => chat.characters.find(c => c.id == props.id))

// Editable fields
const edit = ref({ name: '', description: '', personality: '', scenario: '', system_prompt: '', first_mes: '', voice: null })
const saving = ref(false)

// Avatar
const avatarUrl = ref('')
const uploading = ref(false)

// Tabs within character settings
const tab = ref('profile')

const tabs = [
  { id: 'profile', label: '资料' },
  { id: 'persona', label: '人设' },
  { id: 'voice', label: '语音' },
  { id: 'memory', label: '记忆' },
  { id: 'rel', label: '关系' },
  { id: 'fav', label: '收藏' },
]

// Data sections
const vaultData = ref(null)
const episodes = ref([])
const relData = ref(null)
const favorites = ref([])
const loading = ref(true)

// Foundation types
const foundationTypes = ref([])
const foundationType = ref('')

onMounted(async () => {
  if (!chat.characters.length) {
    try { chat.characters = (await fetchCharacters()).characters || [] } catch(_) {}
  }
  loadCharData()
  loadFoundationTypes()
  loadSections()
})

async function loadCharData() {
  if (!char.value) return
  edit.value = {
    name: char.value.name || '',
    description: char.value.description || '',
    personality: char.value.personality || '',
    scenario: char.value.scenario || '',
    system_prompt: char.value.system_prompt || '',
    first_mes: char.value.first_mes || '',
    voice: char.value.voice || null,
  }

  // Load avatar
  try {
    const r = await fetch(`/avatar/assistant?t=${Date.now()}`)
    const d = await r.json()
    avatarUrl.value = d.url || ''
  } catch(_) {}
}

async function loadFoundationTypes() {
  try {
    const r = await fetch('/settings/foundation-types')
    const d = await r.json()
    foundationTypes.value = d.types || d.foundation_types || []
  } catch(_) {}
}

async function loadSections() {
  try {
    const [vaultRes, epRes, relRes, favRes] = await Promise.all([
      fetch(`/memory/vault?character_id=${cid.value}`).catch(() => null),
      fetch(`/episodes/timeline?days=30&character_id=${cid.value}`).catch(() => null),
      fetch(`/relationship/?character_id=${cid.value}`).catch(() => null),
      fetch(`/favorites?character_id=${cid.value}`).catch(() => null),
    ])
    vaultData.value = vaultRes?.ok ? await vaultRes.json() : null
    episodes.value = epRes?.ok ? (await epRes.json()).episodes || [] : []
    relData.value = relRes?.ok ? await relRes.json() : null
    favorites.value = favRes?.ok ? (await favRes.json()).favorites || [] : []
  } catch(_) {}
  loading.value = false
}

async function save() {
  saving.value = true
  try {
    // Update character card fields via PUT /characters/{id}
    await updateCharacter(cid.value, edit.value)

    // Sync name to global config if this character is active
    if (char.value?.is_active && edit.value.name) {
      await fetch('/settings/', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ key:'ai_name', value: edit.value.name }) })
    }

    // Refresh character list
    chat.characters = (await fetchCharacters()).characters || []
  } catch(e) { console.error('Save failed:', e) }
  saving.value = false
}

async function uploadAvatar(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    await fetch('/avatar/upload/assistant', { method:'POST', body: fd })
    // Refresh avatar
    const r = await fetch(`/avatar/assistant?t=${Date.now()}`)
    const d = await r.json()
    avatarUrl.value = d.url || ''
  } catch(_) {}
  uploading.value = false
  e.target.value = ''
}

async function setFoundation(type) {
  if (!confirm(`切换关系类型为「${type}」？`)) return
  try {
    await fetch('/settings/foundation', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ foundation_type: type, reset_values: false }) })
    foundationType.value = type
  } catch(_) {}
}

async function setSetting(key, value) {
  try {
    await fetch(`/characters/${cid.value}/settings`, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ key, value }) })
  } catch(_) {}
}

function pct(v) { return Math.min(100, Math.max(0, Math.round(v))) }
</script>

<template>
  <div class="view">
    <header class="topbar">
      <button class="back" @click="router.push('/chat')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <span class="tt">{{ char?.name || '角色' }}</span>
    </header>

    <!-- Section tabs -->
    <div class="tabs">
      <button v-for="t in tabs" :key="t.id" class="tab" :class="{ active: tab === t.id }" @click="tab = t.id">{{ t.label }}</button>
    </div>

    <div v-if="loading && tab !== 'profile'" class="loading">加载中…</div>
    <div class="body">

      <!-- ===== PROFILE ===== -->
      <div v-if="tab === 'profile'" class="sec">
        <!-- Avatar -->
        <div class="av-section">
          <div class="av-preview">
            <img v-if="avatarUrl" :src="avatarUrl" class="av-img" />
            <div v-else class="av-placeholder">{{ (edit.name || '?')[0] }}</div>
          </div>
          <div class="av-actions">
            <label class="btn btn-sm" :class="{ disabled: uploading }">
              {{ uploading ? '上传中…' : '更换头像' }}
              <input type="file" accept="image/*" class="hidden-input" @change="uploadAvatar" />
            </label>
            <span class="av-hint">支持 JPG/PNG，建议 256x256</span>
          </div>
        </div>

        <!-- Basic fields -->
        <div class="fr"><div class="fn">名称</div><input v-model="edit.name" class="fi" /></div>
        <div class="fr"><div class="fn">描述</div><input v-model="edit.description" class="fi" /></div>
        <div class="fr"><div class="fn">性格</div><textarea v-model="edit.personality" class="fi ta" rows="2"></textarea></div>
        <div class="fr"><div class="fn">场景</div><textarea v-model="edit.scenario" class="fi ta" rows="2"></textarea></div>
        <div class="fr"><div class="fn">开场白</div><textarea v-model="edit.first_mes" class="fi ta" rows="2" placeholder="首次激活时的问候语"></textarea></div>
        <div class="fr"><div class="fn">系统提示词</div><textarea v-model="edit.system_prompt" class="fi ta" rows="3"></textarea></div>

        <div class="save-row">
          <button class="btn btn-p" @click="save" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>

      <!-- ===== PERSONA ===== -->
      <div v-if="tab === 'persona'" class="sec">
        <div class="fr"><div class="fn">语气</div>
          <select v-model="edit.description" class="fi">
            <option value="">默认</option><option value="冷静">冷静</option><option value="活泼">活泼</option>
            <option value="温柔">温柔</option><option value="毒舌">毒舌</option><option value="傲娇">傲娇</option>
          </select>
        </div>

        <div class="sec-title">关系类型</div>
        <div class="ft-grid">
          <button v-for="ft in foundationTypes" :key="ft" class="ft-btn" :class="{ active: foundationType === ft }" @click="setFoundation(ft)">
            {{ ft }}
          </button>
        </div>
      </div>

      <!-- ===== VOICE ===== -->
      <div v-if="tab === 'voice'" class="sec">
        <div class="fr"><div class="fn">TTS 引擎</div>
          <select class="fi" :value="edit.voice?.engine||''" @change="e=>{edit.voice={...edit.voice,engine:e.target.value};setSetting('voice',edit.voice)}">
            <option value="">关闭</option><option value="edge">Edge TTS</option><option value="gpt-sovits">GPT-SoVITS</option>
            <option value="openai">OpenAI TTS</option><option value="cosyvoice">CosyVoice</option>
          </select>
        </div>
        <div v-if="edit.voice?.engine" class="fr">
          <div class="fn">服务地址</div>
          <input class="fi" :value="edit.voice?.url||''" @change="e=>{edit.voice={...edit.voice,url:e.target.value};setSetting('voice',edit.voice)}" placeholder="http://localhost:9880" />
        </div>
        <div v-if="edit.voice?.engine" class="fr">
          <div class="fn">语言</div>
          <select class="fi" :value="edit.voice?.lang||'zh'" @change="e=>{edit.voice={...edit.voice,lang:e.target.value};setSetting('voice',edit.voice)}">
            <option value="zh">中文</option><option value="ja">日语</option><option value="en">英语</option>
          </select>
        </div>
        <p class="hint" v-if="!edit.voice?.engine">角色语音配置是可选的，关闭则使用全局 TTS 设置</p>
      </div>

      <!-- ===== MEMORY ===== -->
      <div v-if="tab === 'memory'" class="sec">
        <div v-if="!vaultData" class="loading">加载中…</div>
        <template v-else>
          <div v-if="vaultData?.facts?.length" class="section-card">
            <div class="sc-h">关于你的事实</div>
            <div v-for="(f, i) in vaultData.facts.slice(0, 30)" :key="i" class="sc-item">
              <span class="sdot"></span>{{ typeof f === 'string' ? f : f.text || f.value || JSON.stringify(f) }}
            </div>
            <div v-if="!vaultData.facts.length" class="sc-empty">暂无事实</div>
          </div>
          <div v-if="vaultData?.profile && Object.keys(vaultData.profile).length" class="section-card">
            <div class="sc-h">{{ char?.name || 'ta' }}视角的你</div>
            <div v-for="(v, k) in vaultData.profile" :key="k" class="sc-row"><span class="srk">{{ k }}</span><span class="srv">{{ v.value || v }}</span></div>
          </div>
          <div v-if="vaultData?.scratch" class="section-card">
            <div class="sc-h">当前状态</div>
            <div class="sc-scratch">
              <div v-for="(v, k) in vaultData.scratch" :key="k" class="ss-item">
                <span class="ssk">{{ {currently:'正在', mood:'心情', goal:'目标'}[k] || k }}</span>
                <span class="ssv">{{ v }}</span>
              </div>
            </div>
          </div>
          <div v-if="vaultData?.rolling_summary" class="section-card">
            <div class="sc-h">对话摘要</div>
            <p class="sc-text">{{ vaultData.rolling_summary }}</p>
          </div>
          <div v-if="vaultData?.keypoints?.length" class="section-card">
            <div class="sc-h">关键要点</div>
            <div v-for="(kp, i) in vaultData.keypoints.slice(0, 15)" :key="i" class="sc-item"><span class="sdot"></span>{{ typeof kp === 'string' ? kp : kp.text || kp }}</div>
          </div>
        </template>
      </div>

      <!-- ===== RELATIONSHIP ===== -->
      <div v-if="tab === 'rel'" class="sec">
        <div v-if="!relData" class="loading">加载中…</div>
        <template v-else>
          <div class="rg">
            <div class="rc"><div class="rv">♥ {{ pct(relData.affection) }}</div><div class="rl">好感度</div><div class="rb"><div class="rf" :style="{width:pct(relData.affection)+'%'}"></div></div></div>
            <div class="rc"><div class="rv">♦ {{ pct(relData.trust) }}</div><div class="rl">信任度</div><div class="rb"><div class="rf" :style="{width:pct(relData.trust)+'%'}"></div></div></div>
          </div>
          <div v-if="relData.ai_emotion" class="emotion-box">{{ relData.ai_emotion }}</div>
        </template>
      </div>

      <!-- ===== FAVORITES ===== -->
      <div v-if="tab === 'fav'" class="sec">
        <div v-if="!favorites" class="loading">加载中…</div>
        <div v-else-if="!favorites.length" class="loading"><p>暂无收藏</p></div>
        <div v-else class="fav-list">
          <div v-for="f in favorites" :key="f.id" class="fav-item">
            <div class="fav-role">{{ f.role === 'user' ? '你' : char?.name || 'AI' }}</div>
            <div class="fav-text">{{ f.content }}</div>
            <div class="fav-time">{{ (f.timestamp||'').slice(0,16).replace('T',' ') }}</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.view { display:flex; flex-direction:column; height:100%; }
.topbar { height:var(--topbar-h); padding:0 16px; background:var(--bg-glass); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:10px; flex-shrink:0; }
.back { width:32px; height:32px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; }
.back:hover { background:var(--bg-hover); color:var(--text); }
.tt { font-size:16px; font-weight:600; flex:1; }

.tabs { display:flex; padding:0 8px; background:var(--bg-sidebar); border-bottom:1px solid var(--border); overflow-x:auto; flex-shrink:0; }
.tab { padding:8px 12px; font-size:12px; font-weight:500; font-family:var(--font); border:none; background:none; color:var(--text-muted); cursor:pointer; white-space:nowrap; border-bottom:2px solid transparent; }
.tab:hover { color:var(--text-secondary); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }

.body { flex:1; overflow-y:auto; padding:14px 16px; }
.sec { max-width:640px; }
.loading { text-align:center; padding:40px; color:var(--text-muted); font-size:13px; }

/* Profile form */
.av-section { display:flex; align-items:center; gap:14px; margin-bottom:14px; padding:12px; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); }
.av-preview { width:64px; height:64px; border-radius:var(--r-lg); overflow:hidden; background:rgba(255,255,255,0.04); border:1px solid var(--border); flex-shrink:0; display:flex; align-items:center; justify-content:center; }
.av-img { width:100%; height:100%; object-fit:cover; }
.av-placeholder { font-size:24px; font-weight:600; color:var(--accent); }
.av-actions { flex:1; }
.hidden-input { display:none; }

.fr { display:flex; align-items:center; gap:12px; padding:8px 0; }
.fn { flex:1; font-size:13px; font-weight:500; min-width:0; }
.fi { width:200px; flex-shrink:0; background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:var(--r-md); padding:7px 10px; font-family:var(--font); font-size:13px; color:var(--text); outline:none; }
.fi:focus { border-color:var(--accent); }
.ta { resize:vertical; min-height:0; }

.save-row { margin-top:12px; }
.btn { font-family:var(--font); font-size:12px; font-weight:500; padding:6px 14px; border-radius:var(--r-md); border:1px solid var(--border); background:transparent; color:var(--text-secondary); cursor:pointer; transition:all 0.1s; }
.btn:hover { background:var(--bg-hover); color:var(--text); }
.btn-p { background:var(--accent-gradient); color:white; border:none; }
.btn-p:hover { opacity:0.9; }
.btn-p:disabled { opacity:0.5; cursor:default; }
.btn-sm { padding:5px 10px; font-size:11px; }
.disabled { opacity:0.5; pointer-events:none; }
.av-hint { display:block; font-size:11px; color:var(--text-muted); margin-top:4px; }

/* Foundation */
.sec-title { font-size:13px; font-weight:500; margin:14px 0 8px; color:var(--text-secondary); }
.ft-grid { display:flex; flex-wrap:wrap; gap:4px; }
.ft-btn { padding:6px 12px; border-radius:var(--r-md); border:1px solid var(--border); background:rgba(255,255,255,0.02); font-family:var(--font); font-size:12px; color:var(--text-muted); cursor:pointer; transition:all 0.1s; }
.ft-btn:hover { border-color:var(--border-strong); color:var(--text-secondary); }
.ft-btn.active { border-color:var(--accent); color:var(--accent); background:var(--accent-soft); }

/* Hint */
.hint { font-size:12px; color:var(--text-muted); margin-top:8px; padding:10px; background:var(--bg-glass); border-radius:var(--r-md); }

/* Memory sections */
.section-card { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:12px 14px; margin-bottom:8px; }
.sc-h { font-size:13px; font-weight:600; margin-bottom:6px; }
.sc-item { display:flex; gap:8px; padding:4px 0; font-size:13px; color:var(--text-secondary); line-height:1.5; }
.sdot { width:5px; height:5px; border-radius:50%; background:var(--accent); margin-top:7px; flex-shrink:0; }
.sc-empty { font-size:13px; color:var(--text-muted); padding:8px 0; }
.sc-row { display:flex; gap:8px; padding:3px 0; font-size:13px; }
.srk { color:var(--text-muted); min-width:70px; }
.srv { color:var(--text); }
.sc-scratch { display:flex; gap:12px; flex-wrap:wrap; }
.ss-item { flex:1; min-width:100px; }
.ssk { font-size:11px; color:var(--text-muted); display:block; }
.ssv { font-size:14px; font-weight:500; }
.sc-text { font-size:13px; color:var(--text-secondary); line-height:1.7; }

/* Relationship */
.rg { display:flex; gap:10px; }
.rc { flex:1; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:14px; }
.rv { font-size:24px; font-weight:700; color:var(--accent); }
.rl { font-size:11px; color:var(--text-muted); margin-top:1px; }
.rb { height:4px; background:rgba(255,255,255,0.06); border-radius:2px; margin-top:8px; overflow:hidden; }
.rf { height:100%; background:var(--accent-gradient); border-radius:2px; }
.emotion-box { margin-top:8px; padding:12px; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); font-size:13px; color:var(--text-secondary); }

/* Favorites */
.fav-list { display:flex; flex-direction:column; gap:4px; }
.fav-item { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:10px 12px; }
.fav-role { font-size:11px; color:var(--accent); font-weight:500; margin-bottom:2px; }
.fav-text { font-size:12px; color:var(--text-secondary); line-height:1.5; }
.fav-time { font-size:11px; color:var(--text-tertiary); margin-top:4px; }
</style>
