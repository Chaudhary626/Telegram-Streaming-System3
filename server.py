"""
TG Stream Server — Multi-Tenant Streaming Platform v2.0

Features: Secure admin (secret path), multi-payment gateway,
manual payment verification, hierarchical content (Content→Season→Episode),
inline bot buttons, subscription request system.
MTProto streaming (NO Bot API getFile, NO 20MB limit).
"""
import re, time, hmac, hashlib, urllib.request, logging, secrets, traceback
from typing import Optional
from html import escape as he
from collections import defaultdict

import bcrypt
from fastapi import FastAPI, Request, HTTPException, Form, Response
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from urllib.parse import quote as url_quote

from config import (
    API_ID, API_HASH, BOT_TOKEN, CHANNEL_ID,
    STREAM_SECRET, STREAM_HOST, STREAM_PORT,
    STREAM_BASE_URL, TOKEN_LIFETIME, CHUNK_SIZE,
    ALLOWED_ORIGINS, ADMIN_PASSWORD, MAIN_ADMIN_TELEGRAM_ID,
    ADMIN_SECRET_PATH,
    validate as validate_config,
)
from streamer import TelegramStreamer
import database as db
from player import WATCH_PAGE, EMBED_PAGE
from admin_templates import admin_login, admin_page
from panel_templates import panel_login, panel_page, panel_embed_code

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("tg-stream")

tg_client = Client(name="stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True, no_updates=False)
streamer: Optional[TelegramStreamer] = None

app = FastAPI(title="TG Stream Server", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_methods=["GET","HEAD","OPTIONS","POST"], allow_headers=["Range","Content-Type"],
    expose_headers=["Content-Range","Content-Length","Accept-Ranges","Content-Type"])

BASE = lambda: STREAM_BASE_URL or f"http://localhost:{STREAM_PORT}"
AP = ADMIN_SECRET_PATH  # Short alias for admin path prefix

# ── Helpers ──────────────────────────────────────────────────

def _sign(payload): return hmac.new(STREAM_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
def _make_stream_url(file_id, file_size=0):
    exp = int(time.time()) + TOKEN_LIFETIME
    return f"{BASE()}/stream/{url_quote(file_id)}?token={_sign(f'{file_id}:{exp}:{file_size}')}&expires={exp}&size={file_size}"
def _validate_stream_token(file_id, token, expires, file_size=0):
    if not token or not expires or time.time() > expires: return False
    return hmac.compare_digest(token, _sign(f"{file_id}:{expires}:{file_size}"))
def _admin_cookie(): return _sign(f"admin:{ADMIN_PASSWORD}")[:48]
def _panel_cookie(tg_id): return _sign(f"panel:{tg_id}")[:48]
def _is_admin(r): return r.cookies.get("admin_token") == _admin_cookie()
def _get_panel_user(r):
    tg_id = r.cookies.get("panel_tg_id","")
    tok = r.cookies.get("panel_token","")
    if tg_id and tok and tok == _panel_cookie(tg_id):
        user = db.get_user(int(tg_id))
        if user and user.get("is_active"): return user
    return None
def _slugify(t):
    s = re.sub(r'[^a-z0-9\s-]', '', t.lower().strip())
    return re.sub(r'[\s-]+', '-', s).strip('-')[:200]
def _fmt_size(b):
    if not b: return "—"
    if b >= 1073741824: return f"{b/1073741824:.2f} GB"
    if b >= 1048576: return f"{b/1048576:.1f} MB"
    return f"{b/1024:.0f} KB"
def _detect_quality(w, h):
    r = min(w,h) if w>0 and h>0 else max(w,h)
    if r>=2160: return "2160p"
    if r>=1080: return "1080p"
    if r>=720: return "720p"
    return "480p"
def _flash(msg): return f'<div class="flash flash-ok">{he(str(msg))}</div>' if msg else ""
def _hash_pw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
def _check_pw(pw, h):
    try: return bcrypt.checkpw(pw.encode(), h.encode())
    except: return False

def _admin_html(body, title="Dashboard", active="dashboard"):
    pending = 0
    try: pending = db.count_pending_requests()
    except: pass
    return HTMLResponse(admin_page(body, title, active, admin_path=AP, pending_requests=pending))
def _panel_html(body, user, title="Dashboard", active="dashboard"):
    plan = user.get("plan_name") or "Free"
    return HTMLResponse(panel_page(body, plan, title, active))

# ── Rate limiter ──────────────────────────────────────────────
_login_attempts = defaultdict(list)
def _rate_limited(ip, max_attempts=5, window=900):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < window]
    if len(_login_attempts[ip]) >= max_attempts: return True
    _login_attempts[ip].append(now)
    return False

# ── Global exception handler ────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}\n{traceback.format_exc()}")
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Error</title>
<style>body{{background:#0d0d1a;color:#d0d0e8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#141425;border:1px solid #2a2a48;border-radius:16px;padding:40px;max-width:500px;text-align:center}}
h1{{color:#ef4444;font-size:1.3rem}}p{{color:#7777aa;margin-top:12px}}</style></head><body>
<div class="card"><h1>⚠️ Server Error</h1><p>{he(str(exc))}</p><p style="margin-top:16px"><a href="/" style="color:#a78bfa">Home</a></p></div>
</body></html>""", status_code=500)

# ═══════════════════════════════════════════════════════════════
# ROOT + HEALTH
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return JSONResponse({"service": "TG Stream Server", "status": "running", "version": "2.0"})

@app.get("/health")
async def health():
    c = tg_client.is_connected if tg_client else False
    return JSONResponse({"status":"ok" if c else "degraded", "telegram":"connected" if c else "disconnected",
        "protocol":"MTProto (NO getFile)", "max_file":"4GB"})

# ── Block old /admin path ────────────────────────────────────
@app.get("/admin")
@app.get("/admin/{path:path}")
async def block_old_admin(path: str = ""):
    raise HTTPException(404)

# ═══════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    global streamer
    errors = validate_config()
    if errors:
        for e in errors: logger.error(f"Config: {e}")
        return
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=false", timeout=10)
    except: pass
    _register_bot_handlers()
    await tg_client.start()
    streamer = TelegramStreamer(tg_client)
    try:
        db.ensure_tables()
        db.seed_default_plans()
        if MAIN_ADMIN_TELEGRAM_ID:
            db.create_main_admin(MAIN_ADMIN_TELEGRAM_ID, "", _hash_pw(ADMIN_PASSWORD))
    except Exception as e:
        logger.warning(f"DB init: {e}")
    me = await tg_client.get_me()
    logger.info(f"Started | Bot: @{me.username} | Admin: /{AP} | MTProto: ON | Port: {STREAM_PORT}")

@app.on_event("shutdown")
async def shutdown():
    if tg_client.is_connected: await tg_client.stop()

# ═══════════════════════════════════════════════════════════════
# /stream/{file_id} — MTProto streaming
# ═══════════════════════════════════════════════════════════════

@app.get("/stream/{file_id}")
async def stream_video(file_id: str, request: Request, token: str="", expires: int=0, size: int=0):
    if not streamer: raise HTTPException(503)
    if not _validate_stream_token(file_id, token, expires, size): raise HTTPException(403)
    file_size = size
    if not file_size:
        vid = db.get_video_by_file_id(file_id)
        if vid: file_size = vid.get("file_size",0) or 0
        if not file_size:
            try: file_size = await streamer.get_file_size(file_id)
            except: pass
    else:
        streamer.cache_file_size(file_id, file_size)
    rng = request.headers.get("range","")
    start, end, is_range = 0, (file_size-1 if file_size else None), False
    if rng and file_size:
        is_range = True
        parts = rng.replace("bytes=","").split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts)>1 and parts[1] else file_size-1
    clen = (end-start+1) if end is not None else None
    hdrs = {"Content-Type":"video/mp4","Accept-Ranges":"bytes","Cache-Control":"no-store","X-Stream-Method":"mtproto"}
    if file_size and clen: hdrs["Content-Length"]=str(clen)
    if is_range and file_size: hdrs["Content-Range"]=f"bytes {start}-{end}/{file_size}"
    async def gen():
        try:
            async for chunk in streamer.stream(file_id, offset=start, end=end): yield chunk
        except Exception as e: logger.error(f"Stream err: {e}")
    return StreamingResponse(gen(), status_code=206 if is_range else 200, headers=hdrs, media_type="video/mp4")

@app.head("/stream/{file_id}")
async def stream_head(file_id: str, token: str="", expires: int=0, size: int=0):
    if not _validate_stream_token(file_id, token, expires, size): raise HTTPException(403)
    hdrs = {"Content-Type":"video/mp4","Accept-Ranges":"bytes"}
    if size: hdrs["Content-Length"]=str(size)
    return Response(headers=hdrs)

# ═══════════════════════════════════════════════════════════════
# /watch + /embed — Smart player
# ═══════════════════════════════════════════════════════════════

@app.get("/watch/{slug}", response_class=HTMLResponse)
async def watch_page_route(slug: str, request: Request):
    content = db.get_content_by_slug(slug)
    if not content: raise HTTPException(404)
    base = BASE()
    try: db.log_view(content["id"], owner_id=content["owner_id"],
        ip_hash=hashlib.md5((request.client.host or "").encode()).hexdigest()[:16],
        user_agent=(request.headers.get("user-agent") or "")[:255])
    except: pass
    return HTMLResponse(WATCH_PAGE.format(title=he(content["title"]), slug=slug,
        api_sources_url=f"{base}/api/sources/{url_quote(slug)}",
        api_ads_url=f"{base}/api/ads/{content['owner_id']}"))

@app.get("/embed/{slug}", response_class=HTMLResponse)
async def embed_page_route(slug: str):
    content = db.get_content_by_slug(slug)
    if not content: raise HTTPException(404)
    base = BASE()
    return HTMLResponse(EMBED_PAGE.format(
        api_sources_url=f"{base}/api/sources/{url_quote(slug)}",
        api_ads_url=f"{base}/api/ads/{content['owner_id']}"))

@app.get("/api/sources/{slug}")
async def api_sources(slug: str):
    content = db.get_content_by_slug(slug)
    if not content: return JSONResponse({"success":False}, 404)
    sources = db.get_sources_by_content(content["id"])
    return JSONResponse({"success":True, "title":content["title"], "slug":slug,
        "sources": [{"language":s["language"],"quality":s["quality"],
            "url":_make_stream_url(s["file_id"], s["file_size"] or 0),
            "file_size":s["file_size"] or 0, "duration":s["duration"] or 0,
            "label":s["label"] or f"{s['language']} {s['quality']}"} for s in sources]})

@app.get("/api/ads/{owner_id}")
async def api_ads(owner_id: int):
    ads = db.get_active_ads_by_owner(owner_id)
    return JSONResponse([{"ad_type":a["ad_type"],"ad_url":a["ad_url"],"ad_html":a["ad_html"],
        "position":a["position"],"duration":a["duration"],"is_active":True} for a in ads])

# ═══════════════════════════════════════════════════════════════
# ADMIN PANEL (/{AP}/*)  — SECURED WITH SECRET PATH
# ═══════════════════════════════════════════════════════════════

@app.get(f"/{AP}/login", response_class=HTMLResponse)
async def admin_login_page(): return HTMLResponse(admin_login())

@app.post(f"/{AP}/login")
async def admin_login_post(request: Request, password: str = Form(...)):
    ip = request.client.host or "unknown"
    if _rate_limited(ip):
        db.log_activity(0, "admin_login_blocked", f"Rate limited IP: {ip}", ip)
        return HTMLResponse(admin_login("Too many attempts. Try again in 15 minutes."), 429)
    if password != ADMIN_PASSWORD:
        db.log_activity(0, "admin_login_fail", f"IP: {ip}", ip)
        return HTMLResponse(admin_login("Wrong password"), 401)
    db.log_activity(0, "admin_login_ok", f"IP: {ip}", ip)
    r = RedirectResponse(f"/{AP}", 303)
    r.set_cookie("admin_token", _admin_cookie(), httponly=True, max_age=14400)  # 4 hours
    return r

@app.get(f"/{AP}")
async def admin_dashboard(request: Request):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    users = db.list_users()
    stats = db.get_view_stats_global()
    content = db.list_all_content()
    pending = 0
    try: pending = db.count_pending_requests()
    except: pass
    user_rows = ""
    for u in users[:10]:
        uname = he(u.get("username","") or "—")
        tid = u["telegram_id"]
        pn = u.get("plan_name") or "Free"
        cc = u.get("content_count", 0)
        ca = u["created_at"]
        user_rows += f'<tr><td><a href="/{AP}/users/{tid}" style="color:#a78bfa;text-decoration:none">@{uname}</a><br><span class="mono">{tid}</span></td><td><span class="badge badge-acc">{pn}</span></td><td>{cc}</td><td>{ca}</td></tr>'
    pending_html = f'<div class="card stat" style="border:1px solid #f59e0b"><div class="stat-value" style="color:#f59e0b">{pending}</div><div class="stat-label">Pending Requests</div></div>' if pending else '<div class="card stat"><div class="stat-value">0</div><div class="stat-label">Pending Requests</div></div>'
    body = f"""<h1>📊 Main Admin Dashboard</h1>
    <div class="grid">
      <div class="card stat"><div class="stat-value">{len(users)}</div><div class="stat-label">Users</div></div>
      <div class="card stat"><div class="stat-value">{len(content)}</div><div class="stat-label">Content</div></div>
      <div class="card stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total Views</div></div>
      {pending_html}
    </div>
    <div class="card"><h3 style="margin-bottom:12px">Recent Users</h3>
    <table><tr><th>User</th><th>Plan</th><th>Content</th><th>Joined</th></tr>{user_rows}</table></div>"""
    return _admin_html(body, "Dashboard", "dashboard")

# ── Admin: Users ─────────────────────────────────────────────

@app.get(f"/{AP}/users")
async def admin_users(request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    users = db.list_users()
    plans = db.list_plans()
    plan_opts = "".join(f'<option value="{p["slug"]}">{he(p["name"])}</option>' for p in plans)
    rows = ""
    for u in users:
        tid = u["telegram_id"]
        uname = he(u.get("username","") or "—")
        pn = u.get("plan_name") or "Free"
        cc = u.get("content_count", 0)
        exp = str(u.get("plan_expires") or "Never")[:10]
        st = '<span class="badge badge-ok">Active</span>' if u["is_active"] else '<span class="badge badge-err">Banned</span>'
        rows += f'<tr><td><a href="/{AP}/users/{tid}" style="color:#a78bfa;text-decoration:none">@{uname}</a><br><span class="mono">{tid}</span></td>'
        rows += f'<td><span class="badge badge-acc">{pn}</span><br><span class="mono" style="font-size:.7rem">{exp}</span></td><td>{cc}</td><td>{st}</td><td>'
        rows += f'<form method="POST" action="/{AP}/users/{tid}/plan" style="display:inline">'
        rows += f'<select name="plan_slug" style="width:80px;padding:3px;font-size:.75rem;background:#1c1c35;color:#d0d0e8;border:1px solid #2a2a48;border-radius:4px">{plan_opts}</select>'
        rows += ' <button class="btn btn-primary btn-sm">Set</button></form> '
        if u["is_active"]:
            rows += f'<form method="POST" action="/{AP}/users/{tid}/ban" style="display:inline"><button class="btn btn-danger btn-sm">Ban</button></form>'
        else:
            rows += f'<form method="POST" action="/{AP}/users/{tid}/unban" style="display:inline"><button class="btn btn-ok btn-sm">Unban</button></form>'
        rows += '</td></tr>'
    body = f'<h1>👤 User Management ({len(users)} users)</h1>{_flash(msg)}<table><tr><th>User</th><th>Plan / Expires</th><th>Content</th><th>Status</th><th>Actions</th></tr>{rows}</table>'
    return _admin_html(body, "Users", "users")

@app.get(f"/{AP}/users/{{tg_id}}")
async def admin_user_detail(tg_id: int, request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    user = db.get_user(tg_id)
    if not user: raise HTTPException(404, "User not found")
    plans = db.list_plans()
    stats = db.get_view_stats_by_owner(tg_id)
    cc = db.count_content_by_owner(tg_id)
    plan_opts = "".join(f'<option value="{p["slug"]}"{" selected" if user.get("plan_id")==p["id"] else ""}>{he(p["name"])} (₹{p["price"]})</option>' for p in plans)
    st = "Active" if user["is_active"] else "Banned"
    body = f"""<h1>👤 User — @{he(user.get("username","") or "—")}</h1>
    <p style="margin-bottom:16px"><a href="/{AP}/users" style="color:#a78bfa">← Back</a></p>{_flash(msg)}
    <div class="grid">
      <div class="card stat"><div class="stat-value">{cc}</div><div class="stat-label">Content</div></div>
      <div class="card stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total Views</div></div>
      <div class="card stat"><div class="stat-value">{stats['today']}</div><div class="stat-label">Today</div></div>
      <div class="card stat"><div class="stat-value">{st}</div><div class="stat-label">Status</div></div>
    </div>
    <div class="card"><h3>📋 Info</h3><p>Telegram ID: <b class="mono">{tg_id}</b></p>
      <p>Plan: <b>{user.get("plan_name") or "Free"}</b> | Expires: <b>{user.get("plan_expires") or "Never"}</b></p>
      <p>Max Content: <b>{user['max_content']}</b> | Max Views/Day: <b>{user['max_views_day']}</b></p>
      <p>API Key: <span class="mono">{user.get("api_key","") or "—"}</span></p></div>
    <div class="grid">
      <div class="card"><h3 style="margin-bottom:12px">💳 Change Plan</h3>
        <form method="POST" action="/{AP}/users/{tg_id}/plan">
          <div class="form-group"><label>Plan</label><select name="plan_slug">{plan_opts}</select></div>
          <div class="form-group"><label>Duration (days)</label><input type="number" name="duration" value="30"></div>
          <button class="btn btn-primary" type="submit">Set Plan</button></form></div>
      <div class="card"><h3 style="margin-bottom:12px">🔧 Limits</h3>
        <form method="POST" action="/{AP}/users/{tg_id}/limits">
          <div class="form-group"><label>Max Content</label><input type="number" name="max_content" value="{user['max_content']}"></div>
          <div class="form-group"><label>Max Views/Day</label><input type="number" name="max_views_day" value="{user['max_views_day']}"></div>
          <button class="btn btn-primary" type="submit">Update</button></form></div>
    </div>
    <div class="card"><h3>⚡ Actions</h3><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
      {"" if not user["is_active"] else f'<form method="POST" action="/{AP}/users/{tg_id}/ban"><button class="btn btn-danger">Ban</button></form>'}
      {"" if user["is_active"] else f'<form method="POST" action="/{AP}/users/{tg_id}/unban"><button class="btn btn-ok">Unban</button></form>'}
      <form method="POST" action="/{AP}/users/{tg_id}/reset-password"><button class="btn btn-primary">Reset Password</button></form>
    </div></div>"""
    return _admin_html(body, f"User {tg_id}", "users")

@app.post(f"/{AP}/users/{{tg_id}}/plan")
async def admin_set_plan(tg_id: int, request: Request, plan_slug: str = Form(...), duration: int = Form(30)):
    if not _is_admin(request): raise HTTPException(403)
    plan = db.get_plan(plan_slug)
    if plan: db.set_user_plan(tg_id, plan["id"], duration if duration > 0 else plan["duration_days"])
    ref = request.headers.get("referer","")
    if f"/{AP}/users/{tg_id}" in ref: return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Plan set", 303)
    return RedirectResponse(f"/{AP}/users?msg=Plan set", 303)

@app.post(f"/{AP}/users/{{tg_id}}/limits")
async def admin_set_limits(tg_id: int, request: Request, max_content: int = Form(...), max_views_day: int = Form(...)):
    if not _is_admin(request): raise HTTPException(403)
    db.update_user(tg_id, max_content=max_content, max_views_day=max_views_day)
    return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Limits updated", 303)

@app.post(f"/{AP}/users/{{tg_id}}/ban")
async def admin_ban(tg_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.ban_user(tg_id)
    return RedirectResponse(f"/{AP}/users?msg=Banned", 303)

@app.post(f"/{AP}/users/{{tg_id}}/unban")
async def admin_unban(tg_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.unban_user(tg_id)
    return RedirectResponse(f"/{AP}/users?msg=Unbanned", 303)

@app.post(f"/{AP}/users/{{tg_id}}/reset-password")
async def admin_reset_pw(tg_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.update_user(tg_id, password_hash="")
    return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Password reset", 303)

# ── Admin: Channels ──────────────────────────────────────────

@app.get(f"/{AP}/channels")
async def admin_channels(request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    chs = db.list_channels()
    rows = ""
    for c in chs:
        rows += f'<tr><td>{he(c["name"])}</td><td class="mono">{c["channel_id"]}</td><td>{c["category"]}</td>'
        rows += f'<td><form method="POST" action="/{AP}/channels/{c["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    body = f"""<h1>📺 Channels</h1>{_flash(msg)}
    <div class="card"><h3 style="margin-bottom:12px">Add Channel</h3>
    <form method="POST" action="/{AP}/channels/create" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
      <div class="form-group" style="flex:1;min-width:150px"><label>Name</label><input type="text" name="name" required></div>
      <div class="form-group" style="flex:1;min-width:150px"><label>Channel ID</label><input type="text" name="channel_id" required placeholder="-100xxx"></div>
      <div class="form-group" style="min-width:120px"><label>Category</label><select name="category"><option>anime</option><option>movie</option><option>series</option><option>general</option></select></div>
      <button class="btn btn-primary" type="submit">Add</button></form></div>
    <table><tr><th>Name</th><th>Channel ID</th><th>Category</th><th></th></tr>{rows}</table>"""
    return _admin_html(body, "Channels", "channels")

@app.post(f"/{AP}/channels/create")
async def admin_ch_create(request: Request, name: str=Form(...), channel_id: str=Form(...), category: str=Form("general")):
    if not _is_admin(request): raise HTTPException(403)
    db.create_channel(name, int(channel_id), category)
    return RedirectResponse(f"/{AP}/channels?msg=Added", 303)

@app.post(f"/{AP}/channels/{{ch_id}}/delete")
async def admin_ch_delete(ch_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.delete_channel(ch_id)
    return RedirectResponse(f"/{AP}/channels?msg=Deleted", 303)

# ── Admin: Plans ─────────────────────────────────────────────

@app.get(f"/{AP}/plans")
async def admin_plans(request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    plans = db.list_plans()
    rows = ""
    for p in plans:
        rows += f'<tr><td>{he(p["name"])}</td><td class="mono">{p["slug"]}</td><td>₹{p["price"]}</td><td>{p["max_content"]}</td>'
        rows += f'<td>{p["max_views_day"]}</td><td>{p["max_sources"]}</td><td>{"Yes" if p["can_ads"] else "No"}</td><td>{p["duration_days"]}d</td>'
        rows += f'<td><form method="POST" action="/{AP}/plans/{p["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    body = f"""<h1>💳 Plans</h1>{_flash(msg)}
    <table><tr><th>Name</th><th>Slug</th><th>Price</th><th>Content</th><th>Views/Day</th><th>Sources</th><th>Ads</th><th>Duration</th><th></th></tr>{rows}</table>
    <div class="card"><h3 style="margin-bottom:12px">Create Plan</h3>
    <form method="POST" action="/{AP}/plans/create">
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <div class="form-group" style="flex:1;min-width:120px"><label>Name</label><input type="text" name="name" required></div>
        <div class="form-group" style="flex:1;min-width:120px"><label>Slug</label><input type="text" name="slug" required></div>
        <div class="form-group" style="min-width:80px"><label>Price ₹</label><input type="number" name="price" value="499"></div></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <div class="form-group" style="flex:1"><label>Max Content</label><input type="number" name="max_content" value="50"></div>
        <div class="form-group" style="flex:1"><label>Views/Day</label><input type="number" name="max_views_day" value="25000"></div>
        <div class="form-group" style="flex:1"><label>Sources</label><input type="number" name="max_sources" value="9"></div></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <div class="form-group" style="flex:1"><label>Duration (days)</label><input type="number" name="duration_days" value="30"></div>
        <div class="form-group" style="flex:1"><label>Can Ads</label><select name="can_ads"><option value="1">Yes</option><option value="0">No</option></select></div>
        <div class="form-group" style="flex:1"><label>Is Trial</label><select name="is_trial"><option value="0">No</option><option value="1">Yes</option></select></div></div>
      <button class="btn btn-primary" type="submit">Create</button></form></div>"""
    return _admin_html(body, "Plans", "plans")

@app.post(f"/{AP}/plans/create")
async def admin_plan_create(request: Request, name: str=Form(...), slug: str=Form(...), price: int=Form(0),
    max_content: int=Form(50), max_views_day: int=Form(25000), max_sources: int=Form(9),
    can_ads: int=Form(0), duration_days: int=Form(30), is_trial: int=Form(0)):
    if not _is_admin(request): raise HTTPException(403)
    db.create_plan(name, slug, price, max_content, max_views_day, max_sources, can_ads, duration_days, is_trial)
    return RedirectResponse(f"/{AP}/plans?msg=Created {name}", 303)

@app.post(f"/{AP}/plans/{{pid}}/delete")
async def admin_plan_delete(pid: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.delete_plan(pid)
    return RedirectResponse(f"/{AP}/plans?msg=Deleted", 303)

# ── Admin: Content ───────────────────────────────────────────

@app.get(f"/{AP}/content")
async def admin_content(request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    items = db.list_all_content()
    base = BASE()
    rows = ""
    for c in items:
        title = he(c["title"]); slug = c["slug"]; sc = c.get("source_count",0)
        owner = he(c.get("owner_name","") or "—")
        rows += f'<tr><td>{title}<br><span class="mono">{slug}</span></td><td>@{owner}</td><td>{sc}</td>'
        rows += f'<td><a href="{base}/watch/{slug}" target="_blank" style="color:#a78bfa">Watch</a></td>'
        rows += f'<td><form method="POST" action="/{AP}/content/{c["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    body = f'<h1>📁 All Content ({len(items)})</h1>{_flash(msg)}<table><tr><th>Content</th><th>Owner</th><th>Sources</th><th>Link</th><th></th></tr>{rows}</table>'
    return _admin_html(body, "Content", "content")

@app.post(f"/{AP}/content/{{cid}}/delete")
async def admin_content_del(cid: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.delete_content(cid)
    return RedirectResponse(f"/{AP}/content?msg=Deleted", 303)

# ── Admin: Ads ───────────────────────────────────────────────

@app.get(f"/{AP}/ads")
async def admin_ads(request: Request):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    ads = db.list_all_ads()
    rows = ""
    for a in ads:
        ab = "badge-ok" if a["is_active"] else "badge-err"
        at = "Active" if a["is_active"] else "Off"
        rows += f'<tr><td>{he(a["name"])}</td><td>@{he(a.get("owner_name","") or "—")}</td><td>{a["ad_type"]}</td><td>{a["position"]}</td>'
        rows += f'<td><span class="badge {ab}">{at}</span></td>'
        rows += f'<td><form method="POST" action="/{AP}/ads/{a["id"]}/toggle" style="display:inline"><button class="btn btn-primary btn-sm">Toggle</button></form> '
        rows += f'<form method="POST" action="/{AP}/ads/{a["id"]}/delete" style="display:inline"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    body = f'<h1>📢 All Ads ({len(ads)})</h1><table><tr><th>Name</th><th>Owner</th><th>Type</th><th>Pos</th><th>Active</th><th></th></tr>{rows}</table>'
    return _admin_html(body, "Ads", "ads")

@app.post(f"/{AP}/ads/{{aid}}/toggle")
async def admin_ads_toggle(aid: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.toggle_ad(aid); return RedirectResponse(f"/{AP}/ads", 303)

@app.post(f"/{AP}/ads/{{aid}}/delete")
async def admin_ads_delete(aid: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.delete_ad(aid); return RedirectResponse(f"/{AP}/ads", 303)

# ── Admin: Logs ──────────────────────────────────────────────

@app.get(f"/{AP}/logs")
async def admin_logs(request: Request):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    logs = db.get_recent_logs(50)
    stats = db.get_view_stats_global()
    rows = ""
    for l in logs:
        rows += f'<tr><td>{he(l.get("content_title","") or "—")}</td><td class="mono">{l.get("ip_hash","")[:12]}</td>'
        rows += f'<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">{he((l.get("user_agent","") or "")[:60])}</td><td>{l["viewed_at"]}</td></tr>'
    body = f"""<h1>📋 Logs</h1>
    <div class="grid">
      <div class="card stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total</div></div>
      <div class="card stat"><div class="stat-value">{stats['today']}</div><div class="stat-label">Today</div></div>
      <div class="card stat"><div class="stat-value">{stats['unique_ips']}</div><div class="stat-label">Unique IPs</div></div></div>
    <table><tr><th>Content</th><th>IP</th><th>Agent</th><th>Time</th></tr>{rows}</table>"""
    return _admin_html(body, "Logs", "logs")

# ── Admin: Payment Requests ──────────────────────────────────

@app.get(f"/{AP}/requests")
async def admin_requests(request: Request, status: str="pending", msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    reqs = db.list_payment_requests(status if status != "all" else None)
    tabs = ""
    for s in ["pending","approved","rejected","all"]:
        cls = "active" if s == status else ""
        tabs += f'<a href="/{AP}/requests?status={s}" class="tab {cls}">{s.title()}</a>'
    rows = ""
    for r in reqs:
        rb = {"pending":"badge-warn","approved":"badge-ok","rejected":"badge-err"}.get(r["status"],"badge-acc")
        uname = he(r.get("user_name","") or str(r.get("user_id","")))
        pname = he(r.get("plan_name","") or "—")
        rows += f'<tr><td>@{uname}<br><span class="mono">{r.get("user_id","")}</span></td><td>{pname}</td><td>₹{r["amount"]}</td>'
        rows += f'<td>{he(r.get("method_type","") or "—")}</td><td><span class="mono">{he(r.get("transaction_id","") or "—")}</span></td>'
        rows += f'<td><span class="badge {rb}">{r["status"]}</span></td><td>{r["created_at"]}</td><td>'
        if r["status"] == "pending":
            rows += f'<form method="POST" action="/{AP}/requests/{r["id"]}/approve" style="display:inline"><button class="btn btn-ok btn-sm">Approve</button></form> '
            rows += f'<form method="POST" action="/{AP}/requests/{r["id"]}/reject" style="display:inline"><input type="hidden" name="notes" value=""><button class="btn btn-danger btn-sm">Reject</button></form>'
        elif r.get("admin_notes"):
            rows += f'<span class="mono" style="font-size:.7rem">{he(r["admin_notes"][:30])}</span>'
        rows += '</td></tr>'
    body = f"""<h1>📩 Payment Requests</h1>{_flash(msg)}
    <div class="tabs">{tabs}</div>
    <table><tr><th>User</th><th>Plan</th><th>Amount</th><th>Method</th><th>TxnID</th><th>Status</th><th>Date</th><th>Actions</th></tr>{rows}</table>"""
    return _admin_html(body, "Requests", "requests")

@app.post(f"/{AP}/requests/{{rid}}/approve")
async def admin_req_approve(rid: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    req = db.get_payment_request(rid)
    if not req or req["status"] != "pending": return RedirectResponse(f"/{AP}/requests?msg=Invalid request", 303)
    db.approve_payment_request(rid, MAIN_ADMIN_TELEGRAM_ID or 0)
    # Activate user plan
    plan = db.get_plan_by_id(req["plan_id"])
    if plan:
        dur = plan.get("duration_days",30) or 30
        db.set_user_plan(req["user_id"], plan["id"], dur)
        try:
            await tg_client.send_message(req["user_id"],
                f"🎉 **Payment Approved!**\n\nYour **{plan['name']}** plan is now active!\nValid for {dur} days.\n\nEnjoy premium features! ⚡")
        except: pass
    return RedirectResponse(f"/{AP}/requests?msg=Approved and plan activated", 303)

@app.post(f"/{AP}/requests/{{rid}}/reject")
async def admin_req_reject(rid: int, request: Request, notes: str = Form("")):
    if not _is_admin(request): raise HTTPException(403)
    req = db.get_payment_request(rid)
    if not req or req["status"] != "pending": return RedirectResponse(f"/{AP}/requests?msg=Invalid", 303)
    db.reject_payment_request(rid, MAIN_ADMIN_TELEGRAM_ID or 0, notes)
    try:
        reason = f"\nReason: {notes}" if notes else ""
        await tg_client.send_message(req["user_id"], f"❌ **Payment Request Rejected**\n\nYour payment request has been rejected.{reason}\n\nContact admin for help.")
    except: pass
    return RedirectResponse(f"/{AP}/requests?msg=Rejected", 303)

# ── Admin: Payment Methods ───────────────────────────────────

@app.get(f"/{AP}/payments")
async def admin_payments(request: Request, msg: str=""):
    if not _is_admin(request): return RedirectResponse(f"/{AP}/login")
    methods = db.list_payment_methods()
    rows = ""
    for m in methods:
        ab = "badge-ok" if m["is_active"] else "badge-err"
        at = "Active" if m["is_active"] else "Off"
        det = he((m["details"] or "")[:60])
        rows += f'<tr><td>{he(m["title"])}</td><td>{he(m["method_type"])}</td><td style="max-width:200px;overflow:hidden">{det}</td>'
        rows += f'<td><span class="badge {ab}">{at}</span></td>'
        rows += f'<td><form method="POST" action="/{AP}/payments/{m["id"]}/toggle" style="display:inline"><button class="btn btn-primary btn-sm">Toggle</button></form> '
        rows += f'<form method="POST" action="/{AP}/payments/{m["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    body = f"""<h1>💰 Payment Methods</h1>{_flash(msg)}
    <table><tr><th>Title</th><th>Type</th><th>Details</th><th>Active</th><th></th></tr>{rows}</table>
    <div class="card"><h3 style="margin-bottom:12px">Add Payment Method</h3>
    <form method="POST" action="/{AP}/payments/create">
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <div class="form-group" style="flex:1;min-width:150px"><label>Title</label><input type="text" name="title" required placeholder="UPI Payment"></div>
        <div class="form-group" style="min-width:120px"><label>Type</label><select name="method_type"><option value="upi">UPI</option><option value="bank">Bank Transfer</option><option value="razorpay">Razorpay</option><option value="paypal">PayPal</option><option value="crypto">Crypto</option><option value="custom">Custom</option></select></div>
        <div class="form-group" style="min-width:60px"><label>Order</label><input type="number" name="sort_order" value="0"></div></div>
      <div class="form-group"><label>Details (UPI ID / Account / Link / Instructions)</label><textarea name="details" rows="3" placeholder="admin@paytm or https://paypal.me/..."></textarea></div>
      <div class="form-group"><label>QR Image URL (optional)</label><input type="url" name="qr_image_url" placeholder="https://..."></div>
      <button class="btn btn-primary" type="submit">Add Method</button></form></div>"""
    return _admin_html(body, "Payments", "payments")

@app.post(f"/{AP}/payments/create")
async def admin_pm_create(request: Request, title: str=Form(...), method_type: str=Form("upi"),
    details: str=Form(""), qr_image_url: str=Form(""), sort_order: int=Form(0)):
    if not _is_admin(request): raise HTTPException(403)
    db.create_payment_method(method_type, title, details, qr_image_url, sort_order)
    return RedirectResponse(f"/{AP}/payments?msg=Added", 303)

@app.post(f"/{AP}/payments/{{pm_id}}/toggle")
async def admin_pm_toggle(pm_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.toggle_payment_method(pm_id)
    return RedirectResponse(f"/{AP}/payments?msg=Toggled", 303)

@app.post(f"/{AP}/payments/{{pm_id}}/delete")
async def admin_pm_delete(pm_id: int, request: Request):
    if not _is_admin(request): raise HTTPException(403)
    db.delete_payment_method(pm_id)
    return RedirectResponse(f"/{AP}/payments?msg=Deleted", 303)

# ═══════════════════════════════════════════════════════════════
# SUB-ADMIN PANEL (/panel/*)
# ═══════════════════════════════════════════════════════════════

@app.get("/panel/login", response_class=HTMLResponse)
async def panel_login_page(): return HTMLResponse(panel_login())

@app.post("/panel/login")
async def panel_login_post(telegram_id: int = Form(...), password: str = Form(...)):
    user = db.get_user(telegram_id)
    if not user or not user.get("password_hash") or not _check_pw(password, user["password_hash"]):
        return HTMLResponse(panel_login("Invalid credentials."), 401)
    if not user["is_active"]: return HTMLResponse(panel_login("Account suspended."), 403)
    r = RedirectResponse("/panel", 303)
    r.set_cookie("panel_tg_id", str(telegram_id), httponly=True, max_age=86400)
    r.set_cookie("panel_token", _panel_cookie(telegram_id), httponly=True, max_age=86400)
    return r

@app.get("/panel")
async def panel_dashboard(request: Request):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    stats = db.get_view_stats_by_owner(user["telegram_id"])
    cc = db.count_content_by_owner(user["telegram_id"])
    plan = user.get("plan_name") or "Free"
    exp = str(user.get("plan_expires") or "Never")[:10]
    body = f"""<h1>📊 Dashboard</h1>
    <div class="grid">
      <div class="card stat"><div class="stat-value">{cc}</div><div class="stat-label">My Content</div></div>
      <div class="card stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total Views</div></div>
      <div class="card stat"><div class="stat-value">{stats['today']}</div><div class="stat-label">Today</div></div>
      <div class="card stat"><div class="stat-value">{plan}</div><div class="stat-label">Plan</div></div></div>
    <div class="card"><p>📅 Expires: <b>{exp}</b></p><p>📦 Content: <b>{cc}/{user['max_content']}</b> | Views: <b>{user['max_views_day']}/day</b></p></div>"""
    return _panel_html(body, user, "Dashboard", "dashboard")

# ── Panel: Content (with hierarchy) ──────────────────────────

@app.get("/panel/content")
async def panel_content(request: Request, parent: int=0, msg: str=""):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    pid = parent if parent > 0 else None
    items = db.get_content_tree(user["telegram_id"], pid)
    # Breadcrumb
    bc = ""
    if pid:
        crumbs = db.get_breadcrumb(pid)
        bc = '<a href="/panel/content" style="color:#a78bfa">Root</a>'
        for cr in crumbs:
            bc += f' → <a href="/panel/content?parent={cr["id"]}" style="color:#a78bfa">{he(cr["title"])}</a>'
        bc = f'<p style="margin-bottom:12px;font-size:.85rem">📂 {bc}</p>'
    rows = ""
    for c in items:
        cid = c["id"]; title = he(c["title"]); slug = c["slug"]
        sc = c.get("source_count", 0); cc_count = c.get("child_count", 0)
        type_badge = f'<span class="badge badge-acc">{cc_count} sub</span>' if cc_count > 0 else f'<span class="badge badge-ok">{sc} src</span>'
        rows += f'<tr><td><a href="/panel/content?parent={cid}" style="color:#a78bfa;text-decoration:none">{title}</a><br><span class="mono">{slug}</span></td><td>{type_badge}</td>'
        rows += f'<td><a href="/panel/embeds/{cid}" class="btn btn-primary btn-sm">Embed</a> '
        rows += f'<a href="/panel/content/{cid}/sources" class="btn btn-primary btn-sm">Sources</a> '
        rows += f'<form method="POST" action="/panel/content/{cid}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    parent_field = f'<input type="hidden" name="parent_id" value="{pid}">' if pid else ''
    body = f"""<h1>📁 My Content</h1>{_flash(msg)}{bc}
    <div class="card"><h3 style="margin-bottom:12px">Create New</h3>
    <form method="POST" action="/panel/content/create" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
      {parent_field}
      <div class="form-group" style="flex:1;min-width:200px"><label>Title</label><input type="text" name="title" required placeholder="Naruto Episode 1"></div>
      <div class="form-group" style="min-width:120px"><label>Category</label><select name="category"><option>anime</option><option>movie</option><option>series</option><option>general</option></select></div>
      <button class="btn btn-primary" type="submit">Create</button></form></div>
    <table><tr><th>Content</th><th>Type</th><th>Actions</th></tr>{rows}</table>"""
    return _panel_html(body, user, "Content", "content")

@app.post("/panel/content/create")
async def panel_content_create(request: Request, title: str=Form(...), category: str=Form("general"), parent_id: int=Form(0)):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    cc = db.count_content_by_owner(user["telegram_id"])
    if cc >= user["max_content"]:
        return RedirectResponse(f"/panel/content?msg=Limit reached ({user['max_content']})", 303)
    slug = _slugify(title)
    if not slug: slug = f"content-{secrets.token_hex(4)}"
    pid = parent_id if parent_id > 0 else None
    try:
        db.create_content(user["telegram_id"], title, slug, category, parent_id=pid)
        redir = f"/panel/content?parent={pid}&msg=Created: {title}" if pid else f"/panel/content?msg=Created: {title}"
        return RedirectResponse(redir, 303)
    except:
        slug = f"{slug}-{secrets.token_hex(3)}"
        try:
            db.create_content(user["telegram_id"], title, slug, category, parent_id=pid)
            redir = f"/panel/content?parent={pid}&msg=Created: {title}" if pid else f"/panel/content?msg=Created: {title}"
            return RedirectResponse(redir, 303)
        except Exception as e:
            return RedirectResponse(f"/panel/content?msg=Error: {e}", 303)

@app.post("/panel/content/{cid}/delete")
async def panel_content_del(cid: int, request: Request):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.delete_content(cid, user["telegram_id"])
    return RedirectResponse("/panel/content?msg=Deleted", 303)

@app.get("/panel/content/{cid}/sources")
async def panel_sources(cid: int, request: Request, msg: str=""):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    content = db.get_content_by_id(cid)
    if not content or content["owner_id"] != user["telegram_id"]: raise HTTPException(404)
    sources = db.get_sources_by_content(cid)
    rows = ""
    for s in sources:
        fid_short = s["file_id"][:35]
        rows += f'<tr><td>{s["language"]}</td><td>{s["quality"]}</td><td>{s["width"]}x{s["height"]}</td><td>{_fmt_size(s["file_size"])}</td>'
        rows += f'<td class="mono" style="max-width:180px;overflow:hidden;text-overflow:ellipsis">{fid_short}...</td>'
        rows += f'<td><form method="POST" action="/panel/source/{s["id"]}/delete" style="display:inline"><input type="hidden" name="cid" value="{cid}"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    ct = he(content['title'])
    body = f"""<h1>📁 {ct} — Sources</h1>
    <p style="margin-bottom:16px"><a href="/panel/content" style="color:#a78bfa">← Back</a></p>{_flash(msg)}
    <div class="card"><h3 style="margin-bottom:12px">Add Source</h3>
    <form method="POST" action="/panel/source/add" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
      <input type="hidden" name="cid" value="{cid}">
      <div class="form-group" style="flex:2;min-width:200px"><label>File ID</label><input type="text" name="file_id" required></div>
      <div class="form-group" style="flex:1;min-width:100px"><label>Language</label><input type="text" name="language" value="Hindi" required></div>
      <div class="form-group" style="min-width:80px"><label>Quality</label><select name="quality"><option>480p</option><option selected>720p</option><option>1080p</option><option>2160p</option></select></div>
      <div class="form-group" style="min-width:80px"><label>Size (bytes)</label><input type="number" name="file_size" value="0"></div>
      <button class="btn btn-primary" type="submit">Add</button></form></div>
    <table><tr><th>Lang</th><th>Quality</th><th>Res</th><th>Size</th><th>File ID</th><th></th></tr>{rows}</table>"""
    return _panel_html(body, user, "Sources", "content")

@app.post("/panel/source/add")
async def panel_source_add(request: Request, cid: int=Form(...), file_id: str=Form(...),
                           language: str=Form("Hindi"), quality: str=Form("720p"), file_size: int=Form(0)):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    content = db.get_content_by_id(cid)
    if not content or content["owner_id"] != user["telegram_id"]: raise HTTPException(403)
    db.add_source(cid, file_id.strip(), language.strip(), quality.strip(), file_size=file_size)
    return RedirectResponse(f"/panel/content/{cid}/sources?msg=Added", 303)

@app.post("/panel/source/{sid}/delete")
async def panel_source_del(sid: int, request: Request, cid: int=Form(...)):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.delete_source(sid)
    return RedirectResponse(f"/panel/content/{cid}/sources?msg=Deleted", 303)

# ── Panel: Embeds ────────────────────────────────────────────

@app.get("/panel/embeds")
async def panel_embeds(request: Request):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    items = db.list_content_by_owner(user["telegram_id"])
    base = BASE()
    rows = ""
    for c in items:
        rows += f'<tr><td>{he(c["title"])}</td><td>{c.get("source_count",0)}</td><td><a href="{base}/watch/{c["slug"]}" target="_blank" style="color:#a78bfa">{base}/watch/{c["slug"]}</a></td>'
        rows += f'<td><a href="/panel/embeds/{c["id"]}" class="btn btn-primary btn-sm">Get Code</a></td></tr>'
    body = f'<h1>🔗 Embed Links</h1><table><tr><th>Content</th><th>Sources</th><th>Watch URL</th><th></th></tr>{rows}</table>'
    return _panel_html(body, user, "Embeds", "embeds")

@app.get("/panel/embeds/{cid}")
async def panel_embed_code_page(cid: int, request: Request):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    content = db.get_content_by_id(cid)
    if not content or content["owner_id"] != user["telegram_id"]: raise HTTPException(404)
    base = BASE()
    body = panel_embed_code(he(content["title"]), f"{base}/watch/{content['slug']}", f"{base}/embed/{content['slug']}")
    return _panel_html(body, user, "Embed Code", "embeds")

# ── Panel: Ads ───────────────────────────────────────────────

@app.get("/panel/ads")
async def panel_ads(request: Request, msg: str=""):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    plan_allows_ads = False
    if user.get("plan_id"):
        plan = db.get_plan_by_id(user["plan_id"])
        if plan: plan_allows_ads = bool(plan.get("can_ads"))
    ads = db.get_ads_by_owner(user["telegram_id"])
    rows = ""
    for a in ads:
        ab = "badge-ok" if a["is_active"] else "badge-err"
        at = "Active" if a["is_active"] else "Off"
        rows += f'<tr><td>{he(a["name"])}</td><td>{a["ad_type"]}</td><td>{a["position"]}</td><td>{a["duration"]}s</td>'
        rows += f'<td><span class="badge {ab}">{at}</span></td>'
        rows += f'<td><form method="POST" action="/panel/ads/{a["id"]}/toggle" style="display:inline"><button class="btn btn-primary btn-sm">Toggle</button></form> '
        rows += f'<form method="POST" action="/panel/ads/{a["id"]}/delete" style="display:inline"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
    notice = '<div class="card" style="border-color:#ef4444"><p style="color:#ef4444"><b>Your plan does not include ads.</b> Upgrade to use ads.</p></div>' if not plan_allows_ads else ""
    body = f"""<h1>📢 My Ads</h1>{_flash(msg)}{notice}
    <div class="card"><h3 style="margin-bottom:12px">Create Ad</h3>
    <form method="POST" action="/panel/ads/create">
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">
        <div class="form-group" style="flex:1;min-width:150px"><label>Name</label><input type="text" name="name" required></div>
        <div class="form-group" style="min-width:100px"><label>Type</label><select name="ad_type"><option value="vast">VAST</option><option value="custom">Custom</option></select></div>
        <div class="form-group" style="min-width:80px"><label>Position</label><select name="position"><option value="pre">Pre</option><option value="mid">Mid</option></select></div>
        <div class="form-group" style="min-width:60px"><label>Sec</label><input type="number" name="duration" value="5"></div></div>
      <div class="form-group"><label>VAST URL</label><input type="text" name="ad_url"></div>
      <div class="form-group"><label>Custom HTML</label><textarea name="ad_html" rows="2"></textarea></div>
      <button class="btn btn-primary" type="submit">Create</button></form></div>
    <table><tr><th>Name</th><th>Type</th><th>Pos</th><th>Dur</th><th>Active</th><th></th></tr>{rows}</table>"""
    return _panel_html(body, user, "Ads", "ads")

@app.post("/panel/ads/create")
async def panel_ads_create(request: Request, name: str=Form(...), ad_type: str=Form("custom"),
    ad_url: str=Form(""), ad_html: str=Form(""), position: str=Form("pre"), duration: int=Form(5)):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.create_ad(user["telegram_id"], name, ad_type, ad_url, ad_html, position, duration)
    return RedirectResponse("/panel/ads?msg=Created", 303)

@app.post("/panel/ads/{aid}/toggle")
async def panel_ads_toggle(aid: int, request: Request):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.toggle_ad(aid, user["telegram_id"])
    return RedirectResponse("/panel/ads", 303)

@app.post("/panel/ads/{aid}/delete")
async def panel_ads_delete(aid: int, request: Request):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.delete_ad(aid, user["telegram_id"])
    return RedirectResponse("/panel/ads?msg=Deleted", 303)

# ── Panel: Subscription + Payment ────────────────────────────

@app.get("/panel/subscription")
async def panel_sub(request: Request, msg: str=""):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    plans = db.list_plans()
    plan_cards = ""
    for p in plans:
        is_current = user.get("plan_id") == p["id"]
        border = "border:2px solid #a78bfa;" if is_current else ""
        tag = '<span class="badge badge-ok" style="margin-left:8px">Current</span>' if is_current else ""
        can_ads = "Ads: Yes" if p["can_ads"] else "Ads: No"
        plan_cards += f'<div class="card" style="{border}"><h3>{he(p["name"])}{tag}</h3>'
        plan_cards += f'<div class="stat-value" style="font-size:1.5rem;margin:8px 0">₹{p["price"]}</div>'
        plan_cards += f'<p style="color:#7777aa;font-size:.82rem">{p["max_content"]} content | {p["max_views_day"]} views/day | {p["max_sources"]} sources | {can_ads} | {p["duration_days"]}d</p>'
        if not is_current and p["slug"] != "free" and float(p["price"]) > 0:
            plan_cards += f'<a href="/panel/subscription/pay/{p["slug"]}" class="btn btn-primary" style="margin-top:10px">Buy {he(p["name"])} — ₹{p["price"]}</a>'
        plan_cards += '</div>'
    body = f"""<h1>💳 Subscription</h1>{_flash(msg)}
    <div class="card"><p>Current: <b>{user.get("plan_name") or "Free"}</b> | Expires: <b>{str(user.get("plan_expires") or "Never")[:10]}</b></p></div>
    <h3 style="margin:20px 0 12px">Available Plans</h3>
    <div class="grid">{plan_cards}</div>"""
    return _panel_html(body, user, "Subscription", "subscription")

@app.get("/panel/subscription/pay/{plan_slug}")
async def panel_pay(plan_slug: str, request: Request):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    plan = db.get_plan(plan_slug)
    if not plan: raise HTTPException(404)
    methods = db.list_payment_methods(active_only=True)
    method_cards = ""
    for m in methods:
        icon = {"upi":"💳","bank":"🏦","razorpay":"💰","paypal":"🌐","crypto":"₿","custom":"📋"}.get(m["method_type"],"💳")
        det = he(m["details"] or "").replace("\n","<br>")
        qr = f'<img src="{m["qr_image_url"]}" style="max-width:200px;border-radius:8px;margin-top:8px">' if m.get("qr_image_url") else ""
        method_cards += f'<div class="card"><h3>{icon} {he(m["title"])}</h3><p style="margin-top:8px;word-break:break-all">{det}</p>{qr}</div>'
    if not method_cards:
        method_cards = '<div class="card"><p style="color:#7777aa">No payment methods configured yet. Contact admin.</p></div>'
    body = f"""<h1>💰 Pay for {he(plan["name"])} — ₹{plan["price"]}</h1>
    <p style="margin-bottom:16px"><a href="/panel/subscription" style="color:#a78bfa">← Back to Plans</a></p>
    <h3 style="margin-bottom:12px">Step 1: Make Payment</h3>
    <div class="grid">{method_cards}</div>
    <h3 style="margin:20px 0 12px">Step 2: Submit Proof</h3>
    <div class="card">
    <form method="POST" action="/panel/subscription/submit">
      <input type="hidden" name="plan_slug" value="{plan_slug}">
      <div class="form-group"><label>Payment Method Used</label>
        <select name="method_type"><option value="">Select...</option>{"".join(f'<option value="{m["method_type"]}">{he(m["title"])}</option>' for m in methods)}</select></div>
      <div class="form-group"><label>Transaction ID / UTR Number</label><input type="text" name="transaction_id" required placeholder="Enter UTR or Transaction ID"></div>
      <div class="form-group"><label>Your Telegram ID</label><input type="text" name="tg_id_confirm" value="{user['telegram_id']}" readonly></div>
      <div class="form-group"><label>Additional Notes (optional)</label><textarea name="notes" rows="2" placeholder="Any additional info..."></textarea></div>
      <p style="color:#7777aa;font-size:.82rem;margin-bottom:12px">💡 Send payment screenshot to the bot using /proof command</p>
      <button class="btn btn-primary" type="submit">Submit Payment Proof</button>
    </form></div>"""
    return _panel_html(body, user, "Payment", "subscription")

@app.post("/panel/subscription/submit")
async def panel_sub_submit(request: Request, plan_slug: str=Form(...), method_type: str=Form(""),
    transaction_id: str=Form(""), notes: str=Form(""), tg_id_confirm: str=Form("")):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    plan = db.get_plan(plan_slug)
    if not plan: return RedirectResponse("/panel/subscription?msg=Plan not found", 303)
    # Check for pending screenshot
    screenshot_fid = _pending_proofs.get(user["telegram_id"], "")
    db.create_payment_request(user["telegram_id"], plan["id"], float(plan["price"]),
        method_type, transaction_id.strip(), screenshot_fid, notes)
    # Notify admin
    try:
        if MAIN_ADMIN_TELEGRAM_ID:
            uname = user.get("username","") or str(user["telegram_id"])
            msg_text = (f"📩 **New Payment Request**\n\n"
                f"User: @{uname} (`{user['telegram_id']}`)\n"
                f"Plan: **{plan['name']}** — ₹{plan['price']}\n"
                f"Method: {method_type or '—'}\n"
                f"TxnID: `{transaction_id or '—'}`\n\n"
                f"Review in admin panel: {BASE()}/{AP}/requests")
            await tg_client.send_message(MAIN_ADMIN_TELEGRAM_ID, msg_text)
    except: pass
    if screenshot_fid:
        del _pending_proofs[user["telegram_id"]]
    return RedirectResponse("/panel/subscription?msg=Payment proof submitted! Admin will review shortly.", 303)

# ── Panel: Profile ───────────────────────────────────────────

@app.get("/panel/profile")
async def panel_profile(request: Request, msg: str=""):
    user = _get_panel_user(request)
    if not user: return RedirectResponse("/panel/login")
    uname = he(user.get("username","") or "—")
    body = f"""<h1>👤 Profile</h1>{_flash(msg)}
    <div class="card"><p>Telegram ID: <b class="mono">{user["telegram_id"]}</b></p>
      <p>Username: <b>@{uname}</b></p><p>Plan: <b>{user.get("plan_name") or "Free"}</b></p>
      <p>API Key: <span class="mono">{user.get("api_key","") or "—"}</span></p></div>
    <div class="card"><h3 style="margin-bottom:12px">Change Password</h3>
    <form method="POST" action="/panel/profile/password" style="display:flex;gap:10px;align-items:end">
      <div class="form-group" style="flex:1"><label>New Password</label><input type="password" name="password" required minlength="4"></div>
      <button class="btn btn-primary" type="submit">Update</button></form></div>
    <div class="card"><a href="/panel/logout" class="btn btn-danger">Logout</a></div>"""
    return _panel_html(body, user, "Profile", "profile")

@app.post("/panel/profile/password")
async def panel_set_password(request: Request, password: str=Form(...)):
    user = _get_panel_user(request)
    if not user: raise HTTPException(403)
    db.update_user(user["telegram_id"], password_hash=_hash_pw(password))
    return RedirectResponse("/panel/profile?msg=Password updated", 303)

@app.get("/panel/logout")
async def panel_logout():
    r = RedirectResponse("/panel/login", 303)
    r.delete_cookie("panel_tg_id"); r.delete_cookie("panel_token")
    return r

# ═══════════════════════════════════════════════════════════════
# BOT HANDLERS — with Inline Buttons + Hierarchy
# ═══════════════════════════════════════════════════════════════

_pending_videos: dict = {}
_pending_proofs: dict = {}  # telegram_id -> file_id for payment screenshots

def _btn(*rows):
    """Helper to build InlineKeyboardMarkup."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) if data else InlineKeyboardButton(text, url=url)
         for text, data, url in row] for row in rows
    ])

def _b(text, data=None, url=None):
    """Shortcut to create button tuple."""
    return (text, data, url)

def _register_bot_handlers():

    def is_ma(uid): return uid == MAIN_ADMIN_TELEGRAM_ID if MAIN_ADMIN_TELEGRAM_ID else False

    @tg_client.on_message(filters.private & filters.command("start"))
    async def cmd_start(_c, m: Message):
        uid = m.from_user.id
        user = db.get_user(uid)
        if not user:
            db.create_user(uid, m.from_user.username or "", m.from_user.first_name or "")
            free = db.get_plan("free")
            if free: db.set_user_plan(uid, free["id"], 0)
        name = m.from_user.first_name or "there"
        admin_hint = "\n🔑 **Admin:** /users /grant /stats /broadcast" if is_ma(uid) else ""
        await m.reply_text(
            f"👋 **Welcome, {name}!**\n\n"
            f"🎬 **TG Stream — Premium Video Platform**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 **/new** `Title` — Create content\n"
            f"📁 **/new** `Title/Season/Episode` — Nested content\n"
            f"📹 Send video → **/add** `slug Lang Quality`\n"
            f"🔗 **/links** `slug` — Get embed links\n"
            f"📋 **/myvideos** — List my content\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 **/subscribe** — View plans\n"
            f"📊 **/myplan** — Current plan\n"
            f"🔐 **/setpassword** `pass` — Set password\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ MTProto streaming — **NO 20MB limit!**{admin_hint}",
            reply_markup=_btn(
                [_b("📁 My Content", "menu:content"), _b("💳 Plans", "menu:plans")],
                [_b("🖥 Open Panel", url=f"{BASE()}/panel/login"), _b("📊 Status", "menu:status")]
            ))

    @tg_client.on_message(filters.private & filters.command("setpassword"))
    async def cmd_setpw(_c, m: Message):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2: return await m.reply_text("Usage: `/setpassword YourPassword`\n\nMinimum 4 characters.")
        pw = parts[1].strip()
        if len(pw) < 4: return await m.reply_text("❌ Password must be at least 4 characters.")
        user = db.get_user(m.from_user.id)
        if not user: return await m.reply_text("Send /start first.")
        db.update_user(m.from_user.id, password_hash=_hash_pw(pw))
        await m.reply_text(
            f"✅ **Password Set!**\n\n"
            f"🖥 Panel: {BASE()}/panel/login\n"
            f"🆔 Telegram ID: `{m.from_user.id}`",
            reply_markup=_btn([_b("🖥 Open Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("panel"))
    async def cmd_panel(_c, m: Message):
        await m.reply_text(
            f"🖥 **Sub-Admin Panel**\n\n"
            f"Link: {BASE()}/panel/login\n"
            f"Your ID: `{m.from_user.id}`\n\n"
            f"Set password first: /setpassword",
            reply_markup=_btn([_b("🖥 Open Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("subscribe"))
    async def cmd_subscribe(_c, m: Message):
        plans = db.list_plans()
        lines = ""
        buttons = []
        for p in plans:
            emoji = {"free":"🆓","trial":"🎁","basic":"⭐","pro":"👑"}.get(p["slug"],"💎")
            lines += f"\n{emoji} **{p['name']}** — ₹{p['price']}\n"
            lines += f"   {p['max_content']} content · {p['max_views_day']} views/day · {p['duration_days']}d\n"
            if p["slug"] not in ("free",) and float(p["price"]) > 0:
                buttons.append(_b(f"💳 {p['name']} ₹{p['price']}", f"buy:{p['slug']}"))
        btn_rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        btn_rows.append([_b("🎁 Free Trial", "menu:trial")])
        await m.reply_text(
            f"💳 **Subscription Plans**\n"
            f"━━━━━━━━━━━━━━━━━━━━{lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Select a plan below to purchase:",
            reply_markup=_btn(*btn_rows))

    @tg_client.on_message(filters.private & filters.command("trial"))
    async def cmd_trial(_c, m: Message):
        user = db.get_user(m.from_user.id)
        if not user: return await m.reply_text("Send /start first.")
        if user.get("plan_slug") == "trial" or (user.get("plan_expires") and str(user.get("plan_expires")) > "2020"):
            return await m.reply_text("⚠️ You already have an active plan or used trial.")
        trial = db.get_plan("trial")
        if trial:
            db.set_user_plan(m.from_user.id, trial["id"], trial["duration_days"])
            await m.reply_text(
                "🎉 **7-Day Trial Activated!**\n\n"
                "✅ 20 content · 5000 views/day · Ads enabled\n"
                "⏰ Expires in 7 days\n\n"
                "Start creating: /new `Title`",
                reply_markup=_btn([_b("📁 Create Content", "menu:new_help"), _b("🖥 Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("myplan"))
    async def cmd_myplan(_c, m: Message):
        user = db.get_user(m.from_user.id)
        if not user: return await m.reply_text("Send /start first.")
        cc = db.count_content_by_owner(m.from_user.id)
        stats = db.get_view_stats_by_owner(m.from_user.id)
        await m.reply_text(
            f"📋 **Your Plan**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Plan: **{user.get('plan_name') or 'Free'}**\n"
            f"📅 Expires: {user.get('plan_expires') or 'Never'}\n"
            f"📁 Content: {cc}/{user['max_content']}\n"
            f"📊 Views: {stats['total']} total · {stats['today']} today\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=_btn([_b("💳 Upgrade", "menu:plans"), _b("🖥 Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("new"))
    async def cmd_new(_c, m: Message):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2: return await m.reply_text(
            "📁 **Create Content**\n\n"
            "Usage:\n"
            "`/new Naruto Episode 1`\n"
            "`/new Kaiju No.8/Season 1/Episode 1`\n\n"
            "The `/` creates nested structure automatically!")
        user = db.get_user(m.from_user.id)
        if not user: return await m.reply_text("Send /start first.")
        raw_title = parts[1].strip()
        # Handle hierarchical paths: Title/SubTitle/SubSubTitle
        path_parts = [p.strip() for p in raw_title.split("/") if p.strip()]
        if not path_parts: return await m.reply_text("❌ Invalid title.")
        cc = db.count_content_by_owner(m.from_user.id)
        if cc + len(path_parts) > user["max_content"] + 5:  # small buffer for hierarchy
            return await m.reply_text(f"❌ Content limit reached ({user['max_content']}). Upgrade plan.")
        parent_id = None
        created_slugs = []
        for i, part_title in enumerate(path_parts):
            slug = _slugify(part_title)
            if not slug: slug = f"content-{secrets.token_hex(4)}"
            # Check if this already exists under this parent
            existing = db.get_content_by_slug(slug)
            if existing and existing["owner_id"] == m.from_user.id:
                parent_id = existing["id"]
                created_slugs.append((part_title, slug, False))
                continue
            try:
                new_id = db.create_content(m.from_user.id, part_title, slug, parent_id=parent_id)
                parent_id = new_id
                created_slugs.append((part_title, slug, True))
            except:
                slug = f"{slug}-{secrets.token_hex(3)}"
                try:
                    new_id = db.create_content(m.from_user.id, part_title, slug, parent_id=parent_id)
                    parent_id = new_id
                    created_slugs.append((part_title, slug, True))
                except Exception as e:
                    return await m.reply_text(f"❌ Error creating '{part_title}': {e}")
        last_slug = created_slugs[-1][1]
        path_display = " → ".join(f"**{t}**" for t, _, _ in created_slugs)
        new_items = sum(1 for _, _, is_new in created_slugs if is_new)
        await m.reply_text(
            f"✅ **Content Created!**\n\n"
            f"📂 {path_display}\n"
            f"🏷 Slug: `{last_slug}`\n"
            f"📦 {new_items} new item(s)\n\n"
            f"📹 Send a video, then:\n`/add {last_slug} Hindi 720p`",
            reply_markup=_btn(
                [_b("🔗 Get Links", f"links:{last_slug}"), _b("📁 My Content", "menu:content")]))

    @tg_client.on_message(filters.private & (filters.video | filters.document))
    async def on_video(_c, m: Message):
        media = m.video or (m.document if m.document and (m.document.mime_type or "").startswith("video/") else None)
        if not media: return
        q = _detect_quality(getattr(media,"width",0) or 0, getattr(media,"height",0) or 0)
        _pending_videos[m.from_user.id] = {
            "file_id": media.file_id, "file_unique_id": media.file_unique_id,
            "file_size": media.file_size or 0, "duration": getattr(media,"duration",0) or 0,
            "width": getattr(media,"width",0) or 0, "height": getattr(media,"height",0) or 0,
            "file_name": getattr(media,"file_name","") or ""}
        try: db.save_video({"file_id":media.file_id,"file_unique_id":media.file_unique_id,"file_size":media.file_size or 0,
            "duration":getattr(media,"duration",0) or 0,"width":getattr(media,"width",0) or 0,"height":getattr(media,"height",0) or 0,
            "file_name":getattr(media,"file_name","") or "","mime_type":media.mime_type or "video/mp4",
            "caption":m.caption or "","message_id":m.id,"channel_id":m.chat.id,"quality":q})
        except: pass
        fname = getattr(media,'file_name','') or 'N/A'
        fsize = _fmt_size(media.file_size or 0)
        await m.reply_text(
            f"📹 **Video Received!**\n\n"
            f"📄 {fname}\n"
            f"📊 {q} · {fsize}\n\n"
            f"To add to content:\n"
            f"`/add <slug> <Language> <Quality>`\n\n"
            f"Example: `/add naruto-ep1 Hindi {q}`", quote=True)

    @tg_client.on_message(filters.private & filters.command("add"))
    async def cmd_add(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 4: return await m.reply_text("Usage: `/add slug Language Quality`\n\nSend video first!")
        slug, lang, qual = parts[1], parts[2], parts[3]
        pending = _pending_videos.get(m.from_user.id)
        if not pending: return await m.reply_text("⚠️ Send a video first.")
        content = db.get_content_by_slug(slug)
        if not content: return await m.reply_text(f"❌ `{slug}` not found. Create with /new.")
        if content["owner_id"] != m.from_user.id: return await m.reply_text("❌ Not your content.")
        try:
            db.add_source(content["id"], pending["file_id"], lang, qual, pending["file_unique_id"],
                pending["file_size"], pending["duration"], pending["width"], pending["height"])
            del _pending_videos[m.from_user.id]
            sources = db.get_sources_by_content(content["id"])
            ss = " · ".join(f"{s['language']} {s['quality']}" for s in sources)
            await m.reply_text(
                f"✅ **Source Added!**\n\n"
                f"📁 {content['title']}\n"
                f"🎬 {lang} {qual}\n"
                f"📺 All: {ss}",
                reply_markup=_btn([_b("🔗 Get Links", f"links:{slug}"), _b("📁 Content", "menu:content")]))
        except Exception as e: await m.reply_text(f"❌ Error: {e}")

    @tg_client.on_message(filters.private & filters.command("links"))
    async def cmd_links(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/links slug`")
        content = db.get_content_by_slug(parts[1])
        if not content: return await m.reply_text("❌ Not found.")
        sources = db.get_sources_by_content(content["id"])
        base = BASE()
        langs = {}
        for s in sources: langs.setdefault(s["language"],[]).append(s["quality"])
        ss = "\n".join(f"  🎬 {l}: {', '.join(q)}" for l,q in langs.items())
        watch_url = f"{base}/watch/{content['slug']}"
        await m.reply_text(
            f"🔗 **{content['title']}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"▶️ **Player:**\n`{watch_url}`\n\n"
            f"🖼 **iFrame:**\n`<iframe src=\"{base}/embed/{content['slug']}\" width=\"720\" height=\"405\" allowfullscreen></iframe>`\n\n"
            f"📺 **Sources:**\n{ss}\n\n"
            f"⚡ MTProto — NO 20MB limit",
            disable_web_page_preview=True,
            reply_markup=_btn([_b("▶️ Watch", url=watch_url), _b("🖥 Panel", url=f"{base}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("myvideos"))
    async def cmd_myvideos(_c, m: Message):
        items = db.list_content_by_owner(m.from_user.id, 20)
        if not items: return await m.reply_text("📭 No content yet.\n\nUse /new to create!",
            reply_markup=_btn([_b("📁 Create Content", "menu:new_help")]))
        lines = "\n".join(f"{'📂' if True else '📄'} **{c['title']}** (`{c['slug']}`) — {c.get('source_count',0)} sources" for c in items)
        await m.reply_text(
            f"📁 **My Content ({len(items)})**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n{lines}",
            reply_markup=_btn([_b("📁 Create New", "menu:new_help"), _b("🖥 Panel", url=f"{BASE()}/panel/content")]))

    @tg_client.on_message(filters.private & filters.command("delete"))
    async def cmd_delete(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/delete slug`")
        content = db.get_content_by_slug(parts[1])
        if not content: return await m.reply_text("❌ Not found.")
        if content["owner_id"] != m.from_user.id and not is_ma(m.from_user.id):
            return await m.reply_text("❌ Not your content.")
        db.delete_content(content["id"])
        await m.reply_text(f"🗑 Deleted: **{content['title']}**")

    @tg_client.on_message(filters.private & filters.command("proof"))
    async def cmd_proof(_c, m: Message):
        if m.reply_to_message and m.reply_to_message.photo:
            fid = m.reply_to_message.photo.file_id
            _pending_proofs[m.from_user.id] = fid
            await m.reply_text("✅ **Screenshot saved!**\n\nNow go to the payment page and submit your proof.")
        else:
            await m.reply_text(
                "📸 **Submit Payment Proof**\n\n"
                "1. Send payment screenshot as a photo\n"
                "2. Reply to that photo with /proof\n"
                "3. Go to payment page and fill the form")

    @tg_client.on_message(filters.private & filters.command("status"))
    async def cmd_status(_c, m: Message):
        c = tg_client.is_connected
        cc = db.count_content_by_owner(m.from_user.id)
        stats = db.get_view_stats_by_owner(m.from_user.id)
        await m.reply_text(
            f"📊 **Server Status**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔌 MTProto: {'✅ Connected' if c else '❌ Disconnected'}\n"
            f"📦 20MB Limit: **BYPASSED**\n"
            f"📁 My content: {cc}\n"
            f"👁 Views: {stats['total']} total · {stats['today']} today\n"
            f"🌐 Server: {BASE()}")

    # ── Main Admin Commands ──────────────────────────────────

    @tg_client.on_message(filters.private & filters.command("addchannel"))
    async def cmd_addchannel(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 3: return await m.reply_text("Usage: `/addchannel Name -100xxxx [category]`")
        db.create_channel(parts[1], int(parts[2]), parts[3] if len(parts)>3 else "general")
        await m.reply_text(f"✅ Channel **{parts[1]}** added")

    @tg_client.on_message(filters.private & filters.command("channels"))
    async def cmd_channels(_c, m: Message):
        if not is_ma(m.from_user.id): return
        chs = db.list_channels()
        if not chs: return await m.reply_text("No channels.")
        lines = "\n".join(f"• **{c['name']}** `{c['channel_id']}` ({c['category']})" for c in chs)
        await m.reply_text(f"📺 **Channels:**\n\n{lines}")

    @tg_client.on_message(filters.private & filters.command("rmchannel"))
    async def cmd_rmchannel(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/rmchannel Name`")
        ch = db.get_channel_by_name(parts[1])
        if ch: db.delete_channel(ch["id"]); await m.reply_text(f"🗑 Removed")
        else: await m.reply_text("Not found.")

    @tg_client.on_message(filters.private & filters.command("users"))
    async def cmd_users(_c, m: Message):
        if not is_ma(m.from_user.id): return
        users = db.list_users(20)
        lines = "\n".join(f"• @{u.get('username','') or '—'} `{u['telegram_id']}` — {u.get('plan_name') or 'Free'} {'🔴' if not u['is_active'] else ''}" for u in users)
        await m.reply_text(f"👤 **Users ({len(users)}):**\n\n{lines}",
            reply_markup=_btn([_b("🖥 Admin Panel", url=f"{BASE()}/{AP}/users")]))

    @tg_client.on_message(filters.private & filters.command("grant"))
    async def cmd_grant(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 3: return await m.reply_text("Usage: `/grant telegram_id plan_slug`")
        plan = db.get_plan(parts[2])
        if not plan: return await m.reply_text("Plan not found.")
        db.set_user_plan(int(parts[1]), plan["id"], plan["duration_days"])
        await m.reply_text(f"✅ Granted **{plan['name']}** to `{parts[1]}`")
        try: await tg_client.send_message(int(parts[1]), f"🎉 Plan upgraded to **{plan['name']}**! Valid for {plan['duration_days']} days.")
        except: pass

    @tg_client.on_message(filters.private & filters.command("revoke"))
    async def cmd_revoke(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/revoke telegram_id`")
        free = db.get_plan("free")
        if free: db.set_user_plan(int(parts[1]), free["id"], 0)
        await m.reply_text(f"✅ Revoked to Free: `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("ban"))
    async def cmd_ban(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/ban telegram_id`")
        db.ban_user(int(parts[1])); await m.reply_text(f"🚫 Banned `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("unban"))
    async def cmd_unban(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 2: return await m.reply_text("Usage: `/unban telegram_id`")
        db.unban_user(int(parts[1])); await m.reply_text(f"✅ Unbanned `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("stats"))
    async def cmd_stats(_c, m: Message):
        if not is_ma(m.from_user.id): return
        stats = db.get_view_stats_global()
        uc = db.count_users()
        pending = 0
        try: pending = db.count_pending_requests()
        except: pass
        await m.reply_text(
            f"📊 **Global Stats**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Users: {uc}\n"
            f"👁 Views: {stats['total']} total · {stats['today']} today\n"
            f"🌐 Unique IPs: {stats['unique_ips']}\n"
            f"📩 Pending Requests: {pending}",
            reply_markup=_btn([_b("🖥 Admin Panel", url=f"{BASE()}/{AP}")]))

    @tg_client.on_message(filters.private & filters.command("broadcast"))
    async def cmd_broadcast(_c, m: Message):
        if not is_ma(m.from_user.id): return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2: return await m.reply_text("Usage: `/broadcast Your message`")
        msg = parts[1]; users = db.list_users(500); sent = 0
        for u in users:
            try: await tg_client.send_message(u["telegram_id"], f"📢 **Broadcast:**\n\n{msg}"); sent += 1
            except: pass
        await m.reply_text(f"✅ Broadcast sent to {sent}/{len(users)} users.")

    @tg_client.on_message(filters.channel & (filters.video | filters.document))
    async def on_channel_video(_c, m: Message):
        media = m.video or (m.document if m.document and (m.document.mime_type or "").startswith("video/") else None)
        if not media: return
        try: db.save_video({"file_id":media.file_id,"file_unique_id":media.file_unique_id,"file_size":media.file_size or 0,
            "duration":getattr(media,"duration",0) or 0,"width":getattr(media,"width",0) or 0,"height":getattr(media,"height",0) or 0,
            "file_name":getattr(media,"file_name","") or "","mime_type":media.mime_type or "video/mp4","caption":m.caption or "",
            "message_id":m.id,"channel_id":m.chat.id,"quality":_detect_quality(getattr(media,"width",0) or 0,getattr(media,"height",0) or 0)})
        except: pass

    # ── Callback Query Handler ───────────────────────────────

    @tg_client.on_callback_query()
    async def on_callback(client, cq: CallbackQuery):
        data = cq.data or ""
        uid = cq.from_user.id

        if data == "menu:content":
            items = db.list_content_by_owner(uid, 10)
            if not items:
                await cq.answer("No content yet. Use /new", show_alert=True)
                return
            lines = "\n".join(f"📁 **{c['title']}** (`{c['slug']}`) — {c.get('source_count',0)} src" for c in items)
            await cq.message.edit_text(f"📁 **My Content:**\n\n{lines}",
                reply_markup=_btn([_b("📁 Create New", "menu:new_help"), _b("🖥 Panel", url=f"{BASE()}/panel/content")]))

        elif data == "menu:plans":
            plans = db.list_plans()
            lines = "\n".join(f"{'🆓' if p['slug']=='free' else '💎'} **{p['name']}** — ₹{p['price']} | {p['max_content']} content | {p['duration_days']}d" for p in plans)
            await cq.message.edit_text(f"💳 **Plans:**\n\n{lines}\n\nUse /subscribe for details.",
                reply_markup=_btn([_b("💳 View Details", "menu:subscribe_detail")]))

        elif data == "menu:subscribe_detail":
            await cq.answer("Use /subscribe command", show_alert=True)

        elif data == "menu:status":
            c = tg_client.is_connected
            cc = db.count_content_by_owner(uid)
            await cq.answer(f"MTProto: {'ON' if c else 'OFF'} | Content: {cc}", show_alert=True)

        elif data == "menu:new_help":
            await cq.answer("Use: /new Title or /new Title/Season/Episode", show_alert=True)

        elif data == "menu:trial":
            await cq.answer("Use /trial command", show_alert=True)

        elif data.startswith("links:"):
            slug = data[6:]
            content = db.get_content_by_slug(slug)
            if not content: return await cq.answer("Not found", show_alert=True)
            base = BASE()
            await cq.message.edit_text(
                f"🔗 **{content['title']}**\n\n▶️ `{base}/watch/{slug}`",
                reply_markup=_btn([_b("▶️ Watch", url=f"{base}/watch/{slug}"), _b("🖥 Panel", url=f"{base}/panel/login")]))

        elif data.startswith("buy:"):
            plan_slug = data[4:]
            base = BASE()
            await cq.message.edit_text(
                f"💳 **Purchase Plan**\n\nComplete payment on the panel:",
                reply_markup=_btn([_b("💰 Pay Now", url=f"{base}/panel/subscription/pay/{plan_slug}"), _b("← Back", "menu:plans")]))

        else:
            await cq.answer("Unknown action", show_alert=True)

    logger.info("Bot handlers registered (v2.0 — inline buttons + hierarchy).")

# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=STREAM_HOST, port=STREAM_PORT, log_level="info")
