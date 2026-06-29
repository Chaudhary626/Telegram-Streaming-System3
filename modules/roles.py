"""
Roles & Permissions (RBAC) module.
Manages user roles and permission checks.
"""
import logging
from html import escape as he

from fastapi import Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

import database as db
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)

# Available roles
ROLES = {
    'admin': {'label': 'Admin', 'icon': '👑', 'desc': 'Full system access'},
    'moderator': {'label': 'Moderator', 'icon': '🛡️', 'desc': 'Content moderation, user management'},
    'uploader': {'label': 'Uploader', 'icon': '📤', 'desc': 'Upload content, manage own items'},
    'viewer': {'label': 'Viewer', 'icon': '👁️', 'desc': 'View content only'},
    'vip': {'label': 'VIP', 'icon': '💎', 'desc': 'Premium access, no ads'},
}

# Permissions per role
ROLE_PERMISSIONS = {
    'admin': '*',
    'moderator': 'content.view,content.edit,content.delete,users.view,users.edit,ads.manage',
    'uploader': 'content.view,content.create,content.edit,upload.queue',
    'viewer': 'content.view',
    'vip': 'content.view,download.enabled,ads.skip',
}


def register(app, ctx):
    """Register role management routes."""

    @app.get(f"/{AP}/roles")
    async def admin_roles_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        # Get role stats
        try:
            role_stats = db.list_all_roles()
        except Exception:
            role_stats = []

        stats_map = {r['role']: r['user_count'] for r in role_stats}

        role_cards = '<div class="grid grid-3" style="margin-bottom:20px">'
        for key, info in ROLES.items():
            count = stats_map.get(key, 0)
            role_cards += f"""
<div class="card" style="text-align:center;padding:16px">
  <div style="font-size:2em">{info['icon']}</div>
  <h3 style="margin:8px 0 4px">{info['label']}</h3>
  <p style="color:var(--txt2);font-size:0.85em">{info['desc']}</p>
  <div class="stat-value" style="margin-top:8px">{count}</div>
  <div class="stat-label">Users</div>
</div>"""
        role_cards += '</div>'

        # Assign role form
        role_options = ''.join(f'<option value="{k}">{v["icon"]} {v["label"]}</option>' for k, v in ROLES.items())
        assign_form = f"""
<div class="card" style="margin-bottom:20px">
  <h3>➕ Assign Role</h3>
  <form method="post" action="/{AP}/roles/assign" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">
    <div class="form-group" style="flex:1;min-width:160px"><label>Telegram ID</label>
      <input name="user_id" type="number" placeholder="123456789" required></div>
    <div class="form-group" style="min-width:150px"><label>Role</label>
      <select name="role">{role_options}</select></div>
    <button class="btn">Assign</button>
  </form>
</div>"""

        # Users with roles table
        try:
            all_roles = []
            for role_key in ROLES:
                users = db.list_users_by_role(role_key, limit=20)
                for u in users:
                    all_roles.append(u)
        except Exception:
            all_roles = []

        rows = ""
        for r in all_roles[:50]:
            uid = r.get('user_id', 0)
            role = r.get('role', '')
            role_info = ROLES.get(role, {'icon': '❓', 'label': role})
            username = escape(r.get('username', '') or str(uid))
            display = escape(r.get('display_name', '') or '')
            granted = str(r.get('granted_at', ''))[:16]
            perms = escape(r.get('permissions', '') or ROLE_PERMISSIONS.get(role, ''))[:60]
            rows += f"""<tr>
<td>{uid}</td><td>{username}<br><small style="color:var(--txt2)">{display}</small></td>
<td><span class="badge">{role_info['icon']} {role_info['label']}</span></td>
<td><small style="color:var(--txt2)">{perms}</small></td>
<td><small>{granted}</small></td>
<td><a href="/{AP}/roles/{uid}/{role}/remove" class="btn btn-sm btn-danger"
       onclick="return confirm('Remove {role} from {uid}?')">🗑</a></td>
</tr>"""

        table = f"""<table>
<thead><tr><th>User ID</th><th>Username</th><th>Role</th><th>Permissions</th><th>Granted</th><th>Actions</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--txt2)">No roles assigned yet</td></tr>'}</tbody>
</table>"""

        body = f"{flash(msg)}<h1>🛡️ Roles & Permissions</h1>{role_cards}{assign_form}{table}"
        return admin_html(body, title="Roles", active="roles")

    @app.post(f"/{AP}/roles/assign")
    async def admin_assign_role(request: Request, user_id: int = Form(...), role: str = Form(...)):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        if role not in ROLES:
            return RedirectResponse(f"/{AP}/roles?msg=Invalid role", status_code=303)
        perms = ROLE_PERMISSIONS.get(role, '')
        try:
            db.assign_role(user_id, role, granted_by=0, permissions=perms)
            return RedirectResponse(f"/{AP}/roles?msg=Role '{role}' assigned to {user_id}", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/roles?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/roles/{{user_id}}/{{role}}/remove")
    async def admin_remove_role(user_id: int, role: str, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        db.remove_role(user_id, role)
        return RedirectResponse(f"/{AP}/roles?msg=Role '{role}' removed from {user_id}", status_code=303)

    # ── Permission check API ─────────────────────────────────

    @app.get("/api/roles/check")
    async def api_check_permission(request: Request, user_id: int = 0, permission: str = ""):
        if not is_admin(request):
            raise HTTPException(403)
        has = db.has_permission(user_id, permission) if user_id and permission else False
        return JSONResponse({"user_id": user_id, "permission": permission, "allowed": has})

    @app.get("/api/roles/user")
    async def api_user_roles(request: Request, user_id: int = 0):
        if not is_admin(request):
            raise HTTPException(403)
        roles = db.get_user_roles(user_id) if user_id else []
        return JSONResponse([{"role": r['role'], "permissions": r.get('permissions', '')} for r in roles])

    logger.info("Module: roles routes registered.")
