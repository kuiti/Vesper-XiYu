<template>
  <div class="app" :data-theme="currentTheme" :class="{ 'blur-bg': modalOpen }" :style="colorVariables">
    <div class="top-bar">
      <span class="brand">Vesper</span>
      <span class="status" :class="{ online: wsReady }">{{ wsReady ? '在线' : '连接中...' }}</span>
      <span class="location">{{ locationText }}</span>
      <span class="top-date" v-if="floatingDate">{{ floatingDate }}</span>
      <span class="msg-count" v-if="totalMessages">{{ totalMessages }} 条消息</span>
    </div>

    <div class="layout">
      <nav class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="nav-icons">
          <button @click="openTodoModal" title="待办"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="22" height="22" rx="2"/><path d="M8 12l3 3 5-5"/></svg><span class="nav-label">待办</span></button>
          <button @click="openNoteModal" title="笔记"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg><span class="nav-label">笔记</span></button>
          <button @click="showHistoryPanel = true" title="历史"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 12"/><path d="M12 2a10 10 0 0 1 0 20"/></svg><span class="nav-label">历史</span></button>
          <button @click="scrollToBottom(true)" title="回到底部"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg><span class="nav-label">底部</span></button>
        </div>
        <button class="nav-settings" @click="openSettings" title="设置"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg><span class="nav-label">设置</span></button>
        <button class="sidebar-toggle" @click="sidebarCollapsed=!sidebarCollapsed" :title="sidebarCollapsed?'展开':'收起'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline :points="sidebarCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/></svg>
        </button>
      </nav>

      <div class="chat">
        <div class="chat-top">
          <button class="btn-more" @click="loadMoreHistory" :disabled="loadingMore || !nextAfterId">
            {{ loadingMore ? '加载中...' : '更早的消息' }}
          </button>
        </div>

        <div class="msg-list" ref="messagesContainer">
          <div v-if="!messages.length" class="empty-chat">{{ loadError || '开始和Vesper聊天吧' }}</div>
          <template v-for="(msg, idx) in messages" :key="msg.id || idx">
            <div v-if="idx === 0 || dateLabel(msg.timestamp) !== dateLabel(messages[idx-1].timestamp)" class="date-sep">{{ dateLabel(msg.timestamp) }}</div>
            <div :class="['msg', msg.role]">
              <img class="msg-avatar" :src="msg.role === 'user' ? userAvatarUrl : assistantAvatarUrl" />
              <div class="msg-body">
                <div class="msg-bubble" v-html="safeLinkify(msg.content)" @contextmenu.prevent="openContextMenu($event, msg)" @dblclick="copyMessage(msg)"></div>
                <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </template>
          <div v-show="isStreaming" class="msg assistant">
            <img class="msg-avatar" :src="assistantAvatarUrl" />
            <div class="msg-body">
              <div class="msg-bubble typing-cursor"><span class="cursor-bar"></span></div>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <div v-if="quoteMsg" class="quote-bar">{{ quoteMsg.content }}<button @click="quoteMsg=null">✕</button></div>
          <div class="input-row">
            <button class="emoji-btn" @click="showEmojiPicker=!showEmojiPicker" title="颜文字">^_^</button>
            <div v-if="showEmojiPicker" class="kaomoji-picker">
              <span v-for="k in kaomojis" :key="k" @click="inputText+=k;showEmojiPicker=false;$refs.inputEl.focus()" class="kaomoji-item">{{ k }}</span>
            </div>
            <textarea
              ref="inputEl"
              v-model="inputText"
              @keydown.enter.exact="sendMessage"
              @keydown.shift.enter="inputText += '\n'"
              @input="autoResizeInput"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
              rows="1"
              :disabled="isStreaming"
            ></textarea>
            <button class="btn-send" @click="sendMessage" :disabled="isStreaming || !inputText.trim()">发送</button>
          </div>
        </div>

        <!-- 右键菜单 -->
        <div v-if="showContextMenu" class="context-menu" :style="{left:ctxMenuX+'px',top:ctxMenuY+'px'}" @click.stop>
          <div class="ctx-item" @click="copyMessage(ctxTargetMsg)">复制</div>
          <div class="ctx-item" @click="quoteMessage(ctxTargetMsg)">引用</div>
          <div class="ctx-item ctx-danger" @click="deleteMessage(ctxTargetMsg)">删除</div>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <div v-if="showTodoModal" class="modal-overlay" @click.self="closeTodoModal">
      <div class="modal small"><div class="modal-hd"><h3>待办</h3><button @click="closeTodoModal">✕</button></div><div class="modal-bd"><TodoList /></div></div>
    </div>
    <div v-if="showNoteModal" class="modal-overlay" @click.self="closeNoteModal">
      <div class="modal small"><div class="modal-hd"><h3>笔记</h3><button @click="closeNoteModal">✕</button></div><div class="modal-bd"><NoteList /></div></div>
    </div>
    <div v-if="showCountdownModal" class="modal-overlay" @click.self="closeCountdownModal">
      <div class="modal small"><div class="modal-hd"><h3>倒计时</h3><button @click="closeCountdownModal">✕</button></div><div class="modal-bd"><CountdownList /></div></div>
    </div>
    <div v-if="showReminderModal" class="modal-overlay" @click.self="closeReminderModal">
      <div class="modal small"><div class="modal-hd"><h3>提醒</h3><button @click="closeReminderModal">✕</button></div><div class="modal-bd"><ReminderList /></div></div>
    </div>
    <div v-if="showHistoryPanel" class="modal-overlay" @click.self="showHistoryPanel=false">
      <div class="modal small"><div class="modal-hd"><h3>历史回顾</h3><button @click="showHistoryPanel=false">✕</button></div><div class="modal-bd"><HistoryPanel /></div></div>
    </div>
    <div v-if="showSettingsModal" class="modal-overlay" @click.self="closeSettingsModal">
      <div class="settings-panel" ref="settingsPanel">
        <div class="settings-titlebar" @mousedown="startDrag">
          <span>设置</span>
          <button @click="closeSettingsModal">✕</button>
        </div>
        <div class="settings-body">
          <div class="settings-nav">
            <div v-for="tab in settingsTabs" :key="tab.id"
                 :class="['nav-item', { active: settingsTab === tab.id }]"
                 @click="settingsTab = tab.id">
              <span class="nav-icon"><svg v-if="tab.icon==='api'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 12H8"/><path d="M12 8v8"/></svg><svg v-else-if="tab.icon==='role'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M6 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1"/></svg><svg v-else-if="tab.icon==='voice'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg><svg v-else-if="tab.icon==='appr'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="10"/></svg><svg v-else-if="tab.icon==='data'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="22" height="22" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg></span>
              <span class="nav-label">{{ tab.label }}</span>
            </div>
          </div>
          <div class="settings-content">
            <!-- API -->
            <div v-if="settingsTab === 'api'" class="tab-content">
              <div class="card"><div class="card-title">DeepSeek API</div><div class="card-body">
                <div class="api-row"><input type="password" v-model="apiKeyLocal" placeholder="sk-..."><button class="btn" @click="saveApiKey">保存</button></div>
                <div v-if="apiKeySaved" class="saved-hint">已保存</div>
                <div class="test-row"><span>连通性</span><button class="btn-s" @click="testDeepSeek" :disabled="testing.ds">{{ testing.ds ? '...' : '测试' }}</button><span :class="testing.dsStatus">{{ testing.dsMsg }}</span></div>
              </div></div>
              <div class="card"><div class="card-title">高德地图 API</div><div class="card-body">
                <div class="api-row"><input type="password" v-model="amapKeyLocal" @change="updateGlobalConfig('amap_key', amapKeyLocal)" placeholder="用于天气和IP定位"><button class="btn" @click="saveApiKey">保存</button></div>
                <div class="test-row"><span>天气</span><button class="btn-s" @click="testWeather" :disabled="testing.wt">{{ testing.wt ? '...' : '测试' }}</button><span :class="testing.wtStatus">{{ testing.wtMsg }}</span></div>
                <div class="test-row"><span>定位</span><button class="btn-s" @click="locateAndFill" :disabled="locating">{{ locating ? '获取中...' : '获取定位' }}</button><span :class="testing.ipStatus" style="font-size:11px">{{ testing.ipMsg }}</span></div>
              </div></div>
              <div class="card"><div class="card-title">联网搜索</div><div class="card-body">
                <label class="switch-label"><input type="checkbox" v-model="enableSearchLocal" @change="updateGlobalConfig('enable_web_search', enableSearchLocal)"> DuckDuckGo 关键词匹配</label>
                <div class="test-row"><span>连通性</span><button class="btn-s" @click="testSearch" :disabled="testing.se">{{ testing.se ? '...' : '测试' }}</button><span :class="testing.seStatus">{{ testing.seMsg }}</span></div>
              </div></div>
              <div class="card"><div class="card-title">定位设置</div><div class="card-body">
                <div class="ip-status" v-if="ipCity">{{ ipCity }}</div>
                <div class="btn-row"><button class="btn-s" @click="locateAndFill" :disabled="locating">IP 定位</button><button class="btn-s" @click="preciseLocate" :disabled="locating">精确定位</button></div>
                <div class="loc-hint">精确定位使用浏览器 WiFi/GPS，首次需授权</div>
                <div class="loc-row"><select v-model="selectedProvince" @change="onProvinceChange"><option value="">省份</option><option v-for="p in provinces" :key="p.adcode" :value="p.adcode">{{ p.name }}</option></select><select v-model="selectedCity" :disabled="!selectedProvince"><option value="">城市</option><option v-for="c in cities" :key="c.adcode" :value="c.adcode">{{ c.name }}</option></select><button class="btn-s" @click="savePreciseCity">保存</button></div>
              </div></div>
            </div>

            <!-- 角色 -->
            <div v-if="settingsTab === 'role'" class="tab-content">
              <div class="card"><div class="card-title">基本信息</div><div class="card-body">
                <div class="field"><label>AI 名称</label><input v-model="aiNameLocal" @change="updateGlobalConfig('ai_name', aiNameLocal)"></div>
                <div class="field"><label>你的称呼</label><input v-model="userNameLocal" @change="updateGlobalConfig('user_name', userNameLocal)"></div>
              </div></div>
              <div class="card"><div class="card-title">回复风格</div><div class="card-body">
                <div class="field"><label>语气</label><select v-model="toneLocal" @change="saveTone"><option value="冷静">冷静</option><option value="活泼">活泼</option><option value="温柔">温柔</option><option value="毒舌">毒舌</option><option value="傲娇">傲娇</option></select></div>
                <div class="field"><label>长度</label><select v-model="lengthLocal" @change="updateGlobalConfig('length_level', lengthLocal)"><option value="极短">极短</option><option value="短">短</option><option value="中等">中等</option><option value="长">长</option><option value="详细">详细</option></select></div>
                <div class="field"><label>回忆</label><select v-model="recallLocal" @change="updateGlobalConfig('recall_past', recallLocal)"><option value="从不">从不</option><option value="被动">被动</option></select></div>
              </div></div>
              <div class="card card-grow"><div class="card-title">自定义人设提示词</div><div class="card-body card-body-grow"><textarea v-model="customPromptLocal" @change="updateGlobalConfig('custom_system_prompt', customPromptLocal)" placeholder="留空则使用默认人设..." class="role-textarea"></textarea></div></div>
              <div class="card"><div class="card-title">角色预设</div><div class="card-body">
                <div class="api-row"><input v-model="newPresetName" placeholder="预设名称"><button class="btn-s" @click="savePreset" :disabled="!newPresetName">保存当前</button></div>
                <div v-for="(data, name) in presets" :key="name" class="preset-row"><span>{{ name }}</span><div class="preset-actions"><button class="btn-s" @click="loadPreset(name)">加载</button><button class="btn-s btn-danger" @click="deletePreset(name)">删除</button></div></div>
                <div v-if="Object.keys(presets).length===0" class="empty-hint">暂无预设</div>
              </div></div>
            </div>

            <!-- 外观 -->
            <div v-if="settingsTab === 'appearance'" class="tab-content">
              <div class="card"><div class="card-title">主题</div><div class="card-body">
                <div class="theme-toggle">
                  <button :class="['theme-btn', { active: themeLocal==='dark' }]" @click="setTheme('dark')">🌙 暗色</button>
                  <button :class="['theme-btn', { active: themeLocal==='light' }]" @click="setTheme('light')">☀ 亮色</button>
                </div>
              </div></div>
              <div class="card"><div class="card-title">配色</div><div class="card-body">
                <div class="color-list"><div v-for="c in colorFields" :key="c.key" class="color-row">
                  <span class="color-swatch" :style="{background: colors[c.key]}"></span>
                  <span class="color-label">{{ c.label }}</span>
                  <input type="color" v-model="colors[c.key]" @change="updateGlobalConfig(c.configKey, colors[c.key])" class="color-pick">
                  <input :value="colors[c.key]" @change="updateColorField(c.key, $event.target.value)" class="color-hex" placeholder="#000000" maxlength="7">
                </div></div>
                <div class="preset-bar">
                  <button class="btn-s" @click="applyColorPreset('default')">默认蓝</button>
                  <button class="btn-s" @click="applyColorPreset('wechat')">微信绿</button>
                  <button class="btn-s" @click="applyColorPreset('teal')">青蓝</button>
                  <button class="btn-s" @click="applyColorPreset('warm')">暖橙</button>
                  <button class="btn-s" @click="newPresetName='';saveColorPreset()">+ 保存当前</button>
                </div>
              </div></div>
              <div class="card"><div class="card-title">聊天背景</div><div class="card-body">
                <div class="bg-row"><input v-model="chatBgImage" @change="updateGlobalConfig('chat_bg_image', chatBgImage)" placeholder="图片URL（留空为纯色）"><button class="btn-s" @click="uploadBg">上传</button><button class="btn-s" @click="chatBgImage='';updateGlobalConfig('chat_bg_image','')">清除</button></div>
                <input type="file" ref="bgInput" accept="image/*" style="display:none" @change="onBgFilePicked">
              </div></div>
            </div>

            <!-- 数据 -->
            <div v-if="settingsTab === 'data'" class="tab-content">
              <div class="stats-bar">
                <div class="stat-item"><span class="stat-val">{{ totalMessages }}</span><span class="stat-lbl">消息</span></div>
                <div class="stat-sep"></div>
                <div class="stat-item"><span class="stat-val">{{ conversationDays }}</span><span class="stat-lbl">对话日</span></div>
              </div>
              <div class="card"><div class="card-body"><SearchPanel /></div></div>
              <div class="card"><div class="card-body"><MemoryPanel /></div></div>
              <div class="card"><div class="card-body"><RAGPanel /></div></div>
              <div class="card"><div class="card-body"><ChatManagePanel @changed="onDataChanged" /></div></div>
              <div class="card"><div class="card-body"><MigratePanel /></div></div>
              <div class="card"><div class="card-body"><button class="btn" @click="exportChat">导出聊天记录 (TXT)</button></div></div>
            </div>

          </div>
        </div>
      </div>
    </div>

    <!-- 右侧提醒弹窗 -->
    <div class="reminder-popups">
      <div class="reminder-popups-inner">
      <transition-group name="slide">
        <div v-for="(pop, idx) in reminderPopups" :key="pop._id" :class="['reminder-popup', 'level-' + pop.level]">
          <div class="reminder-popup-bar" :class="'bar-lvl-' + pop.level"></div>
          <div class="reminder-popup-body">
            <span class="reminder-popup-tag">{{ pop.level_name }}</span>
            <span class="reminder-popup-text">{{ pop.content }}</span>
            <span class="reminder-popup-time">截止 {{ pop.target_time }}</span>
            <div class="reminder-popup-actions">
              <button class="reminder-btn-done" @click="completeReminder(pop)">完成</button>
              <button class="reminder-btn-snooze" @click="snoozeReminder(pop)">稍后</button>
            </div>
          </div>
          <button class="reminder-popup-close" @click="dismissReminder(pop._id)">✕</button>
        </div>
      </transition-group>
      </div>
    </div>
  </div>
</template>

<script>
import api, { WS_URL, BASE_URL } from './api.js'
import TodoList from './components/TodoList.vue'
import NoteList from './components/NoteList.vue'
import CountdownList from './components/CountdownList.vue'
import ReminderList from './components/ReminderList.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import SearchPanel from './components/SearchPanel.vue'
import ChatManagePanel from './components/ChatManagePanel.vue'
import RAGPanel from './components/RAGPanel.vue'
import MigratePanel from './components/MigratePanel.vue'
import HistoryPanel from './components/HistoryPanel.vue'

const DEFAULT_AVATAR = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="%234e89ae" stroke-width="1.5"%3E%3Cpath d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"%3E%3C/path%3E%3Ccircle cx="12" cy="7" r="4"%3E%3C/circle%3E%3C/svg%3E'

export default {
  components: { TodoList, NoteList, CountdownList, ReminderList, MemoryPanel, SearchPanel, ChatManagePanel, RAGPanel, MigratePanel, HistoryPanel },
  data() {
    return {
      showTodoModal: false, showNoteModal: false, showCountdownModal: false, showReminderModal: false, showHistoryPanel: false, showSettingsModal: false,
      currentTheme: 'dark', messages: [], inputText: '', ws: null, isStreaming: false, streamingSentence: '', wsReady: false,
      pendingReply: '', schedId: null,
      wsReconnectAttempts: 0, _reconnectTimer: null, userScrolledUp: false, lastScrollTop: 0,
      floatingDate: '', reminderPopups: [], activeReminderCount: 0,
      chatFontSize: 14, chatBgImage: '', saveError: '', loadError: '', showContextMenu: false, ctxMenuX: 0, ctxMenuY: 0, ctxTargetMsg: null, quoteMsg: null, showEmojiPicker: false,
      kaomojis: ['(￣▽￣)','(´･_･`)','(>_<)','(╥﹏╥)','(*¯︶¯*)','(╯‵□′)╯','(=・ω・=)','(・∀・)'],
      apiKeyLocal: '', themeLocal: 'dark', amapKeyLocal: '', enableSearchLocal: true,
      aiNameLocal: 'Vesper', userNameLocal: '', toneLocal: '冷静', lengthLocal: '短', recallLocal: '从不', emotionLocal: false, customPromptLocal: '',
      colors: { primary: '#5390d4', bg: '#0d1117', sidebarBg: '#161b22', chatBg: '#0d1117', userBubble: '#2b5278', aiBubble: '#1e2632' },
      totalMessages: 0, conversationDays: 0, userAvatarUrl: DEFAULT_AVATAR, assistantAvatarUrl: DEFAULT_AVATAR,
      provinces: [], cities: [], selectedProvince: '', selectedCity: '', ipCity: '', ipCityShort: '',
      presets: {}, newPresetName: '', nextAfterId: null, loadingMore: false, apiKeySaved: false,
      testing: { ds: false, dsStatus: '', dsMsg: '', wt: false, wtStatus: '', wtMsg: '', se: false, seStatus: '', seMsg: '', ip: false, ipStatus: '', ipMsg: '' },
      settingsTab: 'api', locating: false,
      sidebarCollapsed: true,
      hasApiKey: false, hasAmapKey: false,
      settingsTabs: [
        { id: 'api', icon: 'api', label: 'API' },
        { id: 'role', icon: 'role', label: '角色' },
        { id: 'appearance', icon: 'appr', label: '外观' },
        { id: 'data', icon: 'data', label: '数据' }
      ]
    }
  },
  computed: {
    colorVariables() { let bg = 'none'; if (this.chatBgImage && /^https?:\/\/[^\s'"()]+\.(jpg|jpeg|png|webp|gif)(\?[^\s'"()]*)?$/i.test(this.chatBgImage)) { bg = `url("${this.chatBgImage}")` }; return { '--p': this.colors.primary, '--bg': this.colors.bg, '--sb': this.colors.sidebarBg, '--cb': this.colors.chatBg, '--ub': this.colors.userBubble, '--ab': this.colors.aiBubble, '--chat-bg-img': bg } },
    locationText() { const c = this.ipCityShort; if (c && c.length > 0 && c !== '[]' && c !== '无法获取定位') return c; return '无法获取定位' },
    modalOpen() { return this.showSettingsModal || this.showTodoModal || this.showNoteModal || this.showCountdownModal || this.showReminderModal || this.showHistoryPanel },
    colorFields() { return [
      { key: 'primary', label: '主色调', configKey: 'primary_color' },
      { key: 'bg', label: '背景', configKey: 'bg_color' },
      { key: 'sidebarBg', label: '侧边栏', configKey: 'sidebar_bg' },
      { key: 'chatBg', label: '聊天区', configKey: 'chat_bg' },
      { key: 'userBubble', label: '用户气泡', configKey: 'user_bubble' },
      { key: 'aiBubble', label: 'AI气泡', configKey: 'ai_bubble' }
    ]}
  },
  async mounted() { await this.loadAllSettings(); this.loadAvatars(); this.loadProvinces(); this.loadPresets(); this.loadHistory(); this.connectWebSocket(); await this.loadIpLocation(); this._locationTimer = setInterval(() => { if (document.visibilityState === 'visible') this.loadIpLocation() }, 600000); if (Notification.permission === 'default') Notification.requestPermission(); this._keydownHandler = (e) => { if (e.key === 'Escape') { this.showContextMenu = false; this.showEmojiPicker = false; this.showSettingsModal = false; this.showTodoModal = false; this.showNoteModal = false; this.showCountdownModal = false; this.showReminderModal = false; this.showHistoryPanel = false } }; document.addEventListener('keydown', this._keydownHandler); this._wheelHandler = (e) => { if (e.ctrlKey) { e.preventDefault(); this.adjustFontSize(e.deltaY < 0 ? 1 : -1) } }; document.addEventListener('wheel', this._wheelHandler, { passive: false }); this.$nextTick(() => { const el = this.$refs.messagesContainer; if (el) el.addEventListener('scroll', () => { const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
this.lastScrollTop = el.scrollTop
this.userScrolledUp = distFromBottom > 250; const seps = el.querySelectorAll('.date-sep'); let visible = ''; for (const s of seps) { if (s.getBoundingClientRect().top > el.getBoundingClientRect().top + 20) break; visible = s.textContent }; this.floatingDate = visible }) }) },
  beforeUnmount() { if (this.ws) this.ws.close(); if (this._locationTimer) clearInterval(this._locationTimer); if (this._reconnectTimer) clearTimeout(this._reconnectTimer); if (this._keydownHandler) document.removeEventListener('keydown', this._keydownHandler); if (this._wheelHandler) document.removeEventListener('wheel', this._wheelHandler) },
  methods: {
    async loadAllSettings() {
      try { const res = await api.get('/settings/'); this.themeLocal = res.data.theme || 'dark'; this.currentTheme = this.themeLocal; document.documentElement.setAttribute('data-theme', this.currentTheme); this.enableSearchLocal = res.data.enable_web_search !== false; this.hasAmapKey = res.data.has_amap_key || false; this.hasApiKey = res.data.has_api_key || false; this.aiNameLocal = res.data.ai_name || 'Vesper'; this.userNameLocal = res.data.user_name || ''; this.toneLocal = res.data.personality_tone || '冷静'; this.lengthLocal = res.data.length_level || '短'; this.recallLocal = res.data.recall_past || '从不'; this.emotionLocal = res.data.allow_emotion === true; this.customPromptLocal = res.data.custom_system_prompt || ''; this.chatBgImage = res.data.chat_bg_image || ''; this.chatFontSize = res.data.chat_font_size || 14;
      if (res.data.precise_city) { this.ipCityShort = res.data.precise_city; this.ipCity = res.data.precise_city }
      this.colors = { primary: res.data.primary_color || '#5390d4', bg: res.data.bg_color || '#0d1117', sidebarBg: res.data.sidebar_bg || '#161b22', chatBg: res.data.chat_bg || '#0d1117', userBubble: res.data.user_bubble || '#2b5278', aiBubble: res.data.ai_bubble || '#1e2632' } } catch (err) { console.error(err) }
    },
    async updateGlobalConfig(key, value) { try { await api.post('/settings/', { key, value }); this.saveError = ''; if (key === 'theme') { this.currentTheme = value; document.documentElement.setAttribute('data-theme', value) } } catch (err) { this.saveError = '保存失败: ' + key; setTimeout(() => { this.saveError = '' }, 3000); console.error(err) } },
    async saveApiKey() { await this.updateGlobalConfig('api_key', this.apiKeyLocal); this.apiKeySaved = true; setTimeout(() => { this.apiKeySaved = false }, 2000) },
    async saveTone() { await this.updateGlobalConfig('personality', { tone: this.toneLocal }) },
    async loadAvatars() { try { const userRes = await api.get('/avatar/user'); if (userRes.data.url) this.userAvatarUrl = `${BASE_URL}${userRes.data.url}?t=${Date.now()}`; const assistantRes = await api.get('/avatar/assistant'); if (assistantRes.data.url) this.assistantAvatarUrl = `${BASE_URL}${assistantRes.data.url}?t=${Date.now()}` } catch (err) { console.error(err) } },
    async loadProvinces() { try { const res = await api.get('/location/provinces'); this.provinces = res.data } catch (err) { console.error(err) } },
    async onProvinceChange() { if (!this.selectedProvince) return; try { const res = await api.get(`/location/cities/${this.selectedProvince}`); this.cities = res.data; this.selectedCity = '' } catch (err) { console.error(err) } },
    async savePreciseCity() { if (!this.selectedCity) { alert('请选择省份和城市'); return } const cityObj = this.cities.find(c => c.adcode === this.selectedCity); await this.updateGlobalConfig('precise_city', cityObj ? cityObj.name : this.selectedCity); alert('已保存') },
    async loadIpLocation() {
      // 1. 已有精确城市则跳过 GPS（避免重复弹权限）
      if (this.ipCityShort && this.ipCityShort.length > 1 && this.ipCityShort !== '无法获取定位') return
      // 2. 尝试浏览器精确定位
      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 })
          })
          const res = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude })
          if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = res.data.detail || res.data.city; this.updateGlobalConfig('precise_city', res.data.city); return }
        } catch(e) { this.testing.ipMsg = 'GPS定位被拒绝或超时，已切换到IP定位'; this.testing.ipStatus = 'fail' }
      }
      // 3. GPS 失败 → IP 定位（但不覆盖已有的 precise_city）
      try {
        const res = await api.get('/location/ip')
        if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = `IP: ${res.data.province||''} ${res.data.city}`; if (!this.ipCityShort || this.ipCityShort === '无法获取定位') { this.updateGlobalConfig('precise_city', res.data.city) }; return }
      } catch(e) {}
      this.ipCity = ''; this.ipCityShort = '无法获取定位'
    },
    async loadPresets() { try { const res = await api.get('/settings/presets'); this.presets = res.data } catch (err) { console.error(err) } },
    async savePreset() { if (!this.newPresetName) return; const currentFullSettings = { api_key: this.apiKeyLocal, theme: this.themeLocal, primary_color: this.colors.primary, bg_color: this.colors.bg, sidebar_bg: this.colors.sidebarBg, chat_bg: this.colors.chatBg, user_bubble: this.colors.userBubble, ai_bubble: this.colors.aiBubble, amap_key: this.amapKeyLocal, enable_web_search: this.enableSearchLocal }; try { await api.post('/settings/presets', { name: this.newPresetName, data: currentFullSettings }); await this.loadPresets(); this.newPresetName = ''; alert('预设已保存') } catch (err) { console.error(err) } },
    async loadPreset(name) { try { const preset = this.presets[name]; for (const [key, value] of Object.entries(preset)) { await this.updateGlobalConfig(key, value) } await this.loadAllSettings(); alert('预设已加载') } catch (err) { console.error(err) } },
    async deletePreset(name) { if (!confirm(`删除预设 "${name}"？`)) return; try { await api.delete(`/settings/presets/${name}`); await this.loadPresets() } catch (err) { console.error(err) } },
    formatTime(ts) { if (!ts) return ''; try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } catch { return '' } },
    dateLabel(ts) { if (!ts) return ''; try { const d = new Date(ts); if (isNaN(d.getTime())) return ''; const today = new Date(); if (d.toDateString() === today.toDateString()) return '今天'; const y = new Date(today); y.setDate(y.getDate()-1); if (d.toDateString() === y.toDateString()) return '昨天'; return d.toLocaleDateString('zh-CN', { month:'long', day:'numeric' }) } catch { return '' } },
    safeLinkify(text) { if (!text) return ''; const escaped = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); return escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>') },
    openContextMenu(e, msg) { this.ctxTargetMsg = msg; this.ctxMenuX = e.clientX; this.ctxMenuY = e.clientY; this.showContextMenu = true; setTimeout(() => { document.addEventListener('click', () => { this.showContextMenu = false }, { once: true }) }) },
    copyMessage(msg) { navigator.clipboard.writeText(msg.content).catch(() => {}); this.showContextMenu = false },
    quoteMessage(msg) { this.quoteMsg = msg; this.showContextMenu = false; this.$nextTick(() => this.$refs.inputEl?.focus()) },
    async deleteMessage(msg) { if (!msg.id) return; if (!confirm('删除这条消息？')) return; try { await api.delete(`/chat/manage/message/${msg.id}`); await this.loadHistory(); this.showContextMenu = false } catch (err) { console.error('删除失败', err) } },
    notifyReminder(data) { if (Notification.permission === 'granted') { new Notification(`${data.level_name}提醒`, { body: `${data.content}\n截止 ${data.target_time}`, icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🔔</text></svg>' }) } },
    adjustFontSize(delta) { this.chatFontSize = Math.min(20, Math.max(10, this.chatFontSize + delta)); document.querySelector('.msg-list').style.fontSize = this.chatFontSize + 'px'; this.updateGlobalConfig('chat_font_size', this.chatFontSize) },
    async exportChat() { try { const res = await api.get('/export/chat?format=txt'); const blob = new Blob([res.data.content], { type: 'text/plain' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = res.data.filename; a.click() } catch (err) { alert('导出失败') } },
    setTheme(v) { this.themeLocal = v; this.currentTheme = v; document.documentElement.setAttribute('data-theme', v); const meta = document.getElementById('theme-color-meta'); if (meta) meta.content = v === 'light' ? '#f5f6fa' : '#0d1117'; api.post('/api/window-theme', { dark: v !== 'light' }).catch(()=>{}); this.updateGlobalConfig('theme', v) },
    updateColorField(key, hex) { if (/^#[0-9a-fA-F]{6}$/.test(hex)) { this.colors[key] = hex; this.updateGlobalConfig(this.colorFields.find(f=>f.key===key)?.configKey, hex) } },
    saveColorPreset() {
      const name = this.newPresetName || prompt('预设名称：')
      if (!name) return
      const data = { theme: this.themeLocal, primary_color: this.colors.primary, bg_color: this.colors.bg, sidebar_bg: this.colors.sidebarBg, chat_bg: this.colors.chatBg, user_bubble: this.colors.userBubble, ai_bubble: this.colors.aiBubble }
      api.post('/settings/presets', { name, data }).then(() => { this.loadPresets(); this.newPresetName = '' }).catch(() => alert('保存失败'))
    },
    uploadBg() { this.$refs.bgInput?.click() },
    async onBgFilePicked(e) {
      const file = e.target.files[0]; if (!file) return
      const form = new FormData(); form.append('file', file, file.name)
      try {
        const res = await api.post('/avatar/upload/bg', form)
        if (res.data.url) { this.chatBgImage = BASE_URL + res.data.url; this.updateGlobalConfig('chat_bg_image', this.chatBgImage) }
      } catch (err) { alert('上传失败') }
    },
    applyColorPreset(name) {
      const presets = {
        default: { primary: '#5390d4', bg: '#0d1117', sidebarBg: '#161b22', chatBg: '#0d1117', userBubble: '#2b5278', aiBubble: '#1e2632' },
        wechat: { primary: '#07C160', bg: '#111111', sidebarBg: '#1a1a1a', chatBg: '#111111', userBubble: '#054', aiBubble: '#1e1e1e' },
        teal: { primary: '#14b8a6', bg: '#0f1724', sidebarBg: '#151e2d', chatBg: '#0f1724', userBubble: '#0f766e', aiBubble: '#1a2332' },
        warm: { primary: '#f59e0b', bg: '#1a1410', sidebarBg: '#221c14', chatBg: '#1a1410', userBubble: '#78350f', aiBubble: '#231f18' }
      }
      const p = presets[name]; Object.keys(p).forEach(k => { this.colors[k] = p[k]; this.updateGlobalConfig(this.colorFields.find(f=>f.key===k)?.configKey || k+'_color', p[k]) })
    },
    async loadHistory() { try { const res = await api.get(`/chat/history/?limit=50`); this.messages = res.data.messages; this.nextAfterId = res.data.next_after_id; const countRes = await api.get(`/chat/history/count`); this.totalMessages = countRes.data.count; if (this.messages.length) { this.conversationDays = Math.ceil((new Date() - new Date(this.messages[0].timestamp)) / 86400000) } this.scrollToBottom(); this.loadError = '' } catch (err) { this.loadError = '加载失败，点击重试'; console.error(err) } },
    async onDataChanged() { await this.loadHistory(); if (this.messages.length === 0) { this.nextAfterId = null } },
    async loadMoreHistory() { if (this.loadingMore || !this.nextAfterId) return; this.loadingMore = true; try { const res = await api.get(`/chat/history/?limit=50&after_id=${this.nextAfterId}`); if (res.data.messages.length) { this.messages = [...res.data.messages, ...this.messages]; this.nextAfterId = res.data.next_after_id } else { this.nextAfterId = null } } catch (err) { console.error(err) } finally { this.loadingMore = false } },
    connectWebSocket() {
      this.ws = new WebSocket(`${WS_URL}/ws/chat`)
      this.ws.onopen = () => { this.wsReady = true; this.wsReconnectAttempts = 0 }
      this.ws.onmessage = (event) => {
        let data; try { data = JSON.parse(event.data) } catch (e) { return }
        if (data.type === 'token') {
          this.pendingReply += data.content
          if (!this.schedId) this.schedulePop()
        } else if (data.type === 'done') {
          this.isStreaming = false
        } else if (data.type === 'greeting') { this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString() }); this.totalMessages++; this.scrollToBottom() }
        else if (data.type === 'reminder_count') {
          this.activeReminderCount = data.count
        }
        else if (data.type === 'reminder') {
          const d = data.data
          if (!d.id || this.reminderPopups.some(p => p.id === d.id)) return
          d._id = crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2, 10))
          this.reminderPopups.push(d)
          this.notifyReminder(d)
          if (d.level < 6) { setTimeout(() => { this.dismissReminder(d._id) }, 8000) }
        }
        else if (data.type === 'error') { this.messages.push({ role: 'assistant', content: '错误：' + data.content, timestamp: new Date().toISOString() }); this.isStreaming = false; this.stopTypewriter() }
      }
      this.ws.onerror = () => { this.wsReady = false; this.stopTypewriter() }
      this.ws.onclose = () => {
        this.wsReady = false; this.stopTypewriter()
        const delay = Math.min(2000 * Math.pow(1.5, this.wsReconnectAttempts), 30000)
        this.wsReconnectAttempts++
        this._reconnectTimer = setTimeout(() => { if (!this.wsReady) this.connectWebSocket() }, delay)
      }
    },
    sendMessage() {
      if (!this.inputText.trim() || this.isStreaming || this._sendingCooldown) return
      if (!this.wsReady) { this.messages.push({ id: 'err_' + Date.now(), role: 'assistant', content: '未连接，请确认后端已启动', timestamp: new Date().toISOString() }); return }
      this._sendingCooldown = true; setTimeout(() => { this._sendingCooldown = false }, 500)
      if (this.schedId) { clearTimeout(this.schedId); this.schedId = null }
      this.userScrolledUp = false
      const userMsg = this.inputText.trim()
      this.messages.push({ role: 'user', content: userMsg, timestamp: new Date().toISOString() })
      this.totalMessages++; this.inputText = ''; this.scrollToBottom(); this.isStreaming = true; this.streamingSentence = ''
      this.ws.send(JSON.stringify({ message: userMsg, history: this.messages.slice(-20).map(m => ({ role: m.role, content: m.content })) }))
      this.$nextTick(() => { const el = this.$refs.inputEl; if (el) { el.style.height = 'auto'; el.focus() } })
    },
    autoResizeInput() {
      const el = this.$refs.inputEl; if (!el) return
      const target = Math.min(el.scrollHeight, 120)
      if (Math.abs(el.offsetHeight - target) > 2) {
        el.style.height = target + 'px'
      }
    },
    openTodoModal() { this.showTodoModal = true }, closeTodoModal() { this.showTodoModal = false },
    openNoteModal() { this.showNoteModal = true }, closeNoteModal() { this.showNoteModal = false },
    openCountdownModal() { this.showCountdownModal = true }, closeCountdownModal() { this.showCountdownModal = false },
    openReminderModal() { this.showReminderModal = true }, closeReminderModal() { this.showReminderModal = false },
    openSettings() { this.showSettingsModal = true; this.loadIpLocation() },
    closeSettingsModal() { this.showSettingsModal = false },
    stopTypewriter() { this.pendingReply = ''; this.streamingSentence = ''; if (this.schedId) { clearTimeout(this.schedId); this.schedId = null } },
    schedulePop() {
      if (this.schedId) return
      const pop = () => {
        this.schedId = null
        this.pendingReply = this.pendingReply.replace(/^[\s\n]+/, '')
        if (!this.pendingReply) return
        const m = this.pendingReply.match(/^([\s\S]*?(?:[。！？!?]|\.{3,}|…|～))/)
        if (m && m[1].trim().length >= 2) {
          const sentence = m[1].trim()
          this.messages.push({ role: 'assistant', content: sentence, timestamp: new Date().toISOString() }); this.totalMessages++
          this.pendingReply = this.pendingReply.slice(m[1].length)
          this.scrollToBottom()
          const delay = Math.min(Math.max(300, 250 + sentence.length * 30), 2000)
          this.schedId = setTimeout(pop, delay)
        } else if (!this.isStreaming) {
          const remain = this.pendingReply.trim()
          if (remain) { this.messages.push({ role: 'assistant', content: remain, timestamp: new Date().toISOString() }); this.totalMessages++ }
          this.pendingReply = ''; this.scrollToBottom()
        } else {
          this.schedId = setTimeout(pop, 120)
        }
      }
      this.schedId = setTimeout(pop, 80)
    },
    dismissReminder(id) { this.reminderPopups = this.reminderPopups.filter(p => p._id !== id) },
    async completeReminder(pop) {
      try { await api.patch(`/reminders/${pop.id}/done`); this.dismissReminder(pop._id) } catch (err) { console.error('标记完成失败', err) }
    },
    async snoozeReminder(pop) {
      this.dismissReminder(pop._id)
      try { await api.patch(`/reminders/${pop.id}/snooze`) } catch (err) { console.error('稍后失败', err) }
    },
    scrollToBottom(force) { if (!force && this.userScrolledUp) return; this.$nextTick(() => { requestAnimationFrame(() => { const el = this.$refs.messagesContainer; if (el) { el.scrollTop = el.scrollHeight } }) }) },
    async testDeepSeek() { this.testing.ds = true; this.testing.dsStatus = ''; this.testing.dsMsg = ''; try { const res = await api.get('/test/deepseek'); this.testing.dsStatus = res.data.ok ? 'ok' : 'fail'; this.testing.dsMsg = res.data.message } catch (err) { this.testing.dsStatus = 'fail'; this.testing.dsMsg = '请求失败' } finally { this.testing.ds = false } },
    async testWeather() { this.testing.wt = true; this.testing.wtStatus = ''; this.testing.wtMsg = ''; try { const res = await api.get('/test/weather'); this.testing.wtStatus = res.data.ok ? 'ok' : 'fail'; this.testing.wtMsg = res.data.ok ? res.data.report : res.data.message } catch (err) { this.testing.wtStatus = 'fail'; this.testing.wtMsg = '请求失败' } finally { this.testing.wt = false } },
    async testSearch() { this.testing.se = true; this.testing.seStatus = ''; this.testing.seMsg = ''; try { const res = await api.get('/test/search'); this.testing.seStatus = res.data.ok ? 'ok' : 'fail'; this.testing.seMsg = res.data.message } catch (err) { this.testing.seStatus = 'fail'; this.testing.seMsg = '请求失败' } finally { this.testing.se = false } },
    async testIp() { this.testing.ip = true; this.testing.ipStatus = ''; this.testing.ipMsg = ''; try { const res = await api.get('/test/ip'); this.testing.ipStatus = res.data.ok ? 'ok' : 'fail'; this.testing.ipMsg = res.data.message; if (res.data.ok) { this.ipCityShort = res.data.message; this.loadIpLocation() } } catch (err) { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '请求失败' } finally { this.testing.ip = false } },
    async locateAndFill() { this.locating = true; this.testing.ipStatus = ''; this.testing.ipMsg = ''; try { const res = await api.get('/test/ip'); if (res.data.ok) { this.testing.ipStatus = 'ok'; this.testing.ipMsg = res.data.message; await this.loadIpLocation() } else { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '定位服务不可用，请手动选城市' } } catch (err) { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '请求失败' } finally { this.locating = false } },
    preciseLocate() {
      this.locating = true; this.testing.ipStatus = ''; this.testing.ipMsg = '';
      if (!navigator.geolocation) { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '浏览器不支持定位'; this.locating = false; return }
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const res = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude })
            if (res.data.city) {
              const addr = res.data.detail || `${res.data.province}${res.data.city}${res.data.district}${res.data.street}`
              this.testing.ipStatus = 'ok'; this.testing.ipMsg = addr; this.ipCityShort = res.data.city; this.ipCity = addr
              await this.updateGlobalConfig('precise_city', res.data.city)
            } else { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '解析失败' }
          } catch (err) { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '请求失败' }
          finally { this.locating = false }
        },
        () => { this.testing.ipStatus = 'fail'; this.testing.ipMsg = '请允许浏览器定位权限'; this.locating = false },
        { enableHighAccuracy: true, timeout: 10000 }
      )
    },
    startDrag(e) { const el = this.$refs.settingsPanel; if (!el) return; const sx = e.clientX - el.offsetLeft, sy = e.clientY - el.offsetTop; const move = (ev) => { el.style.left = (ev.clientX - sx) + 'px'; el.style.top = (ev.clientY - sy) + 'px'; el.style.margin = '0'; }; const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); }; document.addEventListener('mousemove', move); document.addEventListener('mouseup', up); }
  }
}
</script>

<style scoped>
/* ====== Layout ====== */
.app { display: flex; flex-direction: column; position: fixed; inset: 0; background: var(--bg); transition: filter .2s; }
.blur-bg .sidebar, .blur-bg .chat { filter: blur(4px); }

.top-bar { display: flex; align-items: center; gap: 16px; padding: 8px 20px; background: var(--sb); border-bottom: 1px solid rgba(128,128,128,.15); }
.brand { font-size: 16px; font-weight: 700; color: var(--p); }
.status { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #e74c3c33; color: #e74c3c; }
.status.online { background: #4caf5033; color: #4caf50; }
.location { font-size: 11px; padding: 2px 10px; border-radius: 10px; background: #ffffff08; color: #888; display: inline-block; }
.msg-count { font-size: 11px; color: #7f8c8d; }
.top-date { flex: 1; text-align: center; font-size: 12px; color: var(--p); font-weight: 500; }

.layout { display: flex; flex: 1; min-height: 0; overflow: hidden; }

/* ====== Sidebar ====== */
.sidebar { width: 200px; background: var(--sb); display: flex; flex-direction: column; border-right: 1px solid rgba(128,128,128,.1); transition: width .2s; overflow: hidden; }
.sidebar.collapsed { width: 48px; }
.sidebar.collapsed .nav-label { opacity: 0; width: 0; pointer-events: none; }
.sidebar.collapsed .nav-icons button { justify-content: center; padding: 10px 0; }
.nav-icons { display: flex; flex-direction: column; gap: 2px; padding: 8px; flex: 1; }
.nav-icons button { background: none; border: none; cursor: pointer; opacity: .5; transition: all .15s; padding: 8px 10px; border-radius: 6px; color: #8899aa; display: flex; align-items: center; gap: 10px; font-size: 13px; white-space: nowrap; width: 100%; }
.nav-icons button:hover { opacity: 1; color: #ecf0f1; background: rgba(255,255,255,.05); }
.nav-label { transition: opacity .15s; overflow: hidden; }
.nav-settings { margin-top: auto !important; background: none; border: none; cursor: pointer; opacity: .5; transition: all .15s; padding: 8px 10px; border-radius: 6px; color: #8899aa; display: flex; align-items: center; gap: 10px; font-size: 13px; }
.nav-settings:hover { opacity: 1; color: #ecf0f1; background: rgba(255,255,255,.05); }
.reminder-btn { position: relative; }
.badge { position: absolute; top: 2px; right: 4px; min-width: 16px; height: 16px; background: #e74c3c; color: #fff; border-radius: 8px; font-size: 10px; font-weight: 600; display: flex; align-items: center; justify-content: center; padding: 0 4px; }
.sidebar-toggle { background: none; border: none; cursor: pointer; padding: 10px; color: #555; display: flex; justify-content: center; border-top: 1px solid rgba(255,255,255,.05); transition: color .15s; }
.sidebar-toggle:hover { color: #999; }

/* ====== Chat ====== */
.chat { flex: 1; display: flex; flex-direction: column; background: var(--cb); overflow: hidden; }

.chat-top { display: flex; justify-content: center; padding: 8px; }
.btn-more { background: none; border: 1px solid rgba(255,255,255,.1); color: #7f8c8d; padding: 4px 16px; border-radius: 12px; font-size: 12px; cursor: pointer; }
.btn-more:hover:not(:disabled) { color: var(--p); border-color: var(--p); }
.btn-more:disabled { opacity: .3; cursor: default; }

.msg-list { flex: 1; overflow-y: auto; padding: 16px 20px; display: flex; flex-direction: column; gap: 20px; scroll-behavior: smooth; position: relative; background-image: var(--chat-bg-img); background-size: cover; background-position: center; background-repeat: no-repeat; background-attachment: fixed; }
.empty-chat { color: #7f8c8d; text-align: center; margin-top: 120px; font-size: 14px; }
.date-sep { text-align: center; font-size: 12px; color: #7f8c8d; padding: 6px 0; }
.date-sep::before, .date-sep::after { content: ''; display: inline-block; width: 40px; height: 1px; background: rgba(255,255,255,.1); vertical-align: middle; margin: 0 10px; }
.msg-bubble a { color: #6cb4ee; text-decoration: underline; }


/* 输入行 */
.input-row { display: flex; align-items: flex-end; gap: 6px; position: relative; }
.emoji-btn { background: none; border: none; font-size: 13px; color: #888; cursor: pointer; padding: 6px 8px; border-radius: 6px; transition: all .15s; font-family: inherit; }
.emoji-btn:hover { color: var(--p); background: rgba(255,255,255,.05); }
.kaomoji-picker { position: absolute; bottom: 100%; left: 0; display: flex; flex-direction: column; gap: 2px; padding: 6px; background: #1e2a3a; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.4); z-index: 20; margin-bottom: 4px; min-width: 120px; }
.kaomoji-item { font-size: 13px; cursor: pointer; padding: 5px 10px; border-radius: 4px; transition: background .1s; white-space: nowrap; color: #ccc; font-family: inherit; }
.kaomoji-item:hover { background: rgba(255,255,255,.08); color: #fff; }
.quote-bar { padding: 6px 12px; background: rgba(255,255,255,.05); border-radius: 8px 8px 0 0; font-size: 12px; color: #8899aa; display: flex; justify-content: space-between; align-items: center; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.quote-bar button { background: none; border: none; color: #888; cursor: pointer; font-size: 14px; }
.quote-bar button:hover { color: #fff; }

/* 右键菜单 */
.context-menu { position: fixed; z-index: 2000; background: #1e2a3a; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.6); overflow: hidden; min-width: 120px; }
.ctx-item { padding: 8px 16px; font-size: 13px; color: #ccc; cursor: pointer; transition: background .1s; }
.ctx-item:hover { background: rgba(255,255,255,.06); }
.ctx-danger { color: #e74c3c; }
.ctx-danger:hover { background: rgba(231,76,60,.15); }
.msg-list, .settings-content, .modal-bd, .card-compact { scrollbar-width: none; }
.msg-list::-webkit-scrollbar,
.settings-content::-webkit-scrollbar,
.modal-bd::-webkit-scrollbar,
.card-compact::-webkit-scrollbar { display: none; }

/* ====== Messages ====== */
.msg { display: flex; gap: 10px; max-width: 75%; }
.msg.user { align-self: flex-end; flex-direction: row-reverse; }
.msg.assistant { align-self: flex-start; }

.msg-avatar { width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; }
.msg-body { max-width: calc(100% - 36px); }
.msg-bubble { padding: 9px 13px; border-radius: 10px; font-size: 14px; line-height: 1.6; word-break: break-word; white-space: pre-wrap; }
.msg.user .msg-bubble { background: var(--ub); color: #fff; }
.msg.assistant .msg-bubble { background: var(--ab); color: #ecf0f1; }
.msg-bubble.typing-cursor { padding: 10px 16px; }
.cursor-bar { display: inline-block; width: 2px; height: 16px; background: var(--p); vertical-align: text-bottom; animation: cursorBlink .8s infinite; border-radius: 1px; }
@keyframes cursorBlink { 0%,100% { opacity: 1; } 50% { opacity: .15; } }

.msg-time { font-size: 10px; color: #7f8c8d; margin-top: 3px; opacity: .35; }
.msg.user .msg-time { text-align: right; }

/* ====== Input ====== */
.chat-input { display: flex; flex-direction: column; padding: 8px 16px 12px; background: var(--sb); border-top: 1px solid rgba(255,255,255,.05); }
.chat-input textarea { flex: 1; padding: 8px 14px; border-radius: 20px; background: var(--bg); color: #fff; border: 1px solid rgba(255,255,255,.08); outline: none; resize: none; font-size: 14px; font-family: inherit; line-height: 1.4; min-height: 36px; max-height: 120px; transition: height .12s ease; }
.chat-input textarea:focus { border-color: var(--p); }
.chat-input textarea::placeholder { color: #7f8c8d; }
.chat-input textarea:disabled { opacity: .5; }
.btn-send { padding: 10px 20px; background: var(--p); color: #fff; border: none; border-radius: 20px; cursor: pointer; font-size: 14px; font-weight: 600; transition: opacity .15s; }
.btn-send:hover:not(:disabled) { opacity: .85; }
.btn-send:disabled { opacity: .4; cursor: default; }

.btn-voice-toggle { padding: 8px 12px; background: transparent; color: #888; border: 1px solid rgba(255,255,255,.1); border-radius: 20px; cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-voice-toggle:hover { color: var(--p); border-color: var(--p); }

.btn-hold-speak { flex: 1; padding: 12px 20px; background: #1e2a3a; color: #ccc; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; cursor: pointer; font-size: 14px; user-select: none; transition: all .1s; min-height: 42px; display: flex; align-items: center; justify-content: center; }
.btn-hold-speak:active { background: var(--p); color: #fff; border-color: var(--p); }

.btn-play-msg { display: inline-block; margin-left: 6px; color: #888; font-size: 11px; cursor: pointer; padding: 2px 6px; border: 1px solid rgba(255,255,255,.08); border-radius: 4px; user-select: none; }
.btn-play-msg:hover { color: var(--p); border-color: var(--p); }

:root[data-theme="light"] .btn-hold-speak { background: #f5f6fa; color: #333; border-color: #ddd; }
:root[data-theme="light"] .btn-voice-toggle { color: #999; border-color: #ddd; }

/* ====== Modals (small tools) ====== */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); backdrop-filter: blur(6px); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal { background: #1e2a3a; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
.modal.small { width: 420px; max-height: 80vh; }
.modal-hd { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid rgba(128,128,128,.1); }
.modal-hd h3 { margin: 0; color: #ecf0f1; font-size: 16px; }
.modal-hd button { background: none; border: none; color: #888; font-size: 20px; cursor: pointer; }
.modal-bd { flex: 1; overflow-y: auto; padding: 16px; }

/* ====== Settings ====== */
.settings-panel { position: fixed; width: 820px; height: 580px; background: #1e2a3a; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 16px 48px rgba(0,0,0,.5); z-index: 1001; }
.settings-titlebar { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background: var(--sb); cursor: move; user-select: none; border-bottom: 1px solid rgba(128,128,128,.1); }
.settings-titlebar span { color: #ecf0f1; font-size: 14px; font-weight: 600; }
.settings-titlebar button { background: none; border: none; color: #888; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 4px; transition: color .15s; }
.settings-titlebar button:hover { background: rgba(128,128,128,.1); color: #fff; }
.settings-body { display: flex; flex: 1; overflow: hidden; }
.settings-nav { width: 120px; background: var(--sb); padding: 8px 0; display: flex; flex-direction: column; gap: 2px; border-right: 1px solid rgba(128,128,128,.1); }
.nav-item { display: flex; align-items: center; gap: 8px; padding: 8px 14px; cursor: pointer; font-size: 12px; color: #999; transition: all .15s; border-left: 2px solid transparent; }
.nav-item:hover { color: #ccc; background: rgba(255,255,255,.03); }
.nav-item.active { color: #fff; background: rgba(255,255,255,.06); border-left-color: var(--p); }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }
.nav-label { white-space: nowrap; }
.settings-content { flex: 1; overflow-y: auto; padding: 16px 20px; background: #1a1d2a; }
.tab-content { display: flex; flex-direction: column; gap: 10px; }

/* --- Cards --- */
.card { background: #1e2a3a; border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,.03); }
.card-title { padding: 9px 14px; font-size: 12px; font-weight: 500; color: #bdc3c7; background: rgba(255,255,255,.015); border-bottom: 1px solid rgba(255,255,255,.04); letter-spacing: .3px; }
.card-body { padding: 10px 14px; }
.card-grow { flex: 1; display: flex; flex-direction: column; }
.card-body-grow { flex: 1; display: flex; flex-direction: column; }
.switch-label { display: flex; align-items: center; gap: 8px; padding: 4px 0; color: #bdc3c7; font-size: 13px; cursor: pointer; }
.switch-label input[type="checkbox"] { accent-color: var(--p); }

/* --- Settings shared --- */
.api-row { display: flex; gap: 8px; align-items: center; }
.api-row input { flex: 1; }
.saved-hint { color: #4caf50; font-size: 11px; margin-top: 6px; }
.loc-row { display: flex; gap: 6px; margin-top: 8px; }
.loc-row select { flex: 1; padding: 7px 10px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.06); font-size: 12px; outline: none; }
.loc-hint { font-size: 11px; color: #8899aa; margin-top: 6px; }
.btn-row { display: flex; gap: 8px; }
.preset-actions { display: flex; gap: 4px; }
.empty-hint { color: #7f8c8d; text-align: center; font-size: 12px; padding: 12px; }
/* --- Data console --- */
.stats-bar { display: flex; align-items: center; padding: 14px 18px; background: var(--p); border-radius: 8px; margin-bottom: 10px; }
.stat-item { display: flex; flex-direction: column; align-items: center; flex: 1; }
.stat-val { font-size: 20px; font-weight: 600; color: #fff; }
.stat-lbl { font-size: 11px; color: rgba(255,255,255,.7); margin-top: 2px; }
.stat-sep { width: 1px; height: 28px; background: rgba(255,255,255,.3); }
.card-compact { padding: 8px 12px; }
.btn-danger { background: rgba(231,76,60,.15) !important; color: #e74c3c !important; }
.btn-danger:hover { background: rgba(231,76,60,.3) !important; }

/* --- Shared form elements --- */
.field { margin-bottom: 12px; }
.field label { display: block; font-size: 12px; color: #8899aa; margin-bottom: 5px; }
.field input, .field select, .field textarea, .api-row input, .loc-row select { width: 100%; padding: 8px 12px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.08); font-size: 13px; outline: none; resize: vertical; font-family: inherit; }
.field input:focus, .field select:focus, .field textarea:focus, .api-row input:focus, .loc-row select:focus { border-color: var(--p); }
.role-textarea { flex: 1; min-height: 150px; line-height: 1.6; resize: vertical; background: transparent !important; }
input, select, textarea { font-family: inherit; }
.btn { padding: 8px 18px; background: var(--p); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; white-space: nowrap; }
.btn:hover { opacity: .85; }
.btn:disabled { opacity: .4; cursor: default; }
.btn-s { padding: 5px 14px; background: rgba(255,255,255,.08); color: #ccc; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }
.btn-s:hover { background: rgba(255,255,255,.14); color: #fff; }
.btn-s:disabled { opacity: .3; }

/* --- Test rows --- */
.test-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; font-size: 13px; }
.test-row > span:first-child { width: 50px; color: #8899aa; font-size: 12px; flex-shrink: 0; }
.test-row > span:last-child { font-size: 11px; flex: 1; }
.ok { color: #4caf50 !important; }
.fail { color: #e74c3c !important; }
.ip-status { color: #4caf50; font-size: 13px; margin-bottom: 8px; }

/* --- Theme toggle --- */
.theme-toggle { display: flex; gap: 8px; }
.theme-btn { flex: 1; padding: 10px; background: rgba(255,255,255,.04); color: #999; border: 1px solid rgba(255,255,255,.06); border-radius: 6px; cursor: pointer; font-size: 14px; transition: all .15s; }
.theme-btn:hover { color: #ccc; }
.theme-btn.active { background: var(--p); color: #fff; border-color: var(--p); }
:root[data-theme="light"] .theme-btn { background: #f0f0f0; color: #666; }
:root[data-theme="light"] .theme-btn.active { background: var(--p); color: #fff; }

/* --- Colors --- */
.color-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.color-row { display: flex; align-items: center; gap: 10px; }
.color-swatch { width: 22px; height: 22px; border-radius: 4px; border: 1px solid rgba(255,255,255,.15); flex-shrink: 0; }
.color-label { width: 56px; font-size: 12px; color: #8899aa; flex-shrink: 0; }
.color-pick { width: 28px; height: 24px; padding: 0; border: 1px solid rgba(255,255,255,.1); border-radius: 4px; cursor: pointer; background: transparent; }
.color-hex { width: 80px; padding: 4px 8px !important; border-radius: 4px; background: #0f1923; color: #ccc; border: 1px solid rgba(255,255,255,.08); font-size: 12px; outline: none; font-family: monospace; }
.color-hex:focus { border-color: var(--p); }
.preset-bar { display: flex; gap: 6px; flex-wrap: wrap; }
:root[data-theme="light"] .color-hex { background: #f5f6fa; color: #333; }

/* --- Background upload --- */
.bg-row { display: flex; gap: 8px; }
.bg-row input { flex: 1; }

/* --- Presets --- */
.preset-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: rgba(255,255,255,.03); border-radius: 6px; margin-bottom: 6px; }
.preset-row span { font-size: 13px; color: #bdc3c7; }
</style>

<style>
/* QQ 亮色模式 */
:root[data-theme="light"] { --p: #2b6cb0; --bg: #f5f6fa; --sb: #e8e9ed; --cb: #f5f6fa; --ub: #2b6cb0; --ab: #ffffff; }
:root[data-theme="light"] .top-bar,
:root[data-theme="light"] .sidebar,
:root[data-theme="light"] .chat-top,
:root[data-theme="light"] .chat-input { background: #e8e9ed; border-color: #ddd; }
:root[data-theme="light"] .chat-input textarea { background: #fff; color: #333; border-color: #ddd; }
:root[data-theme="light"] .chat { background: #f5f6fa; }
:root[data-theme="light"] .brand { color: #2b6cb0; }
:root[data-theme="light"] .status { background: #e74c3c22; color: #d63031; }
:root[data-theme="light"] .status.online { background: #4caf5022; color: #27ae60; }
:root[data-theme="light"] .location { background: #00000008; color: #999; }
:root[data-theme="light"] .msg.assistant .msg-bubble { background: #fff; color: #333; border: 1px solid #e8e8ea; }
:root[data-theme="light"] .msg.user .msg-bubble { color: #fff; }
:root[data-theme="light"] .msg-time { color: #aaa; }
:root[data-theme="light"] .btn-more { color: #999; border-color: #ddd; }
:root[data-theme="light"] .sidebar-toggle { border-color: #ddd; color: #bbb; }
:root[data-theme="light"] .kaomoji-picker { background: #fff; box-shadow: 0 4px 16px rgba(0,0,0,.1); }
:root[data-theme="light"] .kaomoji-item { color: #555; }
:root[data-theme="light"] .kaomoji-item:hover { background: #f0f0f0; color: #222; }
:root[data-theme="light"] .top-bar { border-color: rgba(0,0,0,.06); }
:root[data-theme="light"] .settings-titlebar button { color: #999; }
:root[data-theme="light"] .settings-titlebar button:hover { background: rgba(0,0,0,.06); color: #333; }
:root[data-theme="light"] .settings-panel,
:root[data-theme="light"] .settings-titlebar,
:root[data-theme="light"] .settings-nav { background: #fff; }
:root[data-theme="light"] .settings-content { background: #f5f6fa; }
:root[data-theme="light"] .card { background: #fff; border-color: #eee; }
:root[data-theme="light"] .card-title { color: #444; background: #fafafa; }
:root[data-theme="light"] .field input, :root[data-theme="light"] .field select, :root[data-theme="light"] .field textarea,
:root[data-theme="light"] .api-row input, :root[data-theme="light"] .loc-row select { background: #f5f6fa; color: #333; border-color: #e0e0e0; }
:root[data-theme="light"] .nav-item { color: #666; }
:root[data-theme="light"] .nav-item.active { color: #2b6cb0; background: #eaf1fb; }
:root[data-theme="light"] .modal { background: #fff; }
:root[data-theme="light"] .modal-hd { border-color: #eee; }
:root[data-theme="light"] .preset-row { background: #f0f0f0; }
:root[data-theme="light"] .preset-row span { color: #333; }
:root[data-theme="light"] .settings-titlebar span, :root[data-theme="light"] .modal-hd h3 { color: #333; }
:root[data-theme="light"] .settings-titlebar { border-color: #eee; }
:root[data-theme="light"] .settings-nav { border-color: #eee; }
:root[data-theme="light"] .btn-s { background: #e8e9ed; color: #555; }
:root[data-theme="light"] .btn-s:hover { background: #ddd; color: #222; }
:root[data-theme="light"] .btn-danger { background: #fce4e4 !important; color: #d63031 !important; }
:root[data-theme="light"] .btn-danger:hover { background: #f8d0d0 !important; }

/* ====== 右侧提醒弹窗 ====== */
.reminder-popups { position: fixed; right: 16px; top: 60px; z-index: 900; pointer-events: none; max-height: calc(100vh - 100px); }
.reminder-popups-inner { display: flex; flex-direction: column; gap: 8px; pointer-events: auto; overflow-y: auto; max-height: calc(100vh - 100px); }
.reminder-popup { width: 280px; background: #1e2a3a; border-radius: 8px; display: flex; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,.4); pointer-events: auto; flex-shrink: 0; }
.reminder-popup-bar { width: 4px; flex-shrink: 0; }
.bar-lvl-7, .bar-lvl-6 { background: #e74c3c; }
.bar-lvl-5, .bar-lvl-4 { background: #f39c12; }
.bar-lvl-3, .bar-lvl-2 { background: #3498db; }
.bar-lvl-1 { background: #4caf50; }
.reminder-popup-body { flex: 1; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.reminder-popup-tag { font-size: 11px; color: var(--p); font-weight: 600; }
.reminder-popup-text { font-size: 13px; color: #ecf0f1; word-break: break-word; }
.reminder-popup-time { font-size: 11px; color: #7f8c8d; }
.reminder-popup-actions { display: flex; gap: 6px; margin-top: 6px; }
.reminder-btn-done { background: #4caf50; border: none; border-radius: 4px; color: #fff; cursor: pointer; padding: 3px 10px; font-size: 11px; }
.reminder-btn-done:hover { opacity: .8; }
.reminder-btn-snooze { background: rgba(255,255,255,.1); border: none; border-radius: 4px; color: #aaa; cursor: pointer; padding: 3px 10px; font-size: 11px; }
.reminder-btn-snooze:hover { background: rgba(255,255,255,.2); color: #fff; }
.reminder-popup-close { background: none; border: none; color: #888; cursor: pointer; padding: 8px; font-size: 14px; align-self: flex-start; }
.reminder-popup-close:hover { color: #fff; }

html, body { scrollbar-width: none; }
html::-webkit-scrollbar, body::-webkit-scrollbar { display: none; }

/* 滑入动画 */
.slide-enter-active { transition: all .3s ease-out; }
.slide-leave-active { transition: all .2s ease-in; }
.slide-enter-from { opacity: 0; transform: translateX(60px); }
.slide-leave-to { opacity: 0; transform: translateX(60px); }

/* 紧急提醒脉冲 */
.level-7 .reminder-popup-bar { animation: pulse .6s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

/* 亮色模式提醒弹窗 */
:root[data-theme="light"] .reminder-popup { background: #fff; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
:root[data-theme="light"] .reminder-popup-text { color: #333; }
:root[data-theme="light"] .reminder-popup-time { color: #999; }
</style>
