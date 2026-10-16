# -*- coding: utf-8 -*-
"""Xbrain MCPO 代理：XMind MCP (OAuth 2.1) → OpenAPI (Bearer)
- /oauth/authorize  引导用户到 XMind 授权页（PKCE S256）
- /oauth/callback   授权回调，换取并保存 token
- /mcp              通用 JSON-RPC 转发（Bearer 保护）
- /tools/{name}     按XMind MCP工具动态生成的 OpenAPI 端点（Bearer 保护）
- /openapi.json     OpenAPI 描述（Open WebUI Tool Server 使用）
- /health           健康检查（watchdog 用）
"""
import json, secrets, hashlib, base64, time, logging, os, re
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
TOKENS_PATH = os.path.join(BASE, "tokens.json")
LOG_PATH = os.path.join(BASE, "proxy.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("xbrain-proxy")

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

BEARER_TOKEN = CONFIG["bearer_token"]
PORT = CONFIG.get("port", 8765)
UPSTREAM = CONFIG.get("mcp_endpoint", "https://app.xmind.com/api/mcp")
OAUTH_META_URL = CONFIG.get("oauth_metadata", "https://app.xmind.com/.well-known/oauth-authorization-server")
SCOPE = CONFIG.get("scope", "mcp:connect")

security = HTTPBearer(auto_error=False)
_oauth_meta: Optional[dict] = None
_pending_auth: dict = {}   # state -> code_verifier
_mcp_session: Optional[str] = None
_tools_cache: Optional[list] = None
_tools_cache_ts: float = 0


def verify_bearer(cred: HTTPAuthorizationCredentials = Depends(security)):
    if cred is None or cred.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing Bearer token")
    return True


def load_tokens() -> Optional[dict]:
    if not os.path.exists(TOKENS_PATH):
        return None
    try:
        with open(TOKENS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_tokens(t: dict):
    now = time.time()
    t["expires_at"] = now + int(t.get("expires_in", 3600)) - 60
    t["saved_at"] = now
    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=2)
    os.chmod(TOKENS_PATH, 0o600)


async def oauth_meta() -> dict:
    global _oauth_meta
    if _oauth_meta is None:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(OAUTH_META_URL)
            r.raise_for_status()
            _oauth_meta = r.json()
    return _oauth_meta


async def get_access_token() -> str:
    """返回有效 access token，必要时自动刷新。"""
    tokens = load_tokens()
    if not tokens:
        raise HTTPException(status_code=409, detail="XMind 未授权：请先打开 http://127.0.0.1:%d/oauth/authorize 完成授权" % PORT)
    if time.time() < tokens.get("expires_at", 0):
        return tokens["access_token"]
    meta = await oauth_meta()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(meta["token_endpoint"], data={
            "grant_type": "refresh_token",
            "refresh_token": tokens.get("refresh_token", ""),
            "client_id": CONFIG["client_id"],
            "scope": SCOPE,
        })
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="token 刷新失败，请重新授权: %s" % r.text[:300])
    new = r.json()
    new.setdefault("refresh_token", tokens.get("refresh_token"))
    save_tokens(new)
    log.info("XMind access token 已刷新")
    return new["access_token"]


def parse_rpc_response(r: httpx.Response, want_id: Any) -> Any:
    """兼容 JSON 与 SSE 两种响应格式，取出匹配 id 的 JSON-RPC 结果。"""
    ctype = r.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in r.text.splitlines():
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:].strip())
                except Exception:
                    continue
                if obj.get("id") == want_id:
                    return obj
        raise HTTPException(status_code=502, detail="上游 SSE 响应中未找到匹配结果")
    obj = r.json()
    if obj.get("id") == want_id:
        return obj
    return obj


# openapi_url=None：禁用内置 /openapi.json（否则会遮蔽下方自定义动态端点）
app = FastAPI(title="Xbrain MCPO Proxy", version="1.0", openapi_url=None, docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
async def index():
    authorized = load_tokens() is not None
    status = "✅ 已授权" if authorized else "⏳ 待授权"
    return HTMLResponse(f"""<html><body style="font-family:sans-serif;max-width:640px;margin:60px auto">
<h2>Xbrain MCPO Proxy</h2>
<p>XMind OAuth 状态：{status}</p>
<p><a href="/oauth/authorize">点击这里完成 XMind 授权</a>（若未授权）</p>
<p>OpenAPI 文档：<a href="/openapi.json">/openapi.json</a> ｜ <a href="/docs">/docs</a></p>
<p>Open WebUI Tool Server 配置：URL <code>http://127.0.0.1:{PORT}</code>，Auth: Bearer（token 见 mcp_proxy/config.json）</p>
</body></html>""")


@app.get("/health")
async def health():
    return {"ok": True, "authorized": load_tokens() is not None, "uptime_ts": time.time()}


@app.get("/oauth/authorize")
async def oauth_authorize():
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _pending_auth[state] = verifier
    meta = await oauth_meta()
    params = {
        "response_type": "code",
        "client_id": CONFIG["client_id"],
        "redirect_uri": CONFIG["redirect_uri"],
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    from urllib.parse import urlencode
    url = meta["authorization_endpoint"] + "?" + urlencode(params)
    return RedirectResponse(url)


@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    err = request.query_params.get("error")
    if err:
        return HTMLResponse(f"<h3>授权失败：{err}</h3><p>{request.query_params.get('error_description','')}</p>", status_code=400)
    verifier = _pending_auth.pop(state, None)
    if not verifier or not code:
        return HTMLResponse("<h3>回调无效（state 不匹配或缺 code）</h3><p>请重新从 <a href='/oauth/authorize'>/oauth/authorize</a> 发起授权。</p>", status_code=400)
    meta = await oauth_meta()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(meta["token_endpoint"], data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CONFIG["redirect_uri"],
            "client_id": CONFIG["client_id"],
            "code_verifier": verifier,
        })
    if r.status_code != 200:
        log.error("token 交换失败: %s", r.text[:500])
        return HTMLResponse(f"<h3>token 交换失败</h3><pre>{r.text[:800]}</pre>", status_code=502)
    save_tokens(r.json())
    global _tools_cache
    _tools_cache = None
    log.info("XMind OAuth 授权成功")
    return HTMLResponse("<h3>✅ XMind 授权成功！token 已保存。</h3><p>可以关闭此页面，返回 Open WebUI 完成 Tool Server 配置。</p>")


async def mcp_post(payload: dict, session: Optional[str] = None) -> httpx.Response:
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["mcp-session-id"] = session
    async with httpx.AsyncClient(timeout=60) as c:
        return await c.post(UPSTREAM, json=payload, headers=headers)


@app.post("/mcp", dependencies=[Depends(verify_bearer)])
async def mcp_forward(request: Request):
    """通用 JSON-RPC 转发：透传客户端的 mcp-session-id。"""
    body = await request.json()
    sess = request.headers.get("mcp-session-id")
    r = await mcp_post(body, sess)
    resp_headers = {}
    if "mcp-session-id" in r.headers:
        resp_headers["mcp-session-id"] = r.headers["mcp-session-id"]
    return ResponseLike(r, resp_headers)


class ResponseLike(JSONResponse):
    def __init__(self, r: httpx.Response, headers: dict):
        content = r.text
        super().__init__(content=content, status_code=r.status_code, headers=headers)


@app.post("/mcp/session/init", dependencies=[Depends(verify_bearer)])
async def mcp_session_init():
    """初始化并缓存 MCP 会话，返回服务器信息。"""
    global _mcp_session
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "xbrain-proxy", "version": "1.0"},
        },
    }
    r = await mcp_post(payload)
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="XMind token 无效，请重新授权")
    if "mcp-session-id" in r.headers:
        _mcp_session = r.headers["mcp-session-id"]
    await mcp_post({"jsonrpc": "2.0", "method": "notifications/initialized"}, _mcp_session)
    return parse_rpc_response(r, 1)


async def ensure_session() -> Optional[str]:
    global _mcp_session
    if not _mcp_session:
        await mcp_session_init()
    return _mcp_session


async def list_tools(force: bool = False) -> list:
    global _tools_cache, _tools_cache_ts
    if not force and _tools_cache and time.time() - _tools_cache_ts < 600:
        return _tools_cache
    sess = await ensure_session()
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    r = await mcp_post(payload, sess)
    obj = parse_rpc_response(r, 2)
    if "error" in obj:
        raise HTTPException(status_code=502, detail=str(obj["error"])[:500])
    _tools_cache = obj.get("result", {}).get("tools", [])
    _tools_cache_ts = time.time()
    return _tools_cache


@app.post("/mcp/tools/list", dependencies=[Depends(verify_bearer)])
async def tools_list():
    try:
        tools = await list_tools(force=True)
        return {"tools": [{"name": t.get("name"), "description": (t.get("description") or "")[:200]} for t in tools]}
    except HTTPException as e:
        if e.status_code == 409:
            return JSONResponse(status_code=409, content={"detail": e.detail})
        raise


@app.post("/tools/{tool_name}", dependencies=[Depends(verify_bearer)])
async def call_tool(tool_name: str, request: Request):
    """调用 XMind MCP 工具，body 即工具参数（JSON 对象）。"""
    arguments = await request.json()
    if not isinstance(arguments, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
    sess = await ensure_session()
    payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": tool_name, "arguments": arguments}}
    r = await mcp_post(payload, sess)
    if r.status_code in (404, 400):
        # 会话失效，重建后重试一次
        global _mcp_session
        _mcp_session = None
        sess = await ensure_session()
        r = await mcp_post(payload, sess)
    obj = parse_rpc_response(r, 3)
    if "error" in obj:
        raise HTTPException(status_code=502, detail=str(obj["error"])[:500])
    return obj.get("result", obj)


def sanitize(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", name)


@app.get("/openapi.json")
async def openapi_spec():
    """动态生成 OpenAPI：XMind 工具各成一个端点；未授权时仅含通用端点。"""
    paths: dict = {}
    def add_post(path: str, op_id: str, summary: str, schema: dict | None = None):
        body_schema = schema or {"type": "object", "additionalProperties": True}
        paths[path] = {
            "post": {
                "summary": summary[:120],
                "operationId": op_id,
                "security": [{"bearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": body_schema}}},
                "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}},
            }
        }
    add_post("/mcp", "mcp_raw_call", "通用 XMind MCP JSON-RPC 转发")
    try:
        tools = await list_tools()
        for t in tools:
            name = t.get("name", "")
            desc = (t.get("description") or name).strip()
            add_post(f"/tools/{name}", f"xmind_{sanitize(name)}", f"XMind: {desc}", t.get("inputSchema"))
    except Exception as e:
        log.info("openapi 生成：工具列表暂不可用（%s），仅暴露通用端点", str(e)[:120])
    return {
        "openapi": "3.1.0",
        "info": {"title": "Xbrain MCPO Proxy (XMind MCP)", "version": "1.0.0"},
        "servers": [{"url": f"http://127.0.0.1:{PORT}"}],
        "paths": paths,
        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearerAuth": []}],
    }
