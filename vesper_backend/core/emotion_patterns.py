# core/emotion_patterns.py — 正则化情感检测
"""替代简单关键词匹配，覆盖：衍生词、否定、加强、语境、混合情感、弱化、反讽"""

import re

# ─── 否定前缀（紧贴情感词前面时反转情感）───
_NEG = r"(?:不|没|没有|不太|并不|并非|并非不|才不|一点也不|完全不|根本不|绝不会|不会)"

# ─── 加强前缀（拆分强度，_INTENSIFY 保留为旧名兼容）───
# 中等加强：+0.25
_STRONG = r"(?:很|非常|挺|蛮|相当)"
# 极强加强：+0.35
_EXTREME = r"(?:极其|超级|特别|贼|巨|老|太|好|真|真的|实在|简直|格外|异常)"
# 兼容旧代码：合并所有加强词
_INTENSIFY = r"(?:很|非常|特别|超级|极其|太|好|真|真的|实在|简直|贼|巨|老|蛮|挺|相当|格外|异常)"

# ─── 弱化前缀（降低强度 -0.2）───
_DIMINISH = r"(?:有点|有些|稍微|稍|略微|略带|略感|一点点|些许)"

# ─── 程度后缀 ───
_SUFFIX = r"(?:了|啦|呀|啊|哦|噢|嘛|呢|吧|死了|坏了|爆了|极了|到不行|得不行|得要命)"

# ─── 情感模式（优先级从高到低）───

# 爱意 / 亲密
LOVE_PATTERNS = [
    re.compile(r"想你|念你|惦记你"),
    re.compile(r"抱抱|搂|亲亲|亲一?下|mua|muah"),
    re.compile(r"爱你|喜欢你|好喜欢你|超喜欢你|最喜欢你"),
    re.compile(r"💕|❤|💗|🥰|😘|💖|💝|💞|💓|💑"),
    re.compile(r"宝贝|亲爱的|小可爱|小甜心"),
    re.compile(r"离不开你|需要你|依赖你"),
    re.compile(r"心动|心跳|小鹿乱撞"),
]

# 惊讶
SURPRISE_PATTERNS = [
    re.compile(r"哇+|卧槽|我(去|靠|天|擦)"),
    re.compile(r"真的吗|不会吧|不是吧|难以置信"),
    re.compile(r"竟然|居然|没想到|出乎意料"),
    re.compile(r"天哪|天啊|我的天|妈呀|妈诶"),
    re.compile(r"震惊|惊了|惊呆|吓一跳|吓死"),
    re.compile(r"万万没想到|始料未及"),
]

# 开心（含衍生 + 否定检测）
# 注意：SAD_PATTERNS 里有"破防/崩溃/受不了/窒息"等会被"笑到崩溃/美到窒息"触发的词，
# 所以"笑到/美到 + 这类词"必须在本表前置匹配，优先级高于 SAD。
HAPPY_PATTERNS = [
    # 核心词 + 衍生
    re.compile(rf"(?:{_INTENSIFY})?(?:开心|高兴|快乐|愉快|欢乐|兴奋|激动|欣喜|喜悦|爽|嗨){_SUFFIX}?"),
    re.compile(r"哈哈+|嘻嘻+|嘿嘿+|呵呵+(?![…。])"),  # 呵呵+后面跟标点可能是反讽
    re.compile(r"太棒了?|太好了?|太赞了?|太爽了?"),
    re.compile(r"好呀|好嘞|好耶|好哦|可以呀|行呀"),
    re.compile(r"耶+|哟+|耶斯|耶嘿|耶呼"),
    re.compile(r"棒极了|爽翻|嗨翻|开心死了|高兴坏了"),
    # "笑到/笑得/笑哭/笑死" 是 happy 的夸张表达，优先于 SAD 的"崩溃/不行"
    re.compile(r"笑(死|哭|喷|裂|到|得)|笑死我了|笑不活了"),
    # "X 到/得 + 崩溃/不行/受不了/窒息/顶不住" 句式是夸张，不是真负面
    re.compile(r"(?:笑|美|帅|高兴|开心|兴奋|爽|嗨|激动)(?:到|得)(?:崩溃|不行|受不了|窒息|顶不住|不行了)"),
    re.compile(r"冲鸭|冲冲冲|加油|太好了"),
    re.compile(r"满足|幸福|幸运|感恩|感激"),
    re.compile(r"期待|盼望|迫不及待"),
    re.compile(r"庆祝|欢呼|雀跃|手舞足蹈"),
]

# 难过
# 收紧原则：裸单字（烦/累/悔/泪/颓）容易误判合成词（麻烦/积累/无悔/眼泪/颓废文学），
# 一律要求前后语境或改成词组形式，避免误判正常表达。
SAD_PATTERNS = [
    re.compile(rf"(?:{_INTENSIFY})?(?:难过|伤心|悲伤|悲痛|哀伤|忧伤|心酸|心痛|心疼){_SUFFIX}?"),
    re.compile(rf"(?:{_INTENSIFY})?(?:生气|愤怒|暴怒|恼火|恼怒|火大|气死|气炸){_SUFFIX}?"),
    re.compile(rf"(?:{_INTENSIFY})?(?:讨厌|厌恶|反感|嫌弃|厌烦|恶心){_SUFFIX}?"),
    # "烦" 收紧：要求带后缀或加强词，避免匹配"麻烦/烦请/烦劳"
    re.compile(rf"(?:{_INTENSIFY})?(?:烦躁|烦死了|烦透了|好烦|很烦|特烦|烦人|烦着|烦得){_SUFFIX}?"),
    re.compile(rf"(?:{_INTENSIFY})?(?:委屈|憋屈|冤枉|难受|不舒服|不爽){_SUFFIX}?"),
    # "累" 收紧：单独"累"会误判"积累/累计/劳累/累加/连累/牵累/受累"
    # 真疲惫用法：前面有加强词（很累/好累/太累），或后面接"了/死/坏/得/不行"
    # 词组形式（疲惫/疲倦/精疲力尽/累死了/累坏了）不需要前缀保护
    re.compile(rf"(?:{_INTENSIFY})?累(?:了|死|坏|得|不行|透)|(?:{_INTENSIFY})?(?:疲惫|疲倦|精疲力尽|累死了|累坏了|好累|太累|很累|特累)|又累又"),
    re.compile(rf"(?:{_INTENSIFY})?(?:焦虑|紧张|不安|恐慌|害怕|恐惧|畏惧){_SUFFIX}?"),
    re.compile(r"哎+|唉+|哎呀|哎哟|哎呦|天哪"),
    # "哭/泪" 收紧：要求词组形式，避免匹配"眼泪是成长的礼物/含泪微笑"
    re.compile(r"哭(了|泣|死|到|得)|想哭|忍不住哭|流泪|落泪|含泪|泪流|泪目"),
    re.compile(r"孤独|寂寞|无聊|空虚|无助|绝望"),
    # "悔" 收紧：要求词组，避免匹配"无悔/悔不当初(正面)"
    re.compile(r"后悔|懊悔|悔恨|悔意|悔不当初"),
    re.compile(r"失落|沮丧|低落|消沉|颓废|颓丧"),
    # "崩溃/破防/受不了/窒息" 等已在 _HAPPY_HYPERBOLE_PATTERNS 前置过滤掉 happy 夸张句式
    # 这里保留单字形式，匹配真负面场景（"我崩溃了/受不了了/破防了"）
    re.compile(r"(?:我|都|真的|实在|已经)?(?:崩溃|撑不住|受不了|扛不住|顶不住|破防)(?:了|啦|不行)?"),
    re.compile(r"失眠|睡不着|彻夜难眠|辗转反侧"),
    re.compile(r"压力大|喘不过气|透不过气"),
]

# 否定情感检测（不开心、没高兴 等）
NEGATIVE_HAPPY_PATTERNS = [
    re.compile(rf"{_NEG}(?:开心|高兴|快乐|愉快|兴奋|激动)"),
    re.compile(r"开心不起来|高兴不起来|快乐不起来"),
    re.compile(r"笑不出来|笑不动|笑不出"),
]

# ─── Happy 夸张前置匹配 ───
# "笑到崩溃/美到窒息/笑死了/破防了笑死" 这类句式虽然含 SAD 关键词，
# 但语义是正面夸张，必须先于 SAD 检测，否则会被 SAD 的"崩溃/窒息/破防"截胡。
_HAPPY_HYPERBOLE_PATTERNS = [
    re.compile(r"笑(死|哭|喷|裂|到|得)|笑死我了|笑不活了|笑崩"),
    re.compile(r"(?:笑|美|帅|高兴|开心|兴奋|爽|嗨|激动|乐|萌)(?:到|得)(?:崩溃|不行|受不了|窒息|顶不住|不行了|哭)"),
    re.compile(r"破防了(?:笑|乐|哭)"),  # "破防了笑死" → happy
    re.compile(r"开心死了|高兴坏了|爽翻了?|嗨翻了?|乐坏了"),
]


def detect_emotion(text: str) -> str:
    """检测文本情感，返回 love/surprise/happy/sad/calm

    支持：衍生词、否定、加强、语境、混合情感
    优先级：否定开心 > happy 夸张前置 > 爱意 > 惊讶 > 难过 > 开心 > 平静
    （happy 夸张前置必须在 SAD 之前，否则"笑到崩溃"会被 SAD 的"崩溃"截胡）
    """
    if not text:
        return "calm"

    # 否定开心归类为 sad
    for p in NEGATIVE_HAPPY_PATTERNS:
        if p.search(text):
            return "sad"

    # happy 夸张前置（"笑到崩溃/美到窒息/破防了笑死"）
    # 必须在 SAD 之前，因为这些词字面含 SAD 关键词但语义是正面夸张
    for p in _HAPPY_HYPERBOLE_PATTERNS:
        if p.search(text):
            return "happy"

    for p in LOVE_PATTERNS:
        if p.search(text):
            return "love"

    for p in SURPRISE_PATTERNS:
        if p.search(text):
            return "surprise"

    for p in SAD_PATTERNS:
        if p.search(text):
            return "sad"

    for p in HAPPY_PATTERNS:
        if p.search(text):
            return "happy"

    return "calm"


# ─── 强度信号模式 ───
_STRONG_RE = re.compile(_STRONG)
_EXTREME_RE = re.compile(_EXTREME)
_DIMINISH_RE = re.compile(_DIMINISH)
# 重复标点（！！！、？？？、！！！？）
_REPEAT_PUNCT = re.compile(r'[！!?！]{2,}')
# 重复情感字（好好好、慢慢慢、哈哈哈+）
_REPEAT_CHAR = re.compile(r'(.)\1{2,}')


def detect_emotion_intensity(text: str) -> tuple:
    """检测情感 + 强度 0-1。

    强度组成：
    - 基础词命中：0.5
    - 中等加强（很/非常/挺）：+0.25
    - 极强加强（极其/超级/太/真）：+0.35
    - 弱化词（有点/稍微）：-0.2
    - 重复标点（!!!）：+0.15
    - 重复字（哈哈哈）：+0.15
    - 否定/复合情感：+0.1
    - love/surprise 天生强度高：+0.05
    - 下限 0.1，上限 1.0

    Returns: (emotion, intensity 0.0-1.0)
    """
    if not text or not text.strip():
        return "calm", 0.0

    emotion = detect_emotion(text)
    if emotion == "calm":
        # 平静文本仍可能有少量标点，但强度极低
        return "calm", 0.1

    intensity = 0.5  # 基础命中

    # 弱化词优先扣减（"有点开心"应该弱于"开心"）
    if _DIMINISH_RE.search(text):
        intensity -= 0.2

    # 极强加强（优先于中等，避免双重计分——同词不可能同时命中两组）
    if _EXTREME_RE.search(text):
        intensity += 0.35
    elif _STRONG_RE.search(text):
        intensity += 0.25

    # 重复标点
    if _REPEAT_PUNCT.search(text):
        intensity += 0.15

    # 重复字（哈哈哈、好好好）
    if _REPEAT_CHAR.search(text):
        intensity += 0.15

    # 否定开心这类复合情感 → 强度更高
    if emotion == "sad":
        for p in NEGATIVE_HAPPY_PATTERNS:
            if p.search(text):
                intensity += 0.1
                break

    # love/surprise 天生强度高
    if emotion in ("love", "surprise"):
        intensity += 0.05

    return emotion, max(0.1, min(1.0, intensity))


# ─── 混合情感检测（"又开心又难过"、"又爱又恨"）───
# "又/既...又/也" 句式 + 情感词并存
_MIXED_CONJUNCTION = re.compile(r"(?:又|既)[^。！？\s]{0,8}?(?:又|也|且)")


def detect_emotions(text: str) -> list:
    """检测文本中所有命中的情感，返回去重保序的列表（最多 3 个）。

    处理"又开心又难过"、"又爱又恨"这类混合情感。
    单一情感时返回 [emotion]。

    Returns: ["happy", "sad", ...] 或 ["calm"]
    """
    if not text or not text.strip():
        return ["calm"]

    # 检测是否有混合连接词
    has_mixed = bool(_MIXED_CONJUNCTION.search(text))

    found = []
    # 否定开心归类为 sad，但仍是 sad 的一种表现
    for p in NEGATIVE_HAPPY_PATTERNS:
        if p.search(text) and "sad" not in found:
            found.append("sad")

    # happy 夸张前置（"笑到崩溃/美到窒息"）——必须在 SAD 之前
    for p in _HAPPY_HYPERBOLE_PATTERNS:
        if p.search(text) and "happy" not in found:
            found.append("happy")
            break

    for p in LOVE_PATTERNS:
        if p.search(text) and "love" not in found:
            found.append("love")
            break  # 每类最多触发一次

    for p in SURPRISE_PATTERNS:
        if p.search(text) and "surprise" not in found:
            found.append("surprise")
            break

    for p in SAD_PATTERNS:
        if p.search(text) and "sad" not in found:
            found.append("sad")
            break

    for p in HAPPY_PATTERNS:
        if p.search(text) and "happy" not in found:
            found.append("happy")
            break

    if not found:
        return ["calm"]

    # 无混合连接词 → 只返回主情感（与 detect_emotion 一致）
    if not has_mixed:
        return [detect_emotion(text)]

    # 有混合连接词 → 返回所有命中（最多 3 个，按优先级排序）
    priority = ["sad", "love", "surprise", "happy"]
    found.sort(key=lambda e: priority.index(e) if e in priority else 99)
    return found[:3]


# ─── 反讽检测（只标高置信，避免误判）───
# 模式1："呵呵" 后跟标点（"呵呵。" "呵呵，" "呵呵！"）—— 中文经典反讽
_SARC_HEHE = re.compile(r"呵{2,}[。，！!？?…\s]|呵{2,}$")
# 模式2："真棒/真好/真厉害/真行" + 紧邻负面词或失败语境
_SARC_TRUE_GOOD = re.compile(
    r"(?:真棒|真好|真厉害|真行|真优秀|真棒棒)(?:[^。！？\n]{0,10}?)"  # 真棒 + 10字内
    r"(?:搞砸|失败|又|还|却|结果|完蛋|糟了|坏了|砸了|黄了|没成|不行|做不到)"
)
# 模式3："哦" 重复或单字 + 标点（"哦哦哦。" "哦。"）—— 敷衍式
_SARC_OH = re.compile(r"哦{2,}[。，！！？?…\s]")


def is_sarcastic(text: str) -> bool:
    """检测高置信反讽。只标记明确的反讽，避免误判正常表达。

    检测模式：
    1. "呵呵" + 标点（中文经典阴阳怪气）
    2. "真棒/真好/真厉害" + 紧邻负面语境词
    3. "哦哦哦" + 标点（敷衍式）

    Returns: bool
    """
    if not text or len(text) < 2:
        return False
    if _SARC_HEHE.search(text):
        return True
    if _SARC_TRUE_GOOD.search(text):
        return True
    if _SARC_OH.search(text):
        return True
    return False


def detect_emotion_keywords(text: str) -> tuple[str, list[str]]:
    """检测情感并返回匹配到的关键词（用于调试和 SmartCrusher）
    
    Returns: (emotion, [matched_keywords])
    """
    if not text:
        return "calm", []

    matched = []

    for p in NEGATIVE_HAPPY_PATTERNS:
        m = p.search(text)
        if m:
            matched.append(m.group())

    for p in LOVE_PATTERNS:
        m = p.search(text)
        if m:
            matched.append(m.group())

    for p in SURPRISE_PATTERNS:
        m = p.search(text)
        if m:
            matched.append(m.group())

    for p in SAD_PATTERNS:
        m = p.search(text)
        if m:
            matched.append(m.group())

    for p in HAPPY_PATTERNS:
        m = p.search(text)
        if m:
            matched.append(m.group())

    if not matched:
        return "calm", []

    # 根据最后匹配到的模式确定情感
    emotion = detect_emotion(text)
    return emotion, matched


def is_question(text: str) -> bool:
    """检测是否为问句（正则化，覆盖各种问法）"""
    if not text:
        return False
    patterns = [
        r"[？?]\s*$",  # 以问号结尾
        r"^(?:请问|想问|问一下|问个|有个问题)",
        r"(?:吗|呢|吧)\s*$",  # 以语气词结尾
        r"(?:怎么|如何|为什么|为啥|啥原因|什么原因)",
        r"(?:是什么|什么是|哪个|哪些|多少|几)",
        r"(?:能不能|可以吗|可不可以|行不行|好不好|要不要|会不会)",
        r"(?:有没有|是不是|对不对|能不能)",
        r"(?:告诉我|教我|帮我|给我看看)",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False
