"""
Downloads module — Secure token-based file download endpoints.
Generates time-limited download tokens and serves files.
"""
import time
import hmac
import hashlib
import logging

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse

import database as db
from config import STREAM_SECRET, TOKEN_LIFETIME
from helpers import AP, is_admin, get_panel_user, admin_html, panel_html, flash, escape

logger = logging.getLogger(__name__)


def _generate_download_token(content_id: int, source_id: int, expires: int = 0) -> str:
    """Generate HMAC-signed download token."""
    if expires <= 0:
        expires = int(time.time()) + TOKEN_LIFETIME
    payload = f"{content_id}:{source_id}:{expires}"
    sig = hmac.new(STREAM_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{content_id}.{source_id}.{expires}.{sig}"


def _validate_download_token(token: str):
    """Validate and parse download token. Returns (content_id, source_id) or None."""
    try:
        parts = token.split('.')
        if len(parts) != 4:
            return None
        content_id, source_id, expires, sig = int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        if int(time.time()) > expires:
            return None
        payload = f"{content_id}:{source_id}:{expires}"
        expected = hmac.new(STREAM_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        return (content_id, source_id)
    except Exception:
        return None


def register(app, ctx):
    """Register download routes."""

    # ── Generate Download Token ──────────────────────────────

    @app.get("/api/download/token")
    async def api_get_download_token(request: Request, content_id: int = 0, source_id: int = 0):
        """Generate a download token for a content+source pair.
        Requires admin or panel user auth."""
        user = get_panel_user(request)
        admin = is_admin(request)
        if not user and not admin:
            raise HTTPException(403, "Authentication required")

        if not content_id or not source_id:
            raise HTTPException(400, "content_id and source_id required")

        # Verify content exists
        content = db.get_content_by_id(content_id)
        if not content:
            raise HTTPException(404, "Content not found")

        # Check ownership for panel users
        if user and not admin:
            if content.get('owner_id') != user.get('telegram_id'):
                # Check if user has download permission
                try:
                    if not db.has_permission(user.get('telegram_id', 0), 'download.enabled'):
                        raise HTTPException(403, "Download not permitted")
                except Exception:
                    pass

        token = _generate_download_token(content_id, source_id)
        return JSONResponse({
            "token": token,
            "download_url": f"/api/download/{token}",
            "expires_in": TOKEN_LIFETIME,
        })

    # ── Download File ────────────────────────────────────────

    @app.get("/api/download/{token}")
    async def api_download_file(token: str, request: Request):
        """Download a file using a signed token."""
        parsed = _validate_download_token(token)
        if not parsed:
            raise HTTPException(403, "Invalid or expired download token")

        content_id, source_id = parsed

        # Get content and source info
        content = db.get_content_by_id(content_id)
        if not content:
            raise HTTPException(404, "Content not found")

        source = db.get_source_by_id(source_id)
        if not source:
            raise HTTPException(404, "Source not found")

        # Get streamer from context
        streamer = ctx.get('streamer')
        if not streamer:
            raise HTTPException(503, "Streaming service unavailable")

        # Determine filename
        title = content.get('title', 'download')
        quality = source.get('quality', '')
        language = source.get('language', '')
        ext = '.mp4'  # Default
        filename = f"{title}"
        if language:
            filename += f" [{language}]"
        if quality:
            filename += f" ({quality})"
        filename += ext
        # Sanitize filename
        filename = ''.join(c for c in filename if c.isalnum() or c in ' ._-[]()').strip()
        if not filename:
            filename = f"download_{content_id}{ext}"

        # Get file reference
        file_ref = str(source.get('message_id', '') or source.get('file_id', ''))
        if not file_ref:
            raise HTTPException(404, "No file reference available")

        try:
            file_size = await streamer.get_file_size(file_ref)
        except Exception:
            file_size = 0

        # Log download
        try:
            ip = request.client.host if request.client else ''
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
            db.log_player_event(
                content_id=content_id,
                source_id=source_id,
                owner_id=content.get('owner_id', 0),
                event_type='download',
                ip_hash=ip_hash,
                user_agent=request.headers.get('user-agent', '')[:255]
            )
        except Exception:
            pass

        # Stream response as download
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'none',
        }
        if file_size > 0:
            headers['Content-Length'] = str(file_size)

        async def generate():
            async for chunk in streamer.stream(file_ref):
                yield chunk

        return StreamingResponse(generate(), headers=headers, media_type='video/mp4')

    # ── Admin Download Stats ─────────────────────────────────

    @app.get(f"/{AP}/downloads")
    async def admin_downloads_page(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        # Get download events
        try:
            from database import get_connection
            with get_connection() as conn:
                with conn.cursor() as c:
                    c.execute(
                        "SELECT COUNT(*) AS cnt FROM tg_player_events WHERE event_type='download'")
                    total_downloads = c.fetchone()['cnt']
                    c.execute(
                        "SELECT COUNT(*) AS cnt FROM tg_player_events "
                        "WHERE event_type='download' AND DATE(created_at)=CURDATE()")
                    today_downloads = c.fetchone()['cnt']
                    c.execute(
                        "SELECT c.title, c.slug, COUNT(pe.id) AS dl_count "
                        "FROM tg_player_events pe "
                        "JOIN tg_content c ON c.id=pe.content_id "
                        "WHERE pe.event_type='download' "
                        "GROUP BY pe.content_id ORDER BY dl_count DESC LIMIT 10")
                    top_downloads = c.fetchall()
        except Exception:
            total_downloads = 0
            today_downloads = 0
            top_downloads = []

        top_rows = ''
        for i, item in enumerate(top_downloads, 1):
            title = escape(item.get('title', 'Unknown'))
            slug = escape(item.get('slug', ''))
            count = item.get('dl_count', 0)
            top_rows += f'<tr><td>{i}</td><td><b>{title}</b><br><small style="color:var(--txt2)">{slug}</small></td><td>{count:,}</td></tr>'

        body = f"""<h1>📥 Downloads</h1>
<div class="grid grid-2" style="margin-bottom:16px">
  <div class="stat-card"><div class="stat-value">{total_downloads:,}</div><div class="stat-label">Total Downloads</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{today_downloads:,}</div><div class="stat-label">Today</div></div>
</div>
<div class="card">
  <h3>🏆 Most Downloaded</h3>
  <table><thead><tr><th>#</th><th>Content</th><th>Downloads</th></tr></thead>
  <tbody>{top_rows if top_rows else '<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--txt2)">No downloads yet</td></tr>'}</tbody></table>
</div>
<div class="card" style="margin-top:16px;padding:16px">
  <h3>🔗 Download API</h3>
  <p style="color:var(--txt2)">Generate download tokens via the API:</p>
  <pre style="background:var(--bg2);padding:12px;border-radius:8px;overflow-x:auto"><code>GET /api/download/token?content_id=123&source_id=456
Response: {{"token": "...", "download_url": "/api/download/...", "expires_in": 14400}}</code></pre>
</div>"""
        return admin_html(body, title="Downloads", active="downloads")

    logger.info("Module: downloads routes registered.")
