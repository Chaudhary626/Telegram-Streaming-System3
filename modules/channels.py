"""
Channel Manager module — CRUD, auto-rotation, storage tracking.
"""
import logging
from html import escape as he

from fastapi import Request, Form
from fastapi.responses import RedirectResponse

import database as db
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register channel management routes."""

    @app.get(f"/{AP}/channels")
    async def admin_channels_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        channels = db.list_channels()

        # Group by category
        categories = {}
        for ch in channels:
            cat = ch.get('category', 'general')
            categories.setdefault(cat, []).append(ch)

        # Stats
        total = len(channels)
        active = sum(1 for ch in channels if ch.get('is_active', 1))
        total_storage = sum(ch.get('used_storage_gb', 0) or 0 for ch in channels)

        stat_cards = f"""
<div class="grid grid-4">
  <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Total Channels</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{active}</div><div class="stat-label">Active</div></div>
  <div class="stat-card"><div class="stat-value">{total - active}</div><div class="stat-label">Disabled</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{total_storage:.1f} GB</div><div class="stat-label">Total Storage</div></div>
</div>"""

        # Channel table
        rows = ""
        for ch in channels:
            cid = ch['id']
            name = escape(ch.get('name', ''))
            tid = ch.get('channel_id', '')
            cat = escape(ch.get('category', 'general'))
            act = ch.get('is_active', 1)
            used = ch.get('used_storage_gb', 0) or 0
            mx = ch.get('max_storage_gb', 50) or 50
            pct = min(100, (used / mx * 100)) if mx > 0 else 0
            status = '<span class="badge badge-success">Active</span>' if act else '<span class="badge badge-danger">Disabled</span>'
            bar_color = 'var(--ok)' if pct < 80 else ('var(--err)' if pct > 95 else '#f59e0b')
            storage_bar = f'<div style="background:var(--s2);border-radius:4px;height:8px;width:120px"><div style="background:{bar_color};height:100%;width:{pct}%;border-radius:4px"></div></div><small>{used:.1f}/{mx:.0f} GB</small>'

            rows += f"""<tr>
<td>#{cid}</td><td><b>{name}</b></td><td><code>{tid}</code></td>
<td><span class="badge">{cat}</span></td><td>{status}</td>
<td>{storage_bar}</td>
<td>
  <a href="/{AP}/channels/{cid}/toggle" class="btn btn-sm">{'⏸' if act else '▶️'}</a>
  <a href="/{AP}/channels/{cid}/delete" class="btn btn-sm btn-danger" onclick="return confirm('Delete channel?')">🗑</a>
</td></tr>"""

        table = f"""<table>
<thead><tr><th>ID</th><th>Name</th><th>Channel ID</th><th>Category</th><th>Status</th><th>Storage</th><th>Actions</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--txt2)">No channels. Add one below.</td></tr>'}</tbody>
</table>"""

        # Add channel form
        add_form = f"""<div class="card" style="margin-top:20px">
<h3>➕ Add Channel</h3>
<form method="post" action="/{AP}/channels/add" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">
  <div class="form-group" style="flex:1;min-width:150px"><label>Name</label><input name="name" placeholder="Anime Channel 1" required></div>
  <div class="form-group" style="flex:1;min-width:180px"><label>Channel ID</label><input name="channel_id" type="number" placeholder="-1001234567890" required></div>
  <div class="form-group" style="min-width:130px"><label>Category</label>
    <select name="category"><option>general</option><option>anime</option><option>movie</option><option>adult</option><option>cartoon</option><option>drama</option><option>vip</option></select></div>
  <div class="form-group" style="min-width:100px"><label>Max GB</label><input name="max_storage" type="number" value="50" style="width:80px"></div>
  <button class="btn">Add Channel</button>
</form></div>"""

        body = f"{flash(msg)}<h1>📺 Channel Manager</h1>{stat_cards}{table}{add_form}"
        return admin_html(body, title="Channels", active="channels")

    @app.post(f"/{AP}/channels/add")
    async def admin_channel_add(request: Request, name: str = Form(...),
                                channel_id: int = Form(...), category: str = Form("general"),
                                max_storage: float = Form(50)):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        try:
            cid = db.create_channel(name, channel_id, category)
            if max_storage != 50:
                db.update_channel(cid, max_storage_gb=max_storage)
            return RedirectResponse(f"/{AP}/channels?msg=Channel added: {name}", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/channels?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/channels/{{ch_id}}/toggle")
    async def admin_channel_toggle(ch_id: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        db.toggle_channel(ch_id)
        return RedirectResponse(f"/{AP}/channels?msg=Channel toggled", status_code=303)

    @app.get(f"/{AP}/channels/{{ch_id}}/delete")
    async def admin_channel_delete(ch_id: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        db.delete_channel(ch_id)
        return RedirectResponse(f"/{AP}/channels?msg=Channel deleted", status_code=303)

    # Auto-rotation API
    @app.get("/api/channels/next")
    async def api_next_channel(request: Request, category: str = "general"):
        if not is_admin(request):
            from fastapi import HTTPException
            raise HTTPException(403)
        ch = db.get_next_channel(category)
        if not ch:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "No available channels"}, 404)
        from fastapi.responses import JSONResponse
        return JSONResponse({"id": ch['id'], "name": ch['name'], "channel_id": ch['channel_id'], "category": ch['category']})

    logger.info("Module: channels routes registered.")
