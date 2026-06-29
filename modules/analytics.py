"""
Analytics module — Player events, Chart.js dashboard, view tracking.
"""
import json
import hashlib
import logging

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import database as db
from helpers import AP, is_admin, get_panel_user, admin_html, panel_html, flash, escape

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register analytics routes."""

    # ── Player Event Beacon ──────────────────────────────────

    @app.post("/api/player/event")
    async def api_player_event(request: Request):
        """Receive player events (play, pause, complete, buffer, error)."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False}, 400)
        ip = request.client.host if request.client else ""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        ua = request.headers.get("user-agent", "")[:255]
        try:
            db.log_player_event(
                content_id=body.get("content_id"),
                source_id=body.get("source_id"),
                owner_id=body.get("owner_id", 0),
                event_type=body.get("event", "play")[:30],
                ip_hash=ip_hash,
                user_agent=ua,
                duration_sec=int(body.get("duration", 0)),
                position_sec=int(body.get("position", 0)),
                quality=body.get("quality", "")[:20],
                buffering_count=int(body.get("buffering", 0))
            )
        except Exception as e:
            logger.warning(f"Player event error: {e}")
        return JSONResponse({"ok": True})

    # ── Admin Analytics Dashboard ────────────────────────────

    @app.get(f"/{AP}/analytics")
    async def admin_analytics_page(request: Request, days: int = 30):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")

        try:
            data = db.get_analytics_overview(days=days)
        except Exception:
            data = {'total_views': 0, 'views_today': 0, 'views_week': 0,
                    'unique_today': 0, 'events': {}, 'daily_views': [], 'top_content': []}

        total = data.get('total_views', 0)
        today = data.get('views_today', 0)
        week = data.get('views_week', 0)
        unique = data.get('unique_today', 0)
        events = data.get('events', {})
        plays = events.get('play', 0)
        completes = events.get('complete', 0)
        errors = events.get('error', 0)

        stat_cards = f"""
<div class="grid grid-4">
  <div class="stat-card"><div class="stat-value">{total:,}</div><div class="stat-label">Total Views</div></div>
  <div class="stat-card" style="border-left:3px solid var(--acc)"><div class="stat-value">{today:,}</div><div class="stat-label">Today</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{week:,}</div><div class="stat-label">This Week</div></div>
  <div class="stat-card"><div class="stat-value">{unique:,}</div><div class="stat-label">Unique Today</div></div>
</div>
<div class="grid grid-3" style="margin-top:12px">
  <div class="stat-card" style="border-left:3px solid #3b82f6"><div class="stat-value">{plays:,}</div><div class="stat-label">▶️ Plays</div></div>
  <div class="stat-card" style="border-left:3px solid var(--ok)"><div class="stat-value">{completes:,}</div><div class="stat-label">✅ Completed</div></div>
  <div class="stat-card" style="border-left:3px solid var(--err)"><div class="stat-value">{errors:,}</div><div class="stat-label">❌ Errors</div></div>
</div>"""

        # Chart.js line chart data
        daily = data.get('daily_views', [])
        labels_json = json.dumps([d[0][-5:] for d in daily])  # MM-DD format
        values_json = json.dumps([d[1] for d in daily])

        chart_html = f"""
<div class="card" style="margin-top:20px;padding:20px">
  <h3>📈 Views — Last {days} Days</h3>
  <canvas id="viewsChart" height="100"></canvas>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script>
new Chart(document.getElementById('viewsChart'), {{
  type: 'line',
  data: {{
    labels: {labels_json},
    datasets: [{{
      label: 'Views',
      data: {values_json},
      borderColor: '#7c5cfc',
      backgroundColor: 'rgba(124,92,252,0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointBackgroundColor: '#7c5cfc'
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>"""

        # Top content table
        top = data.get('top_content', [])
        top_rows = ""
        for i, item in enumerate(top[:10], 1):
            title = escape(item.get('title', 'Unknown'))
            slug = escape(item.get('slug', ''))
            views = item.get('views', 0)
            top_rows += f'<tr><td>{i}</td><td><b>{title}</b><br><small style="color:var(--txt2)">{slug}</small></td><td>{views:,}</td></tr>'

        top_table = f"""
<div class="card" style="margin-top:16px">
  <h3>🏆 Top Content</h3>
  <table><thead><tr><th>#</th><th>Content</th><th>Views</th></tr></thead>
  <tbody>{top_rows if top_rows else '<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--txt2)">No data yet</td></tr>'}</tbody></table>
</div>"""

        # Period selector
        period_tabs = f'<div class="tabs" style="margin:16px 0">'
        for d, label in [(7, "7 Days"), (30, "30 Days"), (90, "90 Days")]:
            active = " active" if days == d else ""
            period_tabs += f'<a href="/{AP}/analytics?days={d}" class="tab{active}">{label}</a>'
        period_tabs += '</div>'

        body = f"<h1>📊 Analytics</h1>{period_tabs}{stat_cards}{chart_html}{top_table}"
        return admin_html(body, title="Analytics", active="logs")

    # ── Analytics API ────────────────────────────────────────

    @app.get("/api/analytics/overview")
    async def api_analytics_overview(request: Request, days: int = 30):
        if not is_admin(request):
            raise HTTPException(403)
        data = db.get_analytics_overview(days=min(days, 365))
        # Convert for JSON serialization
        data['daily_views'] = [{'date': d[0], 'views': d[1]} for d in data.get('daily_views', [])]
        data['top_content'] = [{'title': t.get('title',''), 'slug': t.get('slug',''), 'views': t.get('views',0)}
                                for t in data.get('top_content', [])]
        return JSONResponse(data)

    # ── Panel Analytics ──────────────────────────────────────

    @app.get("/panel/analytics")
    async def panel_analytics(request: Request, days: int = 30):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        try:
            data = db.get_analytics_by_owner(user['telegram_id'], days=days)
        except Exception:
            data = {'total_views': 0, 'views_today': 0, 'daily_views': [], 'top_content': []}

        total = data.get('total_views', 0)
        today = data.get('views_today', 0)
        daily = data.get('daily_views', [])
        labels_json = json.dumps([d[0][-5:] for d in daily])
        values_json = json.dumps([d[1] for d in daily])

        chart_html = f"""
<div class="card" style="margin-top:16px;padding:20px">
  <canvas id="viewsChart" height="120"></canvas>
</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script>
new Chart(document.getElementById('viewsChart'), {{
  type: 'line',
  data: {{ labels: {labels_json}, datasets: [{{ label: 'Views', data: {values_json},
    borderColor: '#a78bfa', backgroundColor: 'rgba(167,139,250,0.1)', fill: true, tension: 0.4 }}] }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true }}, x: {{ grid: {{ display: false }} }} }} }}
}});
</script>"""

        top = data.get('top_content', [])
        top_rows = ''.join(
            f'<tr><td>{i}</td><td>{escape(t.get("title",""))}</td><td>{t.get("views",0):,}</td></tr>'
            for i, t in enumerate(top[:5], 1)
        )

        body = f"""
<h1>📊 Analytics</h1>
<div class="grid">
  <div class="card stat"><div class="stat-value">{total:,}</div><div class="stat-label">Total Views</div></div>
  <div class="card stat"><div class="stat-value">{today:,}</div><div class="stat-label">Today</div></div>
</div>
{chart_html}
<div class="card" style="margin-top:12px"><h3>🏆 Top Content</h3>
<table><thead><tr><th>#</th><th>Title</th><th>Views</th></tr></thead>
<tbody>{top_rows or '<tr><td colspan="3" style="text-align:center;padding:16px">No data</td></tr>'}</tbody></table></div>"""
        return panel_html(body, user, "Analytics", "analytics")

    logger.info("Module: analytics routes registered.")
