"""
Streaming module — /stream, /watch, /embed, API endpoints.
Extracted from server.py for modular architecture.
"""
import hashlib
import logging
from urllib.parse import quote as url_quote

from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, Response

import database as db
from helpers import validate_stream_token, make_stream_url, escape, BASE
from player import WATCH_PAGE, EMBED_PAGE

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register streaming routes on the FastAPI app."""
    streamer_ref = ctx  # ctx holds streamer reference

    def _get_streamer():
        return ctx.get("streamer")

    # ── /stream/{file_id} — Direct streaming ─────────────────

    @app.get("/stream/{file_id}")
    async def stream_video(file_id: str, request: Request, token: str = "", expires: int = 0, size: int = 0):
        streamer = _get_streamer()
        if not streamer:
            raise HTTPException(503)
        if not validate_stream_token(file_id, token, expires, size):
            raise HTTPException(403)
        file_size = size
        if not file_size:
            vid = db.get_video_by_file_id(file_id)
            if vid:
                file_size = vid.get("file_size", 0) or 0
            if not file_size:
                try:
                    file_size = await streamer.get_file_size(file_id)
                except Exception:
                    pass
        else:
            streamer.cache_file_size(file_id, file_size)
        rng = request.headers.get("range", "")
        start, end, is_range = 0, (file_size - 1 if file_size else None), False
        if rng and file_size:
            is_range = True
            parts = rng.replace("bytes=", "").split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        clen = (end - start + 1) if end is not None else None
        hdrs = {"Content-Type": "video/mp4", "Accept-Ranges": "bytes",
                "Cache-Control": "no-store", "X-Stream-Method": "direct"}
        if file_size and clen:
            hdrs["Content-Length"] = str(clen)
        if is_range and file_size:
            hdrs["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        async def gen():
            try:
                async for chunk in streamer.stream(file_id, offset=start, end=end):
                    yield chunk
            except Exception as e:
                logger.error(f"Stream err: {e}")

        return StreamingResponse(gen(), status_code=206 if is_range else 200,
                                 headers=hdrs, media_type="video/mp4")

    @app.head("/stream/{file_id}")
    async def stream_head(file_id: str, token: str = "", expires: int = 0, size: int = 0):
        if not validate_stream_token(file_id, token, expires, size):
            raise HTTPException(403)
        hdrs = {"Content-Type": "video/mp4", "Accept-Ranges": "bytes"}
        if size:
            hdrs["Content-Length"] = str(size)
        return Response(headers=hdrs)

    # ── /watch + /embed — Smart player ───────────────────────

    @app.get("/watch/{slug}", response_class=HTMLResponse)
    async def watch_page_route(slug: str, request: Request):
        content = db.get_content_by_slug(slug)
        if not content:
            raise HTTPException(404)
        base = BASE()
        try:
            db.log_view(content["id"], owner_id=content["owner_id"],
                        ip_hash=hashlib.md5((request.client.host or "").encode()).hexdigest()[:16],
                        user_agent=(request.headers.get("user-agent") or "")[:255])
        except Exception:
            pass
        return HTMLResponse(WATCH_PAGE.format(
            title=escape(content["title"]), slug=slug,
            api_sources_url=f"{base}/api/sources/{url_quote(slug)}",
            api_ads_url=f"{base}/api/ads/{content['owner_id']}"))

    @app.get("/embed/{slug}", response_class=HTMLResponse)
    async def embed_page_route(slug: str):
        content = db.get_content_by_slug(slug)
        if not content:
            raise HTTPException(404)
        base = BASE()
        return HTMLResponse(EMBED_PAGE.format(
            api_sources_url=f"{base}/api/sources/{url_quote(slug)}",
            api_ads_url=f"{base}/api/ads/{content['owner_id']}"))

    # ── API endpoints ────────────────────────────────────────

    @app.get("/api/sources/{slug}")
    async def api_sources(slug: str):
        content = db.get_content_by_slug(slug)
        if not content:
            return JSONResponse({"success": False}, 404)
        sources = db.get_sources_by_content(content["id"])
        return JSONResponse({"success": True, "title": content["title"], "slug": slug,
            "sources": [{"language": s["language"], "quality": s["quality"],
                "url": make_stream_url(s["file_id"], s["file_size"] or 0),
                "file_size": s["file_size"] or 0, "duration": s["duration"] or 0,
                "label": s["label"] or f"{s['language']} {s['quality']}"} for s in sources]})

    @app.get("/api/ads/{owner_id}")
    async def api_ads(owner_id: int):
        ads = db.get_active_ads_by_owner(owner_id)
        return JSONResponse([{"ad_type": a["ad_type"], "ad_url": a["ad_url"],
            "ad_html": a["ad_html"], "position": a["position"],
            "duration": a["duration"], "is_active": True} for a in ads])

    logger.info("Module: streaming routes registered.")
