<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchSettings, updateSetting, fetchCharacters, activateCharacter, deactivateCharacter, deleteCharacter, createCharacter } from '../utils/api.js'
import { useChat, setFontSize } from '../stores/chatStore.js'

const PROVIDER_MAP = {
  deepseek: { label: 'DeepSeek', url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  mimo: { label: 'MiMo', url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2-flash' },
  openai: { label: 'OpenAI', url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  claude: { label: 'Claude (Anthropic)', url: 'https://api.anthropic.com/v1', model: 'claude-3-5-haiku-latest' },
  gemini: { label: 'Google Gemini', url: 'https://generativelanguage.googleapis.com/v1beta', model: 'gemini-2.0-flash' },
  qwen: { label: '通义千问 (Qwen)', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  moonshot: { label: '月之暗面 (Kimi)', url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  zhipu: { label: '智谱 GLM', url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  siliconflow: { label: '硅基流动 (SiliconFlow)', url: 'https://api.siliconflow.cn/v1', model: 'deepseek-v4-flash' },
  baidu: { label: '百度文心', url: 'https://qianfan.baidubce.com/v2', model: 'ernie-4.0' },
  doubao: { label: '豆包 (火山引擎)', url: 'https://ark.cn-beijing.volces.com/api/v3', model: 'ep-xxx' },
  groq: { label: 'Groq', url: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
  xai: { label: 'xAI (Grok)', url: 'https://api.x.ai/v1', model: 'grok-2-latest' },
  together: { label: 'Together AI', url: 'https://api.together.xyz/v1', model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo' },
  perplexity: { label: 'Perplexity', url: 'https://api.perplexity.ai/v1', model: 'llama-3.1-sonar-large-128k-online' },
  yi: { label: '零一万物 (Yi)', url: 'https://api.lingyiwanwu.com/v1', model: 'yi-lightning' },
  step: { label: '阶跃星辰 (Step)', url: 'https://api.stepfun.com/v1', model: 'step-1-flash' },
  hunyuan: { label: '腾讯混元', url: 'https://api.hunyuan.cloud.tencent.com/v1', model: 'hunyuan-lite' },
  ollama: { label: 'Ollama (本地)', url: 'http://localhost:11434/v1', model: '' },
  custom: { label: '自定义', url: '', model: '' },
}

const router = useRouter()
const chat = useChat()
const tab = ref('api')
const testingApi = ref(false)
const testOk = ref(false)
const testMsg = ref('')

const tabs = [
  { id: 'api', label: 'API' },
  { id: 'display', label: '显示' },
  { id: 'characters', label: '角色' },
  { id: 'about', label: '关于' },
]

const themeList = [
  { id: 'dark', label: '深色', color: '#7289fe' },
  { id: 'light', label: '浅色', color: '#c9717a' },
  { id: 'vesper', label: '夕语', color: '#9b8fb8' },
  { id: 'sakura', label: '樱花', color: '#e8929b' },
  { id: 'ocean', label: '深海', color: '#7aa2f7' },
  { id: 'forest', label: '森林', color: '#a7c080' },
  { id: 'sunset', label: '日落', color: '#e8715a' },
  { id: 'candy', label: '甜系', color: '#f5c2e7' },
  { id: 'mono', label: '单色', color: '#888' },
  { id: 'nord', label: '北欧', color: '#88c0d0' },
]

// API & Display
const settings = ref({})
const loading = ref(true)

// Characters
const chars = ref([])
const showCharForm = ref(false)
const nn = ref('')
const nd = ref('')
const importMode = ref('')
const importPaste = ref('')


onMounted(loadAll)
async function loadAll() {
  try {
    const [s, c] = await Promise.all([
      fetchSettings().catch(() => ({})),
      fetchCharacters().catch(() => ({ characters: [] })),
    ])
    settings.value = s
    chars.value = c.characters || []
  } catch (_) {}
  loading.value = false
}

function watchTab(id) { tab.value = id }

async function setVal(k, v) { try { await updateSetting(k, v); settings.value[k] = v } catch(_) {} }

function onProviderChange(id) {
  const p = PROVIDER_MAP[id]
  if (p) {
    settings.value.api_provider = id
    settings.value.api_base_url = p.url
    settings.value.api_model = p.model
    setVal('api_provider', id)
    setVal('api_base_url', p.url)
    setVal('api_model', p.model)
  }
}

async function testApi() {
  testingApi.value = true; testOk.value = false; testMsg.value = ''
  try {
    const r = await fetch('/test/', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ type: 'quick' }) })
    const d = await r.json()
    testOk.value = d.ok; testMsg.value = d.ok ? '连接成功' : (d.error || '失败')
  } catch (e) { testMsg.value = '请求失败' }
  testingApi.value = false
}

function setTheme(id) {
  settings.value.theme = id
  document.documentElement.setAttribute('data-theme', id)
  try { localStorage.setItem('vesper_theme', id) } catch(_) {}
  setVal('theme', id)
}

// Character ops
async function actChar(id) { await activateCharacter(id); chars.value = (await fetchCharacters()).characters || []; router.push('/chat') }
async function delChar(id) { if (!confirm('删除？')) return; await deleteCharacter(id); chars.value = (await fetchCharacters()).characters || [] }
async function createChar() {
  if (!nn.value.trim()) return
  await createCharacter({ name: nn.value.trim(), description: nd.value.trim() })
  nn.value = ''; nd.value = ''; showCharForm.value = false; chars.value = (await fetchCharacters()).characters || []
}
async function importChar() {
  if (!importPaste.value.trim()) return
  try {
    const d = JSON.parse(importPaste.value); await fetch('/characters/import/json', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(d) })
    importPaste.value = ''; importMode.value = ''; chars.value = (await fetchCharacters()).characters || []
  } catch(_) { alert('JSON 格式错误') }
}
async function handleFile(e) {
  const f = e.target.files?.[0]; if (!f) return
  const fd = new FormData(); fd.append('file', f)
  try { await fetch(f.name.endsWith('.png') ? '/characters/import/png' : '/characters/import/json', { method:'POST', body: fd }); chars.value = (await fetchCharacters()).characters || [] } catch(_) {}
  e.target.value = ''
}
async function removeFav(id) { try { await fetch(`/favorites/${id}`, { method:'DELETE' }); favs.value = favs.value.filter(x => x.id !== id) } catch(_) {} }

function pct(v) { return Math.min(100, Math.max(0, Math.round(v))) }
</script>

<template>
  <div class="view">
    <header class="topbar">
      <button class="back" @click="router.push('/chat')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <span class="tt">设置</span>
    </header>

    <!-- Tab bar -->
    <div class="tabs">
      <button v-for="t in tabs" :key="t.id" class="tab" :class="{ active: tab === t.id }" @click="watchTab(t.id)">{{ t.label }}</button>
    </div>

    <div class="body">

      <!-- ===== API ===== -->
      <div v-if="tab === 'api'" class="sec">
        <div class="fr"><div class="fn">AI 名称</div><input class="fi" :value="settings.ai_name||'夕语'" @change="e=>setVal('ai_name',e.target.value)" /></div>
        <div class="fr"><div class="fn">用户名称</div><input class="fi" :value="settings.user_name||'我'" @change="e=>setVal('user_name',e.target.value)" /></div>
        <div class="fr"><div class="fn">提供商</div>
          <select class="fi" :value="settings.api_provider||'deepseek'" @change="onProviderChange($event.target.value)">
            <option v-for="(p, k) in PROVIDER_MAP" :key="k" :value="k">{{ p.label }}</option>
          </select>
        </div>
        <div class="fr"><div class="fn">API Key</div><input class="fi" type="password" :value="settings.api_key?'********':''" @change="e=>setVal('api_key',e.target.value)" placeholder="sk-..." /></div>
        <div class="fr"><div class="fn">API 地址</div><input class="fi" :value="settings.api_base_url||''" @change="e=>setVal('api_base_url',e.target.value)" placeholder="https://api.deepseek.com/v1" /></div>
        <div class="fr"><div class="fn">模型</div><input class="fi" :value="settings.api_model||''" @change="e=>setVal('api_model',e.target.value)" placeholder="deepseek-chat" /></div>
        <div class="fr"><div class="fn"></div>
          <div class="fa">
            <button class="btn btn-p" @click="testApi" :disabled="testingApi">{{ testingApi ? '测试中…' : '测试连接' }}</button>
            <span v-if="testMsg" class="test-msg" :class="{ ok: testOk }">{{ testMsg }}</span>
          </div>
        </div>
      </div>

      <!-- ===== Display ===== -->
      <div v-if="tab === 'display'" class="sec">
        <div class="fr"><div class="fn">主题</div>
          <div class="theme-grid">
            <div v-for="th in themeList" :key="th.id" class="theme-card" :class="{ active: (settings.theme||'dark') === th.id }" @click="setTheme(th.id)">
              <div class="theme-swatch" :style="{ background: th.color }"></div>
              <div class="theme-label">{{ th.label }}</div>
            </div>
          </div>
        </div>
        <div class="fr"><div class="fn">回复长度</div>
          <select class="fi" :value="settings.length_level||'短'" @change="e=>setVal('length_level',e.target.value)"><option value="极短">极短</option><option value="短">短</option><option value="中">中</option><option value="长">长</option></select>
        </div>
        <div class="fr"><div class="fn">字号 {{ chat.fontSize }}px</div>
          <input type="range" class="fi-slider" min="12" max="20" step="1" :value="chat.fontSize" @input="e=>setFontSize(Number(e.target.value))" />
        </div>
        <div class="fr"><div class="fn">搜索源</div>
          <select class="fi" :value="settings.search_provider||'ddg'" @change="e=>setVal('search_provider',e.target.value)"><option value="off">关闭</option><option value="ddg">DuckDuckGo</option><option value="llm">LLM</option></select>
        </div>
        <div class="fr"><div class="fn">记忆提取指令</div>
          <textarea class="fi ta" rows="2" :value="settings.memory_prompt||''" @change="e=>setVal('memory_prompt',e.target.value)" placeholder="留空使用默认。可自定义 AI 记忆提取规则，如：只记录用户明确表达的偏好，忽略情绪化表达"></textarea>
        </div>
      </div>

      <!-- ===== Characters ===== -->
      <div v-if="tab === 'characters'" class="sec">
        <div class="top-acts">
          <button class="btn btn-p" @click="showCharForm=!showCharForm">+ 新建</button>
          <button class="btn" @click="importMode='file'">导入文件</button>
          <button class="btn" @click="importMode='json'">粘贴 JSON</button>
        </div>
        <div v-if="showCharForm" class="sheet">
          <input v-model="nn" class="fi" placeholder="名称" @keyup.enter="createChar" />
          <input v-model="nd" class="fi" placeholder="描述" />
          <div class="fa"><button class="btn btn-p" @click="createChar">创建</button><button class="btn ghost" @click="showCharForm=false">取消</button></div>
        </div>
        <div v-if="importMode==='file'" class="sheet">
          <div class="sh">导入角色卡</div>
          <div class="sd">支持酒馆 PNG 或 JSON</div>
          <input type="file" accept=".png,.json" @change="handleFile" />
          <button class="btn ghost" @click="importMode=''">取消</button>
        </div>
        <div v-if="importMode==='json'" class="sheet">
          <div class="sh">粘贴角色卡 JSON</div>
          <textarea v-model="importPaste" class="fi ta" rows="5" placeholder="粘贴 JSON…"></textarea>
          <div class="fa"><button class="btn btn-p" @click="importChar">导入</button><button class="btn ghost" @click="importMode=''">取消</button></div>
        </div>
        <div class="clist">
          <div v-for="c in chars" :key="c.id" class="ci" :class="{ on: c.is_active }">
            <div class="cia">{{ (c.name||'?')[0] }}</div>
            <div class="cib"><div class="cin">{{ c.name }}<span v-if="c.is_active" class="tag">当前</span></div><div class="cid">{{ c.description||'无描述' }}</div></div>
            <div class="ci-acts">
              <button v-if="!c.is_active" class="ibtn" @click="actChar(c.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </button>
              <button class="ibtn dng" @click="delChar(c.id)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
          <div v-if="!chars.length" class="empty">暂无角色</div>
        </div>
      </div>

      <!-- ===== Memory Vault ===== -->
      <div v-if="tab === 'vault'" class="sec">
        <div v-if="!vaultData" class="loading">加载中…</div>
        <div v-else class="vault">
          <!-- Profile -->
          <div v-if="vaultData.profile" class="vc">
            <div class="vch">用户画像</div>
            <div class="vcb">
              <div v-for="(v, k) in vaultData.profile" :key="k" class="vr">
                <span class="vrk">{{ k }}</span>
                <span class="vrv">{{ typeof v === 'object' ? v.value || v : v }}</span>
              </div>
              <div v-if="!Object.keys(vaultData.profile).length" class="vm">暂无画像数据</div>
            </div>
          </div>

          <!-- Facts -->
          <div v-if="vaultData.facts" class="vc">
            <div class="vch">关于你的事实</div>
            <div class="vcb">
              <div v-for="(f, i) in vaultData.facts.slice(0, 20)" :key="i" class="vf">
                <span class="vdot"></span>
                {{ typeof f === 'string' ? f : f.text || f.value || JSON.stringify(f) }}
              </div>
              <div v-if="!vaultData.facts.length" class="vm">暂无事实</div>
            </div>
          </div>

          <!-- Scratch -->
          <div v-if="vaultData.scratch" class="vc">
            <div class="vch">当前状态</div>
            <div class="vcb scratch-grid">
              <div v-for="(v, k) in vaultData.scratch" :key="k" class="sr-item">
                <span class="srk">{{ {currently:'正在', mood:'心情', goal:'目标'}[k] || k }}</span>
                <span class="srv">{{ v }}</span>
              </div>
            </div>
          </div>

          <!-- Summary -->
          <div v-if="vaultData.rolling_summary" class="vc">
            <div class="vch">对话摘要</div>
            <div class="vcb"><p class="vs">{{ vaultData.rolling_summary }}</p></div>
          </div>

          <!-- Keypoints -->
          <div v-if="vaultData.keypoints" class="vc">
            <div class="vch">关键要点</div>
            <div class="vcb">
              <div v-for="(kp, i) in vaultData.keypoints.slice(0, 15)" :key="i" class="vf">
                <span class="vkey">•</span>
                {{ typeof kp === 'string' ? kp : kp.text || kp }}
              </div>
            </div>
          </div>

          <!-- Entities (only if non-empty) -->
          <div v-if="vaultData.entities && vaultData.entities.length" class="vc">
            <div class="vch">知识实体 ({{ vaultData.entities.length }})</div>
            <div class="vcb chips">
              <span v-for="(e, i) in vaultData.entities.slice(0, 30)" :key="i" class="chip">{{ typeof e === 'string' ? e : e.name || e }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Episodes ===== -->
      <div v-if="tab === 'episodes'" class="sec">
        <div v-if="!episodes.length" class="loading">{{ episodes === null ? '加载中…' : '暂无情景记录' }}</div>
        <div v-else class="tl">
          <div v-for="ep in episodes" :key="ep.id" class="tl-item">
            <div class="tl-dot"></div>
            <div class="tl-card">
              <div class="tl-date">{{ (ep.start_time||'').slice(0,16).replace('T',' ') }}</div>
              <div class="tl-title">{{ ep.topic_summary||'对话' }}</div>
              <div class="tl-meta">{{ ep.user_message_count||0 }} 条 · 重要性 {{ (ep.importance||0).toFixed(1) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Relationship ===== -->
      <div v-if="tab === 'rel'" class="sec">
        <div v-if="!rel" class="loading">加载中…</div>
        <template v-else>
          <div class="rgrid">
            <div class="rc"><div class="rv">♥ {{ pct(rel.affection) }}</div><div class="rl">好感度</div><div class="rb"><div class="rf" :style="{width:pct(rel.affection)+'%'}"></div></div></div>
            <div class="rc"><div class="rv">♦ {{ pct(rel.trust) }}</div><div class="rl">信任度</div><div class="rb"><div class="rf" :style="{width:pct(rel.trust)+'%'}"></div></div></div>
          </div>
          <div v-if="rel.ai_emotion" class="rc" style="margin-top:10px;padding:14px;background:var(--bg-glass);border:1px solid var(--border);border-radius:var(--r-lg);">
            <div class="rl">当前情绪</div>
            <div class="rv" style="font-size:16px">{{ rel.ai_emotion }}</div>
          </div>
          <div class="ms" v-if="milestones.length">
            <div class="msh">里程碑</div>
            <div v-for="m in milestones" :key="m.key" class="msi" :class="{ ok: m.unlocked }">
              <span class="msc">{{ m.unlocked ? '✓' : '○' }}</span>
              <div><div class="msn">{{ m.name }}</div><div class="msd">{{ m.desc }}</div></div>
            </div>
          </div>
        </template>
      </div>

      <!-- ===== Favorites ===== -->
      <div v-if="tab === 'fav'" class="sec">
        <div v-if="!favs" class="loading">加载中…</div>
        <div v-else-if="!favs.length" class="loading"><p>暂无收藏</p></div>
        <div v-else class="favs">
          <div v-for="f in favs" :key="f.id" class="fi2">
            <div class="fr2">{{ f.role === 'user' ? '你' : 'AI' }}</div>
            <div class="ft">{{ f.content }}</div>
            <div class="ftm">{{ (f.timestamp||'').slice(0,16).replace('T',' ') }}</div>
            <button class="fdel" @click="removeFav(f.id)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- ===== About ===== -->
      <div v-if="tab === 'about'" class="sec about-sec">
        <div class="ac"><div class="ai"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg></div><div class="an">夕语</div><div class="av">v5.0.0</div><div class="ad">AI 角色扮演引擎</div></div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.view { display:flex; flex-direction:column; height:100%; }
.topbar { height:var(--topbar-h); padding:0 16px; background:var(--bg-glass); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:10px; flex-shrink:0; }
.back { width:32px; height:32px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; }
.back:hover { background:var(--bg-hover); color:var(--text); }
.tt { font-size:16px; font-weight:600; }

.tabs { display:flex; gap:0; padding:0 8px; background:var(--bg-sidebar); border-bottom:1px solid var(--border); overflow-x:auto; flex-shrink:0; }
.tab { padding:8px 12px; font-size:12px; font-weight:500; font-family:var(--font); border:none; background:none; color:var(--text-muted); cursor:pointer; white-space:nowrap; border-bottom:2px solid transparent; transition:all 0.1s; }
.tab:hover { color:var(--text-secondary); }
.tab.active { color:var(--accent); border-bottom-color:var(--accent); }

.body { flex:1; overflow-y:auto; padding:14px 16px; }

/* Shared */
.sec { max-width:640px; }
.fr { display:flex; align-items:center; gap:12px; padding:8px 0; }
.fn { flex:1; font-size:13px; font-weight:500; min-width:0; }
.fi { width:200px; flex-shrink:0; background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:var(--r-md); padding:7px 10px; font-family:var(--font); font-size:13px; color:var(--text); outline:none; }
.fi:focus { border-color:var(--accent); }
select.fi { cursor:pointer; }
.loading { text-align:center; padding:40px; color:var(--text-muted); font-size:13px; }
.empty { text-align:center; padding:24px; color:var(--text-muted); font-size:13px; }

/* Buttons */
.btn { font-family:var(--font); font-size:12px; font-weight:500; padding:5px 12px; border-radius:var(--r-md); border:1px solid var(--border); background:transparent; color:var(--text-secondary); cursor:pointer; transition:all 0.1s; }
.btn:hover { background:var(--bg-hover); color:var(--text); }
.btn-p { background:var(--accent-gradient); color:white; border:none; }
.btn-p:hover { opacity:0.9; }
.ghost { border-color:transparent; color:var(--text-muted); }
.top-acts { display:flex; gap:6px; margin-bottom:10px; flex-wrap:wrap; }

/* Sheets */
.sheet { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:14px; margin-bottom:12px; display:flex; flex-direction:column; gap:8px; }
.sh { font-size:13px; font-weight:500; }
.sd { font-size:11px; color:var(--text-muted); }
.ta { resize:vertical; }
.fa { display:flex; gap:6px; }

/* Characters */
.clist { display:flex; flex-direction:column; gap:4px; }
.ci { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:var(--r-md); transition:background 0.1s; }
.ci:hover { background:var(--bg-hover); }
.ci.on { background:var(--accent-soft); }
.cia { width:36px; height:36px; border-radius:var(--r-md); background:rgba(255,255,255,0.04); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:600; color:var(--text-secondary); flex-shrink:0; }
.ci.on .cia { border-color:var(--accent); color:var(--accent); }
.cib { flex:1; min-width:0; }
.cin { font-size:13px; font-weight:500; display:flex; align-items:center; gap:6px; }
.cid { font-size:11px; color:var(--text-muted); margin-top:1px; }
.tag { font-size:10px; padding:1px 6px; border-radius:3px; background:var(--accent-soft); color:var(--accent); }
.ci-acts { display:flex; gap:2px; }
.ibtn { width:28px; height:28px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; }
.ibtn:hover { background:var(--bg-hover); color:var(--text); }
.ibtn.dng:hover { color:var(--danger); background:rgba(237,73,86,0.1); }

/* Vault */
.vault { display:flex; flex-direction:column; gap:10px; }
.vc { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); overflow:hidden; }
.vch { padding:10px 14px; font-size:13px; font-weight:600; border-bottom:1px solid var(--border); background:rgba(255,255,255,0.02); }
.vcb { padding:8px 14px 10px; }
.vr { display:flex; gap:8px; padding:4px 0; font-size:13px; }
.vrk { color:var(--text-muted); min-width:70px; flex-shrink:0; }
.vrv { color:var(--text); }
.vf { display:flex; gap:8px; padding:5px 0; font-size:13px; color:var(--text-secondary); line-height:1.5; border-bottom:1px solid var(--border); }
.vf:last-child { border-bottom:none; }
.vdot { width:5px; height:5px; border-radius:50%; background:var(--accent); margin-top:7px; flex-shrink:0; }
.vkey { color:var(--accent); font-weight:700; }
.vm { font-size:13px; color:var(--text-muted); padding:8px 0; }
.vs { font-size:13px; color:var(--text-secondary); line-height:1.7; }
.scratch-grid { display:flex; gap:12px; flex-wrap:wrap; }
.sr-item { flex:1; min-width:120px; }
.srk { font-size:11px; color:var(--text-muted); display:block; }
.srv { font-size:14px; font-weight:500; color:var(--text); }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { padding:4px 10px; border-radius:var(--r-md); background:var(--accent-soft); color:var(--accent); font-size:12px; }

/* Timeline */
.tl { position:relative; padding-left:18px; }
.tl::before { content:''; position:absolute; left:7px; top:0; bottom:0; width:1px; background:var(--border); }
.tl-item { position:relative; padding-bottom:12px; }
.tl-dot { position:absolute; left:-15px; top:4px; width:8px; height:8px; border-radius:50%; background:var(--accent); border:2px solid var(--bg-chat); }
.tl-card { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:10px 12px; }
.tl-date { font-size:11px; color:var(--accent); }
.tl-title { font-size:13px; font-weight:500; margin-top:2px; }
.tl-meta { font-size:11px; color:var(--text-muted); margin-top:2px; }

/* Relationship */
.rgrid { display:flex; gap:10px; }
.rc { flex:1; background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:14px; }
.rv { font-size:24px; font-weight:700; color:var(--accent); }
.rl { font-size:11px; color:var(--text-muted); margin-top:1px; }
.rb { height:4px; background:rgba(255,255,255,0.06); border-radius:2px; margin-top:8px; overflow:hidden; }
.rf { height:100%; background:var(--accent-gradient); border-radius:2px; transition:width 0.4s; }
.ms { margin-top:12px; }
.msh { font-size:13px; font-weight:500; margin-bottom:8px; }
.msi { display:flex; gap:8px; padding:6px 0; align-items:flex-start; border-bottom:1px solid var(--border); opacity:0.35; }
.msi.ok { opacity:1; }
.msi:last-child { border:none; }
.msc { font-size:12px; color:var(--accent); margin-top:2px; }
.msn { font-size:12px; font-weight:500; }
.msd { font-size:11px; color:var(--text-muted); margin-top:1px; }

/* Theme grid */
.theme-grid { display:flex; flex-wrap:wrap; gap:8px; }
.theme-card { width:56px; cursor:pointer; text-align:center; padding:6px 4px; border-radius:var(--r-md); border:1.5px solid transparent; transition:all .15s; }
.theme-card:hover { background:var(--bg-hover); }
.theme-card.active { border-color:var(--accent); background:var(--accent-soft); }
.theme-swatch { width:32px; height:32px; border-radius:50%; margin:0 auto 4px; border:1px solid var(--border-strong); }
.theme-label { font-size:10px; color:var(--text-muted); line-height:1.2; }

/* Favorites */
.favs { display:flex; flex-direction:column; gap:4px; }
.fi2 { background:var(--bg-glass); border:1px solid var(--border); border-radius:var(--r-lg); padding:10px 12px; position:relative; }
.fr2 { font-size:11px; color:var(--accent); font-weight:500; margin-bottom:2px; }
.ft { font-size:12px; color:var(--text-secondary); line-height:1.5; }
.ftm { font-size:11px; color:var(--text-tertiary); margin-top:4px; }
.fdel { position:absolute; top:6px; right:6px; width:22px; height:22px; border-radius:var(--r-sm); border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; opacity:0; transition:opacity 0.1s; }
.fi2:hover .fdel { opacity:1; }
.fdel:hover { background:var(--bg-hover); color:var(--danger); }

/* About */
.about-sec { display:flex; justify-content:center; padding:40px 0; }
.ac { text-align:center; }
.ai { color:var(--accent); margin-bottom:10px; }
.an { font-size:22px; font-weight:700; }
.av { font-size:12px; color:var(--text-muted); margin-top:4px; }
.ad { font-size:13px; color:var(--text-secondary); margin-top:6px; }
.fi-slider { flex:1; max-width:200px; height:4px; -webkit-appearance:none; appearance:none; background:var(--border); border-radius:2px; outline:none; cursor:pointer; }
.fi-slider::-webkit-slider-thumb { -webkit-appearance:none; width:16px; height:16px; border-radius:50%; background:var(--accent); border:2px solid var(--bg-sidebar); cursor:pointer; }
.test-msg { font-size:12px; margin-left:8px; }
.test-msg.ok { color:var(--success); }
.test-msg:not(.ok) { color:var(--danger); }
</style>
