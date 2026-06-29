"""
Admin Core module — Login, Dashboard, User management.
Extracted from server.py admin panel routes.
"""
import logging
from html import escape as he

from fastapi import Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import ADMIN_PASSWORD, MAIN_ADMIN_TELEGRAM_ID
import database as db
from admin_templates import admin_login
from helpers import (AP, is_admin, admin_cookie, admin_html, flash,
                     rate_limited, hash_password)

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register admin core routes (login, dashboard, users)."""

    @app.get(f"/{AP}/login", response_class=HTMLResponse)
    async def admin_login_page():
        return HTMLResponse(admin_login())

    @app.post(f"/{AP}/login")
    async def admin_login_post(request: Request, password: str = Form(...)):
        ip = request.client.host or "unknown"
        if rate_limited(ip):
            db.log_activity(0, "admin_login_blocked", f"Rate limited IP: {ip}", ip)
            return HTMLResponse(admin_login("Too many attempts. Try again in 15 minutes."), 429)
        if password != ADMIN_PASSWORD:
            db.log_activity(0, "admin_login_fail", f"IP: {ip}", ip)
            return HTMLResponse(admin_login("Wrong password"), 401)
        db.log_activity(0, "admin_login_ok", f"IP: {ip}", ip)
        r = RedirectResponse(f"/{AP}", 303)
        r.set_cookie("admin_token", admin_cookie(), httponly=True, max_age=14400)
        return r

    @app.get(f"/{AP}")
    async def admin_dashboard(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        users = db.list_users()
        stats = db.get_view_stats_global()
        content = db.list_all_content()
        pending = 0
        try:
            pending = db.count_pending_requests()
        except Exception:
            pass
        user_rows = ""
        for u in users[:10]:
            uname = he(u.get("username", "") or "—")
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
        return admin_html(body, "Dashboard", "dashboard")

    # ── Users ────────────────────────────────────────────────

    @app.get(f"/{AP}/users")
    async def admin_users(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        users = db.list_users()
        plans = db.list_plans()
        plan_opts = "".join(f'<option value="{p["slug"]}">{he(p["name"])}</option>' for p in plans)
        rows = ""
        for u in users:
            tid = u["telegram_id"]
            uname = he(u.get("username", "") or "—")
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
        body = f'<h1>👤 User Management ({len(users)} users)</h1>{flash(msg)}<table><tr><th>User</th><th>Plan / Expires</th><th>Content</th><th>Status</th><th>Actions</th></tr>{rows}</table>'
        return admin_html(body, "Users", "users")

    @app.get(f"/{AP}/users/{{tg_id}}")
    async def admin_user_detail(tg_id: int, request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        user = db.get_user(tg_id)
        if not user:
            raise HTTPException(404, "User not found")
        plans = db.list_plans()
        stats = db.get_view_stats_by_owner(tg_id)
        cc = db.count_content_by_owner(tg_id)
        plan_opts = "".join(f'<option value="{p["slug"]}"{" selected" if user.get("plan_id")==p["id"] else ""}>{he(p["name"])} (₹{p["price"]})</option>' for p in plans)
        st = "Active" if user["is_active"] else "Banned"
        body = f"""<h1>👤 User — @{he(user.get("username","") or "—")}</h1>
        <p style="margin-bottom:16px"><a href="/{AP}/users" style="color:#a78bfa">← Back</a></p>{flash(msg)}
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
        return admin_html(body, f"User {tg_id}", "users")

    @app.post(f"/{AP}/users/{{tg_id}}/plan")
    async def admin_set_plan(tg_id: int, request: Request, plan_slug: str = Form(...), duration: int = Form(30)):
        if not is_admin(request):
            raise HTTPException(403)
        plan = db.get_plan(plan_slug)
        if plan:
            db.set_user_plan(tg_id, plan["id"], duration if duration > 0 else plan["duration_days"])
        ref = request.headers.get("referer", "")
        if f"/{AP}/users/{tg_id}" in ref:
            return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Plan set", 303)
        return RedirectResponse(f"/{AP}/users?msg=Plan set", 303)

    @app.post(f"/{AP}/users/{{tg_id}}/limits")
    async def admin_set_limits(tg_id: int, request: Request, max_content: int = Form(...), max_views_day: int = Form(...)):
        if not is_admin(request):
            raise HTTPException(403)
        db.update_user(tg_id, max_content=max_content, max_views_day=max_views_day)
        return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Limits updated", 303)

    @app.post(f"/{AP}/users/{{tg_id}}/ban")
    async def admin_ban(tg_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.ban_user(tg_id)
        return RedirectResponse(f"/{AP}/users?msg=Banned", 303)

    @app.post(f"/{AP}/users/{{tg_id}}/unban")
    async def admin_unban(tg_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.unban_user(tg_id)
        return RedirectResponse(f"/{AP}/users?msg=Unbanned", 303)

    @app.post(f"/{AP}/users/{{tg_id}}/reset-password")
    async def admin_reset_pw(tg_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.update_user(tg_id, password_hash="")
        return RedirectResponse(f"/{AP}/users/{tg_id}?msg=Password reset", 303)

    logger.info("Module: admin_core routes registered.")
