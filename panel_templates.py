"""
Sub-Admin Panel HTML Templates.
Used by server.py for /panel/* routes.

Uses function-based rendering (NOT .format) to avoid CSS var() conflicts.
"""


def panel_login(error=""):
    """Render panel login page."""
    err_html = f'<p class="err">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Panel Login</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d0d1a;color:#d0d0e8;font-family:'Segoe UI',system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#141425;border:1px solid #2a2a48;border-radius:16px;
  padding:40px;width:100%;max-width:400px;text-align:center}}
h1{{font-size:1.3rem;margin-bottom:8px}}
p{{color:#7777aa;font-size:.85rem;margin-bottom:24px}}
input{{background:#1c1c35;border:1px solid #2a2a48;color:#d0d0e8;
  padding:10px 14px;border-radius:8px;width:100%;font-size:.9rem;outline:none;margin-bottom:14px}}
input:focus{{border-color:#9333ea}}
button{{background:linear-gradient(135deg,#7c5cfc,#9333ea);color:#fff;border:none;padding:10px 24px;
  border-radius:8px;font-size:.9rem;cursor:pointer;width:100%}}
button:hover{{opacity:.9}}
.err{{color:#ef4444;font-size:.82rem;margin-bottom:12px}}
.hint{{color:#7777aa;font-size:.78rem;margin-top:16px}}
.hint a{{color:#a78bfa;text-decoration:none}}
</style></head><body>
<div class="card">
<h1>🎬 TG Stream Panel</h1>
<p>Sub-Admin Access</p>
{err_html}
<form method="POST" action="/panel/login">
  <input type="number" name="telegram_id" placeholder="Your Telegram ID" required>
  <input type="password" name="password" placeholder="Password" required>
  <button type="submit">Login</button>
</form>
<p class="hint">New? Send <b>/start</b> to the bot first, then <b>/setpassword</b></p>
</div>
</body></html>"""


_PCSS = """
:root{--bg:#0d0d1a;--s1:#141425;--s2:#1c1c35;--bdr:#2a2a48;--txt:#d0d0e8;
  --txt2:#7777aa;--acc:#9333ea;--acc2:#a78bfa;--ok:#22c55e;--err:#ef4444}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--txt);font-family:'Segoe UI',system-ui,sans-serif;display:flex;min-height:100vh}
.sidebar{width:220px;background:var(--s1);border-right:1px solid var(--bdr);padding:20px 0;flex-shrink:0}
.sidebar h2{padding:0 20px 12px;font-size:1rem;color:var(--acc2)}
.sidebar .plan-badge{display:block;margin:0 20px 16px;padding:4px 10px;background:rgba(147,51,234,.15);
  color:var(--acc2);border-radius:8px;font-size:.72rem;text-align:center}
.sidebar a{display:block;padding:10px 20px;color:var(--txt2);text-decoration:none;font-size:.88rem;
  border-left:3px solid transparent;transition:all .15s}
.sidebar a:hover,.sidebar a.active{color:var(--txt);background:var(--s2);border-left-color:var(--acc)}
.main{flex:1;padding:24px 32px;overflow-y:auto;max-height:100vh}
.main h1{font-size:1.5rem;margin-bottom:20px;color:#fff}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:.85rem}
th{text-align:left;padding:10px 12px;background:var(--s2);color:var(--txt2);border-bottom:1px solid var(--bdr);
  font-weight:500;font-size:.78rem;text-transform:uppercase;letter-spacing:.5px}
td{padding:10px 12px;border-bottom:1px solid var(--bdr);vertical-align:top}
tr:hover td{background:rgba(147,51,234,.04)}
.btn{display:inline-block;padding:6px 16px;border-radius:8px;font-size:.82rem;cursor:pointer;border:none;
  text-decoration:none;transition:all .15s;color:#fff}
.btn-primary{background:var(--acc)}.btn-primary:hover{background:var(--acc2)}
.btn-danger{background:var(--err)}.btn-sm{padding:4px 10px;font-size:.75rem}
.card{background:var(--s1);border:1px solid var(--bdr);border-radius:12px;padding:20px;margin-bottom:16px}
.stat{text-align:center}.stat-value{font-size:2rem;font-weight:700;color:var(--acc2)}
.stat-label{font-size:.78rem;color:var(--txt2);margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:16px 0}
input[type=text],input[type=password],input[type=number],select,textarea{background:var(--s2);border:1px solid var(--bdr);
  color:var(--txt);padding:8px 12px;border-radius:8px;font-size:.85rem;width:100%;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--acc)}
label{display:block;font-size:.78rem;color:var(--txt2);margin-bottom:4px;text-transform:uppercase;letter-spacing:.3px}
.form-group{margin-bottom:14px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.7rem}
.badge-ok{background:rgba(34,197,94,.15);color:var(--ok)}
.badge-err{background:rgba(239,68,68,.15);color:var(--err)}
.badge-acc{background:rgba(147,51,234,.15);color:var(--acc2)}
.mono{font-family:monospace;font-size:.8rem;word-break:break-all;color:var(--txt2)}
.flash{padding:10px 16px;border-radius:8px;margin-bottom:16px;font-size:.85rem}
.flash-ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);color:var(--ok)}
.code-box{background:var(--s2);border:1px solid var(--bdr);border-radius:8px;padding:12px;
  font-family:monospace;font-size:.8rem;word-break:break-all;position:relative;margin:8px 0}
.copy-btn{position:absolute;top:6px;right:6px;background:var(--acc);color:#fff;border:none;
  padding:4px 10px;border-radius:6px;font-size:.72rem;cursor:pointer}
.copy-btn:hover{background:var(--acc2)}
@media(max-width:768px){.sidebar{display:none}.main{padding:16px}}
"""


def panel_page(body, plan_name="Free", title="Dashboard", active="dashboard"):
    """Render panel page layout. Uses string concat to avoid .format() issues."""
    nav_items = [
        ("dashboard", "/panel", "📊 Dashboard"),
        ("content", "/panel/content", "📁 Content"),
        ("ads", "/panel/ads", "📢 Ads"),
        ("embeds", "/panel/embeds", "🔗 Embeds"),
        ("subscription", "/panel/subscription", "💳 Subscription"),
        ("profile", "/panel/profile", "👤 Profile"),
    ]
    nav_html = ""
    for key, href, label in nav_items:
        cls = ' class="active"' if key == active else ""
        nav_html += f'<a href="{href}"{cls}>{label}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Panel — {title}</title>
<style>{_PCSS}</style>
</head><body>
<nav class="sidebar">
  <h2>🎬 My Panel</h2>
  <div class="plan-badge">Plan: {plan_name}</div>
  {nav_html}
</nav>
<div class="main">
{body}
</div>
<script>
function copyText(id){{
  const el=document.getElementById(id);
  if(el){{navigator.clipboard.writeText(el.textContent.trim());
    const btn=el.parentElement.querySelector('.copy-btn');
    if(btn){{btn.textContent='Copied!';setTimeout(()=>btn.textContent='Copy',1500)}}
  }}
}}
</script>
</body></html>"""


def panel_embed_code(title, watch_url, embed_url, back_url="/panel/embeds"):
    """Render embed code page for a content item."""
    return f"""
<h1>🔗 Embed Code — {title}</h1>
<p style="margin-bottom:16px;color:#7777aa">
  <a href="{back_url}" style="color:#a78bfa">← Back to Content</a>
</p>

<div class="card">
  <h3 style="margin-bottom:12px">▶️ Player URL</h3>
  <div class="code-box"><span id="c1">{watch_url}</span><button class="copy-btn" onclick="copyText('c1')">Copy</button></div>
</div>

<div class="card">
  <h3 style="margin-bottom:12px">🖼 iFrame Embed Code</h3>
  <div class="code-box"><span id="c2">&lt;iframe src="{embed_url}" width="720" height="405" frameborder="0" allowfullscreen&gt;&lt;/iframe&gt;</span><button class="copy-btn" onclick="copyText('c2')">Copy</button></div>
</div>

<div class="card">
  <h3 style="margin-bottom:12px">📺 Direct Embed URL</h3>
  <div class="code-box"><span id="c3">{embed_url}</span><button class="copy-btn" onclick="copyText('c3')">Copy</button></div>
</div>

<div class="card">
  <h3 style="margin-bottom:12px">🖥 Live Preview</h3>
  <div style="aspect-ratio:16/9;max-width:720px;border-radius:8px;overflow:hidden;border:1px solid #2a2a48">
    <iframe src="{embed_url}" style="width:100%;height:100%;border:none" allowfullscreen></iframe>
  </div>
</div>
"""
