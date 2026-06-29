"""
Shared helper functions used across all modules.
Extracted from server.py to avoid circular dependencies.
"""
import re
import time
import hmac
import hashlib
import logging
import bcrypt
from html import escape as he
from urllib.parse import quote as url_quote

from config import (
    STREAM_SECRET, STREAM_BASE_URL, STREAM_PORT,
    TOKEN_LIFETIME, ADMIN_PASSWORD, ADMIN_SECRET_PATH,
)
import database as db
from admin_templates import admin_page
from panel_templates import panel_page

logger = logging.getLogger(__name__)

# ── Admin path alias ─────────────────────────────────────────
AP = ADMIN_SECRET_PATH

# ── URL helpers ──────────────────────────────────────────────

def BASE():
    return STREAM_BASE_URL or f"http://localhost:{STREAM_PORT}"

def _sign(payload):
    return hmac.new(STREAM_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def make_stream_url(file_id, file_size=0):
    exp = int(time.time()) + TOKEN_LIFETIME
    return f"{BASE()}/stream/{url_quote(file_id)}?token={_sign(f'{file_id}:{exp}:{file_size}')}&expires={exp}&size={file_size}"

def validate_stream_token(file_id, token, expires, file_size=0):
    if not token or not expires or time.time() > expires:
        return False
    return hmac.compare_digest(token, _sign(f"{file_id}:{expires}:{file_size}"))

# ── Auth helpers ─────────────────────────────────────────────

def admin_cookie():
    return _sign(f"admin:{ADMIN_PASSWORD}")[:48]

def panel_cookie(tg_id):
    return _sign(f"panel:{tg_id}")[:48]

def is_admin(request):
    return request.cookies.get("admin_token") == admin_cookie()

def get_panel_user(request):
    tg_id = request.cookies.get("panel_tg_id", "")
    tok = request.cookies.get("panel_token", "")
    if tg_id and tok and tok == panel_cookie(tg_id):
        user = db.get_user(int(tg_id))
        if user and user.get("is_active"):
            return user
    return None

# ── String helpers ───────────────────────────────────────────

def slugify(text):
    s = re.sub(r'[^a-z0-9\s-]', '', text.lower().strip())
    return re.sub(r'[\s-]+', '-', s).strip('-')[:200]

def fmt_size(b):
    if not b:
        return "—"
    if b >= 1073741824:
        return f"{b/1073741824:.2f} GB"
    if b >= 1048576:
        return f"{b/1048576:.1f} MB"
    return f"{b/1024:.0f} KB"

def detect_quality(w, h):
    r = min(w, h) if w > 0 and h > 0 else max(w, h)
    if r >= 2160:
        return "2160p"
    if r >= 1080:
        return "1080p"
    if r >= 720:
        return "720p"
    return "480p"

# ── HTML helpers ─────────────────────────────────────────────

def flash(msg):
    return f'<div class="flash flash-ok">{he(str(msg))}</div>' if msg else ""

def escape(text):
    return he(str(text)) if text else ""

# ── Password helpers ─────────────────────────────────────────

def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_password(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

# ── Template wrappers ────────────────────────────────────────

def admin_html(body, title="Dashboard", active="dashboard"):
    from fastapi.responses import HTMLResponse
    pending = 0
    try:
        pending = db.count_pending_requests()
    except Exception:
        pass
    return HTMLResponse(admin_page(body, title, active, admin_path=AP, pending_requests=pending))

def panel_html(body, user, title="Dashboard", active="dashboard"):
    from fastapi.responses import HTMLResponse
    plan = user.get("plan_name") or "Free"
    return HTMLResponse(panel_page(body, plan, title, active))

# ── Rate limiting ────────────────────────────────────────────

from collections import defaultdict
_login_attempts = defaultdict(list)

def rate_limited(ip, max_attempts=5, window=900):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < window]
    if len(_login_attempts[ip]) >= max_attempts:
        return True
    _login_attempts[ip].append(now)
    return False
