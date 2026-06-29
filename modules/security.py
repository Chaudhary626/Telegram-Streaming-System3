"""
Security module — Rate limiting, CSRF protection, Audit logs.
"""
import time
import hashlib
import secrets
import logging
from collections import defaultdict

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import database as db
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# RATE LIMITER
# ══════════════════════════════════════════════════════════════

class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self, max_requests=60, window_sec=60):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._hits = defaultdict(list)  # ip -> [timestamps]

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        window_start = now - self.window_sec
        # Prune old entries
        self._hits[ip] = [t for t in self._hits[ip] if t > window_start]
        if len(self._hits[ip]) >= self.max_requests:
            return False
        self._hits[ip].append(now)
        return True

    def remaining(self, ip: str) -> int:
        now = time.time()
        window_start = now - self.window_sec
        self._hits[ip] = [t for t in self._hits[ip] if t > window_start]
        return max(0, self.max_requests - len(self._hits[ip]))

    def cleanup(self):
        """Remove expired entries to prevent memory leak."""
        now = time.time()
        expired = []
        for ip, hits in self._hits.items():
            if not hits or hits[-1] < now - self.window_sec * 2:
                expired.append(ip)
        for ip in expired:
            del self._hits[ip]


# Global rate limiters
_api_limiter = RateLimiter(max_requests=120, window_sec=60)  # API: 120/min
_login_limiter = RateLimiter(max_requests=10, window_sec=300)  # Login: 10/5min
_upload_limiter = RateLimiter(max_requests=30, window_sec=60)  # Upload: 30/min


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Select limiter based on path
        if "/login" in path:
            limiter = _login_limiter
        elif path.startswith("/api/"):
            limiter = _api_limiter
        else:
            limiter = _api_limiter  # Default

        if not limiter.is_allowed(ip):
            logger.warning(f"Rate limit exceeded: {ip} on {path}")
            return JSONResponse(
                {"error": "Too many requests. Please try again later."},
                status_code=429,
                headers={"Retry-After": str(limiter.window_sec)}
            )

        response = await call_next(request)
        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(limiter.remaining(ip))
        return response


# ══════════════════════════════════════════════════════════════
# CSRF PROTECTION
# ══════════════════════════════════════════════════════════════

_csrf_tokens = {}  # session_key -> (token, expiry)
CSRF_TOKEN_LIFETIME = 3600  # 1 hour


def generate_csrf_token(session_key: str) -> str:
    """Generate and store a CSRF token for a session."""
    token = secrets.token_hex(32)
    _csrf_tokens[session_key] = (token, time.time() + CSRF_TOKEN_LIFETIME)
    # Cleanup old tokens periodically
    if len(_csrf_tokens) > 1000:
        _cleanup_csrf()
    return token


def validate_csrf_token(session_key: str, token: str) -> bool:
    """Validate a CSRF token."""
    stored = _csrf_tokens.get(session_key)
    if not stored:
        return False
    stored_token, expiry = stored
    if time.time() > expiry:
        del _csrf_tokens[session_key]
        return False
    return secrets.compare_digest(stored_token, token)


def _cleanup_csrf():
    now = time.time()
    expired = [k for k, (_, exp) in _csrf_tokens.items() if now > exp]
    for k in expired:
        del _csrf_tokens[k]


def csrf_input(session_key: str) -> str:
    """Generate hidden input HTML for CSRF token."""
    token = generate_csrf_token(session_key)
    return f'<input type="hidden" name="_csrf_token" value="{token}">'


# ══════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════

def register(app, ctx):
    """Register security routes and middleware."""

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # ── Audit Logs Page ──────────────────────────────────────

    @app.get(f"/{AP}/audit")
    async def admin_audit_page(request: Request, page: int = 1, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        per_page = 50
        offset = (page - 1) * per_page

        try:
            logs = db.get_activity_logs(limit=per_page, offset=offset)
        except Exception:
            logs = []

        rows = ""
        for log in logs:
            lid = log.get('id', 0)
            uid = log.get('user_id', 0)
            action = escape(log.get('action', ''))
            details = escape(str(log.get('details', ''))[:100])
            ip = log.get('ip_address', '')
            created = str(log.get('created_at', ''))[:19]

            # Color-code actions
            color = 'var(--txt)'
            if 'delete' in action.lower():
                color = 'var(--err)'
            elif 'create' in action.lower() or 'add' in action.lower():
                color = 'var(--ok)'
            elif 'login' in action.lower():
                color = 'var(--acc)'

            rows += f"""<tr>
<td><small>#{lid}</small></td>
<td>{uid}</td>
<td style="color:{color}"><b>{action}</b></td>
<td><small style="color:var(--txt2)">{details}</small></td>
<td><small><code>{ip}</code></small></td>
<td><small>{created}</small></td>
</tr>"""

        # Pagination
        prev_link = f'<a href="/{AP}/audit?page={page-1}" class="btn btn-sm">&laquo; Prev</a>' if page > 1 else ''
        next_link = f'<a href="/{AP}/audit?page={page+1}" class="btn btn-sm">Next &raquo;</a>' if len(logs) >= per_page else ''
        pagination = f'<div style="display:flex;justify-content:space-between;margin-top:16px">{prev_link}<span style="color:var(--txt2)">Page {page}</span>{next_link}</div>'

        # Stats
        try:
            total_logs = db.count_activity_logs()
        except Exception:
            total_logs = len(logs)

        body = f"""{flash(msg)}
<h1>📜 Audit Logs</h1>
<div class="grid grid-3" style="margin-bottom:16px">
  <div class="stat-card"><div class="stat-value">{total_logs:,}</div><div class="stat-label">Total Events</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{per_page}</div><div class="stat-label">Per Page</div></div>
  <div class="stat-card"><div class="stat-value">{page}</div><div class="stat-label">Current Page</div></div>
</div>
<table>
<thead><tr><th>ID</th><th>User</th><th>Action</th><th>Details</th><th>IP</th><th>Time</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--txt2)">No audit logs</td></tr>'}</tbody>
</table>
{pagination}"""
        return admin_html(body, title="Audit Logs", active="audit")

    # ── Security Status API ──────────────────────────────────

    @app.get("/api/security/status")
    async def api_security_status(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        ip = request.client.host if request.client else "unknown"
        return JSONResponse({
            "rate_limit": {
                "api_remaining": _api_limiter.remaining(ip),
                "login_remaining": _login_limiter.remaining(ip),
                "active_ips": len(_api_limiter._hits),
            },
            "csrf": {
                "active_tokens": len(_csrf_tokens),
            }
        })

    logger.info("Module: security routes registered.")
