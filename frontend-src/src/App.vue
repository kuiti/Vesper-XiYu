<template>
  <div class="app" :data-theme="currentTheme" :class="{ 'blur-bg': modalOpen }" :style="colorVariables">
    <div class="top-bar">
      <span class="brand">夕语</span>
      <span class="status" :class="{ online: wsReady }">{{ wsReady ? '在线' : '连接中...' }}</span>
      <span class="location">{{ locationText }}</span>
      <span class="top-date" v-if="floatingDate">{{ floatingDate }}</span>
      <span class="msg-count" v-if="totalMessages">{{ totalMessages }} 条消息</span>
      <span class="reminder-badge" v-if="reminderCount > 0" :title="`${reminderCount} 条提醒`">{{ reminderCount }} 条提醒</span>
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
          <div v-if="!messages.length" class="empty-chat">
            <div class="empty-greeting">{{ timeGreeting }}</div>
            <div class="empty-hint">{{ loadError || '我在这里，随时陪你聊天' }}</div>
            <div class="empty-suggestions">
              <span v-for="s in chatSuggestions" :key="s" class="suggestion-chip" @click="inputText=s;sendMessage()">{{ s }}</span>
            </div>
          </div>
          <template v-for="(msg, idx) in messages" :key="msg.id || idx">
            <div v-if="idx === 0 || dateLabel(msg.timestamp) !== dateLabel(messages[idx-1].timestamp)" class="date-sep">{{ dateLabel(msg.timestamp) }}</div>
            <div :class="['msg', msg.role, { proactive: msg.isProactive }]">
              <div class="msg-avatar-wrap">
                <span class="msg-name">{{ msg.role === 'user' ? (userNameLocal || '你') : (aiNameLocal || '夕语') }}</span>
                <img class="msg-avatar" :src="msg.role === 'user' ? userAvatarUrl : assistantAvatarUrl" />
              </div>
              <div class="msg-body">
                <div v-if="msg.isWeather" class="weather-msg"><WeatherCard :data="msg.weatherData" /></div>
                <div v-else class="msg-bubble" v-html="safeLinkify(msg.content)" @contextmenu.prevent="openContextMenu($event, msg)" @dblclick="copyMessage(msg)"></div>
                <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </template>
          <div v-show="isStreaming" class="msg assistant">
            <div class="msg-avatar-wrap">
              <span class="msg-name">{{ aiNameLocal || '夕语' }}</span>
              <img class="msg-avatar" :src="assistantAvatarUrl" />
            </div>
            <div class="msg-body">
              <div class="msg-bubble typing-dots"><span class="dot-bounce"></span><span class="dot-bounce"></span><span class="dot-bounce"></span></div>
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
              <div class="card"><div class="card-title">AI 接口配置</div><div class="card-body">
                <div class="field"><label>提供商</label><select v-model="apiProviderLocal" @change="onProviderChange"><option value="deepseek">DeepSeek</option><option value="qwen">通义千问</option><option value="moonshot">Moonshot</option><option value="zhipu">智谱 GLM</option><option value="openai">OpenAI</option><option value="custom">自定义</option></select></div>
                <div class="field"><label>API 地址</label><input v-model="apiBaseUrlLocal" placeholder="https://api.deepseek.com/v1"></div>
                <div class="field"><label>模型</label>
                  <div class="model-row">
                    <select v-if="availableModels.length" v-model="apiModelLocal" class="model-select">
                      <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
                    </select>
                    <input v-else v-model="apiModelLocal" placeholder="deepseek-chat" class="model-input">
                    <button class="btn-s" @click="fetchModels" :disabled="loadingModels">{{ loadingModels ? '...' : '获取模型' }}</button>
                  </div>
                </div>
                <div class="field"><label>API Key</label><input type="password" v-model="apiKeyLocal" placeholder="sk-..."></div>
                <div class="prompt-actions"><button class="btn" @click="saveApiConfig">保存</button><span v-if="apiConfigSaved" class="saved-hint">已保存</span></div>
                <div class="test-row"><span>连通性</span><button class="btn-s" @click="testApiConnection" :disabled="testing.ds">{{ testing.ds ? '...' : '测试' }}</button><span :class="testing.dsStatus">{{ testing.dsMsg }}</span></div>
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
                <div class="btn-row" style="margin-top:8px"><button class="btn-s" @click="resetLocationPermission">重新询问定位权限</button></div>
                <div class="loc-row"><select v-model="selectedProvince" @change="onProvinceChange"><option value="">省份</option><option v-for="p in provinces" :key="p.adcode" :value="p.adcode">{{ p.name }}</option></select><select v-model="selectedCity" :disabled="!selectedProvince"><option value="">城市</option><option v-for="c in cities" :key="c.adcode" :value="c.adcode">{{ c.name }}</option></select><button class="btn-s" @click="savePreciseCity">保存</button></div>
              </div></div>
            </div>

            <!-- 角色 -->
            <div v-if="settingsTab === 'role'" class="tab-content">
              <div class="card"><div class="card-title">基本信息</div><div class="card-body">
                <div class="avatar-section">
                  <div class="avatar-preview">
                    <img :src="assistantAvatarUrl" class="avatar-img" />
                    <span class="avatar-label">AI 头像</span>
                  </div>
                  <div class="avatar-actions">
                    <button class="btn-s" @click="$refs.aiAvatarInput.click()">本地上传</button>
                    <input type="file" ref="aiAvatarInput" accept="image/*" style="display:none" @change="uploadAvatar('assistant', $event)">
                    <div class="url-row">
                      <input v-model="aiAvatarUrl" placeholder="或输入图片URL" class="url-input">
                      <button class="btn-s" @click="uploadAvatarByUrl('assistant')" :disabled="!aiAvatarUrl">导入</button>
                    </div>
                  </div>
                </div>
                <div class="avatar-section">
                  <div class="avatar-preview">
                    <img :src="userAvatarUrl" class="avatar-img" />
                    <span class="avatar-label">用户头像</span>
                  </div>
                  <div class="avatar-actions">
                    <button class="btn-s" @click="$refs.userAvatarInput.click()">本地上传</button>
                    <input type="file" ref="userAvatarInput" accept="image/*" style="display:none" @change="uploadAvatar('user', $event)">
                    <div class="url-row">
                      <input v-model="userAvatarUrlInput" placeholder="或输入图片URL" class="url-input">
                      <button class="btn-s" @click="uploadAvatarByUrl('user')" :disabled="!userAvatarUrlInput">导入</button>
                    </div>
                  </div>
                </div>
                <div class="card"><div class="card-title">关系状态</div><div class="card-body">
                  <div class="relationship-bars">
                    <div class="rel-item">
                      <span class="rel-label">好感度</span>
                      <div class="rel-bar"><div class="rel-fill affection" :style="{width: relationship.affection + '%'}"></div></div>
                      <span class="rel-value">{{ relationship.affection }}</span>
                    </div>
                    <div class="rel-item">
                      <span class="rel-label">信任度</span>
                      <div class="rel-bar"><div class="rel-fill trust" :style="{width: relationship.trust + '%'}"></div></div>
                      <span class="rel-value">{{ relationship.trust }}</span>
                    </div>
                    <div class="rel-item">
                      <span class="rel-label">AI 状态</span>
                      <span class="ai-emotion-tag">{{ relationship.ai_emotion_label }}</span>
                      <span class="ai-emotion-desc">{{ relationship.ai_emotion_description }}</span>
                    </div>
                  </div>
                </div></div>
                <div class="field"><label>AI 名称</label><input v-model="aiNameLocal" @change="updateGlobalConfig('ai_name', aiNameLocal)"></div>
                <div class="field"><label>你的称呼</label><input v-model="userNameLocal" @change="updateGlobalConfig('user_name', userNameLocal)"></div>
              </div></div>
              <div class="card"><div class="card-title">回复风格</div><div class="card-body">
                <div class="field"><label>语气</label><select v-model="toneLocal" @change="saveTone"><option value="冷静">冷静</option><option value="活泼">活泼</option><option value="温柔">温柔</option><option value="毒舌">毒舌</option><option value="傲娇">傲娇</option></select></div>
                <div class="field"><label>长度</label><select v-model="lengthLocal" @change="updateGlobalConfig('length_level', lengthLocal)"><option value="极短">极短</option><option value="短">短</option><option value="中等">中等</option><option value="长">长</option><option value="详细">详细</option></select></div>
                <div class="field"><label>回忆</label><select v-model="recallLocal" @change="updateGlobalConfig('recall_past', recallLocal)"><option value="从不">从不</option><option value="被动">被动</option></select></div>
              </div></div>
              <div class="card card-grow"><div class="card-title">自定义人设提示词</div><div class="card-body card-body-grow"><textarea v-model="customPromptLocal" placeholder="留空则使用默认人设..." class="role-textarea"></textarea><div class="prompt-actions"><button class="btn" @click="saveCustomPrompt">保存</button><span v-if="promptSaved" class="saved-hint">已保存</span></div></div></div>
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
                  <button :class="['theme-btn', { active: themeLocal==='sakura' }]" @click="setTheme('sakura')">🌸 樱花粉</button>
                  <button :class="['theme-btn', { active: themeLocal==='vesper' }]" @click="setTheme('vesper')">✨ 夕语</button>
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
                  <button class="btn-s" @click="applyColorPreset('sakura')">夕语樱</button>
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
              <div class="card"><div class="card-title">情绪趋势（7天）</div><div class="card-body">
                <div class="emotion-chart">
                  <div v-for="d in emotionTrend" :key="d.date" class="emotion-bar-group">
                    <div class="emotion-bar" :style="{height: Math.abs(d.score) * 2 + 'px', background: d.score >= 0 ? '#4caf50' : '#e74c3c'}"></div>
                    <span class="emotion-date">{{ d.date.slice(5) }}</span>
                  </div>
                </div>
                <div v-if="emotionTrend.length === 0" class="empty-hint">暂无情绪数据</div>
              </div></div>
              <div class="card"><div class="card-body"><SearchPanel /></div></div>
              <div class="card"><div class="card-body"><MemoryPanel /></div></div>
              <div class="card"><div class="card-body"><RAGPanel /></div></div>
              <div class="card"><div class="card-body"><ChatManagePanel @changed="onDataChanged" /></div></div>
              <div class="card"><div class="card-body"><MigratePanel /></div></div>
              <div class="card"><div class="card-title">知识库</div><div class="card-body"><KnowledgePanel /></div></div>
              <div class="card"><div class="card-body"><button class="btn" @click="exportChat">导出聊天记录 (TXT)</button></div></div>
            </div>

            <!-- 通知 -->
            <div v-if="settingsTab === 'voice'" class="tab-content">
              <div class="card"><div class="card-title">提醒方式</div><div class="card-body">
                <label class="switch-label"><input type="checkbox" v-model="useSystemNotification" @change="updateGlobalConfig('use_system_notification', useSystemNotification)"> 使用 Windows 系统通知</label>
                <div class="loc-hint">开启后提醒将通过系统通知中心推送，软件内不弹窗</div>
                <div class="field" v-if="useSystemNotification" style="margin-top:12px">
                  <label>通知风格</label>
                  <select v-model="notificationStyle" @change="updateGlobalConfig('notification_style', notificationStyle)">
                    <option value="warm">温和亲切</option>
                    <option value="casual">随意自然</option>
                    <option value="professional">专业简洁</option>
                  </select>
                </div>
              </div></div>
              <div class="card"><div class="card-title">天气关怀</div><div class="card-body">
                <label class="switch-label"><input type="checkbox" v-model="useWeatherCare" @change="updateGlobalConfig('use_weather_care', useWeatherCare)"> 每日天气推送</label>
                <div class="loc-hint">每天 7:00、12:00、19:00 自动推送天气信息</div>
              </div></div>
              <div class="card"><div class="card-title">托盘行为</div><div class="card-body">
                <label class="switch-label"><input type="checkbox" v-model="showTrayNotification" @change="updateGlobalConfig('show_tray_notification', showTrayNotification)"> 关闭窗口时显示托盘提示</label>
              </div></div>
            </div>

          </div>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="confirmDialog.show" class="modal-overlay" @click.self="confirmDialog.show=false">
      <div class="confirm-dialog">
        <div class="confirm-msg">{{ confirmDialog.message }}</div>
        <div class="confirm-actions">
          <button class="btn-confirm-cancel" @click="confirmDialog.resolve(false);confirmDialog.show=false">取消</button>
          <button class="btn-confirm-ok" @click="confirmDialog.resolve(true);confirmDialog.show=false">确认</button>
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
import KnowledgePanel from './components/KnowledgePanel.vue'
import WeatherCard from './components/WeatherCard.vue'

const DEFAULT_AVATAR = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="%234e89ae" stroke-width="1.5"%3E%3Cpath d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"%3E%3C/path%3E%3Ccircle cx="12" cy="7" r="4"%3E%3C/circle%3E%3C/svg%3E'

export default {
  components: { TodoList, NoteList, CountdownList, ReminderList, MemoryPanel, SearchPanel, ChatManagePanel, RAGPanel, MigratePanel, HistoryPanel, KnowledgePanel, WeatherCard },
  data() {
    return {
      showTodoModal: false, showNoteModal: false, showCountdownModal: false, showReminderModal: false, showHistoryPanel: false, showSettingsModal: false,
      currentTheme: 'dark', messages: [], inputText: '', ws: null, isStreaming: false, wsReady: false,
      pendingReply: '', schedId: null, _currentReplyLen: 0,
      wsReconnectAttempts: 0, _reconnectTimer: null, userScrolledUp: false, lastScrollTop: 0,
      floatingDate: '', reminderPopups: [], reminderCount: 0,
      chatFontSize: 14, chatBgImage: '', saveError: '', loadError: '', showContextMenu: false, ctxMenuX: 0, ctxMenuY: 0, ctxTargetMsg: null, quoteMsg: null, showEmojiPicker: false,
      kaomojis: ['(￣▽￣)','(´･_･`)','(>_<)','(╥﹏╥)','(*¯︶¯*)','(╯‵□′)╯','(=・ω・=)','(・∀・)'],
      apiKeyLocal: '', themeLocal: 'dark', amapKeyLocal: '', enableSearchLocal: true,
      aiNameLocal: '夕语', userNameLocal: '', toneLocal: '冷静', lengthLocal: '短', recallLocal: '从不', customPromptLocal: '',
      colors: { primary: '#e8929b', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#3d2b3a', aiBubble: '#251e25' },
      totalMessages: 0, conversationDays: 0, userAvatarUrl: DEFAULT_AVATAR, assistantAvatarUrl: DEFAULT_AVATAR,
      aiAvatarUrl: '', userAvatarUrlInput: '',
      provinces: [], cities: [], selectedProvince: '', selectedCity: '', ipCity: '', ipCityShort: '',
      presets: {}, newPresetName: '', nextAfterId: null, loadingMore: false, apiKeySaved: false, promptSaved: false, apiConfigSaved: false,
      apiProviderLocal: 'deepseek', apiBaseUrlLocal: 'https://api.deepseek.com/v1', apiModelLocal: 'deepseek-chat',
      availableModels: [], loadingModels: false,
      testing: { ds: false, dsStatus: '', dsMsg: '', wt: false, wtStatus: '', wtMsg: '', se: false, seStatus: '', seMsg: '', ip: false, ipStatus: '', ipMsg: '' },
      settingsTab: 'api', locating: false,
      isRecording: false, mediaRecorder: null, audioChunks: [], sidebarCollapsed: true,
      confirmDialog: { show: false, message: '', resolve: null },
      relationship: { affection: 30, trust: 50, ai_emotion: 'neutral', ai_emotion_label: '平静', ai_emotion_description: '正常状态' },
      emotionTrend: [],
      useSystemNotification: false, notificationStyle: 'warm', useWeatherCare: true, showTrayNotification: true,
      settingsTabs: [
        { id: 'api', icon: 'api', label: 'API' },
        { id: 'role', icon: 'role', label: '角色' },
        { id: 'voice', icon: 'voice', label: '通知' },
        { id: 'appearance', icon: 'appr', label: '外观' },
        { id: 'data', icon: 'data', label: '数据' }
      ]
    }
  },
  provide() { return { showConfirm: this.showConfirm } },
  computed: {
    colorVariables() { let bg = 'none'; if (this.chatBgImage && /^https?:\/\/[^\s'"()]+\.(jpg|jpeg|png|webp|gif)(\?[^\s'"()]*)?$/i.test(this.chatBgImage)) { bg = `url("${this.chatBgImage}")` }; return { '--p': this.colors.primary, '--bg': this.colors.bg, '--sb': this.colors.sidebarBg, '--cb': this.colors.chatBg, '--ub': this.colors.userBubble, '--ab': this.colors.aiBubble, '--chat-bg-img': bg } },
    locationText() { const c = this.ipCityShort; if (c && c.length > 0 && c !== '[]' && c !== '无法获取定位') return c; return '无法获取定位' },
    modalOpen() { return this.showSettingsModal || this.showTodoModal || this.showNoteModal || this.showCountdownModal || this.showReminderModal || this.showHistoryPanel },
    timeGreeting() { const h = new Date().getHours(); const name = this.userNameLocal || ''; const greet = h < 6 ? '夜深了' : h < 9 ? '早上好' : h < 12 ? '上午好' : h < 14 ? '中午好' : h < 18 ? '下午好' : h < 22 ? '晚上好' : '夜深了'; return name ? greet + '，' + name : greet },
    chatSuggestions() { return ['今天天气怎么样', '帮我记个待办', '陪我聊聊天'] },
    colorFields() { return [
      { key: 'primary', label: '主色调', configKey: 'primary_color' },
      { key: 'bg', label: '背景', configKey: 'bg_color' },
      { key: 'sidebarBg', label: '侧边栏', configKey: 'sidebar_bg' },
      { key: 'chatBg', label: '聊天区', configKey: 'chat_bg' },
      { key: 'userBubble', label: '用户气泡', configKey: 'user_bubble' },
      { key: 'aiBubble', label: 'AI气泡', configKey: 'ai_bubble' }
    ]}
  },
  async mounted() { this.loadTheme(); await this.loadAllSettings(); this.loadAvatars(); this.loadHistory(); this.connectWebSocket(); this.loadIpLocation(); this.loadRelationship(); this.loadEmotionTrend(); this._locationTimer = setInterval(() => { if (document.visibilityState === 'visible') this.loadIpLocation() }, 600000); if (Notification.permission === 'default') Notification.requestPermission(); this._keydownHandler = (e) => { if (e.key === 'Escape') { this.showContextMenu = false; this.showEmojiPicker = false; this.showSettingsModal = false; this.showTodoModal = false; this.showNoteModal = false; this.showCountdownModal = false; this.showReminderModal = false; this.showHistoryPanel = false } }; document.addEventListener('keydown', this._keydownHandler); this._wheelHandler = (e) => { if (e.ctrlKey) { e.preventDefault(); this.adjustFontSize(e.deltaY < 0 ? 1 : -1) } }; document.addEventListener('wheel', this._wheelHandler, { passive: false }); this.$nextTick(() => { const el = this.$refs.messagesContainer; if (el) el.addEventListener('scroll', () => { const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
this.lastScrollTop = el.scrollTop
this.userScrolledUp = distFromBottom > 250; const seps = el.querySelectorAll('.date-sep'); let visible = ''; for (const s of seps) { if (s.getBoundingClientRect().top > el.getBoundingClientRect().top + 20) break; visible = s.textContent }; this.floatingDate = visible }) }) },
  beforeUnmount() { if (this.ws) this.ws.close(); if (this._locationTimer) clearInterval(this._locationTimer); if (this._reconnectTimer) clearTimeout(this._reconnectTimer); if (this._keydownHandler) document.removeEventListener('keydown', this._keydownHandler); if (this._wheelHandler) document.removeEventListener('wheel', this._wheelHandler) },
  methods: {
    async loadTheme() {
      try { const res = await api.get('/settings/'); this.themeLocal = res.data.theme || 'dark'; this.currentTheme = this.themeLocal; document.documentElement.setAttribute('data-theme', this.currentTheme) } catch (err) {}
    },
    async loadAllSettings() {
      try { const res = await api.get('/settings/'); this.themeLocal = res.data.theme || 'dark'; this.currentTheme = this.themeLocal; document.documentElement.setAttribute('data-theme', this.currentTheme); this.enableSearchLocal = res.data.enable_web_search !== false; this.aiNameLocal = res.data.ai_name || '夕语'; this.userNameLocal = res.data.user_name || ''; this.toneLocal = res.data.personality_tone || '冷静'; this.lengthLocal = res.data.length_level || '短'; this.recallLocal = res.data.recall_past || '从不'; this.customPromptLocal = res.data.custom_system_prompt || ''; this.chatBgImage = res.data.chat_bg_image || ''; this.chatFontSize = res.data.chat_font_size || 14; this.apiBaseUrlLocal = res.data.api_base_url || 'https://api.deepseek.com/v1'; this.apiModelLocal = res.data.api_model || 'deepseek-chat';
      if (res.data.precise_city) { this.ipCityShort = res.data.precise_city; this.ipCity = res.data.precise_city }
      if (res.data.use_system_notification !== undefined) this.useSystemNotification = res.data.use_system_notification
      if (res.data.notification_style) this.notificationStyle = res.data.notification_style
      if (res.data.use_weather_care !== undefined) this.useWeatherCare = res.data.use_weather_care
      if (res.data.show_tray_notification !== undefined) this.showTrayNotification = res.data.show_tray_notification
      this.colors = { primary: res.data.primary_color || '#e8929b', bg: res.data.bg_color || '#1a1418', sidebarBg: res.data.sidebar_bg || '#221a1f', chatBg: res.data.chat_bg || '#1a1418', userBubble: res.data.user_bubble || '#3d2b3a', aiBubble: res.data.ai_bubble || '#251e25' } } catch (err) { console.error(err) }
    },
    async updateGlobalConfig(key, value) { try { await api.post('/settings/', { key, value }); this.saveError = ''; if (key === 'theme') { this.currentTheme = value; document.documentElement.setAttribute('data-theme', value) } } catch (err) { this.saveError = '保存失败: ' + key; setTimeout(() => { this.saveError = '' }, 3000); console.error(err) } },
    async saveApiKey() { await this.updateGlobalConfig('api_key', this.apiKeyLocal); this.apiKeySaved = true; setTimeout(() => { this.apiKeySaved = false }, 2000) },
    onProviderChange() { const p = { deepseek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' }, qwen: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' }, moonshot: { url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' }, zhipu: { url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' }, openai: { url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' }, custom: { url: '', model: '' } }[this.apiProviderLocal]; if (p) { this.apiBaseUrlLocal = p.url; this.apiModelLocal = p.model; this.availableModels = [] } },
    async saveApiConfig() { await api.post('/settings/', { key: 'api_base_url', value: this.apiBaseUrlLocal }); await api.post('/settings/', { key: 'api_model', value: this.apiModelLocal }); await this.updateGlobalConfig('api_key', this.apiKeyLocal); this.apiConfigSaved = true; setTimeout(() => { this.apiConfigSaved = false }, 2000); this.fetchModels() },
    async testApiConnection() { this.testing.ds = true; this.testing.dsStatus = ''; this.testing.dsMsg = ''; try { const res = await api.get('/test/deepseek'); this.testing.dsStatus = res.data.ok ? 'ok' : 'fail'; this.testing.dsMsg = res.data.message } catch (err) { this.testing.dsStatus = 'fail'; this.testing.dsMsg = '请求失败' } finally { this.testing.ds = false } },
    async saveTone() { await this.updateGlobalConfig('personality', { tone: this.toneLocal }) },
    async saveCustomPrompt() { await this.updateGlobalConfig('custom_system_prompt', this.customPromptLocal); this.promptSaved = true; setTimeout(() => { this.promptSaved = false }, 2000) },
    async loadRelationship() { try { const res = await api.get('/relationship/'); this.relationship = res.data } catch (err) { console.error(err) } },
    async loadEmotionTrend() { try { const res = await api.get('/emotion/trend?days=7'); this.emotionTrend = res.data.trend || [] } catch (err) { console.error(err) } },
    async fetchModels() {
      this.loadingModels = true
      try {
        const res = await api.get('/test/models')
        if (res.data.ok && res.data.models.length) {
          this.availableModels = res.data.models
          if (!this.availableModels.includes(this.apiModelLocal)) {
            this.apiModelLocal = this.availableModels[0]
          }
        } else {
          this.availableModels = []
        }
      } catch (err) {
        this.availableModels = []
      } finally {
        this.loadingModels = false
      }
    },
    async loadAvatars() { try { const userRes = await api.get('/avatar/user'); if (userRes.data.url) this.userAvatarUrl = `${BASE_URL}${userRes.data.url}?t=${Date.now()}`; const assistantRes = await api.get('/avatar/assistant'); if (assistantRes.data.url) this.assistantAvatarUrl = `${BASE_URL}${assistantRes.data.url}?t=${Date.now()}` } catch (err) { console.error(err) } },
    async uploadAvatar(role, event) {
      const file = event.target.files[0]; if (!file) return
      const form = new FormData(); form.append('file', file, file.name)
      try {
        const res = await api.post(`/avatar/upload/${role}`, form)
        if (res.data.url) {
          const url = `${BASE_URL}${res.data.url}?t=${Date.now()}`
          if (role === 'user') this.userAvatarUrl = url
          else this.assistantAvatarUrl = url
        }
      } catch (err) { alert('上传失败') }
    },
    async uploadAvatarByUrl(role) {
      const url = role === 'user' ? this.userAvatarUrlInput : this.aiAvatarUrl
      if (!url) return
      try {
        const res = await api.post(`/avatar/upload-url/${role}`, { url })
        if (res.data.url) {
          const avatarUrl = `${BASE_URL}${res.data.url}?t=${Date.now()}`
          if (role === 'user') { this.userAvatarUrl = avatarUrl; this.userAvatarUrlInput = '' }
          else { this.assistantAvatarUrl = avatarUrl; this.aiAvatarUrl = '' }
        }
      } catch (err) { alert('导入失败: ' + (err.response?.data?.detail || err.message)) }
    },
    async loadProvinces() { try { const res = await api.get('/location/provinces'); this.provinces = res.data } catch (err) { console.error(err) } },
    async onProvinceChange() { if (!this.selectedProvince) return; try { const res = await api.get(`/location/cities/${this.selectedProvince}`); this.cities = res.data; this.selectedCity = '' } catch (err) { console.error(err) } },
    async savePreciseCity() { if (!this.selectedCity) { alert('请选择省份和城市'); return } const cityObj = this.cities.find(c => c.adcode === this.selectedCity); await this.updateGlobalConfig('precise_city', cityObj ? cityObj.name : this.selectedCity); alert('已保存') },
    async loadIpLocation() {
      // 1. 已有精确城市则跳过
      if (this.ipCityShort && this.ipCityShort.length > 1 && this.ipCityShort !== '无法获取定位') return

      // 2. 检查 localStorage 记住的定位权限
      const locationGranted = localStorage.getItem('location_granted') === 'true'
      const locationDenied = localStorage.getItem('location_denied') === 'true'

      // 3. 用户授权过 GPS，直接用（不弹框）
      if (locationGranted && navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 })
          })
          const res = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude })
          if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = res.data.detail || res.data.city; this.updateGlobalConfig('precise_city', res.data.city); return }
        } catch(e) { /* GPS 失败，继续 IP 定位 */ }
      }

      // 4. 用户拒绝过或未授权，直接 IP 定位
      if (locationDenied || !navigator.geolocation) {
        try {
          const res = await api.get('/location/ip')
          if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = `IP: ${res.data.province||''} ${res.data.city}`; this.updateGlobalConfig('precise_city', res.data.city); return }
        } catch(e) {}
        this.ipCity = ''; this.ipCityShort = '无法获取定位'
        return
      }

      // 5. 首次使用，询问 GPS 权限
      if (navigator.geolocation) {
        try {
          const pos = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 })
          })
          localStorage.setItem('location_granted', 'true')
          const res = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude })
          if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = res.data.detail || res.data.city; this.updateGlobalConfig('precise_city', res.data.city); return }
        } catch(e) {
          localStorage.setItem('location_denied', 'true')
        }
      }

      // 6. fallback: IP 定位
      try {
        const res = await api.get('/location/ip')
        if (res.data.city) { this.ipCityShort = res.data.city; this.ipCity = `IP: ${res.data.province||''} ${res.data.city}`; this.updateGlobalConfig('precise_city', res.data.city); return }
      } catch(e) {}
      this.ipCity = ''; this.ipCityShort = '无法获取定位'
    },
    resetLocationPermission() {
      localStorage.removeItem('location_granted')
      localStorage.removeItem('location_denied')
      this.ipCityShort = ''
      this.ipCity = ''
      this.loadIpLocation()
    },
    async loadPresets() { try { const res = await api.get('/settings/presets'); this.presets = res.data } catch (err) { console.error(err) } },
    async savePreset() { if (!this.newPresetName) return; const currentFullSettings = { api_key: this.apiKeyLocal, theme: this.themeLocal, primary_color: this.colors.primary, bg_color: this.colors.bg, sidebar_bg: this.colors.sidebarBg, chat_bg: this.colors.chatBg, user_bubble: this.colors.userBubble, ai_bubble: this.colors.aiBubble, amap_key: this.amapKeyLocal, enable_web_search: this.enableSearchLocal }; try { await api.post('/settings/presets', { name: this.newPresetName, data: currentFullSettings }); await this.loadPresets(); this.newPresetName = ''; alert('预设已保存') } catch (err) { console.error(err) } },
    async loadPreset(name) { try { const preset = this.presets[name]; for (const [key, value] of Object.entries(preset)) { await this.updateGlobalConfig(key, value) } await this.loadAllSettings(); alert('预设已加载') } catch (err) { console.error(err) } },
    async deletePreset(name) { if (!await this.showConfirm(`删除预设 "${name}"？`)) return; try { await api.delete(`/settings/presets/${name}`); await this.loadPresets() } catch (err) { console.error(err) } },
    formatTime(ts) { if (!ts) return ''; try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } catch { return '' } },
    dateLabel(ts) { if (!ts) return ''; try { const d = new Date(ts); if (isNaN(d.getTime())) return ''; const today = new Date(); if (d.toDateString() === today.toDateString()) return '今天'; const y = new Date(today); y.setDate(y.getDate()-1); if (d.toDateString() === y.toDateString()) return '昨天'; return d.toLocaleDateString('zh-CN', { month:'long', day:'numeric' }) } catch { return '' } },
    safeLinkify(text) { if (!text) return ''; const escaped = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); return escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>') },
    openContextMenu(e, msg) { this.ctxTargetMsg = msg; this.ctxMenuX = e.clientX; this.ctxMenuY = e.clientY; this.showContextMenu = true; setTimeout(() => { document.addEventListener('click', () => { this.showContextMenu = false }, { once: true }) }) },
    copyMessage(msg) { navigator.clipboard.writeText(msg.content).catch(() => {}); this.showContextMenu = false },
    quoteMessage(msg) { this.quoteMsg = msg; this.showContextMenu = false; this.$nextTick(() => this.$refs.inputEl?.focus()) },
    async deleteMessage(msg) { if (!msg.id) return; if (!await this.showConfirm('删除这条消息？')) return; try { await api.delete(`/chat/manage/message/${msg.id}`); await this.loadHistory(); this.showContextMenu = false } catch (err) { console.error('删除失败', err) } },
    notifyReminder(data) { if (Notification.permission === 'granted') { new Notification(`${data.level_name}提醒`, { body: `${data.content}\n截止 ${data.target_time}`, icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🔔</text></svg>' }) } },
    generateWarmMessage(data) {
      const content = data.content
      const level = data.level
      const style = this.notificationStyle
      const hour = new Date().getHours()
      if (hour >= 22 || hour < 8) {
        if (level < 7) return null
      }
      const categoryKeywords = { work: ['报告','会议','项目','客户','deadline','交付','汇报','工作','上班','加班'], health: ['吃药','体检','运动','喝水','休息','睡觉','锻炼','看病','复查'], study: ['考试','复习','作业','论文','学习','上课','培训'], personal: ['买','取','寄','约','聚会','生日','快递','购物','做饭','打扫'] }
      let category = 'general'
      for (const [cat, keywords] of Object.entries(categoryKeywords)) {
        if (keywords.some(kw => content.includes(kw))) { category = cat; break }
      }
      const urgency = level >= 6 ? 'high' : level >= 4 ? 'medium' : 'low'
      const templates = {
        warm: {
          work: { low: ['{c}，有空处理一下就好', '{c}，不着急，安排一下'], medium: ['{c}，时间快到了呢', '{c}，差不多该准备了'], high: ['{c}，不能再拖了哦', '{c}，赶紧处理一下吧'] },
          health: { low: ['{c}，注意身体哦', '{c}，别太累了'], medium: ['{c}，该休息一下了', '{c}，身体最重要'], high: ['{c}，必须马上处理！', '{c}，健康不能等！'] },
          study: { low: ['{c}，有空准备一下', '{c}，不急，慢慢来'], medium: ['{c}，该开始准备了', '{c}，时间不多了哦'], high: ['{c}，不能再拖了！', '{c}，赶紧复习！'] },
          personal: { low: ['{c}，有空的话记得一下', '{c}，不着急～'], medium: ['{c}，别忘了哦', '{c}，提醒你一下'], high: ['{c}，赶紧去！', '{c}，不能再等了！'] },
          general: { low: ['{c}，有空处理一下', '{c}，记得哦'], medium: ['{c}，该处理了', '{c}，提醒你一下'], high: ['{c}，赶紧处理！', '{c}，不能再拖了！'] }
        },
        casual: {
          work: { low: ['{c}，记一下', '{c}，有空搞'], medium: ['{c}，该搞了', '{c}，快到了'], high: ['{c}！赶紧！', '{c}！不能再拖！'] },
          health: { low: ['{c}！', '{c}，注意！'], medium: ['{c}！该了！', '{c}！必须！'], high: ['{c}！！！', '{c}！立刻！'] },
          study: { low: ['{c}，加油', '{c}，慢慢来'], medium: ['{c}！冲！', '{c}！加油！'], high: ['{c}！！！', '{c}！拼了！'] },
          personal: { low: ['{c}，顺便', '{c}，有空搞'], medium: ['{c}！别忘！', '{c}！该了！'], high: ['{c}！赶紧！', '{c}！快！'] },
          general: { low: ['{c}，记一下', '{c}，有空搞'], medium: ['{c}！该了！', '{c}！别忘！'], high: ['{c}！赶紧！', '{c}！快！'] }
        },
        professional: {
          work: { low: ['提醒：{c}', '待办：{c}'], medium: ['提醒：{c}（即将到期）', '待办：{c}（需处理）'], high: ['紧急：{c}', '重要：{c}（立即处理）'] },
          health: { low: ['健康提醒：{c}', '身体提醒：{c}'], medium: ['健康提醒：{c}（请及时）', '身体提醒：{c}（重要）'], high: ['紧急健康：{c}', '健康警告：{c}（立即处理）'] },
          study: { low: ['学习提醒：{c}', '学业：{c}'], medium: ['学习提醒：{c}（即将截止）', '学业：{c}（需准备）'], high: ['紧急学业：{c}', '学业警告：{c}（立即处理）'] },
          personal: { low: ['个人提醒：{c}', '待办：{c}'], medium: ['个人提醒：{c}（别忘了）', '待办：{c}（该处理了）'], high: ['紧急个人：{c}', '个人警告：{c}（立即处理）'] },
          general: { low: ['提醒：{c}', '待办：{c}'], medium: ['提醒：{c}（即将到期）', '待办：{c}（需处理）'], high: ['紧急：{c}', '重要：{c}（立即处理）'] }
        }
      }
      const styleTemplates = templates[style] || templates.warm
      const catTemplates = styleTemplates[category] || styleTemplates.general
      const urgTemplates = catTemplates[urgency] || catTemplates.medium
      const template = urgTemplates[Math.floor(Math.random() * urgTemplates.length)]
      return template.replace('{c}', content)
    },
    sendSystemNotification(data) {
      const message = this.generateWarmMessage(data)
      if (!message) return
      if (Notification.permission === 'granted') {
        const notification = new Notification(data.level_name, {
          body: message,
          icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🔔</text></svg>',
          silent: false,
          requireInteraction: false,
        })
        setTimeout(() => notification.close(), 5000)
      }
    },
    adjustFontSize(delta) { this.chatFontSize = Math.min(20, Math.max(10, this.chatFontSize + delta)); document.querySelector('.msg-list').style.fontSize = this.chatFontSize + 'px'; this.updateGlobalConfig('chat_font_size', this.chatFontSize) },
    async exportChat() { try { const res = await api.get('/export/chat?format=txt'); const blob = new Blob([res.data.content], { type: 'text/plain' }); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = res.data.filename; a.click() } catch (err) { alert('导出失败') } },
    setTheme(v) { this.themeLocal = v; this.currentTheme = v; document.documentElement.setAttribute('data-theme', v); const metaColors = { dark: '#0d1117', light: '#f5f6fa', sakura: '#1a1418', vesper: '#12101a' }; const meta = document.getElementById('theme-color-meta'); if (meta) meta.content = metaColors[v] || '#0d1117'; api.post('/api/window-theme', { dark: v !== 'light' }).catch(()=>{}); this.updateGlobalConfig('theme', v) },
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
      const t = this.currentTheme
      const presets = {
        sakura: {
          dark:    { primary: '#e8929b', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#3d2b3a', aiBubble: '#251e25' },
          light:   { primary: '#d4727f', bg: '#fff5f6', sidebarBg: '#ffe8eb', chatBg: '#fff5f6', userBubble: '#e8929b', aiBubble: '#ffffff' },
          sakura:  { primary: '#e8929b', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#c76e7a', aiBubble: '#251e25' },
          vesper:  { primary: '#d4a0aa', bg: '#12101a', sidebarBg: '#1a1726', chatBg: '#12101a', userBubble: '#6b4f5a', aiBubble: '#1e1b2e' }
        },
        default: {
          dark:    { primary: '#5390d4', bg: '#0d1117', sidebarBg: '#161b22', chatBg: '#0d1117', userBubble: '#2b5278', aiBubble: '#1e2632' },
          light:   { primary: '#2b6cb0', bg: '#f5f6fa', sidebarBg: '#e8e9ed', chatBg: '#f5f6fa', userBubble: '#2b6cb0', aiBubble: '#ffffff' },
          sakura:  { primary: '#7a9ec4', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#3d4a5a', aiBubble: '#251e25' },
          vesper:  { primary: '#6b8fa3', bg: '#12101a', sidebarBg: '#1a1726', chatBg: '#12101a', userBubble: '#3a5060', aiBubble: '#1e1b2e' }
        },
        wechat: {
          dark:    { primary: '#07C160', bg: '#111111', sidebarBg: '#1a1a1a', chatBg: '#111111', userBubble: '#054', aiBubble: '#1e1e1e' },
          light:   { primary: '#07C160', bg: '#f5f5f5', sidebarBg: '#e8e8e8', chatBg: '#f5f5f5', userBubble: '#07C160', aiBubble: '#ffffff' },
          sakura:  { primary: '#07C160', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#1a4a2a', aiBubble: '#251e25' },
          vesper:  { primary: '#07C160', bg: '#12101a', sidebarBg: '#1a1726', chatBg: '#12101a', userBubble: '#1a4a2a', aiBubble: '#1e1b2e' }
        },
        teal: {
          dark:    { primary: '#14b8a6', bg: '#0f1724', sidebarBg: '#151e2d', chatBg: '#0f1724', userBubble: '#0f766e', aiBubble: '#1a2332' },
          light:   { primary: '#0d9488', bg: '#f0fdfa', sidebarBg: '#e0f5f0', chatBg: '#f0fdfa', userBubble: '#14b8a6', aiBubble: '#ffffff' },
          sakura:  { primary: '#14b8a6', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#1a4a44', aiBubble: '#251e25' },
          vesper:  { primary: '#14b8a6', bg: '#12101a', sidebarBg: '#1a1726', chatBg: '#12101a', userBubble: '#1a4a44', aiBubble: '#1e1b2e' }
        },
        warm: {
          dark:    { primary: '#f59e0b', bg: '#1a1410', sidebarBg: '#221c14', chatBg: '#1a1410', userBubble: '#78350f', aiBubble: '#231f18' },
          light:   { primary: '#d97706', bg: '#fffbeb', sidebarBg: '#fef3c7', chatBg: '#fffbeb', userBubble: '#f59e0b', aiBubble: '#ffffff' },
          sakura:  { primary: '#f59e0b', bg: '#1a1418', sidebarBg: '#221a1f', chatBg: '#1a1418', userBubble: '#5a3a1a', aiBubble: '#251e25' },
          vesper:  { primary: '#f59e0b', bg: '#12101a', sidebarBg: '#1a1726', chatBg: '#12101a', userBubble: '#5a3a1a', aiBubble: '#1e1b2e' }
        }
      }
      const p = (presets[name] && presets[name][t]) || (presets[name] && presets[name].dark) || presets.default.dark
      Object.keys(p).forEach(k => { this.colors[k] = p[k]; this.updateGlobalConfig(this.colorFields.find(f=>f.key===k)?.configKey || k+'_color', p[k]) })
    },
    async loadHistory() { try { const res = await api.get(`/chat/history/?limit=50`); this.messages = res.data.messages.map(m => { if (m.role === 'assistant' && m.content && m.content.startsWith('__WEATHER_CARD__')) { try { return { ...m, isWeather: true, weatherData: JSON.parse(m.content.slice(16)), content: '__WEATHER_CARD__' } } catch(e) { return m } } return m }); this.nextAfterId = res.data.next_after_id; const countRes = await api.get(`/chat/history/count`); this.totalMessages = countRes.data.count; if (this.messages.length) { this.conversationDays = Math.ceil((new Date() - new Date(this.messages[0].timestamp)) / 86400000) } this.scrollToBottom(); this.loadError = '' } catch (err) { this.loadError = '加载失败，点击重试'; console.error(err) } },
    async onDataChanged() { await this.loadHistory(); if (this.messages.length === 0) { this.nextAfterId = null } },
    async loadMoreHistory() { if (this.loadingMore || !this.nextAfterId) return; this.loadingMore = true; try { const res = await api.get(`/chat/history/?limit=50&after_id=${this.nextAfterId}`); if (res.data.messages.length) { const mapped = res.data.messages.map(m => { if (m.role === 'assistant' && m.content && m.content.startsWith('__WEATHER_CARD__')) { try { return { ...m, isWeather: true, weatherData: JSON.parse(m.content.slice(16)), content: '__WEATHER_CARD__' } } catch(e) { return m } } return m }); this.messages = [...mapped, ...this.messages]; this.nextAfterId = res.data.next_after_id } else { this.nextAfterId = null } } catch (err) { console.error(err) } finally { this.loadingMore = false } },
    connectWebSocket() {
      this.ws = new WebSocket(`${WS_URL}/ws/chat`)
      this.ws.onopen = () => { this.wsReady = true; this.wsReconnectAttempts = 0 }
      this.ws.onmessage = (event) => {
        let data; try { data = JSON.parse(event.data) } catch (e) { return }
        if (data.type === 'token') {
          this.pendingReply += data.content
          this._currentReplyLen = (this._currentReplyLen || 0) + data.content.length
          if (!this.schedId) this.schedulePop()
        } else if (data.type === 'done') {
          this.stopTypewriter()
        } else if (data.type === 'greeting') { this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString() }); this.totalMessages++; this.scrollToBottom() }
        else if (data.type === 'reminder_count') {
          this.reminderCount = data.count || 0
        }
        else if (data.type === 'proactive') {
          this.messages.push({ role: 'assistant', content: data.content, timestamp: new Date().toISOString(), isProactive: true })
          this.totalMessages++
          this.scrollToBottom()
        }
        else if (data.type === 'weather') {
          this.messages.push({ role: 'assistant', content: '__WEATHER_CARD__', weatherData: data.data, timestamp: new Date().toISOString(), isWeather: true })
          this.totalMessages++
          this.scrollToBottom()
        }
        else if (data.type === 'reroll_start') {
          this.pendingReply = ''
          this.isStreaming = true
          this._currentReplyLen = 0
        }
        else if (data.type === 'reminder') {
          const d = data.data
          if (!d.id || this.reminderPopups.some(p => p.id === d.id)) return
          d._id = crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2, 10))
          if (this.useSystemNotification) {
            this.sendSystemNotification(d)
          } else {
            this.reminderPopups.push(d)
            this.notifyReminder(d)
            if (d.level < 6) { setTimeout(() => { this.dismissReminder(d._id) }, 8000) }
          }
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
      this.totalMessages++; this.inputText = ''; this.scrollToBottom(); this.isStreaming = true; this._currentReplyLen = 0
      if (this._streamTimeout) clearTimeout(this._streamTimeout)
      this._streamTimeout = setTimeout(() => { if (this.isStreaming) { this.stopTypewriter(); this.messages.push({ role: 'assistant', content: '请求超时，请重试', timestamp: new Date().toISOString() }) } }, 60000)
      this.ws.send(JSON.stringify({ message: userMsg, history: this.messages.slice(-35).map(m => ({ role: m.role, content: m.content })) }))
      this.$nextTick(() => { const el = this.$refs.inputEl; if (el) { el.style.height = 'auto'; el.focus() } })
    },
    autoResizeInput() {
      const el = this.$refs.inputEl; if (!el) return
      el.style.height = ''  // 重置高度确保内容变少时能缩小
      const target = Math.min(el.scrollHeight, 120)
      if (Math.abs(el.offsetHeight - target) > 2) {
        el.style.height = target + 'px'
      }
    },
    openTodoModal() { this.showTodoModal = true }, closeTodoModal() { this.showTodoModal = false },
    openNoteModal() { this.showNoteModal = true }, closeNoteModal() { this.showNoteModal = false },
    openCountdownModal() { this.showCountdownModal = true }, closeCountdownModal() { this.showCountdownModal = false },
    openReminderModal() { this.showReminderModal = true }, closeReminderModal() { this.showReminderModal = false },
    openSettings() { this.showSettingsModal = true; this.loadIpLocation(); if (!this.provinces.length) this.loadProvinces(); if (!Object.keys(this.presets).length) this.loadPresets() },
    closeSettingsModal() { this.showSettingsModal = false },
    stopTypewriter() {
      this.isStreaming = false
      if (this._streamTimeout) { clearTimeout(this._streamTimeout); this._streamTimeout = null }
      this._currentReplyLen = 0
      // 始终继续分句，不整段甩出
      if (this.pendingReply.trim() && !this.schedId) {
        this.schedulePop()
      }
    },
    findNextSentence(text) {
      const SENTENCE_END = /[。！？!?…～]/; const GREEDY_END = /[…～]/
      let state = 0, buf = '', parenBuf = ''
      for (let i = 0; i < text.length; i++) {
        const ch = text[i]
        if (state === 0) {
          if (ch === '（' || ch === '(') {
            if (buf.trim()) return [buf.trim(), text.slice(i)]
            state = 1; parenBuf = ch; continue
          }
          if (ch === '\n' && text[i+1] === '\n') {
            if (buf.trim()) return [buf.trim(), text.slice(i+2)]
            i++; continue
          }
          buf += ch
          if (SENTENCE_END.test(ch)) {
            let end = i + 1
            while (end < text.length && GREEDY_END.test(text[end])) { buf += text[end]; end++ }
            return [buf.trim(), text.slice(end)]
          }
        } else if (state === 1) {
          parenBuf += ch
          if (ch === '）' || ch === ')') {
            state = 2
            if (i+1 < text.length && text[i+1] === '\n') {
              const s = parenBuf.trim()
              if (s.length >= 2) return [s, text.slice(i+1)]
            }
          }
        } else if (state === 2) {
          if (ch === '（' || ch === '(') {
            const s = parenBuf.trim()
            if (s.length >= 2) return [s, text.slice(i)]
            parenBuf = ch; state = 1; continue
          }
          if (ch === '\n' && text[i+1] === '\n') {
            const s = parenBuf.trim()
            if (s.length >= 2) return [s, text.slice(i+2)]
            parenBuf = ''; state = 0; i++; continue
          }
          if (ch === '\n') {
            const s = parenBuf.trim()
            if (s.length >= 2) return [s, text.slice(i+1)]
            parenBuf = ''; state = 0; continue
          }
          parenBuf += ch
          if (SENTENCE_END.test(ch)) {
            let end = i + 1
            while (end < text.length && GREEDY_END.test(text[end])) { parenBuf += text[end]; end++ }
            const s = parenBuf.trim()
            if (s.length >= 2) { parenBuf = ''; state = 0; return [s, text.slice(end)] }
          }
        }
      }
      return null
    },
    schedulePop() {
      if (this.schedId) return
      const pop = () => {
        this.schedId = null
        this.pendingReply = this.pendingReply.replace(/^[\s\n]+/, '')
        if (!this.pendingReply) return
        const result = this.findNextSentence(this.pendingReply)
        if (result) {
          const sentence = result[0]
          if (sentence.length >= 2) {
            this.messages.push({ role: 'assistant', content: sentence, timestamp: new Date().toISOString() }); this.totalMessages++
          }
          this.pendingReply = result[1] || ''
          this.scrollToBottom()
          const delay = Math.min(Math.max(300, 250 + sentence.length * 30), 2000)
          this.schedId = setTimeout(pop, delay)
        } else if (!this.isStreaming) {
          const remain = this.pendingReply.trim()
          if (remain) { this.messages.push({ role: 'assistant', content: remain, timestamp: new Date().toISOString() }); this.totalMessages++ }
          this.pendingReply = ''; this.scrollToBottom()
        } else {
          this.schedId = setTimeout(pop, 100)
        }
      }
      this.schedId = setTimeout(pop, 60)
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
    showConfirm(msg) { return new Promise(resolve => { this.confirmDialog = { show: true, message: msg, resolve } }) },
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
.reminder-badge { font-size: 11px; color: #e74c3c; font-weight: 600; cursor: default; }
.top-date { flex: 1; text-align: center; font-size: 12px; color: var(--p); font-weight: 500; }

.layout { display: flex; flex: 1; min-height: 0; overflow: hidden; }

/* ====== Sidebar ====== */
.sidebar { width: 200px; background: var(--sb); display: flex; flex-direction: column; border-right: 1px solid rgba(128,128,128,.1); transition: width .2s; overflow: hidden; }
.sidebar.collapsed { width: 48px; }
.sidebar.collapsed .nav-label { opacity: 0; width: 0; pointer-events: none; }
.sidebar.collapsed .nav-icons button { justify-content: center; padding: 10px 0; }
.nav-icons { display: flex; flex-direction: column; gap: 2px; padding: 8px; flex: 1; }
.nav-icons button { background: none; border: none; cursor: pointer; opacity: .5; transition: all .15s; padding: 8px 10px; border-radius: 6px; color: #8899aa; display: flex; align-items: center; gap: 10px; font-size: 13px; white-space: nowrap; width: 100%; }
.nav-icons button:hover { opacity: 1; color: #ecf0f1; background: rgba(255,255,255,.1); }
.nav-label { transition: opacity .15s; overflow: hidden; }
.nav-settings { background: none; border: none; cursor: pointer; opacity: .5; transition: all .15s; padding: 8px 10px; border-radius: 6px; color: #8899aa; display: flex; align-items: center; gap: 10px; font-size: 13px; }
.nav-icons + .nav-settings { margin-top: auto; }
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
.empty-chat { color: #7f8c8d; text-align: center; margin-top: 100px; font-size: 14px; }
.empty-greeting { font-size: 24px; color: var(--p); margin-bottom: 12px; font-weight: 300; letter-spacing: 2px; }
.empty-hint { font-size: 14px; color: #7f6b7a; margin-bottom: 24px; }
.empty-suggestions { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.suggestion-chip { padding: 6px 16px; background: rgba(255,255,255,.04); border-radius: 16px; font-size: 13px; color: #998; cursor: pointer; transition: all .15s; border: 1px solid rgba(255,255,255,.06); }
.suggestion-chip:hover { background: rgba(232,146,155,.12); color: var(--p); border-color: var(--p); }
.date-sep { text-align: center; font-size: 12px; color: #7f8c8d; padding: 6px 0; }
.date-sep::before, .date-sep::after { content: ''; display: inline-block; width: 40px; height: 1px; background: rgba(255,255,255,.1); vertical-align: middle; margin: 0 10px; }
.msg-bubble a { color: #6cb4ee; text-decoration: underline; }


/* 输入行 */
.input-row { display: flex; align-items: flex-end; gap: 6px; position: relative; }
.emoji-btn { background: none; border: none; font-size: 13px; color: #888; cursor: pointer; padding: 6px 8px; border-radius: 6px; transition: all .15s; font-family: inherit; }
.emoji-btn:hover { color: var(--p); background: rgba(255,255,255,.05); }
.kaomoji-picker { position: absolute; bottom: 100%; left: 0; display: flex; flex-direction: column; gap: 2px; padding: 6px; background: var(--bg); border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.4); z-index: 20; margin-bottom: 4px; min-width: 120px; }
.kaomoji-item { font-size: 13px; cursor: pointer; padding: 5px 10px; border-radius: 4px; transition: background .1s; white-space: nowrap; color: #ccc; font-family: inherit; }
.kaomoji-item:hover { background: rgba(255,255,255,.08); color: #fff; }
.quote-bar { padding: 6px 12px; background: rgba(255,255,255,.05); border-radius: 8px 8px 0 0; font-size: 12px; color: #8899aa; display: flex; justify-content: space-between; align-items: center; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.quote-bar button { background: none; border: none; color: #888; cursor: pointer; font-size: 14px; }
.quote-bar button:hover { color: #fff; }

/* 右键菜单 */
.context-menu { position: fixed; z-index: 2000; background: var(--bg); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,.6); overflow: hidden; min-width: 120px; }
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

.msg-avatar-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; flex-shrink: 0; }
.msg-name { font-size: 11px; color: #8899aa; white-space: nowrap; max-width: 60px; overflow: hidden; text-overflow: ellipsis; }
.msg-avatar { width: 26px; height: 26px; border-radius: 50%; }
.msg-body { max-width: calc(100% - 36px); }
.msg-bubble { padding: 9px 13px; border-radius: 16px; font-size: 14px; line-height: 1.6; word-break: break-word; white-space: pre-wrap; position: relative; transition: transform .15s, box-shadow .2s; animation: msgIn .35s ease-out; }
.msg-bubble:hover { transform: translateY(-1px); }
.msg.user .msg-bubble { background: var(--ub); color: #fff; border-bottom-right-radius: 4px; }
.msg.assistant .msg-bubble { background: var(--ab); color: #ecf0f1; border-bottom-left-radius: 4px; }
.msg.proactive .msg-bubble { opacity: 0.85; font-style: italic; border-left: 2px solid var(--p); }
.msg.user .msg-bubble::after { content: ''; position: absolute; bottom: 0; right: -6px; width: 0; height: 0; border-left: 6px solid var(--ub); border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
.msg.assistant .msg-bubble::after { content: ''; position: absolute; bottom: 0; left: -6px; width: 0; height: 0; border-right: 6px solid var(--ab); border-top: 6px solid transparent; border-bottom: 6px solid transparent; }
.weather-msg { padding: 4px 0; animation: msgIn .35s ease-out; }
@keyframes msgIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.msg-bubble.typing-dots { padding: 10px 18px; display: flex; gap: 5px; align-items: center; }
.dot-bounce { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--p); animation: dotBounce 1.2s infinite; }
.dot-bounce:nth-child(2) { animation-delay: .15s; }
.dot-bounce:nth-child(3) { animation-delay: .3s; }
@keyframes dotBounce { 0%,60%,100% { opacity: .2; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-6px); } }

.msg-time { font-size: 10px; color: #7f8c8d; margin-top: 3px; opacity: .6; }
.msg-bubble.typing-dots { animation: none; }
.msg.user .msg-time { text-align: right; }

/* ====== Input ====== */
.chat-input { display: flex; flex-direction: column; padding: 8px 16px 12px; background: var(--sb); border-top: 1px solid rgba(255,255,255,.05); }
.chat-input textarea { flex: 1; padding: 8px 14px; border-radius: 20px; background: var(--bg); color: #fff; border: 1px solid rgba(255,255,255,.08); outline: none; resize: none; font-size: 14px; font-family: inherit; line-height: 1.4; min-height: 36px; max-height: 120px; transition: height .12s ease; }
.chat-input textarea:focus { border-color: var(--p); }
.chat-input textarea::placeholder { color: #7f8c8d; }
.chat-input textarea:disabled { opacity: .5; }
.btn-send { padding: 10px 20px; background: var(--p); color: #fff; border: none; border-radius: 20px; cursor: pointer; font-size: 14px; font-weight: 600; transition: opacity .15s; }
.btn-send:hover:not(:disabled) { opacity: .85; }
.btn-send:disabled { opacity: .5; cursor: default; }

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
.modal { background: var(--bg); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
.modal.small { width: 420px; max-height: 80vh; }
.modal-hd { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid rgba(128,128,128,.1); }
.modal-hd h3 { margin: 0; color: #ecf0f1; font-size: 16px; }
.modal-hd button { background: none; border: none; color: #888; font-size: 20px; cursor: pointer; }
.modal-bd { flex: 1; overflow-y: auto; padding: 16px; }

/* ====== Confirm Dialog ====== */
.confirm-dialog { background: var(--bg); border-radius: 12px; padding: 24px; min-width: 320px; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,.5); }
.confirm-msg { color: #ecf0f1; font-size: 14px; margin-bottom: 20px; text-align: center; line-height: 1.6; }
.confirm-actions { display: flex; gap: 10px; justify-content: center; }
.btn-confirm-cancel { padding: 8px 24px; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); color: #999; border-radius: 8px; cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-confirm-cancel:hover { background: rgba(255,255,255,.1); color: #ccc; }
.btn-confirm-ok { padding: 8px 24px; background: var(--p); border: none; color: #fff; border-radius: 8px; cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-confirm-ok:hover { opacity: .85; }

/* ====== Settings ====== */
.settings-panel { position: fixed; width: 820px; height: 580px; background: var(--bg); border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 16px 48px rgba(0,0,0,.5); z-index: 1001; }
.settings-titlebar { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background: var(--sb); cursor: move; user-select: none; border-bottom: 1px solid rgba(128,128,128,.1); }
.settings-titlebar span { color: #ecf0f1; font-size: 14px; font-weight: 600; }
.settings-titlebar button { background: none; border: none; color: #888; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 4px; transition: color .15s; }
.settings-titlebar button:hover { background: rgba(128,128,128,.1); color: #fff; }
.settings-body { display: flex; flex: 1; overflow: hidden; }
.settings-nav { width: 120px; background: var(--sb); padding: 8px 0; display: flex; flex-direction: column; gap: 2px; border-right: 1px solid rgba(128,128,128,.1); }
.nav-item { display: flex; align-items: center; gap: 8px; padding: 8px 14px; cursor: pointer; font-size: 12px; color: #999; transition: all .15s; border-left: 2px solid transparent; }
.nav-item:hover { color: #ddd; background: rgba(255,255,255,.06); }
.nav-item.active { color: #fff; background: rgba(255,255,255,.06); border-left-color: var(--p); }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }
.nav-label { white-space: nowrap; }
.settings-content { flex: 1; overflow-y: auto; padding: 16px 20px; background: var(--bg); }
.tab-content { display: flex; flex-direction: column; gap: 10px; }

/* --- Cards --- */
.card { background: var(--ab); border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,.03); }
.card-title { padding: 9px 14px; font-size: 12px; font-weight: 500; color: #bdc3c7; background: rgba(128,128,128,.08); border-bottom: 1px solid rgba(255,255,255,.04); letter-spacing: .3px; }
.card-body { padding: 10px 14px; overflow: hidden; }
.card-grow { flex: 1; display: flex; flex-direction: column; }
.card-body-grow { flex: 1; display: flex; flex-direction: column; }
.switch-label { display: flex; align-items: center; gap: 8px; padding: 4px 0; color: #bdc3c7; font-size: 13px; cursor: pointer; }
.switch-label input[type="checkbox"] { accent-color: var(--p); }

/* --- Settings shared --- */
.api-row { display: flex; gap: 8px; align-items: center; }
.api-row input { flex: 1; }
.model-row { display: flex; gap: 6px; align-items: center; }
.model-select { flex: 1; padding: 8px 12px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.08); font-size: 13px; outline: none; box-sizing: border-box; }
.model-select:focus { border-color: var(--p); }
.model-input { flex: 1; padding: 8px 12px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.08); font-size: 13px; outline: none; box-sizing: border-box; }
.model-input:focus { border-color: var(--p); }
.saved-hint { color: #4caf50; font-size: 11px; margin-top: 6px; }
.prompt-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.loc-row { display: flex; gap: 6px; margin-top: 8px; }
.loc-row select { flex: 1; padding: 7px 10px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.06); font-size: 12px; outline: none; }
.loc-hint { font-size: 11px; color: #8899aa; margin-top: 6px; }
.btn-row { display: flex; gap: 8px; }
.preset-actions { display: flex; gap: 4px; }
.empty-hint { color: #7f8c8d; text-align: center; font-size: 12px; padding: 12px; }

/* --- Avatar section --- */
.avatar-section { display: flex; gap: 16px; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,.05); }
.avatar-section:last-of-type { border-bottom: none; }
.avatar-preview { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.avatar-img { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,.1); }
.avatar-label { font-size: 11px; color: #8899aa; }
.avatar-actions { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.url-row { display: flex; gap: 6px; }
.url-input { flex: 1; padding: 6px 10px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.08); font-size: 12px; outline: none; }
.url-input:focus { border-color: var(--p); }

/* --- Relationship bars --- */
.relationship-bars { display: flex; flex-direction: column; gap: 12px; }
.rel-item { display: flex; align-items: center; gap: 10px; }
.rel-label { width: 50px; font-size: 12px; color: #8899aa; flex-shrink: 0; }
.rel-bar { flex: 1; height: 8px; background: rgba(255,255,255,.08); border-radius: 4px; overflow: hidden; }
.rel-fill { height: 100%; border-radius: 4px; transition: width .3s ease; }
.rel-fill.affection { background: #e8929b; }
.rel-fill.trust { background: #5390d4; }
.rel-value { width: 30px; font-size: 12px; color: #bdc3c7; text-align: right; }
.ai-emotion-tag { font-size: 12px; color: var(--p); font-weight: 500; }
.ai-emotion-desc { font-size: 11px; color: #8899aa; }

/* --- Emotion chart --- */
.emotion-chart { display: flex; align-items: flex-end; gap: 8px; height: 80px; padding: 0 4px; }
.emotion-bar-group { display: flex; flex-direction: column; align-items: center; flex: 1; height: 100%; justify-content: flex-end; }
.emotion-bar { width: 100%; min-height: 2px; border-radius: 2px 2px 0 0; transition: height .3s ease; }
.emotion-date { font-size: 10px; color: #8899aa; margin-top: 4px; }
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
.field input, .field select, .field textarea, .api-row input, .loc-row select { width: 100%; padding: 8px 12px; border-radius: 6px; background: #0f1923; color: #ddd; border: 1px solid rgba(255,255,255,.08); font-size: 13px; outline: none; resize: vertical; font-family: inherit; box-sizing: border-box; }
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
:root[data-theme="light"] .location { background: #00000008; color: #777; }
:root[data-theme="light"] .msg.assistant .msg-bubble { background: #fff; color: #333; border: 1px solid #e8e8ea; }
:root[data-theme="light"] .msg.user .msg-bubble { color: #fff; }
:root[data-theme="light"] .msg-time { color: #888; }
:root[data-theme="light"] .btn-more { color: #999; border-color: #ddd; }
:root[data-theme="light"] .sidebar-toggle { border-color: #ddd; color: #888; }
:root[data-theme="light"] .kaomoji-picker { background: #fff; box-shadow: 0 4px 16px rgba(0,0,0,.1); }
:root[data-theme="light"] .kaomoji-item { color: #555; }
:root[data-theme="light"] .kaomoji-item:hover { background: #f0f0f0; color: #222; }
:root[data-theme="light"] .top-bar { border-color: rgba(0,0,0,.06); }
:root[data-theme="light"] .settings-titlebar button { color: #999; }
:root[data-theme="light"] .settings-titlebar button:hover { background: rgba(0,0,0,.06); color: #333; }
:root[data-theme="light"] .settings-titlebar { border-color: #eee; }
:root[data-theme="light"] .settings-nav { border-color: #eee; }
:root[data-theme="light"] .field input, :root[data-theme="light"] .field select, :root[data-theme="light"] .field textarea,
:root[data-theme="light"] .api-row input, :root[data-theme="light"] .loc-row select { background: rgba(128,128,128,.08); color: #333; border-color: #e0e0e0; }
:root[data-theme="light"] .nav-item { color: #666; }
:root[data-theme="light"] .nav-item.active { color: #2b6cb0; background: rgba(43,108,176,.1); }
:root[data-theme="light"] .nav-icons button { color: #666; }
:root[data-theme="light"] .nav-icons button:hover { color: #333; background: rgba(0,0,0,.06); }
:root[data-theme="light"] .btn-s { background: rgba(128,128,128,.12); color: #555; }
:root[data-theme="light"] .btn-s:hover { background: rgba(128,128,128,.2); color: #222; }
:root[data-theme="light"] .btn-danger { background: rgba(231,76,60,.15) !important; color: #d63031 !important; }
:root[data-theme="light"] .btn-danger:hover { background: rgba(231,76,60,.25) !important; }

/* ====== 右侧提醒弹窗 ====== */
.reminder-popups { position: fixed; right: 16px; top: 60px; z-index: 900; pointer-events: none; max-height: calc(100vh - 100px); }
.reminder-popups-inner { display: flex; flex-direction: column; gap: 8px; pointer-events: auto; overflow-y: auto; max-height: calc(100vh - 100px); }
.reminder-popup { width: 280px; background: var(--bg); border-radius: 8px; display: flex; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,.4); pointer-events: auto; flex-shrink: 0; }
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
.slide-enter-active { transition: all .4s cubic-bezier(0.34, 1.56, 0.64, 1); }
.slide-leave-active { transition: all .25s ease-in; }
.slide-enter-from { opacity: 0; transform: translateX(30px) scale(.95); }
.slide-leave-to { opacity: 0; transform: translateX(30px) scale(.95); }

/* 紧急提醒脉冲 */
.level-7 .reminder-popup-bar { animation: pulse .6s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

/* 亮色模式提醒弹窗 */
:root[data-theme="light"] .reminder-popup { background: #fff; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
:root[data-theme="light"] .reminder-popup-text { color: #333; }
:root[data-theme="light"] .reminder-popup-time { color: #999; }

/* ═══ 樱花粉主题 ═══ */
:root[data-theme="sakura"] { --p: #e8929b; --bg: #1a1418; --sb: #221a1f; --cb: #1a1418; --ub: #c76e7a; --ab: #251e25; --pink: #e8929b; }
:root[data-theme="sakura"] .top-bar,
:root[data-theme="sakura"] .sidebar,
:root[data-theme="sakura"] .chat-top,
:root[data-theme="sakura"] .chat-input { background: #221a1f; border-color: #3d2b3a; }
:root[data-theme="sakura"] .chat { background: #1a1418; }
:root[data-theme="sakura"] .brand { color: #e8929b; }
:root[data-theme="sakura"] .status { background: #e74c3c22; color: #e8929b; }
:root[data-theme="sakura"] .status.online { background: #4caf5022; color: #a8d6a8; }
:root[data-theme="sakura"] .msg.assistant .msg-bubble { background: #251e25; color: #ecf0f1; }
:root[data-theme="sakura"] .msg.user .msg-bubble { background: #c76e7a; color: #fff; }
:root[data-theme="sakura"] .theme-btn { background: #2e1f28; color: #7f6b7a; }
:root[data-theme="sakura"] .theme-btn.active { background: #e8929b; color: #fff; }
:root[data-theme="sakura"] .nav-item.active { color: #e8929b; background: rgba(232,146,155,.12); }
:root[data-theme="sakura"] .reminder-popup { background: #221a1f; box-shadow: 0 8px 24px rgba(0,0,0,.4); }
:root[data-theme="sakura"] .settings-titlebar { border-color: #3d2b3a; }
:root[data-theme="sakura"] .settings-nav { border-color: #3d2b3a; }
:root[data-theme="sakura"] .nav-icons button { color: #8a7080; }
:root[data-theme="sakura"] .nav-icons button:hover { color: #e8929b; background: rgba(232,146,155,.08); }
:root[data-theme="sakura"] .sidebar-toggle { color: #8a7080; }
:root[data-theme="sakura"] .sidebar-toggle:hover { color: #e8929b; }
:root[data-theme="sakura"] .msg-time { color: #7a6575; }
:root[data-theme="sakura"] .location { color: #7a6575; }

/* ═══ 夕语主题（青紫 + 星光）═══ */
:root[data-theme="vesper"] { --p: #7c6e9a; --bg: #12101a; --sb: #1a1726; --cb: #12101a; --ub: #5a4f7a; --ab: #1e1b2e; --pink: #7c6e9a; }
:root[data-theme="vesper"] .top-bar,
:root[data-theme="vesper"] .sidebar,
:root[data-theme="vesper"] .chat-top,
:root[data-theme="vesper"] .chat-input { background: #1a1726; border-color: #2a2540; }
:root[data-theme="vesper"] .chat { background: #12101a; }
:root[data-theme="vesper"] .brand { color: #9b8fb8; }
:root[data-theme="vesper"] .status { background: #e74c3c22; color: #c4a0e0; }
:root[data-theme="vesper"] .status.online { background: #4caf5022; color: #a0d6b4; }
:root[data-theme="vesper"] .msg.assistant .msg-bubble { background: #1e1b2e; color: #d0c8e0; }
:root[data-theme="vesper"] .msg.user .msg-bubble { background: #5a4f7a; color: #fff; }
:root[data-theme="vesper"] .theme-btn { background: #1e1b2e; color: #6b6080; }
:root[data-theme="vesper"] .theme-btn.active { background: #7c6e9a; color: #fff; }
:root[data-theme="vesper"] .nav-item.active { color: #9b8fb8; background: rgba(124,110,154,.12); }
:root[data-theme="vesper"] .reminder-popup { background: #1a1726; box-shadow: 0 8px 24px rgba(0,0,0,.5); }
:root[data-theme="vesper"] .settings-titlebar { border-color: #2a2540; }
:root[data-theme="vesper"] .settings-nav { border-color: #2a2540; }
:root[data-theme="vesper"] .nav-icons button { color: #6b6080; }
:root[data-theme="vesper"] .nav-icons button:hover { color: #9b8fb8; background: rgba(124,110,154,.1); }
:root[data-theme="vesper"] .sidebar-toggle { color: #6b6080; }
:root[data-theme="vesper"] .sidebar-toggle:hover { color: #9b8fb8; }
:root[data-theme="vesper"] .msg-time { color: #5a5070; }
:root[data-theme="vesper"] .location { color: #5a5070; }

/* 夕语星光效果 */
:root[data-theme="vesper"] .chat::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    radial-gradient(1px 1px at 3% 10%, rgba(255,255,255,.8), transparent),
    radial-gradient(1.5px 1.5px at 7% 55%, rgba(200,180,255,.6), transparent),
    radial-gradient(1px 1px at 11% 28%, rgba(255,255,255,.5), transparent),
    radial-gradient(2px 2px at 15% 78%, rgba(180,200,255,.7), transparent),
    radial-gradient(1px 1px at 19% 42%, rgba(255,255,255,.6), transparent),
    radial-gradient(1.5px 1.5px at 23% 15%, rgba(200,180,255,.5), transparent),
    radial-gradient(1px 1px at 27% 65%, rgba(255,255,255,.7), transparent),
    radial-gradient(1px 1px at 31% 88%, rgba(180,200,255,.4), transparent),
    radial-gradient(2px 2px at 35% 35%, rgba(255,255,255,.6), transparent),
    radial-gradient(1px 1px at 39% 52%, rgba(200,180,255,.5), transparent),
    radial-gradient(1.5px 1.5px at 43% 8%, rgba(255,255,255,.8), transparent),
    radial-gradient(1px 1px at 47% 72%, rgba(180,200,255,.6), transparent),
    radial-gradient(1px 1px at 51% 22%, rgba(255,255,255,.5), transparent),
    radial-gradient(2px 2px at 55% 48%, rgba(200,180,255,.7), transparent),
    radial-gradient(1px 1px at 59% 85%, rgba(255,255,255,.4), transparent),
    radial-gradient(1.5px 1.5px at 63% 18%, rgba(180,200,255,.6), transparent),
    radial-gradient(1px 1px at 67% 62%, rgba(255,255,255,.7), transparent),
    radial-gradient(1px 1px at 71% 38%, rgba(200,180,255,.5), transparent),
    radial-gradient(2px 2px at 75% 92%, rgba(255,255,255,.6), transparent),
    radial-gradient(1px 1px at 79% 5%, rgba(180,200,255,.8), transparent),
    radial-gradient(1.5px 1.5px at 83% 45%, rgba(255,255,255,.5), transparent),
    radial-gradient(1px 1px at 87% 75%, rgba(200,180,255,.6), transparent),
    radial-gradient(1px 1px at 91% 30%, rgba(255,255,255,.7), transparent),
    radial-gradient(2px 2px at 95% 58%, rgba(180,200,255,.5), transparent),
    radial-gradient(1px 1px at 98% 82%, rgba(255,255,255,.6), transparent),
    radial-gradient(1px 1px at 8% 95%, rgba(200,180,255,.4), transparent),
    radial-gradient(1.5px 1.5px at 25% 50%, rgba(255,255,255,.5), transparent),
    radial-gradient(1px 1px at 45% 15%, rgba(180,200,255,.6), transparent),
    radial-gradient(1px 1px at 65% 70%, rgba(255,255,255,.7), transparent),
    radial-gradient(2px 2px at 85% 25%, rgba(200,180,255,.5), transparent);
  animation: vesper-twinkle 5s ease-in-out infinite alternate;
  pointer-events: none;
  z-index: 0;
  opacity: 0.8;
}
@keyframes vesper-twinkle {
  0% { opacity: 0.4; }
  50% { opacity: 0.7; }
  100% { opacity: 0.5; }
}
:root[data-theme="vesper"] .chat > * { position: relative; z-index: 1; }
</style>
