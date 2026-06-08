<template>
  <div class="settings-view">
    <div class="settings-nav">
      <button v-for="cat in categories" :key="cat.id" :class="['sn-item', { active: activeCat === cat.id }]" @click="activeCat = cat.id">{{ cat.label }}</button>
    </div>
    <div class="settings-content">
      <!-- 服务器连接 -->
      <div v-if="activeCat==='server'" class="sc-pane">
        <div class="card"><h3>云端服务器连接</h3><p class="hint">连接到云端部署的夕语后端。本地使用请留空。</p>
          <div class="field"><label>服务器地址</label><input v-model="serverHost" placeholder="47.98.120.186（留空=本地模式）"></div>
          <div class="field"><label>端口</label><input v-model="serverPort" placeholder="18060"></div>
          <div class="field"><label>访问令牌</label><input type="password" v-model="serverToken" placeholder="输入云端 Token"></div>
          <div class="btn-row">
            <button class="btn" @click="saveServer">保存并连接</button>
            <button class="btn-s" @click="testServer" :disabled="testingServer">{{ testingServer ? '...' : '测试连接' }}</button>
            <span v-if="serverTestMsg" :class="serverTestOk ? 'ok' : 'fail'">{{ serverTestMsg }}</span>
          </div>
          <p class="hint" style="margin-top:8px">当前模式：{{ serverHost ? '☁️ 云端' : '💻 本地' }}</p>
        </div>
      </div>

      <!-- API -->
      <div v-if="activeCat==='api'" class="sc-pane">
        <div class="card"><h3>AI 接口配置</h3>
          <div class="field"><label>提供商</label><select v-model="provider" @change="onProviderChange"><option value="deepseek">DeepSeek</option><option value="qwen">通义千问</option><option value="moonshot">Moonshot</option><option value="zhipu">智谱</option><option value="openai">OpenAI</option><option value="ollama">Ollama (本地)</option><option value="custom">自定义</option></select></div>
          <div class="field"><label>API 地址</label><input v-model="apiBaseUrl" placeholder="https://api.deepseek.com/v1"></div>
          <div class="field"><label>模型</label><div class="btn-row"><input v-model="apiModel" placeholder="deepseek-chat" style="flex:1"><button class="btn-s" @click="fetchModels" :disabled="fetchingModels">{{ fetchingModels ? '...' : '获取' }}</button></div></div>
          <div class="field"><label>API Key</label><input type="password" v-model="apiKey" placeholder="sk-..."></div>
          <div class="btn-row"><button class="btn" @click="saveApi">保存</button><button class="btn-s" @click="testApi" :disabled="testingApi">{{ testingApi ? '...' : '测试连接' }}</button><span v-if="testMsg" :class="testOk ? 'ok' : 'fail'">{{ testMsg }}</span></div>
          <div v-if="availableModels.length" class="field" style="margin-top:8px"><label>可用模型</label><select v-model="apiModel"><option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option></select></div>
        </div>
        <div class="card"><h3>联网搜索</h3><p class="hint">选择搜索方式。大模型模式由 AI 自行判断是否需要联网；DuckDuckGo 仅在识别到搜索意图时调用。仅大模型支持联网时生效。</p>
          <select v-model="searchProvider" @change="saveCfg('search_provider', searchProvider)"><option value="off">关闭</option><option value="llm">大模型</option><option value="ddg">DuckDuckGo</option></select>
        </div>
      </div>

      <!-- 角色人设 -->
      <div v-if="activeCat==='role'" class="sc-pane">
        <div class="card"><h3>基本信息</h3>
          <div class="field"><label>AI 名字</label><input v-model="aiName" @change="saveCfg('ai_name', aiName)"></div>
          <div class="field"><label>你的名字</label><input v-model="userName" @change="saveCfg('user_name', userName)"></div>
        </div>
        <div class="card"><h3>头像</h3>
          <div class="avatar-section"><div class="avatar-preview"><img :src="assistantAvatarUrl" class="avatar-img"><span class="avatar-label">AI 头像</span></div><div class="avatar-actions"><button class="btn-s" @click="$refs.aiAvatarInput.click()">本地上传</button><input type="file" ref="aiAvatarInput" accept="image/*" style="display:none" @change="uploadAvatar('assistant', $event)"><input v-model="aiAvatarUrlLocal" placeholder="或输入URL" class="url-input"><button class="btn-s" @click="uploadAvatarByUrl('assistant')" :disabled="!aiAvatarUrlLocal">导入</button></div></div>
          <div class="avatar-section"><div class="avatar-preview"><img :src="userAvatarUrl" class="avatar-img"><span class="avatar-label">用户头像</span></div><div class="avatar-actions"><button class="btn-s" @click="$refs.userAvatarInput.click()">本地上传</button><input type="file" ref="userAvatarInput" accept="image/*" style="display:none" @change="uploadAvatar('user', $event)"><input v-model="userAvatarUrlLocal" placeholder="或输入URL" class="url-input"><button class="btn-s" @click="uploadAvatarByUrl('user')" :disabled="!userAvatarUrlLocal">导入</button></div></div>
        </div>
        <div class="card"><h3>关系状态</h3>
          <div class="rel-item"><span class="rel-label">好感度</span><div class="rel-bar"><div class="rel-fill affection" :style="{width: (relationship.affection || 30) + '%'}"></div></div><span class="rel-value">{{ relationship.affection || 30 }}</span></div>
          <div class="rel-item"><span class="rel-label">信任度</span><div class="rel-bar"><div class="rel-fill trust" :style="{width: (relationship.trust || 30) + '%'}"></div></div><span class="rel-value">{{ relationship.trust || 30 }}</span></div>
          <div class="rel-item"><span class="rel-label">AI 状态</span><span class="ai-emotion-tag">{{ relationship.ai_emotion_label || '平静' }}</span><span class="ai-emotion-desc">{{ relationship.ai_emotion_description || '正常状态' }}</span></div>
        </div>
        <div class="card"><h3>性格设置</h3>
          <div class="field"><label>语气</label><select v-model="tone" @change="saveCfg('personality_tone', tone)"><option value="冷静">冷静</option><option value="活泼">活泼</option><option value="温柔">温柔</option><option value="毒舌">毒舌</option><option value="傲娇">傲娇</option><option value="自由">自由</option></select></div>
          <div class="field"><label>回复长度</label><select v-model="length" @change="saveCfg('length_level', length)"><option value="极短">极短（一句话）</option><option value="短">短（两三句）</option><option value="中等">中等（一段话）</option><option value="长">长（详细展开）</option><option value="详细">非常详细</option><option value="自由发挥">自由发挥</option><option value="不限">不限</option></select></div>
          <div class="field"><label>记忆回调</label><select v-model="recall" @change="saveCfg('recall_past', recall)"><option value="从不">从不</option><option value="被动">被动</option></select><p class="hint">控制 AI 是否在对话中主动提及过去的记忆。被动模式仅在相关话题出现时引用。</p></div>
          <label class="switch"><input type="checkbox" v-model="allowEmotion" @change="saveCfg('allow_emotion', allowEmotion)"> 允许使用颜文字</label><p class="hint">开启后 AI 会在自然的时候用颜文字表达情绪，如（笑）（叹气）（歪头），而非 emoji 图标。</p>
        </div>
        <div class="card"><h3>自定义提示词</h3>
          <textarea v-model="customPrompt" @change="saveCfg('custom_system_prompt', customPrompt)" rows="10" placeholder="留空则使用默认人设" style="min-height:200px;resize:vertical"></textarea>
          <p class="hint">右下角小标按住可拖动调整高度</p>
        </div>
        <div class="card"><h3>设定背景板</h3><p class="hint">记录你为 AI 设定的背景信息，如外号、喜好、身份等。AI 会遵循这些设定。重置关系时清空。</p>
          <textarea v-model="aiBackground" @change="saveCfg('ai_background', aiBackground)" rows="5" placeholder="例如：&#10;外号：小仓&#10;喜欢：咖啡、下雨天&#10;身份：我的大学室友" style="min-height:100px;resize:vertical"></textarea>
        </div>
        <div class="card"><h3>关系类型</h3><p class="hint">选择你和 AI 的关系类型，会影响人设和说话风格。</p>
          <select v-model="foundationType" @change="onFoundationChange">
            <option value="空白">空白（默认）</option>
            <option v-for="(info, type) in foundationTypes" :key="type" :value="type">{{ type }} (好感:{{ info.default_affection }} 信任:{{ info.default_trust }})</option>
          </select>
          <div v-if="pendingFoundation" class="foundation-confirm">
            <p>是否将好感度和信任度重置为「{{ pendingFoundation }}」的默认值？</p>
            <label><input type="checkbox" v-model="resetFoundationValues"> 重置好感/信任</label>
            <div class="btn-row">
              <button class="btn" @click="confirmFoundation">确认</button>
              <button class="btn btn-secondary" @click="cancelFoundation">取消</button>
            </div>
          </div>
        </div>
        <div class="card"><h3>角色预设</h3>
          <div class="btn-row"><input v-model="presetName" placeholder="预设名称"><button class="btn" @click="savePreset">保存当前</button></div>
          <div class="preset-list"><div v-for="(d, name) in presets" :key="name" class="preset-item" @click="loadPreset(name, d)">{{ name }}<span class="preset-del" @click.stop="deletePreset(name)">&times;</span></div></div>
        </div>
      </div>

      <!-- 外观 -->
      <div v-if="activeCat==='appearance'" class="sc-pane">
        <div class="card"><h3>主题</h3>
          <div class="theme-row">
            <button :class="['theme-btn', { active: themeLocal==='dark' }]" @click="setTheme('dark')">暗色</button>
            <button :class="['theme-btn', { active: themeLocal==='light' }]" @click="setTheme('light')">亮色</button>
            <button :class="['theme-btn', { active: themeLocal==='sakura' }]" @click="setTheme('sakura')">樱花</button>
            <button :class="['theme-btn', { active: themeLocal==='vesper' }]" @click="setTheme('vesper')">夕语</button>
          </div>
        </div>
        <div class="card"><h3>聊天背景</h3>
          <div class="field"><label>本地上传</label><div class="bg-row"><button class="btn-s" @click="$refs.bgFileInput.click()">选择图片</button><input type="file" ref="bgFileInput" accept="image/*" style="display:none" @change="uploadBg"><span v-if="bgUploadMsg" class="ok" style="font-size:11px">{{ bgUploadMsg }}</span></div></div>
          <div class="field"><label>图片 URL</label><div class="bg-row"><input v-model="chatBgImage" @change="saveCfg('chat_bg_image', chatBgImage)" placeholder="留空为纯色"><button class="btn-s" @click="clearBg">清除</button></div></div>
          <div class="field"><label>透明度</label><input type="range" min="0" max="100" v-model.number="bgOpacity" @change="saveBgStyle"></div>
          <div class="field"><label>模糊度</label><input type="range" min="0" max="20" v-model.number="bgBlur" @change="saveBgStyle"></div>
          <div class="field"><label>显示模式</label><select v-model="bgMode" @change="saveBgStyle"><option value="cover">拉伸</option><option value="contain">完整</option><option value="repeat">平铺</option><option value="center">居中</option></select></div>
        </div>
        <div class="card"><h3>向量记忆引擎</h3>
          <p class="hint">将聊天记录和知识库文档转为语义向量索引，AI 能通过含义（而非关键词）找到相关历史对话。首次使用需下载 ~420MB 模型。导入备份后需手动重建索引。</p>
          <div v-if="ragStatus === 'ready'" class="ok" style="margin-bottom:6px">已就绪 · {{ ragCount }} 条向量</div>
          <div v-else-if="ragStatus === 'installed'" style="color:var(--tc2);font-size:12px;margin-bottom:6px">已安装，启动时自动加载</div>
          <div v-else style="color:#f39c12;font-size:12px;margin-bottom:6px">未安装 · <button class="btn-s" @click="installRag" :disabled="installingRag">{{ installingRag ? '安装中...' : '点击安装' }}</button></div>
          <button class="btn-s" @click="rebuildRag" :disabled="rebuildingRag" style="margin-top:4px">{{ rebuildingRag ? '重建中...' : '重建向量索引' }}</button>
          <div v-if="ragMsg" :class="ragMsgOk ? 'ok' : 'fail'" style="margin-top:6px;font-size:11px">{{ ragMsg }}</div>
        </div>
      </div>

      <!-- 聊天偏好 -->
      <div v-if="activeCat==='chat'" class="sc-pane">
        <div class="card"><h3>字体大小</h3>
          <div class="field"><input type="range" min="10" max="20" v-model.number="chatFontSize" @change="saveCfg('chat_font_size', chatFontSize)"><span style="margin-left:8px;font-size:13px;color:var(--tc2)">{{ chatFontSize }}px</span></div>
        </div>
        <div class="card"><h3>分句模式</h3><p class="hint">智能分句：按标点自动断句，短于12字的句子会自动合并避免刷屏。分隔符分句：AI 主动用分隔符控制断句位置。逐字显示：模拟打字效果逐字弹出。连续输出：一次性显示全部回复。</p>
          <select v-model="sentenceMode" @change="saveCfg('sentence_mode', sentenceMode)"><option value="auto">智能分句</option><option value="delimiter">分隔符分句</option><option value="typewriter">逐字显示</option><option value="raw">连续输出</option></select>
        </div>
        <div class="card"><h3>主动频率</h3><p class="hint">AI 在你沉默后主动发起话题的间隔。关闭：不主动说话；低：约 3 小时；中：约 40-120 分钟（根据你回复率自动调整）；高：约 30 分钟。深夜 23:00-7:00 不打扰。</p>
          <select v-model="proactiveFreq" @change="saveCfg('proactive_frequency', proactiveFreq)"><option value="off">关闭</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select>
        </div>
        <div class="card"><h3>主动风格</h3><p class="hint">AI 主动找你说话时的语气。温暖关怀：像朋友一样关心近况再自然聊开；幽默调侃：带俏皮玩笑让人会心一笑；简洁直接：控制在15字以内说重点；自由发挥：由 AI 自行决定语气。主动消息会自动融入天气和位置信息。</p>
          <select v-model="proactiveStyle" @change="saveCfg('proactive_style', proactiveStyle)"><option value="warm">温暖关怀</option><option value="humorous">幽默调侃</option><option value="concise">简洁直接</option><option value="free">自由发挥</option></select>
        </div>
        <div class="card"><h3>关系模式</h3><p class="hint">快速模式好感度/信任度变化更快；长期模式每日有上限。好感度与信任度互相牵制——信任高了好感涨得快，反之亦然。聊天频率和情绪质量也会影响性格演化。</p>
          <select v-model="relMode" @change="saveCfg('relationship_mode', relMode)"><option value="fast">快速</option><option value="long_term">长期</option></select>
        </div>
        <div class="card"><h3>快捷短语</h3>
          <div v-for="(p, i) in quickPhrases" :key="i" class="phrase-row"><input :value="p" @input="updPhrase(i, $event.target.value)"><button class="btn-s" @click="delPhrase(i)">x</button></div>
          <button class="btn-s" @click="addPhrase">+ 添加</button>
        </div>
      </div>

      <!-- 定位 -->
      <div v-if="activeCat==='location'" class="sc-pane">
        <div class="card"><h3>高德地图 API</h3><p class="hint">用于天气查询和 GPS 精确定位。在高德开放平台免费申请 Web服务 Key 后填入。</p>
          <div class="field"><label>API Key (Web服务)</label><div class="btn-row"><input v-model="amapKey" placeholder="输入高德 Web服务 Key"><button class="btn" @click="saveAmapKey">保存</button><button class="btn-s" @click="testAmap" :disabled="testingAmap">{{ testingAmap ? '...' : '测试' }}</button></div><div v-if="amapTestMsg" class="field" style="margin-top:4px"><span :class="amapTestOk ? 'ok' : 'fail'">{{ amapTestMsg }}</span></div></div>
        </div>
        <div class="card"><h3>定位方式</h3><p class="hint">IP 定位写入手动城市（不会覆盖 GPS 结果）。GPS 精确定位精度更高，首次使用需浏览器授权。已授权过的重启后不再询问。</p>
          <div class="btn-row"><button class="btn" @click="locateByIP" :disabled="!!locating">{{ locating === 'ip' ? '定位中...' : 'IP 定位' }}</button><button class="btn" @click="preciseLocate" :disabled="!!locating">{{ locating === 'gps' ? '定位中...' : 'GPS 精确定位' }}</button><button class="btn-s" @click="resetLocation">重置权限</button></div>
          <div v-if="locateResult" class="field" style="margin-top:8px"><span :class="locateOk ? 'ok' : 'fail'">{{ locateResult }}</span></div>
        </div>
        <div class="card"><h3>手动选择</h3><p class="hint">当前定位：{{ currentLocation || '未获取' }}（精确城市优先于手动城市，GPS结果覆盖IP结果）</p>
          <div class="field"><label>省份</label><select v-model="selProvince" @change="loadCities"><option value="">{{ currentProvince || '-- 自动检测 --' }}</option><option v-for="p in provinces" :key="p.adcode" :value="p.adcode">{{ p.name }}</option></select></div>
          <div class="field"><label>城市</label><select v-model="selCity" @change="saveManualCity"><option value="">{{ currentManualCity || '-- 选择城市 --' }}</option><option v-for="c in cities" :key="c.adcode" :value="c.adcode">{{ c.name }}</option></select></div>
        </div>
        <div class="card"><h3>大模型联网天气</h3>
          <label class="switch"><input type="checkbox" v-model="enableLlmWeather" @change="saveCfg('enable_llm_weather_search', enableLlmWeather)"> 使用大模型联网查询天气</label>
          <p class="hint">勾选后天气查询跳过 Open-Meteo，由大模型自行搜索天气信息。仅大模型支持联网时生效。</p>
          <div style="margin-top:12px">
            <button class="btn" @click="testWeather" :disabled="testingWeather">{{ testingWeather ? '测试中...' : '测试天气源' }}</button>
          </div>
          <div v-if="weatherTestResults" style="margin-top:10px">
            <div v-for="r in weatherTestResults.sources" :key="r.source" :style="{color: r.ok ? '#4caf84' : '#e05570', fontSize:'13px', marginBottom:'4px'}">
              {{ r.ok ? '✓' : '✗' }} {{ r.source }}：{{ r.reason }}
              <div v-if="r.preview" style="color:var(--tc2);font-size:12px;margin-left:18px">{{ r.preview }}</div>
            </div>
            <div style="font-size:12px;color:var(--tc2);margin-top:4px">{{ weatherTestResults.summary }}</div>
          </div>
        </div>
      </div>

      <!-- 隐私与通知 -->
      <div v-if="activeCat==='privacy'" class="sc-pane">
        <div class="card"><h3>隐私锁</h3><p class="hint">启动时需要输入密码才能进入聊天界面。忘记密码时输错3次后可重置。</p>
          <label class="switch"><input type="checkbox" v-model="pinEnabled" @change="togglePin"> 启用 PIN 锁</label>
          <div v-if="pinEnabled" class="field" style="margin-top:8px"><label>密码</label><input type="password" v-model="pinCode" @change="savePin"></div>
        </div>
        <div class="card"><h3>通知</h3>
          <label class="switch"><input type="checkbox" v-model="useSysNotify" @change="saveCfg('use_system_notification', useSysNotify)"> 系统通知</label><p class="hint">Windows 桌面推送。提醒到期、AI 主动问候时弹窗。</p>
          <label class="switch"><input type="checkbox" v-model="useWeather" @change="saveCfg('use_weather_care', useWeather)"> 天气关怀</label><p class="hint">每天 7:00 / 12:00 / 19:00 自动推送当地天气，主动问候也会提及天气。定位城市可在「定位」设置中修改。</p>
          <label class="switch"><input type="checkbox" v-model="showTray" @change="saveCfg('show_tray_notification', showTray)"> 托盘提示</label><p class="hint">最小化到托盘时显示气泡提示。</p>
          <div class="field" style="margin-top:8px"><label>通知风格</label><select v-model="notifyStyle" @change="saveCfg('notification_style', notifyStyle)"><option value="warm">温暖</option><option value="casual">随意</option><option value="humorous">幽默</option><option value="concise">简洁</option><option value="tsundere">傲娇</option><option value="free">自由</option></select><p class="hint">影响天气推送和主动问候的文案语气。温暖偏向关怀口吻，随意更口语化，幽默带俏皮玩笑，简洁只说重点，傲娇口是心非，自由由AI自行决定。</p></div>
        </div>
      </div>

      <!-- 语音合成 -->
      <div v-if="activeCat==='tts'" class="sc-pane">
        <div class="card"><h3>语音朗读（TTS）</h3>
          <label class="switch"><input type="checkbox" v-model="ttsEnabled" @change="saveVoice"> 启用语音合成</label><p class="hint">开启后 AI 回复旁会显示朗读按钮。</p>
          <label class="field-label" style="margin-top:8px">引擎</label>
          <select v-model="ttsEngine" @change="onEngineChange" class="input">
            <option value="off">关闭语音合成</option>
            <option value="edge">Edge TTS（免费在线）</option>
            <option value="xiaomi">小米 MiMo TTS（在线）</option>
          </select>
          <p class="hint" v-if="ttsEngine==='xiaomi'">小米 MiMo 平台 API，支持预置音色和声音克隆。</p>
          <p class="hint" v-if="ttsEngineStatus" :class="ttsEngineStatus==='ok'?'hint-ok':'hint-err'">引擎状态: {{ ttsEngineStatus }}</p>
        </div>

        <!-- Edge TTS 配置 -->
        <div v-if="ttsEngine==='edge'" class="card"><h3>Edge TTS 音色</h3>
          <label class="field-label">音色</label>
          <select v-model="ttsVoice" @change="saveVoice" class="input">
            <option value="xiaoyi">小艺（女声温柔）</option>
            <option value="xiaoxiao">小晓（女声活泼）</option>
            <option value="yunxi">云希（男声阳光）</option>
            <option value="yunjian">云健（男声沉稳）</option>
          </select>
        </div>

        <!-- IndexTTS2 配置 -->
        <!-- 小米 TTS 配置 -->
        <div v-if="ttsEngine==='xiaomi'" class="card"><h3>小米 MiMo TTS</h3>
          <label class="field-label">API Key</label>
          <div style="display:flex;gap:8px">
            <input v-model="ttsApiKey" class="input" placeholder="在 platform.xiaomimimo.com 获取" type="password" style="flex:1">
            <button class="btn" @click="saveVoice">确认</button>
            <button class="btn-s" @click="testXiaomiTts" :disabled="testingXiaomi">{{ testingXiaomi ? '...' : '测试' }}</button>
          </div>
          <p class="hint" v-if="xiaomiTestMsg" :class="xiaomiTestOk?'hint-ok':'hint-err'" style="margin-top:4px">{{ xiaomiTestMsg }}</p>
          <label class="field-label" style="margin-top:8px">模式</label>
          <select v-model="ttsCloneMode" @change="onCloneModeChange" class="input">
            <option value="preset">预置音色</option>
            <option value="clone">声音克隆（用自己的声音）</option>
          </select>

          <!-- 预置音色 -->
          <div v-if="ttsCloneMode==='preset'" style="margin-top:8px">
            <label class="field-label">音色</label>
            <select v-model="ttsVoice" @change="saveVoice" class="input">
              <option value="冰糖">冰糖（中文女声）</option>
              <option value="茉莉">茉莉（中文女声）</option>
              <option value="苏打">苏打（中文男声）</option>
              <option value="白桦">白桦（中文男声）</option>
              <option value="Mia">Mia（英文女声）</option>
              <option value="Chloe">Chloe（英文女声）</option>
              <option value="Milo">Milo（英文男声）</option>
              <option value="Dean">Dean（英文男声）</option>
            </select>
          </div>

          <!-- 声音克隆 -->
          <div v-if="ttsCloneMode==='clone'" style="margin-top:8px">
            <label class="field-label">参考音频</label>
            <p class="hint">上传你的录音（10秒以上清晰语音，wav/mp3，≤10MB）</p>
            <input type="file" accept=".wav,.mp3" @change="uploadCloneAudio" class="input" style="padding:4px">
            <p class="hint" v-if="ttsCloneStatus" :class="ttsCloneStatus==='ok'?'hint-ok':'hint-err'">{{ ttsCloneStatusMsg }}</p>
          </div>
        </div>

        <div class="card"><h3>语音输入与播放</h3>
          <label class="switch"><input type="checkbox" v-model="sttEnabled" @change="saveVoice"> 语音输入（语音转文字）</label><p class="hint">长按发送按钮录音，自动转为文字。</p>
          <label class="switch" style="margin-top:6px"><input type="checkbox" v-model="autoPlay" @change="saveVoice"> 自动播放语音</label><p class="hint">AI 回复后自动朗读。</p>
        </div>
      </div>

      <!-- 数据管理 -->
      <div v-if="activeCat==='data'" class="sc-pane">
        <div class="card"><h3>收藏列表</h3><div v-for="f in favorites" :key="f.id" class="fav-item"><span class="fav-role">{{ f.role === 'user' ? userName : aiName }}</span><span class="fav-content">{{ f.content?.slice(0, 80) }}</span><button class="btn-s" @click="delFav(f.msg_id)">取消收藏</button></div><div v-if="!favorites.length" class="empty">暂无收藏</div></div>
        <div class="card"><h3>导出</h3><p class="hint">导出聊天记录。JSON 适合备份恢复，Markdown 适合阅读，TXT 通用纯文本。</p>
          <div class="btn-row"><button class="btn" @click="$emit('export-chat', 'json')">JSON</button><button class="btn" @click="$emit('export-chat', 'txt')">TXT</button><button class="btn" @click="$emit('export-chat', 'md')">Markdown</button></div>
        </div>
        <div class="card"><h3>聊天管理</h3><ChatManagePanel @changed="loadFavorites" /></div>
        <div class="card"><h3>数据迁移</h3><p class="hint">导出完整备份（含配置和记忆），或从备份恢复。恢复后建议重建向量索引。</p><MigratePanel /></div>
        <div class="card"><h3>云端同步</h3><p class="hint">加密备份到 WebDAV 服务器，防止数据丢失。</p>
          <div class="cloud-panel">
            <div class="cloud-row"><label>后端类型</label><select v-model="cloudBackend" @change="saveCloudCfg"><option value="webdav">WebDAV</option></select></div>
            <div class="cloud-row"><label>服务器地址</label><input v-model="cloudUrl" placeholder="https://example.com/dav/" /></div>
            <div class="cloud-row"><label>用户名</label><input v-model="cloudUser" placeholder="WebDAV 用户名" /></div>
            <div class="cloud-row"><label>密码</label><input v-model="cloudPass" type="password" placeholder="WebDAV 密码" /></div>
            <div class="cloud-row"><label>加密密码</label><input v-model="cloudPhrase" type="password" placeholder="可选：备份加密密码" /></div>
            <div class="cloud-actions">
              <button class="btn" @click="saveCloudCfg">保存配置</button>
              <button class="btn-s" @click="testCloudConn">测试连接</button>
              <button class="btn" @click="cloudUpload" :disabled="cloudUploading">{{ cloudUploading ? '上传中...' : '上传备份' }}</button>
            </div>
            <div v-if="cloudMsg" :class="['cloud-msg', cloudMsgOk ? 'ok' : 'err']">{{ cloudMsg }}</div>
            <div v-if="cloudLastSync" class="cloud-last">上次同步：{{ cloudLastSync }}</div>
          </div>
        </div>
        <div class="card"><h3>重置</h3><div class="btn-row"><button class="btn-s" @click="resetRelationship">重置关系(好感/信任)</button><button class="btn-s" @click="resetMemory">重置摘要记忆</button><button class="btn-s danger" @click="fullReset">完全重置</button></div><p class="hint">完全重置：清除所有数据（聊天、提醒、日程、待办、记忆、人设），重新触发引导。API 设置保留。</p></div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api.js'
import ChatManagePanel from './ChatManagePanel.vue'
import MigratePanel from './MigratePanel.vue'

const PROVIDER_MAP = {
  deepseek: { url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  qwen: { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  moonshot: { url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  zhipu: { url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  openai: { url: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  ollama: { url: 'http://localhost:11434/v1', model: '' },
  custom: { url: '', model: '' },
}

export default {
  components: { ChatManagePanel, MigratePanel },
  props: { settings: Object, themeLocal: String, ipCity: String, relationship: Object, emotionTrend: Array, totalMessages: Number, conversationDays: Number, assistantAvatarUrl: String, userAvatarUrl: String },
  emits: ['config-changed', 'export-chat', 'close'],
  data() {
    return {
      activeCat: 'role',
      categories: [
        { id: 'role', label: '角色人设' },
        { id: 'appearance', label: '外观主题' },
        { id: 'chat', label: '聊天偏好' },
        { id: 'tts', label: '语音朗读' },
        { id: 'location', label: '定位' },
        { id: 'privacy', label: '隐私与通知' },
        { id: 'data', label: '数据管理' },
        { id: 'server', label: '服务器连接' },
        { id: 'api', label: 'API 接口' },
      ],
      // 服务器连接
      serverHost: '', serverPort: '8060', serverToken: '', serverProtocol: 'http',
      serverTestMsg: '', serverTestOk: false, testingServer: false,
      provider: 'deepseek', apiBaseUrl: '', apiModel: '', apiKey: '',
      searchProvider: 'ddg', testMsg: '', testOk: false, testingApi: false, fetchingModels: false, availableModels: [],
      ttsEnabled: true, sttEnabled: true, autoPlay: false, notifyStyle: 'warm',
      ttsEngine: 'off', ttsVoice: 'xiaoyi', ttsApiKey: '', ttsApiUrl: '', ttsServerUrl: 'http://127.0.0.1:9880', ttsEngineStatus: '',
      ttsCloneMode: 'preset', ttsCloneStatus: '', ttsCloneStatusMsg: '',
      testingXiaomi: false, xiaomiTestMsg: '', xiaomiTestOk: false,
      aiName: '', userName: '', tone: '冷静', length: '短', recall: '从不', allowEmotion: true,
      customPrompt: '', aiBackground: '', presets: {}, presetName: '',
      foundationType: '空白', foundationTypes: {}, pendingFoundation: '', resetFoundationValues: false,
      chatBgImage: '', bgOpacity: 1, bgBlur: 0, bgMode: 'cover', bgUploadMsg: '',
      aiAvatarUrlLocal: '', userAvatarUrlLocal: '', chatFontSize: 14,
      sentenceMode: 'auto', proactiveFreq: 'medium', relMode: 'fast',
      quickPhrases: [], pinEnabled: false, pinCode: '',
      proactiveStyle: 'warm',
      useSysNotify: false, useWeather: true, showTray: true,
      favorites: [],
      amapKey: '', enableLlmWeather: false, testingWeather: false, weatherTestResults: null,
      locating: false, locateResult: '', locateOk: false, testingAmap: false, amapTestMsg: '', amapTestOk: false,
      ragStatus: '', ragCount: 0, ragMsg: '', ragMsgOk: false, installingRag: false, rebuildingRag: false,
      provinces: [], cities: [], selProvince: '', selCity: '',
      savedColorPresets: [],
      cloudBackend: 'webdav', cloudUrl: '', cloudUser: '', cloudPass: '', cloudPhrase: '',
      cloudMsg: '', cloudMsgOk: false, cloudUploading: false, cloudLastSync: '',
    }
  },
  computed: {
    currentLocation() {
      const precise = (this.settings || {}).precise_city || ''
      const manual = (this.settings || {}).manual_city || ''
      return precise || manual || this.ipCity || ''
    },
    currentProvince() {
      return (this.settings || {}).ip_location_province || ''
    },
    currentManualCity() {
      return (this.settings || {}).manual_city || ''
    }
  },
  async mounted() { this._loadServerSettings(); await this.loadFromSettings(); this.loadPresets(); this.loadFavorites(); this.loadProvinces(); this.checkRagStatus(); this.loadFoundationTypes(); this.loadCloudCfg() },
  methods: {
    // ── 服务器连接 ──
    saveServer() {
      localStorage.setItem('vesper_server_host', this.serverHost)
      localStorage.setItem('vesper_server_port', this.serverPort)
      localStorage.setItem('vesper_api_token', this.serverToken)
      localStorage.setItem('vesper_server_protocol', this.serverProtocol)
      if (this.serverHost) {
        window.__VESPER_CONFIG__ = Object.assign({}, window.__VESPER_CONFIG__ || {}, {
          backendHost: this.serverHost,
          backendPort: parseInt(this.serverPort) || 8060,
          apiToken: this.serverToken,
          backendProtocol: this.serverProtocol,
        })
      }
      this.serverTestMsg = '已保存，正在刷新...'
      this.serverTestOk = true
      setTimeout(() => location.reload(), 500)
    },
    async testServer() {
      this.testingServer = true; this.serverTestMsg = ''
      try {
        const host = this.serverHost || '127.0.0.1'
        const port = this.serverPort || '8060'
        const protocol = this.serverProtocol || 'http'
        const url = `${protocol}://${host}:${port}/health`
        const headers = this.serverToken ? { Authorization: `Bearer ${this.serverToken}` } : {}
        const res = await fetch(url, { headers, signal: AbortSignal.timeout(10000) })
        const data = await res.json()
        if (data.status === 'ok') { this.serverTestMsg = '✅ 连接成功'; this.serverTestOk = true }
        else { this.serverTestMsg = '❌ 响应异常'; this.serverTestOk = false }
      } catch (e) { this.serverTestMsg = '❌ 连接失败: ' + e.message; this.serverTestOk = false }
      this.testingServer = false
    },
    _loadServerSettings() {
      this.serverHost = localStorage.getItem('vesper_server_host') || ''
      this.serverPort = localStorage.getItem('vesper_server_port') || '8060'
      this.serverToken = localStorage.getItem('vesper_api_token') || ''
      this.serverProtocol = localStorage.getItem('vesper_server_protocol') || 'http'
      // 如果有云端配置，覆盖 __VESPER_CONFIG__
      if (this.serverHost) {
        window.__VESPER_CONFIG__ = Object.assign({}, window.__VESPER_CONFIG__ || {}, {
          backendHost: this.serverHost,
          backendPort: parseInt(this.serverPort) || 8060,
          apiToken: this.serverToken,
          backendProtocol: this.serverProtocol,
        })
      }
    },
    _detectProvider(url) { if (!url) return 'deepseek'; if (url.includes('localhost:11434')) return 'ollama'; for (const [k, v] of Object.entries(PROVIDER_MAP)) { if (k !== 'custom' && url.includes(v.url.replace('https://','').split('/')[0])) return k } return 'custom' },
    async loadFromSettings() {
      const s = this.settings || {}
      this.provider = this._detectProvider(s.api_base_url)
      this.apiBaseUrl = s.api_base_url || ''
      this.apiModel = s.api_model || ''
      this.apiKey = s.has_api_key ? '••••••••' : ''
      this.searchProvider = s.search_provider || 'ddg'
      this.aiName = s.ai_name || '夕语'; this.userName = s.user_name || ''
      this.tone = s.personality_tone || '冷静'; this.length = s.length_level || '短'
      this.recall = s.recall_past || '从不'; this.allowEmotion = s.allow_emotion !== false
      this.customPrompt = s.custom_system_prompt || ''
      this.aiBackground = s.ai_background || ''
      this.bgOpacity = s.bg_opacity !== undefined ? Number(s.bg_opacity) : 1
      this.bgBlur = s.bg_blur !== undefined ? Number(s.bg_blur) : 0
      this.chatFontSize = s.chat_font_size || 14
      this.bgMode = s.bg_mode || 'cover'
      if (s.quick_phrases) { try { this.quickPhrases = JSON.parse(s.quick_phrases) } catch (e) { this.quickPhrases = [] } }
      this.sentenceMode = s.sentence_mode || 'auto'
      this.proactiveFreq = s.proactive_frequency || 'medium'
      this.proactiveStyle = s.proactive_style || 'warm'
      this.amapKey = s.amap_key || ''
      this.enableLlmWeather = s.enable_llm_weather_search === true
      this.relMode = s.relationship_mode || 'fast'
      this.pinEnabled = s.pin_enabled === 'true' || s.pin_enabled === true
      this.pinCode = s.pin_code || ''
      this.useSysNotify = s.use_system_notification || false
      this.useWeather = s.use_weather_care !== false
      this.showTray = s.show_tray_notification !== false
      this.notifyStyle = s.notification_style || 'warm'
      this.ttsEnabled = s.tts_enabled !== false; this.sttEnabled = s.stt_enabled !== false
      this.autoPlay = s.auto_play_voice || false
      this.ttsEngine = s.tts_engine || 'off'
      this.ttsVoice = s.tts_voice || 'xiaoyi'
      this.ttsApiKey = s.tts_api_key || ''
      this.ttsApiUrl = s.tts_api_url || ''
      this.ttsServerUrl = s.tts_server_url || 'http://127.0.0.1:9880'
      // 声音克隆状态（从顶级配置读取）
      if (s.tts_clone_audio) {
        this.ttsCloneStatus = 'ok'
        this.ttsCloneStatusMsg = '已上传声音文件'
      } else {
        this.ttsCloneStatus = ''
      }
      // 从后端读取模式设置
      this.ttsCloneMode = s.tts_clone_mode || 'preset'
      this.checkEngineStatus()
    },
    async loadPresets() {
      try {
        const r = await api.get('/settings/presets')
        const all = r.data || {}
        this.presets = {}
        this.savedColorPresets = []
        for (const [k, v] of Object.entries(all)) {
          if (v && v.primary_color) {
            this.savedColorPresets.push({ name: k, primary: v.primary_color, bg: v.bg_color, sidebarBg: v.sidebar_bg, chatBg: v.chat_bg, userBubble: v.user_bubble, aiBubble: v.ai_bubble })
          } else {
            this.presets[k] = v
          }
        }
      } catch (e) {}
    },
    async loadFoundationTypes() {
      try {
        const r = await api.get('/settings/foundation-types')
        this.foundationTypes = r.data || {}
        // 从 ai_background 中读取当前 foundation_type
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          this.foundationType = bg.foundation_type || '空白'
          this._previousFoundationType = this.foundationType
        } catch (e) {
          this.foundationType = '空白'
          this._previousFoundationType = '空白'
        }
      } catch (e) {}
    },
    onFoundationChange() {
      // 暂存选择，等待用户确认
      this.pendingFoundation = this.foundationType
      this.resetFoundationValues = false
      // 恢复原来的选择（等确认后再改）
      this.foundationType = this._previousFoundationType || '空白'
    },
    async confirmFoundation() {
      try {
        await api.post('/settings/foundation', {
          foundation_type: this.pendingFoundation,
          reset_values: this.resetFoundationValues
        })
        this.foundationType = this.pendingFoundation
        this._previousFoundationType = this.pendingFoundation
        // 更新本地 aiBackground
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          bg.foundation_type = this.pendingFoundation
          if (this.pendingFoundation !== '空白') {
            delete bg.foundation  // 使用模板时清除自定义基石
          }
          this.aiBackground = JSON.stringify(bg)
        } catch (e) {}
      } catch (e) {}
      this.pendingFoundation = ''
    },
    cancelFoundation() {
      this.pendingFoundation = ''
      this.resetFoundationValues = false
    },
    async saveFoundation() {
      // 保留旧方法兼容（引导面板用）
      try {
        await api.post('/settings/foundation', { foundation_type: this.foundationType, reset_values: true })
        try {
          const bg = JSON.parse(this.aiBackground || '{}')
          bg.foundation_type = this.foundationType
          if (this.foundationType !== '空白') {
            delete bg.foundation
          }
          this.aiBackground = JSON.stringify(bg)
        } catch (e) {}
      } catch (e) {}
    },
    async loadFavorites() { try { const r = await api.get('/favorites'); this.favorites = r.data || [] } catch (e) {} },
    async saveCfg(key, value) { if (this._saveTimers?.[key]) clearTimeout(this._saveTimers[key]); this._saveTimers = this._saveTimers || {}; this._saveTimers[key] = setTimeout(async () => { try { await api.post('/settings/', { key, value }); this.$emit('config-changed', key, value) } catch (e) {} }, key === 'chat_font_size' || key === 'bg_opacity' || key === 'bg_blur' ? 200 : 50) },
    onProviderChange() { const p = PROVIDER_MAP[this.provider]; if (p) { this.apiBaseUrl = p.url; this.apiModel = p.model } },
    async saveApi() { await this.saveCfg('api_provider', this.provider); await this.saveCfg('api_base_url', this.apiBaseUrl); await this.saveCfg('api_model', this.apiModel); if (this.apiKey && this.apiKey !== '••••••••' && this.apiKey.length >= 10) await this.saveCfg('api_key', this.apiKey) },
    async testApi() { this.testingApi = true; try { const r = await api.get('/test/deepseek'); this.testOk = r.data.ok; this.testMsg = r.data.message } catch (e) { this.testOk = false; this.testMsg = '连接失败' } this.testingApi = false },
    setTheme(v) { this.saveCfg('theme', v) },
    clearBg() { this.chatBgImage = ''; this.saveCfg('chat_bg_image', ''); this.bgUploadMsg = '' },
    async uploadBg(e) { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { const r = await api.post('/avatar/upload/bg', fd); if (r.data.filename) { const url = `/avatars/${r.data.filename}`; this.chatBgImage = url; this.saveCfg('chat_bg_image', url); this.bgUploadMsg = '已上传' } } catch (err) { this.bgUploadMsg = '上传失败' } e.target.value = '' },
    saveBgStyle() { this.saveCfg('bg_opacity', this.bgOpacity); this.saveCfg('bg_blur', this.bgBlur); this.saveCfg('bg_mode', this.bgMode); this.$emit('config-changed', 'bg_style', { opacity: this.bgOpacity, blur: this.bgBlur, mode: this.bgMode }) },
    async fetchModels() { this.fetchingModels = true; try { const r = await api.get('/test/models'); this.availableModels = r.data.models || [] } catch (e) {} this.fetchingModels = false },
    saveVoice() {
      // 不传 tts_clone_audio，由上传端点单独管理
      this.saveCfg('voice', { tts_enabled: this.ttsEnabled, tts_engine: this.ttsEngine, tts_voice: this.ttsVoice, tts_api_key: this.ttsApiKey, tts_api_url: this.ttsApiUrl, tts_server_url: this.ttsServerUrl, stt_enabled: this.sttEnabled, auto_play: this.autoPlay })
    },
    onEngineChange() { this.saveVoice(); this.checkEngineStatus() },
    onCloneModeChange() {
      this.saveCfg('tts_clone_mode', this.ttsCloneMode)
      if (this.ttsCloneMode === 'preset') { this.saveVoice() }
    },
    async uploadCloneAudio(e) {
      const f = e.target.files[0]; if (!f) return
      this.ttsCloneStatus = 'uploading'; this.ttsCloneStatusMsg = '上传中...'
      try {
        const fd = new FormData(); fd.append('file', f)
        const r = await api.post('/tts/upload-voice', fd)
        if (r.data?.status === 'ok') {
          this.ttsCloneStatus = 'ok'; this.ttsCloneStatusMsg = '上传成功，声音克隆已启用'
          // 通知 App 重新加载配置
          this.$emit('config-changed', 'tts_clone_audio', r.data.path)
        }
        else { this.ttsCloneStatus = 'err'; this.ttsCloneStatusMsg = r.data?.error || '上传失败' }
      } catch (err) { this.ttsCloneStatus = 'err'; this.ttsCloneStatusMsg = '上传失败：' + (err.message || '') }
    },
    async checkEngineStatus() {
      if (this.ttsEngine === 'off') { this.ttsEngineStatus = ''; return }
      try {
        const r = await api.get('/tts/health')
        this.ttsEngineStatus = r.data?.status || 'unknown'
        this.indexttsDevice = r.data?.device || ''
      } catch (e) { this.ttsEngineStatus = 'unreachable'; this.indexttsDevice = '' }
    },
    async testXiaomiTts() {
      if (!this.ttsApiKey) { this.xiaomiTestMsg = '请先填写 API Key'; this.xiaomiTestOk = false; return }
      this.testingXiaomi = true; this.xiaomiTestMsg = '测试中...'
      try {
        const r = await api.post('/tts/tts', { text: '你好，这是测试语音。', mode: this.ttsCloneMode === 'clone' ? 'clone' : 'preset' })
        if (r.data?.success) { this.xiaomiTestMsg = `测试成功，音频时长 ${r.data.duration?.toFixed(1) || '?'}s`; this.xiaomiTestOk = true }
        else { this.xiaomiTestMsg = r.data?.error || '测试失败'; this.xiaomiTestOk = false }
      } catch (e) { this.xiaomiTestMsg = '请求失败：' + (e.response?.data?.detail || e.message); this.xiaomiTestOk = false }
      this.testingXiaomi = false
    },
    addPhrase() { this.quickPhrases.push(''); this.savePhrases() },
    updPhrase(i, v) { this.quickPhrases.splice(i, 1, v); this.savePhrases() },
    delPhrase(i) { this.quickPhrases.splice(i, 1); this.savePhrases() },
    savePhrases() { this.saveCfg('quick_phrases', JSON.stringify(this.quickPhrases)) },
    togglePin() { this.saveCfg('pin_enabled', this.pinEnabled); if (!this.pinEnabled) { this.pinCode = ''; this.saveCfg('pin_code', '') } },
    savePin() { if (this.pinCode.length === 4) this.saveCfg('pin_code', this.pinCode) },
    async savePreset() { if (!this.presetName.trim()) return; try { await api.post('/settings/presets', { name: this.presetName, data: { tone: this.tone, length: this.length, recall: this.recall, allow_emotion: this.allowEmotion, custom_system_prompt: this.customPrompt } }); await this.loadPresets() } catch (e) {} },
    async deletePreset(name) { if (!confirm(`删除预设「${name}」？`)) return; try { await api.delete(`/settings/presets/${encodeURIComponent(name)}`); await this.loadPresets() } catch (e) {} },
    async loadPreset(name, d) { if (!d) return; this.tone = d.tone || '冷静'; this.length = d.length || '短'; this.recall = d.recall || '从不'; this.allowEmotion = d.allow_emotion !== false; this.customPrompt = d.custom_system_prompt || ''; this.saveCfg('personality_tone', this.tone); this.saveCfg('length_level', this.length); this.saveCfg('recall_past', this.recall); this.saveCfg('allow_emotion', this.allowEmotion); this.saveCfg('custom_system_prompt', this.customPrompt) },
    async delFav(id) { try { await api.delete(`/favorites/${id}`); await this.loadFavorites() } catch (e) {} },
    // ── 定位 ──
    async saveAmapKey() { await this.saveCfg('amap_key', this.amapKey); this.loadProvinces() },
    async locateByIP() { this.locating = 'ip'; try { const r = await api.get('/location/ip'); if (r.data.city) { this.locateResult = `${r.data.province || ''} ${r.data.city}`; this.locateOk = true; await this.saveCfg('manual_city', r.data.city); if (r.data.province) await this.saveCfg('ip_location_province', r.data.province); this.$emit('config-changed', 'manual_city', r.data.city) } else { this.locateResult = r.data.error || '获取失败'; this.locateOk = false } } catch (e) { this.locateResult = '请求失败'; this.locateOk = false } this.locating = false },
    async preciseLocate() { this.locating = 'gps'; try { let perm = 'prompt'; try { const ps = await navigator.permissions.query({ name: 'geolocation' }); perm = ps.state } catch (e) {} if (perm === 'denied') { this.locateResult = '定位权限已被拒绝，请在浏览器设置中允许'; this.locateOk = false; this.locating = false; return } const pos = await new Promise((resolve, reject) => { navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000, maximumAge: 300000 }) }); localStorage.setItem('gps_location_granted', '1'); const r = await api.post('/location/geo', { lat: pos.coords.latitude, lng: pos.coords.longitude }); if (r.data.city) { const loc = r.data.district ? r.data.city + '·' + r.data.district : r.data.city; this.locateResult = loc; this.locateOk = true; await this.saveCfg('precise_city', loc); if (r.data.province) await this.saveCfg('ip_location_province', r.data.province); this.$emit('config-changed', 'precise_city', loc) } else { this.locateResult = '无法解析位置'; this.locateOk = false } } catch (e) { this.locateResult = e.code === 1 ? '定位权限被拒绝' : '定位失败，请检查权限'; this.locateOk = false } this.locating = false },
    resetLocation() { try { localStorage.removeItem('gps_location_granted'); localStorage.removeItem('location_granted'); localStorage.removeItem('location_denied') } catch (e) {} this.selProvince = ''; this.selCity = ''; this.cities = []; this.locateResult = '已重置'; this.locateOk = true },
    async loadProvinces() { try { const r = await api.get('/location/provinces'); this.provinces = r.data || [] } catch (e) {} },
    async loadCities() { this.selCity = ''; this.cities = []; if (!this.selProvince) return; try { const r = await api.get(`/location/cities/${this.selProvince}`); this.cities = r.data || [] } catch (e) {} },
    async saveManualCity() { if (!this.selCity) return; const city = this.cities.find(c => c.adcode === this.selCity); if (city) { await this.saveCfg('manual_city', city.name); this.locateResult = `已选择: ${city.name}`; this.locateOk = true } },
    // ── 颜色 ──
    async testAmap() { this.testingAmap = true; try { const r = await api.get('/location/ip'); this.amapTestOk = r.data.city ? true : false; this.amapTestMsg = r.data.city ? '连接成功: ' + r.data.city : (r.data.error || '无数据') } catch (e) { this.amapTestOk = false; this.amapTestMsg = '连接失败' } this.testingAmap = false },
    async testWeather() { this.testingWeather = true; this.weatherTestResults = null; try { const r = await api.get('/test/weather'); this.weatherTestResults = r.data } catch (e) { this.weatherTestResults = { ok: false, summary: '请求失败', sources: [{source:'网络',ok:false,reason:e.message||'未知错误'}] } } this.testingWeather = false },
    async checkRagStatus() { try { const r = await api.get('/rag/status'); this.ragStatus = r.data.model_loaded ? 'ready' : (r.data.installed ? 'installed' : 'missing'); this.ragCount = r.data.total_vectors || r.data.vector_count || 0 } catch (e) {} },
    async installRag() { this.installingRag = true; this.ragMsg = '正在安装向量引擎...'; this.ragMsgOk = false; try { const r = await api.post('/rag/install'); if (r.data.ok) { this.ragMsg = r.data.msg; this.ragMsgOk = true; this.checkRagStatus() } else { this.ragMsg = r.data.error; this.ragMsgOk = false } } catch (e) { this.ragMsg = '安装失败'; this.ragMsgOk = false } this.installingRag = false },
    async rebuildRag() { this.rebuildingRag = true; this.ragMsg = '正在重建索引...'; this.ragMsgOk = false; try { await api.post('/rag/rebuild'); this.ragMsg = '重建任务已提交，稍后刷新查看进度'; this.ragMsgOk = true; setTimeout(() => this.checkRagStatus(), 5000) } catch (e) { this.ragMsg = '重建失败'; this.ragMsgOk = false } this.rebuildingRag = false },
    async resetRelationship() { if (!confirm('确定要重置好感度、信任度和AI情绪为初始值吗？')) return; try { await api.post('/relationship/reset'); alert('已重置') } catch (e) { alert('重置失败') } },
    async resetMemory() { if (!confirm('确定要重置摘要记忆吗？此操作不可撤销。')) return; try { await api.post('/summary/reset'); alert('已重置') } catch (e) { alert('重置失败') } },
    async fullReset() {
      if (!confirm('确定要完全重置吗？\n\n将清除：\n- 所有聊天记录\n- 所有提醒、日程、待办\n- 所有记忆和摘要\n- 人设和性格设置\n\nAPI 设置会保留。\n\n此操作不可撤销！')) return
      try {
        await api.post('/settings/full-reset')
        localStorage.removeItem('vesper_api_token')
        location.reload()
      } catch (e) { alert('重置失败: ' + (e.message || '未知错误')) }
    },
    async uploadAvatar(role, e) { const f = e.target.files[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); try { await api.post(`/avatar/upload/${role}`, fd); this.$emit('config-changed', 'avatar_updated'); e.target.value = '' } catch (err) { alert('上传失败') } },
    async uploadAvatarByUrl(role) { const url = role === 'assistant' ? this.aiAvatarUrlLocal : this.userAvatarUrlLocal; if (!url) return; try { await api.post(`/avatar/upload-url/${role}`, { url }); this.$emit('config-changed', 'avatar_updated'); if (role === 'assistant') this.aiAvatarUrlLocal = ''; else this.userAvatarUrlLocal = '' } catch (err) { alert('导入失败') } },
    // 云端同步
    async saveCloudCfg() {
      try {
        await api.post('/cloud/config', { backend_type: this.cloudBackend, url: this.cloudUrl, username: this.cloudUser, password: this.cloudPass, passphrase: this.cloudPhrase })
        this.cloudMsg = '配置已保存'; this.cloudMsgOk = true
        setTimeout(() => this.cloudMsg = '', 3000)
      } catch (e) { this.cloudMsg = '保存失败'; this.cloudMsgOk = false }
    },
    async testCloudConn() {
      try {
        const r = await api.post('/cloud/test')
        this.cloudMsg = r.data.message || '连接成功'; this.cloudMsgOk = r.data.status === 'ok'
      } catch (e) { this.cloudMsg = '连接失败'; this.cloudMsgOk = false }
    },
    async cloudUpload() {
      this.cloudUploading = true; this.cloudMsg = ''
      try {
        const r = await api.post('/cloud/upload', { passphrase: this.cloudPhrase })
        this.cloudMsg = r.data.status === 'ok' ? '上传成功' : (r.data.message || '上传失败')
        this.cloudMsgOk = r.data.status === 'ok'
        if (r.data.status === 'ok') { const sr = await api.get('/cloud/status'); this.cloudLastSync = sr.data.last_sync || '' }
      } catch (e) { this.cloudMsg = '上传失败'; this.cloudMsgOk = false }
      finally { this.cloudUploading = false }
    },
    async loadCloudCfg() {
      try {
        const r = await api.get('/cloud/config')
        const cfg = r.data.config || {}
        this.cloudUrl = cfg.url || ''; this.cloudUser = cfg.username || ''; this.cloudPass = cfg.password || ''
        this.cloudBackend = cfg.backend_type || 'webdav'
        const sr = await api.get('/cloud/status')
        this.cloudLastSync = sr.data.last_sync || ''
      } catch (e) {}
    },
  }
}
</script>

<style scoped>
.settings-view { display: flex; height: 100%; }
.settings-nav { width: 180px; border-right: 1px solid var(--border); padding: 16px 0; display: flex; flex-direction: column; gap: 2px; }
.sn-item { padding: 10px 20px; background: none; border: none; text-align: left; font-size: 13px; color: var(--tc2); cursor: pointer; }
.sn-item:hover { background: rgba(255,255,255,.03); color: var(--tc); }
.sn-item.active { background: rgba(255,255,255,.04); color: var(--p); }
.settings-content { flex: 1; overflow-y: auto; padding: 20px; }
.sc-pane { display: flex; flex-direction: column; gap: 12px; }
.card { background: rgba(255,255,255,.02); border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--tc2); margin: 0 0 10px 0; line-height: 1.5; opacity: .75; }
.hint-ok { color: #4caf50 !important; opacity: 1 !important; }
.hint-err { color: #e74c3c !important; opacity: 1 !important; }
.field-label { display: block; font-size: 12px; color: var(--tc2); margin-bottom: 4px; }
.input { width: 100%; padding: 6px 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--tc); font-size: 13px; outline: none; box-sizing: border-box; }
.input:focus { border-color: var(--p); }
.field { margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: var(--tc2); margin-bottom: 4px; }
.field input, .field select, textarea { width: 100%; padding: 7px 10px; border-radius: 5px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 13px; font-family: inherit; box-sizing: border-box; }
.field select { width: 100%; }
textarea { resize: vertical; }
.btn { padding: 7px 16px; background: var(--p); color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: .4; }
.btn-s { padding: 5px 10px; background: rgba(255,255,255,.04); border: 1px solid var(--border); border-radius: 4px; color: var(--tc2); cursor: pointer; font-size: 12px; }
.btn-s:hover { background: rgba(255,255,255,.06); }
.btn-s.danger { color: #f85149; border-color: #f85149; }
.btn-s.danger:hover { background: rgba(248,81,73,.1); }
.btn-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ok { color: #2ea043; font-size: 12px; }
.fail { color: #e74c3c; font-size: 12px; }
.switch { display: block; font-size: 13px; color: var(--tc); margin: 4px 0; cursor: pointer; }
.switch input { margin-right: 6px; }
.theme-row { display: flex; gap: 6px; flex-wrap: wrap; }
.theme-btn { flex: 1; padding: 8px; background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 6px; color: var(--tc2); cursor: pointer; font-size: 12px; min-width: 50px; }
.theme-btn.active { background: var(--p); color: #fff; border-color: var(--p); }
.preset-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.preset-item { padding: 4px 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 4px; font-size: 12px; cursor: pointer; }
.preset-item:hover { background: rgba(255,255,255,.06); }
.phrase-row { display: flex; gap: 6px; margin-bottom: 6px; }
.phrase-row input { flex: 1; padding: 5px 8px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg); color: var(--tc); font-size: 12px; }
.fav-item { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,.03); font-size: 12px; }
.fav-role { color: var(--p); white-space: nowrap; min-width: 30px; }
.fav-content { flex: 1; color: var(--tc); }
.empty { color: var(--tc2); font-size: 12px; padding: 10px; }
.preset-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.preset-chip { display: flex; align-items: center; gap: 4px; padding: 4px 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--tc2); transition: border-color .15s; }
.preset-chip:hover { border-color: var(--p); color: var(--tc); }
.preset-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.preset-del { color: #e74c3c; font-size: 14px; opacity: .4; }
.preset-del:hover { opacity: 1; }
.loc-hint { font-size: 11px; color: var(--tc2); margin-top: 4px; }
.color-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.color-field label { font-size: 11px; color: var(--tc2); }
.color-row { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.color-swatch { width: 20px; height: 20px; border-radius: 4px; border: 1px solid var(--border); flex-shrink: 0; }
.color-row input[type="color"] { width: 28px; height: 20px; padding: 0; border: none; background: none; cursor: pointer; }
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

/* 移动端适配 */
@media (max-width: 768px) {
  .settings-view { flex-direction: column; }
  .settings-nav {
    width: 100%;
    flex-direction: row;
    border-right: none;
    border-bottom: 1px solid var(--border);
    padding: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .settings-nav::-webkit-scrollbar { display: none; }
  .sn-item {
    padding: 10px 14px;
    white-space: nowrap;
    flex-shrink: 0;
    font-size: 12px;
    min-height: 44px;
    display: flex;
    align-items: center;
  }
  .settings-content { padding: 12px; }
  .card { padding: 12px; }
  .avatar-section { flex-direction: column; align-items: flex-start; }
  .color-grid { grid-template-columns: 1fr; }
  .btn { min-height: 44px; }
  .btn-s { min-height: 44px; }
  .hint { font-size: 12px; }
}
.foundation-confirm { margin-top: 12px; padding: 12px; background: rgba(83,144,212,.08); border-radius: 8px; border: 1px solid var(--border, #30363d); }
.foundation-confirm p { margin: 0 0 8px; font-size: 13px; }
.foundation-confirm label { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 10px; cursor: pointer; }
.foundation-confirm .btn-row { display: flex; gap: 8px; }
.foundation-confirm .btn { padding: 6px 16px; font-size: 13px; }
.btn-secondary { background: var(--border, #30363d); color: var(--tc, #e6edf3); }
.btn-secondary:hover { background: var(--tc2, #8b949e); }
.cloud-panel { display: flex; flex-direction: column; gap: 8px; }
.cloud-row { display: flex; align-items: center; gap: 8px; }
.cloud-row label { font-size: 12px; color: var(--tc2); min-width: 80px; flex-shrink: 0; }
.cloud-row input, .cloud-row select { flex: 1; padding: 6px 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--tc); font-size: 12px; }
.cloud-actions { display: flex; gap: 8px; margin-top: 4px; }
.cloud-msg { font-size: 12px; padding: 4px 0; }
.cloud-msg.ok { color: #4caf50; }
.cloud-msg.err { color: #e74c3c; }
.cloud-last { font-size: 11px; color: var(--tc2); }
</style>
