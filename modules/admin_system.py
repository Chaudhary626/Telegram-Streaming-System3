"""
Admin System module — Settings, Health, Errors, Backups.
New admin routes added as part of the modular architecture.
"""
import time
import json
import logging
import traceback

from fastapi import Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import database as db
import settings as app_settings
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)

_start_time = time.time()


def register(app, ctx):
    """Register system admin routes."""

    # ── Settings Page ────────────────────────────────────────

    @app.get(f"/{AP}/settings")
    async def admin_settings_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        grouped = app_settings.get_by_category()
        category_icons = {
            "general": "🌐", "appearance": "🎨", "player": "📺",
            "download": "📥", "upload": "📤", "system": "⚙️", "security": "🔒"
        }
        tabs = ""
        panels = ""
        first = True
        for cat, settings_list in sorted(grouped.items()):
            icon = category_icons.get(cat, "📋")
            active_cls = " active" if first else ""
            tabs += f'<a href="#" class="tab{active_cls}" onclick="showSettingsTab(\'{cat}\',this);return false">{icon} {cat.title()}</a>'
            display = "" if first else "display:none"
            rows = ""
            for s in settings_list:
                key = escape(s["setting_key"])
                val = s["setting_value"] or ""
                desc = escape(s.get("description", ""))
                stype = s.get("setting_type", "string")
                if stype == "boolean":
                    checked = " checked" if val.lower() in ("true", "1", "yes") else ""
                    inp = f'<label class="toggle"><input type="checkbox" name="{key}" value="true"{checked}><span class="toggle-slider"></span></label>'
                    inp += f'<input type="hidden" name="_bool_{key}" value="1">'
                elif stype == "number":
                    inp = f'<input type="number" name="{key}" value="{escape(val)}" style="width:120px">'
                else:
                    inp = f'<input type="text" name="{key}" value="{escape(val)}">'
                rows += f'<div class="setting-row"><div class="setting-info"><div class="setting-key">{key}</div><div class="setting-desc">{desc}</div></div><div class="setting-input">{inp}</div></div>'
            panels += f'<div id="settings-{cat}" class="settings-panel" style="{display}">{rows}</div>'
            first = False
        body = f"""<h1>⚙️ Global Settings</h1>{flash(msg)}
        <form method="POST" action="/{AP}/settings">
        <div class="tabs">{tabs}</div>
        {panels}
        <div style="margin-top:20px"><button class="btn btn-primary" type="submit">💾 Save Settings</button></div>
        </form>
        <style>
        .setting-row{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--bdr2,rgba(255,255,255,.06))}}
        .setting-key{{font-weight:600;font-size:.9rem;color:var(--txt,#e2e4f0)}}
        .setting-desc{{font-size:.75rem;color:var(--txt2,#6b6b8d);margin-top:2px}}
        .setting-input input{{background:var(--s2,rgba(22,22,44,.6));border:1px solid var(--bdr,rgba(99,66,255,.1));color:var(--txt,#e2e4f0);padding:6px 10px;border-radius:6px}}
        .toggle{{position:relative;display:inline-block;width:44px;height:24px;cursor:pointer}}
        .toggle input{{opacity:0;width:0;height:0}}
        .toggle-slider{{position:absolute;inset:0;background:var(--s3);border-radius:24px;transition:.3s}}
        .toggle-slider:before{{content:'';position:absolute;width:18px;height:18px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}}
        .toggle input:checked+.toggle-slider{{background:var(--acc,#6342ff)}}
        .toggle input:checked+.toggle-slider:before{{transform:translateX(20px)}}
        .settings-panel{{background:var(--s1);border-radius:12px;border:1px solid var(--bdr);overflow:hidden;margin-top:12px}}
        </style>
        <script>
        function showSettingsTab(cat,el){{
          document.querySelectorAll('.settings-panel').forEach(p=>p.style.display='none');
          document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
          document.getElementById('settings-'+cat).style.display='block';
          el.classList.add('active');
        }}
        </script>"""
        return admin_html(body, "Settings", "settings")

    @app.post(f"/{AP}/settings")
    async def admin_settings_save(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        form = await request.form()
        # Get all settings to know their types
        all_settings = app_settings.get_all()
        settings_map = {s["setting_key"]: s for s in all_settings}
        for key, meta in settings_map.items():
            if meta.get("setting_type") == "boolean":
                val = "true" if form.get(key) else "false"
            else:
                val = form.get(key)
                if val is None:
                    continue
            app_settings.set_value(key, str(val))
        return RedirectResponse(f"/{AP}/settings?msg=Settings saved", 303)

    # ── System Health ────────────────────────────────────────

    @app.get(f"/{AP}/health")
    async def admin_health_page(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        tg_client = ctx.get("tg_client")
        tg_ok = tg_client.is_connected if tg_client else False
        # DB check
        db_ok = False
        db_ping = 0
        try:
            start = time.time()
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT 1")
            db_ping = round((time.time() - start) * 1000, 1)
            db_ok = True
        except Exception:
            pass
        # Queue stats
        queue_stats = {}
        try:
            from workers.queue import task_queue
            queue_stats = task_queue.get_stats()
        except Exception:
            pass
        # Worker status
        worker_status = {}
        try:
            from workers import get_status
            worker_status = get_status()
        except Exception:
            pass
        # Cache stats
        cache_stats = {}
        try:
            from cache import cache
            cache_stats = cache.stats
        except Exception:
            pass
        # System metrics
        sys_metrics = {"cpu_percent": -1, "memory_mb": -1, "disk_percent": -1}
        try:
            import psutil
            sys_metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            sys_metrics["memory_mb"] = psutil.Process().memory_info().rss // (1024 * 1024)
            sys_metrics["disk_percent"] = psutil.disk_usage('/').percent
        except ImportError:
            pass
        except Exception:
            pass
        uptime = int(time.time() - _start_time)
        uptime_str = f"{uptime // 86400}d {(uptime % 86400) // 3600}h {(uptime % 3600) // 60}m"
        # Maintenance mode
        maint = app_settings.get("maintenance_mode", False)

        def _status_badge(ok, label=""):
            if ok:
                return f'<span class="badge badge-ok">🟢 OK</span> {label}'
            return f'<span class="badge badge-err">🔴 Error</span> {label}'

        body = f"""<h1>💚 System Health</h1>
        <meta http-equiv="refresh" content="30">
        <div class="grid">
          <div class="card stat"><div class="stat-value">{uptime_str}</div><div class="stat-label">⏱ Uptime</div></div>
          <div class="card stat"><div class="stat-value">{sys_metrics['cpu_percent']}%</div><div class="stat-label">🖥 CPU</div></div>
          <div class="card stat"><div class="stat-value">{sys_metrics['memory_mb']} MB</div><div class="stat-label">📦 RAM</div></div>
          <div class="card stat"><div class="stat-value">{'ON' if maint else 'OFF'}</div><div class="stat-label">🔧 Maintenance</div></div>
        </div>
        <div class="card"><h3 style="margin-bottom:16px">Component Status</h3>
        <table><tr><th>Component</th><th>Status</th><th>Details</th></tr>
          <tr><td>Telegram Bot</td><td>{_status_badge(tg_ok)}</td><td>{'Connected' if tg_ok else 'Disconnected'}</td></tr>
          <tr><td>Database</td><td>{_status_badge(db_ok)}</td><td>{f'{db_ping}ms ping' if db_ok else 'Connection failed'}</td></tr>
          <tr><td>Upload Queue</td><td>{_status_badge(True)}</td><td>P:{queue_stats.get('pending',0)} · A:{queue_stats.get('processing',0)} · F:{queue_stats.get('failed',0)}</td></tr>
          <tr><td>Workers</td><td>{_status_badge(worker_status.get('active',0) > 0)}</td><td>{worker_status.get('active',0)} active / {worker_status.get('total',0)} total</td></tr>
          <tr><td>Cache</td><td>{_status_badge(True)}</td><td>{cache_stats.get('active_entries',0)}/{cache_stats.get('max_size',0)} entries · {cache_stats.get('hit_rate_percent',0)}% hit</td></tr>
        </table></div>"""
        return admin_html(body, "Health", "health")

    # ── Error Monitor ────────────────────────────────────────

    @app.get(f"/{AP}/errors")
    async def admin_errors_page(request: Request, show: str = "unresolved"):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        try:
            resolved = False if show == "unresolved" else (True if show == "resolved" else None)
            errors = db.list_errors(resolved=resolved)
        except Exception:
            errors = []
        tabs = ""
        for s in ["unresolved", "resolved", "all"]:
            cls = " active" if s == show else ""
            tabs += f'<a href="/{AP}/errors?show={s}" class="tab{cls}">{s.title()}</a>'
        rows = ""
        for e in errors:
            rb = "badge-err" if not e.get("is_resolved") else "badge-ok"
            st = "Resolved" if e.get("is_resolved") else "Open"
            msg_short = escape((e.get("message", "") or "")[:80])
            rows += f'<tr><td><span class="badge {rb}">{st}</span></td>'
            rows += f'<td>{escape(e.get("module",""))}</td>'
            rows += f'<td>{escape(e.get("error_type",""))}</td>'
            rows += f'<td style="max-width:250px;overflow:hidden;text-overflow:ellipsis">{msg_short}</td>'
            rows += f'<td>{e.get("created_at","")}</td>'
            rows += '<td>'
            if not e.get("is_resolved"):
                rows += f'<form method="POST" action="/{AP}/errors/{e["id"]}/resolve" style="display:inline"><button class="btn btn-ok btn-sm">Resolve</button></form>'
            rows += '</td></tr>'
        body = f"""<h1>❌ Error Monitor ({len(errors)})</h1>
        <div class="tabs">{tabs}</div>
        <table><tr><th>Status</th><th>Module</th><th>Type</th><th>Message</th><th>Time</th><th></th></tr>{rows}</table>"""
        return admin_html(body, "Errors", "errors")

    @app.post(f"/{AP}/errors/{{eid}}/resolve")
    async def admin_resolve_error(eid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        try:
            db.resolve_error(eid, 0)
        except Exception:
            pass
        return RedirectResponse(f"/{AP}/errors", 303)

    # ── Live System Overview ─────────────────────────────────

    @app.get(f"/{AP}/live")
    async def admin_live_page(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        body = f"""<h1>📈 Live System Overview</h1>
        <div id="live-grid" class="grid"></div>
        <script>
        async function refreshLive(){{
          try{{
            const r=await fetch('/{AP}/api/live');
            const d=await r.json();
            let html='';
            const cards=[
              ['🖥 CPU',d.cpu_percent>=0?d.cpu_percent+'%':'N/A'],
              ['📦 RAM',d.memory_mb>=0?d.memory_mb+' MB':'N/A'],
              ['⏱ Uptime',d.uptime_str||''],
              ['📤 Queue',d.queue_pending+' pending'],
              ['⚙ Workers',d.workers_active+' active'],
              ['👤 Users',d.total_users],
              ['📁 Content',d.total_content],
              ['📺 Channels',d.total_channels],
              ['💰 Pending Pay',d.pending_payments],
              ['❌ Errors',d.unresolved_errors],
              ['🔧 Maintenance',d.maintenance?'ON':'OFF'],
              ['📊 Views Today',d.views_today],
            ];
            for(const[label,val] of cards){{
              html+=`<div class="card stat"><div class="stat-value">${{val}}</div><div class="stat-label">${{label}}</div></div>`;
            }}
            document.getElementById('live-grid').innerHTML=html;
          }}catch(e){{console.error(e)}}
        }}
        refreshLive();setInterval(refreshLive,5000);
        </script>"""
        return admin_html(body, "Live", "live")

    @app.get(f"/{AP}/api/live")
    async def admin_live_api(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        tg_client = ctx.get("tg_client")
        # System metrics
        cpu, mem = -1, -1
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.Process().memory_info().rss // (1024 * 1024)
        except Exception:
            pass
        # Queue
        queue_pending = 0
        try:
            from workers.queue import task_queue
            qs = task_queue.get_stats()
            queue_pending = qs.get("pending", 0)
        except Exception:
            pass
        # Workers
        workers_active = 0
        try:
            from workers import get_status
            ws = get_status()
            workers_active = ws.get("active", 0)
        except Exception:
            pass
        # DB counts
        try:
            users = db.list_users()
            total_users = len(users)
        except Exception:
            total_users = 0
        try:
            content = db.list_all_content()
            total_content = len(content)
        except Exception:
            total_content = 0
        try:
            channels = db.list_channels()
            total_channels = len(channels)
        except Exception:
            total_channels = 0
        try:
            pending_payments = db.count_pending_requests()
        except Exception:
            pending_payments = 0
        try:
            errors = db.list_errors(resolved=False, limit=1000)
            unresolved_errors = len(errors)
        except Exception:
            unresolved_errors = 0
        try:
            stats = db.get_view_stats_global()
            views_today = stats.get("today", 0)
        except Exception:
            views_today = 0
        uptime = int(time.time() - _start_time)
        uptime_str = f"{uptime // 86400}d {(uptime % 86400) // 3600}h {(uptime % 3600) // 60}m"
        maint = app_settings.get("maintenance_mode", False)
        return JSONResponse({
            "cpu_percent": cpu, "memory_mb": mem, "uptime_str": uptime_str,
            "queue_pending": queue_pending, "workers_active": workers_active,
            "total_users": total_users, "total_content": total_content,
            "total_channels": total_channels, "pending_payments": pending_payments,
            "unresolved_errors": unresolved_errors, "views_today": views_today,
            "maintenance": maint,
        })

    # ── Notification API ─────────────────────────────────────

    @app.get("/api/notifications")
    async def api_notifications(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        notifs = db.list_notifications("admin", 0, limit=20)
        return JSONResponse([{
            "id": n["id"], "title": n["title"], "message": n.get("message", ""),
            "severity": n.get("severity", "info"), "is_read": n.get("is_read", 0),
            "created_at": str(n.get("created_at", "")),
        } for n in notifs])

    @app.post("/api/notifications/{nid}/read")
    async def api_notif_read(nid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.mark_notification_read(nid)
        return JSONResponse({"ok": True})

    @app.post("/api/notifications/read-all")
    async def api_notif_read_all(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.mark_all_notifications_read("admin", 0)
        return JSONResponse({"ok": True})

    # ── Upload Queue Management ─────────────────────────────

    @app.get(f"/{AP}/queue")
    async def admin_queue_page(request: Request, status: str = "", msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        stats = {}
        try:
            stats = db.queue_stats()
        except Exception:
            pass

        filter_status = status if status else None
        items = []
        try:
            items = db.queue_list_all(status=filter_status, limit=50)
        except Exception:
            pass

        pending = stats.get("pending", 0)
        processing = stats.get("processing", 0)
        completed = stats.get("completed", 0)
        failed = stats.get("failed", 0)
        cancelled = stats.get("cancelled", 0)
        total = stats.get("total", 0)

        # Stat cards
        stat_cards = f"""
<div class="grid grid-4">
  <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Total Tasks</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{pending}</div><div class="stat-label">⏳ Pending</div></div>
  <div class="stat-card" style="border-left:3px solid #3b82f6"><div class="stat-value">{processing}</div><div class="stat-label">⚙️ Processing</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{completed}</div><div class="stat-label">✅ Completed</div></div>
</div>
<div class="grid grid-3" style="margin-top:12px">
  <div class="stat-card" style="border-left:3px solid var(--err)"><div class="stat-value">{failed}</div><div class="stat-label">❌ Failed</div></div>
  <div class="stat-card" style="border-left:3px solid #666"><div class="stat-value">{cancelled}</div><div class="stat-label">🚫 Cancelled</div></div>
  <div class="stat-card"><div class="stat-value">{pending + processing}</div><div class="stat-label">📦 In Queue</div></div>
</div>"""

        # Filter tabs
        tabs = '<div class="tabs" style="margin:16px 0">'
        for s, label in [("", "All"), ("pending", "Pending"), ("processing", "Processing"),
                          ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")]:
            active = " active" if status == s else ""
            tabs += f'<a href="/{AP}/queue?status={s}" class="tab{active}">{label}</a>'
        tabs += '</div>'

        # Queue actions
        actions = f"""<div style="display:flex;gap:8px;margin-bottom:16px">
  <a href="/{AP}/queue/retry-all" class="btn btn-sm" onclick="return confirm('Retry all failed tasks?')">🔄 Retry All Failed</a>
  <a href="/{AP}/queue/cancel-pending" class="btn btn-sm btn-danger" onclick="return confirm('Cancel all pending tasks?')">❌ Cancel Pending</a>
  <a href="/{AP}/queue/purge" class="btn btn-sm" onclick="return confirm('Purge completed tasks older than 7 days?')">🗑 Purge Old</a>
</div>"""

        # Queue table
        rows = ""
        for item in items:
            sid = item['id']
            s = item['status']
            s_badge = {"pending": "badge-warning", "processing": "badge-info",
                       "completed": "badge-success", "failed": "badge-danger",
                       "cancelled": ""}.get(s, "")
            s_emoji = {"pending": "⏳", "processing": "⚙️", "completed": "✅",
                       "failed": "❌", "cancelled": "🚫"}.get(s, "❓")
            fname = escape(item.get('file_name', '')[:40]) or "—"
            user = escape(item.get('username', '') or item.get('display_name', '') or str(item.get('user_id', '')))
            lang = escape(item.get('language', 'Hindi'))
            quality = escape(item.get('quality', '720p'))
            retries = item.get('retry_count', 0)
            err = escape((item.get('error_message', '') or '')[:50])
            created = str(item.get('created_at', ''))[:16]
            size_mb = f"{(item.get('file_size', 0) or 0) / 1048576:.1f} MB"

            action_btns = ""
            if s == "failed":
                action_btns = f'<a href="/{AP}/queue/{sid}/retry" class="btn btn-sm">🔄</a> '
            if s in ("pending", "failed"):
                action_btns += f'<a href="/{AP}/queue/{sid}/cancel" class="btn btn-sm btn-danger">❌</a>'

            rows += f"""<tr>
<td>#{sid}</td><td>{fname}<br><small style="color:var(--txt2)">{size_mb} · {lang} {quality}</small></td>
<td>{user}</td><td><span class="badge {s_badge}">{s_emoji} {s}</span></td>
<td>{retries}/3</td><td><small>{err}</small></td><td><small>{created}</small></td>
<td>{action_btns}</td></tr>"""

        table = f"""<table>
<thead><tr><th>ID</th><th>File</th><th>User</th><th>Status</th><th>Retries</th><th>Error</th><th>Created</th><th>Actions</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--txt2)">No queue items</td></tr>'}</tbody>
</table>"""

        body = f"{flash(msg)}{stat_cards}{tabs}{actions}{table}"
        return admin_html(body, title="Upload Queue", active="queue")

    @app.get(f"/{AP}/queue/retry-all")
    async def admin_queue_retry_all(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        try:
            items = db.queue_list_all(status="failed", limit=200)
            count = 0
            for item in items:
                if db.queue_retry(item["id"]):
                    count += 1
            return RedirectResponse(f"/{AP}/queue?msg=Retried {count} failed task(s)", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/queue?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/queue/cancel-pending")
    async def admin_queue_cancel_pending(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        try:
            items = db.queue_list_all(status="pending", limit=200)
            count = 0
            for item in items:
                if db.queue_cancel(item["id"]):
                    count += 1
            return RedirectResponse(f"/{AP}/queue?msg=Cancelled {count} pending task(s)", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/queue?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/queue/purge")
    async def admin_queue_purge(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        try:
            count = db.queue_purge_completed(days=7)
            return RedirectResponse(f"/{AP}/queue?msg=Purged {count} old completed task(s)", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/queue?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/queue/{{task_id}}/retry")
    async def admin_queue_retry_one(task_id: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        db.queue_retry(task_id)
        return RedirectResponse(f"/{AP}/queue?msg=Task #{task_id} retried", status_code=303)

    @app.get(f"/{AP}/queue/{{task_id}}/cancel")
    async def admin_queue_cancel_one(task_id: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        db.queue_cancel(task_id)
        return RedirectResponse(f"/{AP}/queue?msg=Task #{task_id} cancelled", status_code=303)

    # ── Queue API ───────────────────────────────────────────

    @app.get("/api/queue/stats")
    async def api_queue_stats(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        return JSONResponse(db.queue_stats())

    # ── Plugins Page ──────────────────────────────────────────

    @app.get(f"/{AP}/plugins")
    async def admin_plugins_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        try:
            from plugins import list_plugins
            plugins = list_plugins()
        except Exception:
            plugins = {}

        cards = '<div class="grid grid-3" style="margin-bottom:20px">'
        if not plugins:
            cards += '<div class="card" style="padding:20px;text-align:center;grid-column:span 3"><p style="color:var(--txt2)">No plugins installed. Add plugin directories to <code>plugins/</code></p></div>'
        for slug, info in plugins.items():
            m = info.get('manifest', {})
            name = escape(m.get('name', slug))
            version = escape(m.get('version', '?'))
            desc = escape(m.get('description', ''))[:100]
            category = escape(m.get('category', 'other'))
            enabled = info.get('enabled', False)
            status = '<span class="badge badge-success">✅ Enabled</span>' if enabled else '<span class="badge">⚪ Disabled</span>'
            cards += f"""
<div class="card" style="padding:16px">
  <div style="display:flex;justify-content:space-between;align-items:start">
    <h3 style="margin:0">{name}</h3>
    {status}
  </div>
  <p style="color:var(--txt2);font-size:0.85em;margin:6px 0">{desc}</p>
  <div style="display:flex;gap:8px;margin-top:8px">
    <span class="badge">{category}</span>
    <small style="color:var(--txt2)">v{version}</small>
  </div>
</div>"""
        cards += '</div>'

        body = f"{flash(msg)}<h1>🔌 Plugins</h1>{cards}"
        return admin_html(body, title="Plugins", active="plugins")

    logger.info("Module: admin_system routes registered.")

