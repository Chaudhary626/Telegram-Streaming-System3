"""
Main Admin Panel HTML Templates — Premium SaaS Design.
Uses Inter font, glassmorphism, gradient cards, micro-animations.
Function-based rendering to avoid CSS var() conflicts.
"""


def admin_login(error=""):
    """Render admin login page — premium glassmorphism."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin Login</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#06060f;color:#e2e4f0;font-family:'Inter',system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;
  background-image:radial-gradient(ellipse at 20% 50%,rgba(99,66,255,.08) 0%,transparent 50%),
    radial-gradient(ellipse at 80% 20%,rgba(139,92,246,.06) 0%,transparent 40%)}}
.card{{background:rgba(16,16,32,.75);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(99,66,255,.15);border-radius:20px;padding:44px 36px;width:100%;max-width:400px;text-align:center;
  box-shadow:0 8px 32px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.04)}}
.logo{{font-size:2rem;margin-bottom:6px;filter:drop-shadow(0 0 8px rgba(99,66,255,.4))}}
h1{{font-size:1.2rem;font-weight:600;letter-spacing:-.02em;margin-bottom:4px}}
.sub{{color:#6b6b8d;font-size:.82rem;margin-bottom:28px}}
input{{background:rgba(255,255,255,.04);border:1px solid rgba(99,66,255,.12);color:#e2e4f0;
  padding:12px 16px;border-radius:12px;width:100%;font-size:.9rem;outline:none;
  font-family:inherit;transition:border-color .2s,box-shadow .2s}}
input:focus{{border-color:rgba(99,66,255,.5);box-shadow:0 0 0 3px rgba(99,66,255,.1)}}
button{{background:linear-gradient(135deg,#6342ff,#8b5cf6);color:#fff;border:none;padding:12px 28px;
  border-radius:12px;font-size:.9rem;font-weight:600;cursor:pointer;width:100%;margin-top:16px;
  font-family:inherit;transition:transform .15s,box-shadow .15s;letter-spacing:.01em}}
button:hover{{transform:translateY(-1px);box-shadow:0 4px 20px rgba(99,66,255,.35)}}
button:active{{transform:translateY(0)}}
.err{{color:#f43f5e;font-size:.82rem;margin-bottom:14px;padding:8px 12px;
  background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.15);border-radius:10px}}
</style></head><body>
<div class="card">
<div class="logo">⚡</div>
<h1>Stream Admin</h1>
<p class="sub">Secure access · Main administrator</p>
{err_html}
<form method="POST">
  <input type="password" name="password" placeholder="Enter admin password" required autofocus>
  <button type="submit">Sign In</button>
</form>
</div>
</body></html>"""


_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--bg:#06060f;--s1:rgba(16,16,32,.75);--s2:rgba(22,22,44,.6);--s3:rgba(30,30,55,.5);
  --bdr:rgba(99,66,255,.1);--bdr2:rgba(255,255,255,.06);--txt:#e2e4f0;--txt2:#6b6b8d;--txt3:#4a4a6a;
  --acc:#6342ff;--acc2:#8b5cf6;--acc3:#a78bfa;--ok:#10b981;--err:#f43f5e;--warn:#f59e0b;
  --grad1:linear-gradient(135deg,#6342ff,#8b5cf6);--grad2:linear-gradient(135deg,#10b981,#34d399);
  --grad3:linear-gradient(135deg,#f59e0b,#fbbf24);--grad4:linear-gradient(135deg,#f43f5e,#fb7185)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:'Inter',system-ui,sans-serif;display:flex;min-height:100vh;
  background-image:radial-gradient(ellipse at 0% 50%,rgba(99,66,255,.06) 0%,transparent 50%)}
::selection{background:rgba(99,66,255,.3)}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(99,66,255,.2);border-radius:3px}

/* ─── SIDEBAR ─── */
.sidebar{width:240px;background:var(--s1);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border-right:1px solid var(--bdr);padding:24px 0;flex-shrink:0;overflow-y:auto;
  display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.sidebar .brand{padding:0 20px 24px;display:flex;align-items:center;gap:10px}
.sidebar .brand-icon{font-size:1.5rem;filter:drop-shadow(0 0 6px rgba(99,66,255,.4))}
.sidebar .brand-text{font-size:1rem;font-weight:700;letter-spacing:-.03em;
  background:var(--grad1);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sidebar .nav-section{font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;
  color:var(--txt3);padding:16px 20px 8px}
.sidebar a{display:flex;align-items:center;gap:10px;padding:9px 20px;color:var(--txt2);text-decoration:none;
  font-size:.85rem;font-weight:500;border-left:2px solid transparent;transition:all .2s;position:relative}
.sidebar a:hover{color:var(--txt);background:rgba(99,66,255,.05)}
.sidebar a.active{color:var(--txt);background:rgba(99,66,255,.08);border-left-color:var(--acc)}
.sidebar a.active::before{content:'';position:absolute;left:-1px;top:50%;transform:translateY(-50%);
  width:2px;height:60%;background:var(--acc);border-radius:1px;box-shadow:0 0 8px var(--acc)}
.nav-icon{font-size:1rem;width:20px;text-align:center;flex-shrink:0}
.pending-badge{background:var(--err);color:#fff;font-size:.6rem;padding:2px 7px;border-radius:10px;
  margin-left:auto;font-weight:700;letter-spacing:.02em;animation:pulse-badge 2s infinite}
@keyframes pulse-badge{0%,100%{opacity:1}50%{opacity:.7}}

/* ─── MAIN ─── */
.main{flex:1;padding:28px 36px;overflow-y:auto;max-height:100vh}
.main h1{font-size:1.6rem;font-weight:700;letter-spacing:-.03em;margin-bottom:6px}
.main .page-desc{color:var(--txt2);font-size:.85rem;margin-bottom:24px}

/* ─── STAT CARDS ─── */
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:16px 0}
.stat-card{background:var(--s1);backdrop-filter:blur(12px);border:1px solid var(--bdr);border-radius:16px;
  padding:20px 22px;transition:transform .2s,box-shadow .2s;position:relative;overflow:hidden}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.stat-card.purple::before{background:var(--grad1)}.stat-card.green::before{background:var(--grad2)}
.stat-card.yellow::before{background:var(--grad3)}.stat-card.red::before{background:var(--grad4)}
.stat-icon{font-size:1.8rem;margin-bottom:8px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.3))}
.stat-value{font-size:2rem;font-weight:700;letter-spacing:-.04em;line-height:1}
.stat-label{font-size:.75rem;color:var(--txt2);margin-top:6px;font-weight:500;text-transform:uppercase;letter-spacing:.04em}

/* ─── CARDS ─── */
.card{background:var(--s1);backdrop-filter:blur(12px);border:1px solid var(--bdr);border-radius:16px;
  padding:22px 24px;margin-bottom:16px;transition:border-color .2s}
.card:hover{border-color:rgba(99,66,255,.2)}
.card h3{font-size:.95rem;font-weight:600;margin-bottom:14px;letter-spacing:-.01em}

/* ─── TABLE ─── */
table{width:100%;border-collapse:separate;border-spacing:0;margin:16px 0;font-size:.84rem}
thead th{text-align:left;padding:10px 14px;color:var(--txt2);font-weight:600;font-size:.72rem;
  text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--bdr);
  background:rgba(99,66,255,.03);position:sticky;top:0}
thead th:first-child{border-radius:12px 0 0 0}thead th:last-child{border-radius:0 12px 0 0}
tbody td{padding:11px 14px;border-bottom:1px solid rgba(255,255,255,.03);vertical-align:middle;
  transition:background .15s}
tbody tr:hover td{background:rgba(99,66,255,.04)}
tbody tr:last-child td{border-bottom:none}

/* ─── BUTTONS ─── */
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 16px;border-radius:10px;font-size:.8rem;
  cursor:pointer;border:none;text-decoration:none;transition:all .2s;color:#fff;font-family:inherit;font-weight:500}
.btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.3)}
.btn:active{transform:translateY(0)}
.btn-primary{background:var(--grad1)}.btn-primary:hover{box-shadow:0 4px 16px rgba(99,66,255,.3)}
.btn-danger{background:var(--grad4)}.btn-ok{background:var(--grad2)}.btn-warn{background:var(--grad3);color:#000}
.btn-ghost{background:transparent;border:1px solid var(--bdr);color:var(--txt2)}
.btn-ghost:hover{border-color:var(--acc);color:var(--txt)}
.btn-sm{padding:5px 12px;font-size:.73rem;border-radius:8px}

/* ─── FORMS ─── */
input[type=text],input[type=password],input[type=number],input[type=url],select,textarea{
  background:rgba(255,255,255,.04);border:1px solid var(--bdr2);color:var(--txt);padding:9px 14px;
  border-radius:10px;font-size:.85rem;width:100%;outline:none;font-family:inherit;transition:border-color .2s,box-shadow .2s}
input:focus,select:focus,textarea:focus{border-color:rgba(99,66,255,.4);box-shadow:0 0 0 3px rgba(99,66,255,.08)}
label{display:block;font-size:.72rem;color:var(--txt2);margin-bottom:5px;font-weight:600;
  text-transform:uppercase;letter-spacing:.04em}
.form-group{margin-bottom:14px}

/* ─── BADGES ─── */
.badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;letter-spacing:.02em}
.badge-ok{background:rgba(16,185,129,.1);color:var(--ok);border:1px solid rgba(16,185,129,.15)}
.badge-err{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.15)}
.badge-acc{background:rgba(99,66,255,.1);color:var(--acc3);border:1px solid rgba(99,66,255,.15)}
.badge-warn{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.15)}
.mono{font-family:'JetBrains Mono',monospace;font-size:.78rem;color:var(--txt2)}

/* ─── FLASH ─── */
.flash{padding:12px 18px;border-radius:12px;margin-bottom:16px;font-size:.85rem;font-weight:500;
  display:flex;align-items:center;gap:8px;animation:flash-in .3s}
.flash-ok{background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);color:var(--ok)}
.flash-err{background:rgba(244,63,94,.08);border:1px solid rgba(244,63,94,.2);color:var(--err)}
@keyframes flash-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}

/* ─── TABS ─── */
.tabs{display:flex;gap:6px;margin-bottom:20px;flex-wrap:wrap}
.tab{padding:7px 18px;border-radius:10px;font-size:.82rem;font-weight:500;cursor:pointer;text-decoration:none;
  color:var(--txt2);background:transparent;border:1px solid var(--bdr2);transition:all .2s}
.tab:hover{color:var(--txt);border-color:rgba(99,66,255,.3);background:rgba(99,66,255,.05)}
.tab.active{color:#fff;border-color:var(--acc);background:rgba(99,66,255,.15)}

.inline-form{display:inline}
@media(max-width:768px){.sidebar{display:none}.main{padding:16px}.grid{grid-template-columns:1fr 1fr}}
@media(max-width:480px){.grid{grid-template-columns:1fr}}
"""


def admin_page(body, title="Dashboard", active="dashboard", admin_path="admin", pending_requests=0):
    """Render admin page layout with premium sidebar."""
    nav_items = [
        ("_section", "", "OVERVIEW"),
        ("dashboard", f"/{admin_path}", "📊", "Dashboard"),
        ("users", f"/{admin_path}/users", "👤", "Users"),
        ("content", f"/{admin_path}/content", "📁", "All Content"),
        ("logs", f"/{admin_path}/logs", "📋", "Analytics"),
        ("_section", "", "MANAGE"),
        ("channels", f"/{admin_path}/channels", "📺", "Channels"),
        ("plans", f"/{admin_path}/plans", "💎", "Plans"),
        ("ads", f"/{admin_path}/ads", "📢", "Ads"),
        ("_section", "", "BILLING"),
        ("requests", f"/{admin_path}/requests", "📩", "Requests"),
        ("payments", f"/{admin_path}/payments", "💰", "Payments"),
    ]
    nav_html = ""
    for item in nav_items:
        if item[0] == "_section":
            nav_html += f'<div class="nav-section">{item[2]}</div>\n'
            continue
        key, href, icon, label = item
        cls = ' class="active"' if key == active else ""
        badge = ""
        if key == "requests" and pending_requests > 0:
            badge = f'<span class="pending-badge">{pending_requests}</span>'
        nav_html += f'<a href="{href}"{cls}><span class="nav-icon">{icon}</span>{label}{badge}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin — {title}</title>
<style>{_CSS}</style>
</head><body>
<nav class="sidebar">
  <div class="brand"><span class="brand-icon">⚡</span><span class="brand-text">Stream Admin</span></div>
  {nav_html}
</nav>
<div class="main">
{body}
</div>
</body></html>"""
