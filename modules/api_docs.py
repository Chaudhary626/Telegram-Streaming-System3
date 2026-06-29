"""
API Documentation module — Route catalog, API status, endpoint reference.
"""
import logging

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

import database as db
from helpers import AP, is_admin, admin_html, escape

logger = logging.getLogger(__name__)

# Complete API endpoint catalog
API_CATALOG = [
    # Streaming
    {'method': 'GET', 'path': '/stream/{token}', 'module': 'streaming', 'auth': 'Token', 'desc': 'Stream video content via signed token'},
    {'method': 'GET', 'path': '/embed/{slug}', 'module': 'streaming', 'auth': 'None', 'desc': 'Embeddable video player page'},
    {'method': 'GET', 'path': '/watch/{slug}', 'module': 'streaming', 'auth': 'None', 'desc': 'Full watch page with player'},
    # Player Events
    {'method': 'POST', 'path': '/api/player/event', 'module': 'analytics', 'auth': 'None', 'desc': 'Log player events (play/pause/complete/buffer)'},
    # Analytics
    {'method': 'GET', 'path': '/api/analytics/overview', 'module': 'analytics', 'auth': 'Admin', 'desc': 'Analytics dashboard data'},
    # Search
    {'method': 'GET', 'path': '/api/search', 'module': 'search', 'auth': 'None', 'desc': 'Full-text content search'},
    {'method': 'GET', 'path': '/api/search/duplicates', 'module': 'search', 'auth': 'Admin', 'desc': 'Check for duplicate content'},
    # Roles
    {'method': 'GET', 'path': '/api/roles/check', 'module': 'roles', 'auth': 'Admin', 'desc': 'Check user permission'},
    {'method': 'GET', 'path': '/api/roles/user', 'module': 'roles', 'auth': 'Admin', 'desc': 'Get user roles'},
    # Security
    {'method': 'GET', 'path': '/api/security/status', 'module': 'security', 'auth': 'Admin', 'desc': 'Rate limiter & CSRF stats'},
    # Backups
    {'method': 'GET', 'path': '/api/backups/list', 'module': 'backups', 'auth': 'Admin', 'desc': 'List recent backups'},
    # Downloads
    {'method': 'GET', 'path': '/api/download/{token}', 'module': 'downloads', 'auth': 'Token', 'desc': 'Download file with signed token'},
    # Notifications
    {'method': 'GET', 'path': '/api/notifications', 'module': 'admin_system', 'auth': 'Admin', 'desc': 'List notifications'},
    {'method': 'POST', 'path': '/api/notifications/{id}/read', 'module': 'admin_system', 'auth': 'Admin', 'desc': 'Mark notification as read'},
    # Content
    {'method': 'GET', 'path': '/api/content/{slug}', 'module': 'streaming', 'auth': 'None', 'desc': 'Get content metadata by slug'},
    # Health
    {'method': 'GET', 'path': '/health', 'module': 'admin_system', 'auth': 'None', 'desc': 'Health check endpoint'},
]


def register(app, ctx):
    """Register API documentation routes."""

    @app.get(f"/{AP}/api-docs")
    async def admin_api_docs_page(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        # Build endpoint table
        rows = ""
        modules = set()
        for ep in API_CATALOG:
            method = ep['method']
            path = escape(ep['path'])
            module = ep['module']
            auth = ep['auth']
            desc = escape(ep['desc'])
            modules.add(module)

            method_color = {
                'GET': '#22c55e', 'POST': '#3b82f6',
                'PUT': '#f59e0b', 'DELETE': '#ef4444',
            }.get(method, 'var(--txt2)')

            auth_badge = {
                'Admin': '<span class="badge" style="background:var(--err);color:#fff">Admin</span>',
                'Token': '<span class="badge" style="background:var(--acc);color:#fff">Token</span>',
                'None': '<span class="badge">Public</span>',
            }.get(auth, f'<span class="badge">{auth}</span>')

            rows += f"""<tr>
<td><span style="color:{method_color};font-weight:700;font-family:monospace">{method}</span></td>
<td><code style="color:var(--acc)">{path}</code></td>
<td><span class="badge">{module}</span></td>
<td>{auth_badge}</td>
<td>{desc}</td>
</tr>"""

        # Stats
        total = len(API_CATALOG)
        public = sum(1 for e in API_CATALOG if e['auth'] == 'None')
        admin_only = sum(1 for e in API_CATALOG if e['auth'] == 'Admin')

        body = f"""<h1>📡 API Documentation</h1>
<div class="grid grid-4" style="margin-bottom:16px">
  <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Endpoints</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{public}</div><div class="stat-label">Public</div></div>
  <div class="stat-card" style="border-left:3px solid var(--err)"><div class="stat-value">{admin_only}</div><div class="stat-label">Admin Only</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{len(modules)}</div><div class="stat-label">Modules</div></div>
</div>
<div class="card" style="margin-bottom:16px;padding:16px">
  <h3>📚 Interactive Docs</h3>
  <p style="color:var(--txt2);margin:8px 0">Swagger UI and ReDoc are available for interactive API exploration.</p>
  <a href="/api/docs" class="btn" target="_blank" style="margin-right:8px">🔗 Swagger UI</a>
  <a href="/api/redoc" class="btn" target="_blank">📖 ReDoc</a>
</div>
<table>
<thead><tr><th>Method</th><th>Endpoint</th><th>Module</th><th>Auth</th><th>Description</th></tr></thead>
<tbody>{rows}</tbody>
</table>"""
        return admin_html(body, title="API Docs", active="api-docs")

    # API endpoint to list all routes
    @app.get("/api/routes")
    async def api_list_routes(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        return JSONResponse(API_CATALOG)

    logger.info("Module: api_docs routes registered.")
