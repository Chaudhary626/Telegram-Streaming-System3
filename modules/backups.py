"""
Backup module — Database backup/restore via mysqldump.
"""
import os
import time
import asyncio
import logging
import subprocess
from datetime import datetime

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse

import database as db
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)

# Backup directory
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)


async def _run_mysqldump(backup_id, filename, tables=None):
    """Run mysqldump in background."""
    filepath = os.path.join(BACKUP_DIR, filename)
    try:
        cmd = [
            'mysqldump',
            f'--host={DB_HOST}',
            f'--port={DB_PORT}',
            f'--user={DB_USER}',
            f'--password={DB_PASS}',
            '--single-transaction',
            '--routines',
            '--triggers',
            DB_NAME,
        ]
        if tables:
            cmd.extend(tables.split(','))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            with open(filepath, 'wb') as f:
                f.write(stdout)
            file_size = os.path.getsize(filepath)
            db.update_backup_status(backup_id, 'completed', file_size=file_size)
            logger.info(f"Backup completed: {filename} ({file_size} bytes)")
        else:
            error = stderr.decode('utf-8', errors='replace')[:500]
            db.update_backup_status(backup_id, 'failed', error_message=error)
            logger.error(f"Backup failed: {error}")
    except FileNotFoundError:
        db.update_backup_status(backup_id, 'failed',
                                error_message='mysqldump not found. Install mysql-client.')
        logger.error("mysqldump not found")
    except Exception as e:
        db.update_backup_status(backup_id, 'failed', error_message=str(e)[:500])
        logger.error(f"Backup error: {e}")


def register(app, ctx):
    """Register backup routes."""

    @app.get(f"/{AP}/backups")
    async def admin_backups_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        backups = db.list_backups(limit=30)

        # Stats
        total = len(backups)
        completed = sum(1 for b in backups if b.get('status') == 'completed')
        total_size = sum(b.get('file_size', 0) or 0 for b in backups)
        size_mb = total_size / (1024 * 1024)

        stat_cards = f"""
<div class="grid grid-3">
  <div class="stat-card"><div class="stat-value">{total}</div><div class="stat-label">Total Backups</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{completed}</div><div class="stat-label">Completed</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{size_mb:.1f} MB</div><div class="stat-label">Total Size</div></div>
</div>"""

        # Backup table
        rows = ""
        for b in backups:
            bid = b['id']
            fname = escape(b.get('filename', ''))
            btype = b.get('backup_type', 'full')
            status = b.get('status', 'pending')
            fsize = b.get('file_size', 0) or 0
            size_str = f"{fsize / (1024*1024):.1f} MB" if fsize > 0 else "—"
            started = str(b.get('started_at', ''))[:19]
            completed_at = str(b.get('completed_at', '') or '')[:19]
            error = escape(str(b.get('error_message', '') or '')[:80])

            status_badge = {
                'completed': '<span class="badge badge-success">✅ Completed</span>',
                'running': '<span class="badge" style="background:#3b82f6;color:#fff">⏳ Running</span>',
                'failed': '<span class="badge badge-danger">❌ Failed</span>',
                'pending': '<span class="badge">⏸ Pending</span>',
            }.get(status, f'<span class="badge">{status}</span>')

            actions = ''
            if status == 'completed':
                actions = f'<a href="/{AP}/backups/{bid}/download" class="btn btn-sm">📥</a> '
            actions += f'<a href="/{AP}/backups/{bid}/delete" class="btn btn-sm btn-danger" onclick="return confirm(\'Delete backup?\')">&times;</a>'

            error_row = f'<br><small style="color:var(--err)">{error}</small>' if error and status == 'failed' else ''

            rows += f"""<tr>
<td>#{bid}</td><td><code>{fname}</code>{error_row}</td>
<td><span class="badge">{btype}</span></td><td>{status_badge}</td>
<td>{size_str}</td><td><small>{started}</small></td>
<td>{actions}</td></tr>"""

        table = f"""<table>
<thead><tr><th>ID</th><th>Filename</th><th>Type</th><th>Status</th><th>Size</th><th>Started</th><th>Actions</th></tr></thead>
<tbody>{rows if rows else '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--txt2)">No backups yet</td></tr>'}</tbody>
</table>"""

        # Create backup form
        create_form = f"""
<div class="card" style="margin-top:20px">
  <h3>💾 Create New Backup</h3>
  <form method="post" action="/{AP}/backups/create" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">
    <div class="form-group" style="min-width:150px"><label>Type</label>
      <select name="backup_type">
        <option value="full">Full Database</option>
        <option value="content">Content Only</option>
        <option value="users">Users Only</option>
        <option value="settings">Settings Only</option>
      </select></div>
    <button class="btn" onclick="this.disabled=true;this.textContent='⏳ Creating...';this.form.submit();">Create Backup</button>
  </form>
</div>"""

        body = f"{flash(msg)}<h1>💾 Backups</h1>{stat_cards}{table}{create_form}"
        return admin_html(body, title="Backups", active="backups")

    @app.post(f"/{AP}/backups/create")
    async def admin_create_backup(request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        form = await request.form()
        backup_type = form.get('backup_type', 'full')

        # Map type to tables
        table_map = {
            'full': '',
            'content': 'tg_content,tg_sources,tg_videos,tg_view_logs',
            'users': 'tg_users,tg_roles,tg_plans',
            'settings': 'tg_settings,tg_channels,tg_ads',
        }
        tables = table_map.get(backup_type, '')

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backup_{backup_type}_{timestamp}.sql"

        try:
            bid = db.create_backup_record(filename, backup_type=backup_type, tables_included=tables)
            # Run mysqldump in background
            asyncio.create_task(_run_mysqldump(bid, filename, tables or None))
            return RedirectResponse(f"/{AP}/backups?msg=Backup started: {filename}", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/{AP}/backups?msg=Error: {e}", status_code=303)

    @app.get(f"/{AP}/backups/{{bid}}/download")
    async def admin_download_backup(bid: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        backup = db.get_backup(bid)
        if not backup or backup['status'] != 'completed':
            return RedirectResponse(f"/{AP}/backups?msg=Backup not available", status_code=303)
        filepath = os.path.join(BACKUP_DIR, backup['filename'])
        if not os.path.exists(filepath):
            return RedirectResponse(f"/{AP}/backups?msg=File not found", status_code=303)
        return FileResponse(filepath, filename=backup['filename'], media_type='application/sql')

    @app.get(f"/{AP}/backups/{{bid}}/delete")
    async def admin_delete_backup(bid: int, request: Request):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        backup = db.get_backup(bid)
        if backup:
            filepath = os.path.join(BACKUP_DIR, backup['filename'])
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            db.delete_backup_record(bid)
        return RedirectResponse(f"/{AP}/backups?msg=Backup deleted", status_code=303)

    # ── Backup API ───────────────────────────────────────────

    @app.get("/api/backups/list")
    async def api_list_backups(request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        backups = db.list_backups(limit=10)
        return JSONResponse([{
            'id': b['id'],
            'filename': b.get('filename', ''),
            'status': b.get('status', ''),
            'file_size': b.get('file_size', 0),
            'backup_type': b.get('backup_type', ''),
            'started_at': str(b.get('started_at', '')),
        } for b in backups])

    logger.info("Module: backups routes registered.")
