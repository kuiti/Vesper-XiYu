#!/usr/bin/env python3
# version: 1.0.0
"""佐仓云端服务器入口 — 用于部署到云服务器"""
import os
import sys
import signal
import uvicorn

# ─── 环境变量配置 ───
# SAKURA_HOST: 绑定地址，默认 0.0.0.0
# SAKURA_PORT: 端口，默认 8060
# SAKURA_API_TOKEN: 访问令牌（必须设置）
# SAKURA_SSL_CERT: SSL 证书路径（可选）
# SAKURA_SSL_KEY: SSL 私钥路径（可选）
# SAKURA_DATA_DIR: 数据目录，默认 data


def main():
    host = os.environ.get("SAKURA_HOST", "0.0.0.0")
    port = int(os.environ.get("SAKURA_PORT", "8060"))
    token = os.environ.get("SAKURA_API_TOKEN", "")
    ssl_cert = os.environ.get("SAKURA_SSL_CERT", "")
    ssl_key = os.environ.get("SAKURA_SSL_KEY", "")
    data_dir = os.environ.get("SAKURA_DATA_DIR", "data")

    # ─── 检查 Token ───
    if not token:
        print("=" * 50)
        print("错误: 云端模式必须设置 SAKURA_API_TOKEN")
        print("")
        print("启动命令:")
        print("  SAKURA_API_TOKEN=你的密码 python3 cloud_server.py")
        print("")
        print("或写入 .env 文件:")
        print("  echo 'SAKURA_API_TOKEN=你的密码' > .env")
        print("=" * 50)
        sys.exit(1)

    # ─── 初始化数据目录 ───
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "avatars"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "chroma_db"), exist_ok=True)

    # ─── 设置工作目录 ───
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 50)
    print(f"  佐仓云端服务器")
    print(f"  地址: {host}:{port}")
    print(f"  数据目录: {data_dir}")
    print(f"  HTTPS: {'是' if ssl_cert else '否'}")
    print("=" * 50)

    # ─── SSL 配置 ───
    ssl_kwargs = {}
    if ssl_cert and ssl_key:
        ssl_kwargs["ssl_certfile"] = ssl_cert
        ssl_kwargs["ssl_keyfile"] = ssl_key

    # ─── 启动 ───
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
