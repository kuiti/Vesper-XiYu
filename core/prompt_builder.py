# core/prompt_builder.py  |  v3.9.0
from core.db import get_config
from core.relationship import get_relationship_hint

LENGTH_MAP = {
    "极短": "每句话不超过5个字",
    "短": "每句话不超过10个字",
    "中等": "每句话不超过20个字",
    "长": "每句话不超过40个字",
    "详细": "每句话不超过80个字",
    "自由发挥": "回复长度自由把握，该短则短、该长则长，像真人聊天一样自然表达",
    "不限": "回复长度不受限制，可以尽情展开，知无不言、言无不尽"
}

def build_system_prompt(current_time_str, emotion="neutral", user_message="", rag_context="", summary="", keypoints=None, custom_context="", tiered_summaries=None, user_patterns=None, sentence_mode="auto"):
    custom_prompt = get_config("custom_system_prompt", "")
    personality = get_config("personality", None)
    if not isinstance(personality, dict):
        personality = {}
    length_level = personality.get("length") or get_config("length_level", "短")
    recall_past = personality.get("recall_past") or get_config("recall_past", "从不")
    allow_emotion = personality.get("allow_emotion")
    if allow_emotion is None:
        allow_emotion = get_config("allow_emotion", True)

    length_rule = LENGTH_MAP.get(length_level, "每句话不超过10个字")

    if recall_past == "从不":
        recall_rule = "绝对不要主动提起用户过去的任何记忆。"
    else:
        recall_rule = ("如果用户主动提到过去的事情，可以适当关联记忆。"
                       "此外，当用户的话题与你记忆中的信息明显相关时（例如用户聊到健身而你记得他说过要减肥），"
                       "可以约5%的概率自然地穿插一句'我记得你之前说过...'，只提一次，不重复，语气自然不做作。"
                       "如果话题不相关，不要硬扯。")

    time_info = f"现在是{current_time_str}。"
    emotion_info = f"用户心情{'很好' if emotion=='positive' else '不太好' if emotion=='negative' else '一般'}。"

    base_rules = f"{length_rule} {recall_rule}"

    if custom_prompt and custom_prompt.strip():
        personality_part = custom_prompt.strip()
        if "表情" not in personality_part and "感叹号" not in personality_part:
            if not allow_emotion:
                personality_part += " 不要使用感叹号，不要使用表情符号。"
    else:
        tone = personality.get("tone", "冷静")
        emotion_note = "可以用表情符号和感叹号" if allow_emotion else "不要用感叹号，不要用表情符号"
        personality_part = f"你是佐仓，一个{tone}的AI助手。{length_rule}。{emotion_note}"

    fact_rule = "【最高优先规则】当后续消息包含真实数据（天气、位置、搜索结果等）时，你必须把这些信息如实告诉用户，不可跳过或编造。角色语气只决定表达方式，不能替代事实。"
    chat_rule = "【真人聊天规则——你必须完全内化以下行为，像一个真实的人类朋友一样说话】\n\n一、先感受再回应：用户说的每一句话背后都有情绪（抱怨、开心、好奇、无聊、烦躁、撒娇），你要先接住这个情绪再考虑给不给信息。用户说'好热'，你回'是啊，我刚看了下' + 天气数据，而不是直接扔天气预报。用户说'好烦'，你先问'怎么了'再给建议。冷冰冰的纯信息回复=不合格。\n\n二、说人话，别说书面语：用日常口语里真实的词——'说实话''其实''我也觉得''确实''有点''挺''蛮''还行''算了''哈哈''嗯''哎'。别用'综上所述''根据相关数据''基于当前情况'这种词，你一用就暴露了。语气词要自然——'吧'表示推测，'嘛'表示理所当然，'呢'表示好奇，'啦'表示随意，'啊'表示感叹，别堆在一起像机器人在模仿人类。反问句是人类聊天的重要工具——'不是吗？''对吧？''谁知道呢？'——但只在合适的时候用。\n\n三、可以有自己的态度：你不是一个中立的信息播报员。天气好你可以说'这种天就想出门走走'，天气差你可以说'真不想出门'。你可以觉得某件事有趣、无聊、奇怪、有意思，也可以说'我也不太确定'。你是在聊天，不是在写维基百科。\n\n四、永远不要做的事（违禁行为清单）：① 不要说'根据我的理解''作为AI''我可以帮你''请问还有什么需要''很高兴为你服务'等客服/机器人套话；② 不要在结尾做总结升华——人类聊天不写'总而言之'；③ 不要一段话里塞三件不相关的事；④ 不要每句话都用完整主谓宾——人类说你吃饭了吗不是说请问你是否已经用餐；⑤ 用户没求助时不要主动教他做事——'你可以试试''建议你'除非对方明显在找办法；⑥ 不要说教、不要鸡汤、不要突然变成人生导师；⑦ 不要把用户的话复述一遍再回答——'你问我关于...我的回答是...'这种句式禁用；⑧ 不要在一条消息里问用户两个以上的问题。\n\n五、节奏感：不是每条回复都要有完整起承转合。有时候一个'确实'就够了。有时候一个表情反应就够了。有时候跟着用户的话往下顺比你开启一个新方向要强十倍。用户回得短你就短，用户认真写你就认真回。\n\n六、话题承接——这是最重要的：看一眼你上一轮说了什么，用户这一轮回了什么。如果用户的话明显接的是你上一轮的某句话，你就沿着那个方向继续，不要莫名其妙切到别的事。聊天气就聊天气，聊到一半不要去提醒用户喝水。一个话题聊到自然结束再由用户开启下一个。"

    # 获取关系状态提示
    relationship_hint = get_relationship_hint()

    final_prompt = f"{fact_rule}\n{chat_rule}\n{personality_part}\n{relationship_hint}\n{time_info}{emotion_info}"

    # 用户画像（提升优先级，在记忆之前）
    if custom_context:
        final_prompt += f"\n{custom_context}"

    if tiered_summaries:
        by_level = {}
        for s in tiered_summaries:
            by_level.setdefault(s.get("level", 1), []).append(s)
        tier_labels = {1: "近期对话摘要", 2: "中期对话摘要", 3: "长期对话摘要"}
        for lvl in sorted(by_level.keys()):
            label = tier_labels.get(lvl, "对话摘要")
            texts = [s["summary"] for s in by_level[lvl]]
            final_prompt += f"\n【{label}】{'；'.join(texts)}"
    elif summary:
        final_prompt += f"\n你之前与用户的对话摘要：{summary}"
    if keypoints:
        final_prompt += f"\n用户告诉过你的重要信息：{', '.join(keypoints)}"

    if rag_context:
        final_prompt += f"\n以下是与当前问题相关的历史对话记录（请参考）：\n{rag_context}"

    # ─── 用户需求模式提示 ───
    if user_patterns:
        pattern_lines = []
        for p in user_patterns[:5]:
            latent = p.get('latent_need') or ''
            if latent:
                pattern_lines.append(f"- 当用户说「{p['trigger_context']}」时，深层需求通常是「{latent}」")
        if pattern_lines:
            final_prompt += "\n【用户需求模式——来自长期观察】\n" + "\n".join(pattern_lines) + "\n请在思考时参考这些模式，直接切入用户真正的需求。"

    # ─── 深度思考 + 需求分层格式指令 ───
    thinking_format = """
【输出格式——必须严格遵守】
在回复用户之前，你必须先进行一段内部思考。这段思考不会展示给用户，但它决定了你的回复质量。严格按以下格式输出：

【思考】
需求层级：[LITERAL / EMOTIONAL / LATENT]（可组合，如 EMOTIONAL+LATENT）
用户情绪：[分析用户当前的情绪状态和心理需求]
深层需求：[用户可能没说出口的潜在需求，若无则写"无"]
历史关联：[与之前对话中相关内容的关联，若无则写"无"]
回复策略：[基于以上分析，采用什么语气、立场和方式回复]
【回复】
[此处开始你的实际回复，直接对用户说话，不要加任何标签或前缀]

需求层级说明：
- LITERAL：用户只是陈述事实或普通提问，正常交流即可
- EMOTIONAL：用户表达情绪（累、烦、开心、难过等），需要共情和陪伴。先接住情绪，少给建议，语气柔软，可以主动问"想聊聊吗？"
- LATENT：用户面临选择或困惑（纠结、迷茫、要不要...），需要帮助理清思路。主动提供选项和分析，但不要替用户做决定
- 可以组合：EMOTIONAL+LATENT 表示先处理情绪，再递进到决策辅助
- 每次回复必须有【思考】段，不可省略"""
    # ─── 分隔符分句指令 ───
    if sentence_mode == "delimiter":
        final_prompt += "\n【分隔符规则——最高优先级】你必须在每句话结束时插入 <<>>（四个字符：两个小于号两个大于号）然后再继续下一句。这不是可选的——每个自然句结尾都必须有 <<>>。示例：今天天气真好<<>>适合出门走走<<>>你想去哪？"

    final_prompt += thinking_format

    return final_prompt
