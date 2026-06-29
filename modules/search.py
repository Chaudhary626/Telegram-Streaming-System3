"""
Search & Duplicate Detection module.
Provides content search API and duplicate checking.
"""
import logging
from html import escape as he

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

import database as db
from helpers import AP, is_admin, get_panel_user, admin_html, flash, escape

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register search routes."""

    # ── Admin Search ───────────────────────────────────────────

    @app.get(f"/{AP}/search")
    async def admin_search(request: Request, q: str = "", msg: str = ""):
        from fastapi.responses import RedirectResponse
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        results = []
        if q.strip():
            results = db.search_content(q.strip(), limit=50)

        rows = ""
        for item in results:
            title = escape(item.get('title', ''))
            slug = escape(item.get('slug', ''))
            cat = escape(item.get('category', 'general'))
            owner = item.get('owner_id', 0)
            sources = item.get('source_count', 0)
            created = str(item.get('created_at', ''))[:16]
            rows += f"""<tr>
<td>#{item['id']}</td><td><b>{title}</b><br><small style="color:var(--txt2)">{slug}</small></td>
<td><span class="badge">{cat}</span></td><td>{owner}</td><td>{sources}</td>
<td><small>{created}</small></td></tr>"""

        table = ""
        if q.strip():
            table = f"""<p style="margin:12px 0;color:var(--txt2)">Found <b>{len(results)}</b> result(s) for \"{escape(q)}\"</p>
<table>
<thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Owner</th><th>Sources</th><th>Created</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--txt2)">No results found</td></tr>'}</tbody>
</table>"""

        search_form = f"""<div style="margin-bottom:16px">
<form method="get" action="/{AP}/search" style="display:flex;gap:8px">
  <input name="q" value="{escape(q)}" placeholder="Search content by title or slug..." style="flex:1;padding:10px;border:1px solid var(--bdr);border-radius:8px;background:var(--s1);color:var(--txt)">
  <button class="btn">🔍 Search</button>
</form></div>"""

        body = f"{flash(msg)}<h1>🔍 Search</h1>{search_form}{table}"
        return admin_html(body, title="Search", active="search")

    # ── Public Search API ───────────────────────────────────

    @app.get("/api/search")
    async def api_search(q: str = "", limit: int = 20):
        if not q.strip():
            return JSONResponse([])
        results = db.search_content(q.strip(), limit=min(limit, 50))
        return JSONResponse([{
            "id": r["id"],
            "title": r.get("title", ""),
            "slug": r.get("slug", ""),
            "category": r.get("category", "general"),
            "source_count": r.get("source_count", 0),
        } for r in results])

    # ── Panel Search ───────────────────────────────────────

    @app.get("/panel/search")
    async def panel_search(request: Request, q: str = ""):
        user = get_panel_user(request)
        if not user:
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/panel/login")
        results = []
        if q.strip():
            results = db.search_content(q.strip(), owner_id=user["telegram_id"], limit=30)
        from helpers import panel_html

        rows = ""
        for item in results:
            title = escape(item.get('title', ''))
            slug = escape(item.get('slug', ''))
            sources = item.get('source_count', 0)
            rows += f'<tr><td><b>{title}</b></td><td><code>{slug}</code></td><td>{sources}</td></tr>'

        table = ""
        if q.strip():
            table = f"""<p style="margin:12px 0;color:var(--txt2)">Found <b>{len(results)}</b> result(s)</p>
<table><thead><tr><th>Title</th><th>Slug</th><th>Sources</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="3" style="text-align:center;padding:20px">No results</td></tr>'}</tbody></table>"""

        search_form = f"""<div style="margin-bottom:16px">
<form method="get" style="display:flex;gap:8px">
  <input name="q" value="{escape(q)}" placeholder="Search your content..." style="flex:1;padding:10px;border:1px solid var(--bdr);border-radius:8px;background:var(--s1);color:var(--txt)">
  <button class="btn">🔍</button>
</form></div>"""

        body = f"<h1>🔍 Search</h1>{search_form}{table}"
        return panel_html(body, user, "Search", "search")

    # ── Duplicate Check API ─────────────────────────────────

    @app.get("/api/duplicate-check")
    async def api_duplicate_check(request: Request, file_unique_id: str = ""):
        if not is_admin(request) and not get_panel_user(request):
            raise HTTPException(403)
        if not file_unique_id:
            return JSONResponse({"duplicate": False})
        dup = db.check_duplicate_source(file_unique_id)
        if dup:
            return JSONResponse({"duplicate": True, "existing": {
                "content_id": dup.get("content_id"),
                "title": dup.get("title", ""),
                "slug": dup.get("slug", ""),
                "language": dup.get("language", ""),
                "quality": dup.get("quality", ""),
            }})
        # Check legacy table too
        legacy = db.check_duplicate_video(file_unique_id)
        if legacy:
            return JSONResponse({"duplicate": True, "legacy": True, "file_id": legacy.get("file_id", "")})
        return JSONResponse({"duplicate": False})

    logger.info("Module: search routes registered.")
