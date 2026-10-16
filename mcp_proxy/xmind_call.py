# -*- coding: utf-8 -*-
"""通过 MCPO 代理调用 XMind MCP 工具的命令行助手
用法: python xmind_call.py <tool_name> [参数JSON文件或'-'表示空参数]
"""
import json, sys, urllib.request, urllib.error, os

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
    TOKEN = json.load(f)["bearer_token"]

def call(tool: str, arguments: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:8765/tools/{tool}",
        method="POST",
        data=json.dumps(arguments).encode("utf-8"),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_detail": e.read().decode("utf-8")[:500]}

if __name__ == "__main__":
    tool = sys.argv[1]
    args = {}
    if len(sys.argv) > 2 and sys.argv[2] != "-":
        with open(sys.argv[2], encoding="utf-8") as f:
            args = json.load(f)
    out = call(tool, args)
    # 只提取 text 内容，便于阅读
    if isinstance(out, dict) and "content" in out:
        for c in out["content"]:
            if c.get("type") == "text":
                print(c["text"])
        if out.get("isError"):
            sys.exit(1)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))
