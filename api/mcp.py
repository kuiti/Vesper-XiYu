"""MCP JSON-RPC 2.0 端点 —— 为外部 MCP 客户端提供标准工具调用接口"""

from fastapi import APIRouter, Request
from core.mcp_tools import TOOLS, call_tool

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.post("/")
async def mcp_endpoint(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}
    method = body.get("method", "")
    req_id = body.get("id")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "result": {"tools": TOOLS}, "id": req_id}

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result_text = call_tool(tool_name, arguments)
        return {
            "jsonrpc": "2.0",
            "result": {"content": [{"type": "text", "text": result_text}]},
            "id": req_id
        }

    return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Unknown method: {method}"}, "id": req_id}
