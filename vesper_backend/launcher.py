# launcher.py — 兼容入口
# 原始文件已拆分为 launcher/ 包
# 本文件保留为入口点，调用 launcher.run()
"""兼容入口点，转发到 launcher 包的 run() 函数"""

from launcher import run

if __name__ == "__main__":
    run()