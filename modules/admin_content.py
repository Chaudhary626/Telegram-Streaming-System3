"""
Admin Content module — Channels, Plans, Content, Ads, Logs.
Extracted from server.py admin panel routes.
"""
import logging
from html import escape as he

from fastapi import Request, HTTPException, Form
from fastapi.responses import RedirectResponse

import database as db
from helpers import AP, is_admin, admin_html, flash, BASE

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register admin content management routes."""

    # ── Channels ─────────────────────────────────────────────

    @app.get(f"/{AP}/channels")
    async def admin_channels(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        chs = db.list_channels()
        rows = ""
        for c in chs:
            rows += f'<tr><td>{he(c["name"])}</td><td class="mono">{c["channel_id"]}</td><td>{c["category"]}</td>'
            rows += f'<td><form method="POST" action="/{AP}/channels/{c["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        body = f"""<h1>📺 Channels</h1>{flash(msg)}
        <div class="card"><h3 style="margin-bottom:12px">Add Channel</h3>
        <form method="POST" action="/{AP}/channels/create" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
          <div class="form-group" style="flex:1;min-width:150px"><label>Name</label><input type="text" name="name" required></div>
          <div class="form-group" style="flex:1;min-width:150px"><label>Channel ID</label><input type="text" name="channel_id" required placeholder="-100xxx"></div>
          <div class="form-group" style="min-width:120px"><label>Category</label><select name="category"><option>anime</option><option>movie</option><option>series</option><option>general</option></select></div>
          <button class="btn btn-primary" type="submit">Add</button></form></div>
        <table><tr><th>Name</th><th>Channel ID</th><th>Category</th><th></th></tr>{rows}</table>"""
        return admin_html(body, "Channels", "channels")

    @app.post(f"/{AP}/channels/create")
    async def admin_ch_create(request: Request, name: str = Form(...), channel_id: str = Form(...), category: str = Form("general")):
        if not is_admin(request):
            raise HTTPException(403)
        db.create_channel(name, int(channel_id), category)
        return RedirectResponse(f"/{AP}/channels?msg=Added", 303)

    @app.post(f"/{AP}/channels/{{ch_id}}/delete")
    async def admin_ch_delete(ch_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.delete_channel(ch_id)
        return RedirectResponse(f"/{AP}/channels?msg=Deleted", 303)

    # ── Plans ────────────────────────────────────────────────

    @app.get(f"/{AP}/plans")
    async def admin_plans(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        plans = db.list_plans()
        rows = ""
        for p in plans:
            rows += f'<tr><td>{he(p["name"])}</td><td class="mono">{p["slug"]}</td><td>₹{p["price"]}</td><td>{p["max_content"]}</td>'
            rows += f'<td>{p["max_views_day"]}</td><td>{p["max_sources"]}</td><td>{"Yes" if p["can_ads"] else "No"}</td><td>{p["duration_days"]}d</td>'
            rows += f'<td><form method="POST" action="/{AP}/plans/{p["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        body = f"""<h1>💳 Plans</h1>{flash(msg)}
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
        return admin_html(body, "Plans", "plans")

    @app.post(f"/{AP}/plans/create")
    async def admin_plan_create(request: Request, name: str = Form(...), slug: str = Form(...), price: int = Form(0),
            max_content: int = Form(50), max_views_day: int = Form(25000), max_sources: int = Form(9),
            can_ads: int = Form(0), duration_days: int = Form(30), is_trial: int = Form(0)):
        if not is_admin(request):
            raise HTTPException(403)
        db.create_plan(name, slug, price, max_content, max_views_day, max_sources, can_ads, duration_days, is_trial)
        return RedirectResponse(f"/{AP}/plans?msg=Created {name}", 303)

    @app.post(f"/{AP}/plans/{{pid}}/delete")
    async def admin_plan_delete(pid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.delete_plan(pid)
        return RedirectResponse(f"/{AP}/plans?msg=Deleted", 303)

    # ── Content ──────────────────────────────────────────────

    @app.get(f"/{AP}/content")
    async def admin_content(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        items = db.list_all_content()
        base = BASE()
        rows = ""
        for c in items:
            title = he(c["title"]); slug = c["slug"]; sc = c.get("source_count", 0)
            owner = he(c.get("owner_name", "") or "—")
            rows += f'<tr><td>{title}<br><span class="mono">{slug}</span></td><td>@{owner}</td><td>{sc}</td>'
            rows += f'<td><a href="{base}/watch/{slug}" target="_blank" style="color:#a78bfa">Watch</a></td>'
            rows += f'<td><form method="POST" action="/{AP}/content/{c["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        body = f'<h1>📁 All Content ({len(items)})</h1>{flash(msg)}<table><tr><th>Content</th><th>Owner</th><th>Sources</th><th>Link</th><th></th></tr>{rows}</table>'
        return admin_html(body, "Content", "content")

    @app.post(f"/{AP}/content/{{cid}}/delete")
    async def admin_content_del(cid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.delete_content(cid)
        return RedirectResponse(f"/{AP}/content?msg=Deleted", 303)

    # ── Ads ──────────────────────────────────────────────────

    @app.get(f"/{AP}/ads")
    async def admin_ads(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
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
        return admin_html(body, "Ads", "ads")

    @app.post(f"/{AP}/ads/{{aid}}/toggle")
    async def admin_ads_toggle(aid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.toggle_ad(aid)
        return RedirectResponse(f"/{AP}/ads", 303)

    @app.post(f"/{AP}/ads/{{aid}}/delete")
    async def admin_ads_delete(aid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.delete_ad(aid)
        return RedirectResponse(f"/{AP}/ads", 303)

    # ── Logs ─────────────────────────────────────────────────

    @app.get(f"/{AP}/logs")
    async def admin_logs(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
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
        return admin_html(body, "Logs", "logs")

    logger.info("Module: admin_content routes registered.")
