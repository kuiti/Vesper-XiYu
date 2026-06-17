"""SQLite MCP Server — 让 Claude Code 直接查询佐仓数据库"""
import sqlite3
import os
from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("SAKURA_DB", "H:/my_cc_ai/data/sakura.db")

mcp = FastMCP("sakura-sqlite")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.text_factory = str
    return conn


@mcp.tool()
def query(sql: str) -> str:
    """执行只读 SQL 查询。仅允许 SELECT 语句。返回结果表格。"""
    sql_stripped = sql.strip().rstrip(";")
    sql_upper = sql_stripped.upper()
    if not sql_upper.startswith("SELECT"):
        return "错误：仅允许 SELECT 查询"
    _dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "EXEC", "UNION",
                  "ATTACH", "DETACH", "PRAGMA", "REPLACE", "VACUUM", "LOAD_EXTENSION"]
    import re as _re
    for kw in _dangerous:
        if _re.search(r'\b' + kw + r'\b', sql_upper):
            return f"错误：不允许包含 {kw} 关键词"
    if ";" in sql_stripped:
        return "错误：不允许堆叠查询（分号）"
    # 防止注释绕过（-- 和 /* */）
    if "--" in sql_stripped or "/*" in sql_stripped:
        return "错误：不允许 SQL 注释"

    conn = _get_conn()
    try:
        cur = conn.execute(sql_stripped)
        rows = cur.fetchall()
        if not rows:
            return "(空结果)"
        cols = [d[0] for d in cur.description]
        lines = ["\t".join(cols)]
        for row in rows:
            lines.append("\t".join(str(v)[:200] if v else "" for v in row))
        return "\n".join(lines[:50])
    except Exception as e:
        return f"查询失败: {e}"
    finally:
        conn.close()


@mcp.tool()
def list_tables() -> str:
    """列出数据库中所有表名"""
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        return "\n".join(tables) if tables else "(无表)"
    finally:
        conn.close()


@mcp.tool()
def describe_table(name: str) -> str:
    """查看指定表的完整 CREATE TABLE 语句"""
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,))
        row = cur.fetchone()
        return row[0] if row and row[0] else f"表 '{name}' 不存在或无 schema"
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
