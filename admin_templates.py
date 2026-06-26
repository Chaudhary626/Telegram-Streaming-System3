"""
Main Admin Panel HTML Templates.
Uses function-based rendering (NOT .format) to avoid CSS var() conflicts.
"""


def admin_login(error=""):
    """Render admin login page."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin Login</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d0d1a;color:#d0d0e8;font-family:'Segoe UI',system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#141425;border:1px solid #2a2a48;border-radius:16px;
  padding:40px;width:100%;max-width:380px;text-align:center}}
h1{{font-size:1.3rem;margin-bottom:8px}}
p{{color:#7777aa;font-size:.85rem;margin-bottom:24px}}
input{{background:#1c1c35;border:1px solid #2a2a48;color:#d0d0e8;
  padding:10px 14px;border-radius:8px;width:100%;font-size:.9rem;outline:none;margin-bottom:16px}}
input:focus{{border-color:#7c5cfc}}
button{{background:#7c5cfc;color:#fff;border:none;padding:10px 24px;
  border-radius:8px;font-size:.9rem;cursor:pointer;width:100%}}
button:hover{{background:#a78bfa}}
.err{{color:#ef4444;font-size:.82rem;margin-bottom:12px}}
</style></head><body>
<div class="card">
<h1>⚡ TG Stream Admin</h1>
<p>Main Admin Access</p>
{err_html}
<form method="POST">
  <input type="password" name="password" placeholder="Admin Password" required autofocus>
  <button type="submit">Login</button>
</form>
</div>
</body></html>"""


_CSS = """
:root{--bg:#0d0d1a;--s1:#141425;--s2:#1c1c35;--bdr:#2a2a48;--txt:#d0d0e8;
  --txt2:#7777aa;--acc:#7c5cfc;--acc2:#a78bfa;--ok:#22c55e;--err:#ef4444;--warn:#f59e0b}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:'Segoe UI',system-ui,sans-serif;display:flex;min-height:100vh}
.sidebar{width:230px;background:var(--s1);border-right:1px solid var(--bdr);padding:20px 0;flex-shrink:0;overflow-y:auto}
.sidebar h2{padding:0 20px 16px;font-size:1rem;color:var(--acc2)}
.sidebar a{display:flex;align-items:center;gap:8px;padding:10px 20px;color:var(--txt2);text-decoration:none;font-size:.88rem;
  border-left:3px solid transparent;transition:all .15s}
.sidebar a:hover,.sidebar a.active{color:var(--txt);background:var(--s2);border-left-color:var(--acc)}
.sidebar .sep{height:1px;background:var(--bdr);margin:12px 20px}
.pending-badge{background:var(--err);color:#fff;font-size:.65rem;padding:2px 6px;border-radius:10px;margin-left:auto;font-weight:700}
.main{flex:1;padding:24px 32px;overflow-y:auto;max-height:100vh}
.main h1{font-size:1.5rem;margin-bottom:20px;color:#fff}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:.85rem}
th{text-align:left;padding:10px 12px;background:var(--s2);color:var(--txt2);border-bottom:1px solid var(--bdr);
  font-weight:500;font-size:.78rem;text-transform:uppercase;letter-spacing:.5px}
td{padding:10px 12px;border-bottom:1px solid var(--bdr);vertical-align:top}
tr:hover td{background:rgba(124,92,252,.04)}
.btn{display:inline-block;padding:6px 16px;border-radius:8px;font-size:.82rem;cursor:pointer;border:none;
  text-decoration:none;transition:all .15s;color:#fff}
.btn-primary{background:var(--acc)}.btn-primary:hover{background:var(--acc2)}
.btn-danger{background:var(--err)}.btn-sm{padding:4px 10px;font-size:.75rem}
.btn-ok{background:var(--ok)}.btn-warn{background:var(--warn);color:#000}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:12px;padding:20px;margin-bottom:16px}
.stat{text-align:center}.stat-value{font-size:2rem;font-weight:700;color:var(--acc2)}
.stat-label{font-size:.78rem;color:var(--txt2);margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:16px 0}
input[type=text],input[type=password],input[type=number],input[type=url],select,textarea{background:var(--s2);border:1px solid var(--bdr);
  color:var(--txt);padding:8px 12px;border-radius:8px;font-size:.85rem;width:100%;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--acc)}
label{display:block;font-size:.78rem;color:var(--txt2);margin-bottom:4px;text-transform:uppercase;letter-spacing:.3px}
.form-group{margin-bottom:14px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.7rem}
.badge-ok{background:rgba(34,197,94,.15);color:var(--ok)}
.badge-err{background:rgba(239,68,68,.15);color:var(--err)}
.badge-acc{background:rgba(124,92,252,.15);color:var(--acc2)}
.badge-warn{background:rgba(245,158,11,.15);color:var(--warn)}
.mono{font-family:monospace;font-size:.8rem;word-break:break-all;color:var(--txt2)}
.flash{padding:10px 16px;border-radius:8px;margin-bottom:16px;font-size:.85rem}
.flash-ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);color:var(--ok)}
.flash-err{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);color:var(--err)}
.inline-form{display:inline}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{padding:6px 16px;border-radius:8px;font-size:.82rem;cursor:pointer;text-decoration:none;color:var(--txt2);
  background:var(--s2);border:1px solid var(--bdr);transition:all .15s}
.tab:hover,.tab.active{color:var(--txt);border-color:var(--acc);background:rgba(124,92,252,.08)}
@media(max-width:768px){.sidebar{display:none}.main{padding:16px}}
"""


def admin_page(body, title="Dashboard", active="dashboard", admin_path="admin", pending_requests=0):
    """Render admin page layout with sidebar. Uses string concat to avoid .format() issues."""
    nav_items = [
        ("dashboard", f"/{admin_path}", "📊 Dashboard"),
        ("users", f"/{admin_path}/users", "👤 Users"),
        ("channels", f"/{admin_path}/channels", "📺 Channels"),
        ("plans", f"/{admin_path}/plans", "💳 Plans"),
        ("content", f"/{admin_path}/content", "📁 All Content"),
        ("ads", f"/{admin_path}/ads", "📢 Ads"),
        ("logs", f"/{admin_path}/logs", "📋 Logs"),
        ("_sep", "", ""),
        ("requests", f"/{admin_path}/requests", "📩 Requests"),
        ("payments", f"/{admin_path}/payments", "💰 Payments"),
    ]
    nav_html = ""
    for key, href, label in nav_items:
        if key == "_sep":
            nav_html += '<div class="sep"></div>\n'
            continue
        cls = ' class="active"' if key == active else ""
        badge = ""
        if key == "requests" and pending_requests > 0:
            badge = f'<span class="pending-badge">{pending_requests}</span>'
        nav_html += f'<a href="{href}"{cls}>{label}{badge}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin — {title}</title>
<style>{_CSS}</style>
</head><body>
<nav class="sidebar">
  <h2>⚡ TG Stream</h2>
  {nav_html}
</nav>
<div class="main">
{body}
</div>
</body></html>"""
