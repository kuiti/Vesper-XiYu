# core/vector_store.py — 兼容 shim
# 原始文件已拆分为 core/vector_store/ 包
# 本文件保留为向后兼容，使旧的 import 路径继续可用
# 例如: from core.vector_store import search_similar  仍然可用（通过包的 __init__.py）
#
# 注意: 当同目录下存在 vector_store/ 包（即 vector_store/__init__.py）时，
# Python 的 import 机制会优先加载包，本文件实际上不会被 import 系统使用。
# 保留此文件仅为文档参考，可安全删除。

from core.vector_store import *  # noqa: F401,F403