"""
Import/Export module — Data import/export in JSON/CSV format.
"""
import io
import csv
import json
import logging
from datetime import datetime

from fastapi import Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse

import database as db
from database import get_connection
from helpers import AP, is_admin, admin_html, flash, escape

logger = logging.getLogger(__name__)

EXPORT_VERSION = "3.0"


def _export_envelope(data_type, data):
    """Wrap data in standard export envelope."""
    return {
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "type": data_type,
        "count": len(data),
        "data": data,
    }


def _fetch_table_data(table, columns="*", limit=50000):
    """Generic table data fetcher."""
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(f"SELECT {columns} FROM {table} ORDER BY id LIMIT %s", (limit,))
            rows = c.fetchall()
            # Convert datetime objects to strings
            for row in rows:
                for k, v in row.items():
                    if hasattr(v, 'isoformat'):
                        row[k] = v.isoformat()
            return rows


def register(app, ctx):
    """Register import/export routes."""

    # ── Export Page ──────────────────────────────────────────

    @app.get(f"/{AP}/import-export")
    async def admin_import_export_page(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        export_items = [
            ("users", "👤", "Users", "All registered users"),
            ("content", "📁", "Content", "Content with sources"),
            ("plans", "💎", "Plans", "Subscription plans"),
            ("channels", "📺", "Channels", "Telegram channels"),
            ("settings", "⚙️", "Settings", "All settings"),
            ("roles", "🛡️", "Roles", "User roles & permissions"),
        ]

        export_cards = '<div class="grid grid-3" style="margin-bottom:20px">'
        for key, icon, label, desc in export_items:
            export_cards += f"""
<div class="card" style="text-align:center;padding:16px">
  <div style="font-size:2em">{icon}</div>
  <h3 style="margin:8px 0 4px">{label}</h3>
  <p style="color:var(--txt2);font-size:0.85em">{desc}</p>
  <div style="margin-top:12px;display:flex;gap:6px;justify-content:center">
    <a href="/{AP}/export/{key}?fmt=json" class="btn btn-sm">📤 JSON</a>
    <a href="/{AP}/export/{key}?fmt=csv" class="btn btn-sm">📄 CSV</a>
  </div>
</div>"""
        export_cards += '</div>'

        import_form = f"""
<div class="card" style="margin-top:20px">
  <h3>📥 Import Data</h3>
  <form method="post" action="/{AP}/import" enctype="multipart/form-data" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">
    <div class="form-group" style="min-width:150px"><label>Type</label>
      <select name="data_type">
        <option value="users">Users</option>
        <option value="content">Content</option>
        <option value="plans">Plans</option>
        <option value="settings">Settings</option>
        <option value="roles">Roles</option>
      </select></div>
    <div class="form-group" style="flex:1;min-width:200px"><label>JSON File</label>
      <input type="file" name="file" accept=".json" required></div>
    <button class="btn" onclick="return confirm('Import data? This may overwrite existing records.')">Import</button>
  </form>
</div>"""

        body = f"{flash(msg)}<h1>📤 Import / Export</h1>{export_cards}{import_form}"
        return admin_html(body, title="Import/Export", active="import-export")

    # ── Export Endpoints ────────────────────────────────────

    @app.get(f"/{AP}/export/{{data_type}}")
    async def admin_export(data_type: str, request: Request, fmt: str = "json"):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        table_map = {
            "users": "tg_users",
            "content": "tg_content",
            "plans": "tg_plans",
            "channels": "tg_channels",
            "settings": "tg_settings",
            "roles": "tg_roles",
        }

        table = table_map.get(data_type)
        if not table:
            return RedirectResponse(f"/{AP}/import-export?msg=Invalid type: {data_type}", 303)

        try:
            data = _fetch_table_data(table)
        except Exception as e:
            return RedirectResponse(f"/{AP}/import-export?msg=Export error: {e}", 303)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{data_type}_{timestamp}"

        if fmt == "csv" and data:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            content = output.getvalue()
            return StreamingResponse(
                io.BytesIO(content.encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'}
            )
        else:
            envelope = _export_envelope(data_type, data)
            content = json.dumps(envelope, indent=2, default=str)
            return StreamingResponse(
                io.BytesIO(content.encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}.json"'}
            )

    # ── Import Endpoint ─────────────────────────────────────

    @app.post(f"/{AP}/import")
    async def admin_import(request: Request, data_type: str = Form(...), file: UploadFile = File(...)):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        try:
            raw = await file.read()
            parsed = json.loads(raw.decode('utf-8'))
        except Exception as e:
            return RedirectResponse(f"/{AP}/import-export?msg=Parse error: {e}", 303)

        # Validate envelope
        if isinstance(parsed, dict) and 'data' in parsed:
            records = parsed['data']
        elif isinstance(parsed, list):
            records = parsed
        else:
            return RedirectResponse(f"/{AP}/import-export?msg=Invalid format", 303)

        if not records:
            return RedirectResponse(f"/{AP}/import-export?msg=No records found", 303)

        table_map = {
            "users": "tg_users",
            "content": "tg_content",
            "plans": "tg_plans",
            "settings": "tg_settings",
            "roles": "tg_roles",
        }

        table = table_map.get(data_type)
        if not table:
            return RedirectResponse(f"/{AP}/import-export?msg=Invalid type", 303)

        imported = 0
        skipped = 0
        try:
            with get_connection() as conn:
                with conn.cursor() as c:
                    for record in records:
                        if not isinstance(record, dict):
                            skipped += 1
                            continue
                        # Remove 'id' to avoid conflicts
                        record.pop('id', None)
                        if not record:
                            skipped += 1
                            continue
                        cols = ', '.join(record.keys())
                        placeholders = ', '.join(['%s'] * len(record))
                        try:
                            c.execute(
                                f"INSERT IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                                list(record.values()))
                            if c.rowcount > 0:
                                imported += 1
                            else:
                                skipped += 1
                        except Exception:
                            skipped += 1
        except Exception as e:
            return RedirectResponse(f"/{AP}/import-export?msg=Import error: {e}", 303)

        return RedirectResponse(
            f"/{AP}/import-export?msg=Imported {imported} records ({skipped} skipped)", 303)

    logger.info("Module: import_export routes registered.")
