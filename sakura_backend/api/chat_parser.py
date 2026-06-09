# api/chat_parser.py  |  ThinkingParser + DSML 解析
# 从 chat.py 拆出的独立解析类，无闭包依赖

import re


class ThinkingParser:
    """解析 LLM 流式输出中的「思考...」和「回复...」结构。
    思考区域只有内部（不展示给用户），回复区域才是正式回复。
    若模型未输出回复格式，视为全部都是回复。
    """
    REPLY_MARKER = "【回复】"
    THINK_MARKER = "【思考】"

    def __init__(self):
        self.buffer = ""
        self.thinking = ""
        self.reply = ""
        self.state = "thinking"  # thinking | reply

    def feed(self, token: str) -> str | None:
        """喂入一个 token，返回应发送给用户的文本。None 表示暂不发送。"""
        self.buffer += token
        if self.state == "thinking":
            # 清除思考段的分隔符和 DSML 工具调用
            self.buffer = self.buffer.replace("<<>>", "")
            if "DSML" in self.buffer and "invoke" in self.buffer:
                # 检测到 DSML 工具调用，从 buffer 中移除
                self.buffer = re.sub(r'<＜＜DSML＞＞tool_calls>.*?</＜＜DSML＞＞tool_calls>', '', self.buffer, flags=re.DOTALL)
            idx = self.buffer.find(self.REPLY_MARKER)
            if idx != -1:
                self.thinking = self.buffer[:idx]
                self.state = "reply"
                remainder = self.buffer[idx + len(self.REPLY_MARKER):]
                if remainder:
                    self.reply = remainder
                return remainder if remainder else None
            return None
        else:
            self.reply += token
            # 清除 DSML 工具调用
            if "DSML" in self.reply and "invoke" in self.reply:
                self.reply = re.sub(r'<＜＜DSML＞＞tool_calls>.*?</＜＜DSML＞＞tool_calls>', '', self.reply, flags=re.DOTALL)
                # 重新计算 buffer 中的 reply 部分
                marker_idx = self.buffer.find(self.REPLY_MARKER)
                if marker_idx != -1:
                    self.buffer = self.buffer[:marker_idx + len(self.REPLY_MARKER)] + self.reply
                return None  # 暂不发送，等 DSML 清除完
            return token

    def fallback_check(self) -> bool:
        """检查是否需要兜底（buffer 超长但未找到分隔符）"""
        return self.state == "thinking" and len(self.buffer) > 1000 and self.REPLY_MARKER not in self.buffer

    def extract_reply_from_buffer(self) -> str:
        """兜底提取：从整个 buffer 中提取回复内容（跳过思考标记和 DSML）"""
        text = self.buffer.strip()
        if not text:
            return ""
        # 移除 DSML 工具调用
        if "DSML" in text:
            text = re.sub(r'<＜＜DSML＞＞tool_calls>.*?</＜＜DSML＞＞tool_calls>', '', text, flags=re.DOTALL).strip()
        # 提取最后一个段落
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if paragraphs:
            last = paragraphs[-1]
            # 如果最后一段太短，取倒数第二段
            if len(last) < 20 and len(paragraphs) >= 2:
                last = paragraphs[-2] + "\n" + last
            return last
        return text

    def extract_demand(self) -> dict | None:
        """从思考区域提取需求层级信息"""
        thinking = self.thinking
        if not thinking:
            return None
        level_match = re.search(r'需求层级[：:]\s*(.+)', thinking)
        emotion_match = re.search(r'用户情绪[：:]\s*(.+)', thinking)
        latent_match = re.search(r'潜在需求[：:]\s*(.+)', thinking)
        strategy_match = re.search(r'回复策略[：:]\s*(.+)', thinking)
        return {
            "level": level_match.group(1).strip() if level_match else "UNKNOWN",
            "emotion": emotion_match.group(1).strip() if emotion_match else "",
            "latent": latent_match.group(1).strip() if latent_match else "",
            "strategy": strategy_match.group(1).strip() if strategy_match else "",
            "thinking_full": thinking.strip()[:500]
        }