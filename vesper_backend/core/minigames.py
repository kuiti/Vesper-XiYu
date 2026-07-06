# core/minigames.py — 内置小游戏
"""猜谜、成语接龙、快问快答等内置迷你游戏"""
import random
import threading


class GameBase:
    """游戏基类，管理运行状态"""
    def __init__(self):
        self.running = False


class GuessGame(GameBase):
    """文字猜谜游戏"""
    def __init__(self):
        super().__init__()
        self.riddles = [
            {"q": "什么东西越洗越脏？", "a": "水"},
            {"q": "什么东西不能吃？", "a": "亏"},
            {"q": "什么门关不上？", "a": "球门"},
            {"q": "什么书买不到？", "a": "遗书"},
            {"q": "什么水不能喝？", "a": "薪水"},
            {"q": "什么蛋不能吃？", "a": "笨蛋"},
            {"q": "什么路最窄？", "a": "冤家路窄"},
            {"q": "什么照片看不出照的是谁？", "a": "X光片"},
        ]
        self.current = None

    def start(self) -> str:
        """随机选一道谜题并开始游戏"""
        self.running = True
        self.current = random.choice(self.riddles)
        return f"猜谜开始！{self.current['q']}"

    def check(self, answer: str) -> str:
        """校验用户答案是否正确"""
        if not self.running:
            return "没有进行中的游戏"
        if answer.strip() == self.current['a']:
            self.running = False
            return "答对了！🎉"
        return "不对哦，再想想~"


class IdiomGame(GameBase):
    """成语接龙游戏"""
    def __init__(self):
        super().__init__()
        self.last_word = ""
        self.idioms = [
            "一心一意", "意气风发", "发扬光大", "大器晚成", "成竹在胸",
            "胸有成竹", "竹报平安", "安居乐业", "业精于勤", "勤学苦练",
        ]

    def start(self) -> str:
        """随机选择一个成语开始接龙"""
        self.running = True
        self.last_word = random.choice(self.idioms)
        return f"成语接龙开始！我说：{self.last_word}"

    def check(self, word: str) -> str:
        """校验用户接的成语是否以最后一个字开头"""
        if not self.running:
            return "没有进行中的游戏"
        if not word or word[0] != self.last_word[-1]:
            return f"要以「{self.last_word[-1]}」开头哦"
        self.last_word = word
        return f"接得好！该我了……{word}（你的回合）"


class QuickQuiz(GameBase):
    """快问快答游戏"""
    def __init__(self):
        super().__init__()
        self.questions = [
            {"q": "1+1=?", "a": "2"},
            {"q": "太阳从哪边升起？", "a": "东"},
            {"q": "一年有几个月？", "a": "12"},
            {"q": "一周有几天？", "a": "7"},
            {"q": "中国有多少个省？", "a": "34"},
        ]
        self.current = None

    def start(self) -> str:
        """随机选一道题目并开始游戏"""
        self.running = True
        self.current = random.choice(self.questions)
        return f"快问快答！{self.current['q']}"

    def check(self, answer: str) -> str:
        """校验用户答案，答错时显示正确答案"""
        if not self.running:
            return "没有进行中的游戏"
        if answer.strip() == self.current['a']:
            self.running = False
            return "答对了！⚡"
        return f"不对哦，答案是「{self.current['a']}」"


# 游戏名称 → 游戏类的映射
GAMES = {
    "猜谜": GuessGame,
    "成语": IdiomGame,
    "快问快答": QuickQuiz,
}

_active_games = {}
_games_lock = threading.Lock()


def get_game(name: str):
    """获取或创建指定名称的游戏实例（线程安全单例）"""
    cls = GAMES.get(name)
    if not cls:
        return None
    with _games_lock:
        if name not in _active_games:
            _active_games[name] = cls()
        return _active_games[name]


def list_games() -> list:
    """返回所有可用游戏名称列表"""
    return list(GAMES.keys())
