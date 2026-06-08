# core/knowledge_graph.py — 知识图谱：从对话中提取实体关系
import json
import logging
from core.db import get_conn, add_knowledge_triplet, query_knowledge_by_entity

logger = logging.getLogger(__name__)

# 提取 prompt
_EXTRACT_PROMPT = """从以下对话中提取实体关系三元组。
格式：[{"subject": "主语", "predicate": "谓语", "object": "宾语"}, ...]

规则：
1. 只提取明确陈述的关系，不要推测
2. 主语和宾语应该是具体的实体（人、物、地点、概念）
3. 谓语应该是动词或动词短语
4. 如果没有明确的关系，返回空数组 []

对话内容：
{content}

输出JSON数组："""


def extract_triplets_from_messages(messages: list, llm_call_func=None) -> list:
    """从消息列表中提取三元组"""
    if not messages or len(messages) < 3:
        return []

    # 只处理用户消息
    user_messages = [m for m in messages if m.get("role") == "user"]
    if len(user_messages) < 2:
        return []

    # 合并消息内容
    content = "\n".join([f"用户: {m['content']}" for m in user_messages[-10:]])

    # 调用 LLM 提取
    if llm_call_func is None:
        try:
            from core.llm_client import call_llm
            llm_call_func = call_llm
        except ImportError:
            logger.warning("[知识图谱] 无法导入 LLM 客户端")
            return []

    try:
        prompt = _EXTRACT_PROMPT.format(content=content)
        result = llm_call_func(prompt=prompt, temperature=0, max_tokens=500, timeout=15)

        if not result:
            return []

        # 解析 JSON
        # 尝试提取 JSON 数组
        import re
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            triplets = json.loads(json_match.group())
        else:
            triplets = json.loads(result)

        # 验证格式
        valid_triplets = []
        for t in triplets:
            if isinstance(t, dict) and "subject" in t and "predicate" in t and "object" in t:
                valid_triplets.append({
                    "subject": str(t["subject"]).strip(),
                    "predicate": str(t["predicate"]).strip(),
                    "object": str(t["object"]).strip(),
                })

        return valid_triplets

    except Exception as e:
        logger.warning(f"[知识图谱] 提取失败: {e}")
        return []


def save_triplets(triplets: list, source_msg_id=None):
    """保存三元组到数据库"""
    for t in triplets:
        try:
            add_knowledge_triplet(
                subject=t["subject"],
                predicate=t["predicate"],
                obj=t["object"],
                confidence=0.7,
                source_msg_id=source_msg_id
            )
        except Exception as e:
            logger.warning(f"[知识图谱] 保存失败: {e}")


def get_context_for_message(message: str) -> str:
    """根据用户消息获取相关的知识图谱上下文"""
    import jieba

    # 提取消息中的实体（简单分词）
    words = list(jieba.cut(message))
    entities = [w.strip() for w in words if len(w.strip()) > 1]

    if not entities:
        return ""

    # 查询相关三元组
    all_triplets = []
    for entity in entities[:5]:  # 最多查询5个实体
        triplets = query_knowledge_by_entity(entity)
        all_triplets.extend(triplets)

    if not all_triplets:
        return ""

    # 去重
    seen = set()
    unique_triplets = []
    for t in all_triplets:
        key = (t["subject"], t["predicate"], t["object"])
        if key not in seen:
            seen.add(key)
            unique_triplets.append(t)

    # 格式化
    lines = [f"{t['subject']}{t['predicate']}{t['object']}" for t in unique_triplets[:10]]
    return "【相关信息】" + "；".join(lines)
