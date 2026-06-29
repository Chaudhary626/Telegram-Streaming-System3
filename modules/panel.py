"""
Sub-Admin Panel module — All /panel/* routes.
Extracted from server.py sub-admin panel section.
"""
import secrets
import logging
from html import escape as he

from fastapi import Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse

import database as db
from panel_templates import panel_login, panel_embed_code
from helpers import (get_panel_user, panel_cookie, panel_html, flash,
                     hash_password, check_password, slugify, fmt_size,
                     make_stream_url, BASE, AP)

logger = logging.getLogger(__name__)

# Shared state for pending payment proofs
_pending_proofs: dict = {}


def get_pending_proofs():
    """Access pending proofs from bot handlers."""
    return _pending_proofs


def register(app, ctx):
    """Register sub-admin panel routes."""
    from config import MAIN_ADMIN_TELEGRAM_ID

    @app.get("/panel/login", response_class=HTMLResponse)
    async def panel_login_page():
        return HTMLResponse(panel_login())

    @app.post("/panel/login")
    async def panel_login_post(telegram_id: int = Form(...), password: str = Form(...)):
        user = db.get_user(telegram_id)
        if not user or not user.get("password_hash") or not check_password(password, user["password_hash"]):
            return HTMLResponse(panel_login("Invalid credentials."), 401)
        if not user["is_active"]:
            return HTMLResponse(panel_login("Account suspended."), 403)
        r = RedirectResponse("/panel", 303)
        r.set_cookie("panel_tg_id", str(telegram_id), httponly=True, max_age=86400)
        r.set_cookie("panel_token", panel_cookie(telegram_id), httponly=True, max_age=86400)
        return r

    @app.get("/panel")
    async def panel_dashboard(request: Request):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        stats = db.get_view_stats_by_owner(user["telegram_id"])
        cc = db.count_content_by_owner(user["telegram_id"])
        plan = user.get("plan_name") or "Free"
        exp = str(user.get("plan_expires") or "Never")[:10]
        # Queue stats
        q_stats = {}
        try:
            q_stats = db.queue_stats_by_user(user["telegram_id"])
        except Exception:
            pass
        q_pending = q_stats.get("pending", 0)
        q_processing = q_stats.get("processing", 0)
        q_failed = q_stats.get("failed", 0)
        q_total = q_pending + q_processing
        q_section = ""
        if q_total > 0 or q_failed > 0:
            q_section = f"""<div class="card" style="border-left:3px solid var(--acc);margin-top:12px">
<h3>📦 Upload Queue</h3>
<p>⏳ Pending: <b>{q_pending}</b> | ⚙️ Processing: <b>{q_processing}</b> | ❌ Failed: <b>{q_failed}</b></p>
<p style="margin-top:8px;color:var(--txt2)">Use <code>/queue</code> in the bot to manage your queue.</p></div>"""
        body = f"""<h1>📊 Dashboard</h1>
        <div class="grid">
          <div class="card stat"><div class="stat-value">{cc}</div><div class="stat-label">My Content</div></div>
          <div class="card stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">Total Views</div></div>
          <div class="card stat"><div class="stat-value">{stats['today']}</div><div class="stat-label">Today</div></div>
          <div class="card stat"><div class="stat-value">{plan}</div><div class="stat-label">Plan</div></div></div>
        <div class="card"><p>📅 Expires: <b>{exp}</b></p><p>📦 Content: <b>{cc}/{user['max_content']}</b> | Views: <b>{user['max_views_day']}/day</b></p></div>{q_section}"""
        return panel_html(body, user, "Dashboard", "dashboard")

    # ── Content (with hierarchy) ─────────────────────────────

    @app.get("/panel/content")
    async def panel_content(request: Request, parent: int = 0, msg: str = ""):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        pid = parent if parent > 0 else None
        items = db.get_content_tree(user["telegram_id"], pid)
        bc = ""
        if pid:
            crumbs = db.get_breadcrumb(pid)
            bc = '<a href="/panel/content" style="color:#a78bfa">Root</a>'
            for cr in crumbs:
                bc += f' → <a href="/panel/content?parent={cr["id"]}" style="color:#a78bfa">{he(cr["title"])}</a>'
            bc = f'<p style="margin-bottom:12px;font-size:.85rem">📂 {bc}</p>'
        rows = ""
        for c in items:
            cid = c["id"]; title = he(c["title"]); slug = c["slug"]
            sc = c.get("source_count", 0); cc_count = c.get("child_count", 0)
            type_badge = f'<span class="badge badge-acc">{cc_count} sub</span>' if cc_count > 0 else f'<span class="badge badge-ok">{sc} src</span>'
            rows += f'<tr><td><a href="/panel/content?parent={cid}" style="color:#a78bfa;text-decoration:none">{title}</a><br><span class="mono">{slug}</span></td><td>{type_badge}</td>'
            rows += f'<td><a href="/panel/embeds/{cid}" class="btn btn-primary btn-sm">Embed</a> '
            rows += f'<a href="/panel/content/{cid}/sources" class="btn btn-primary btn-sm">Sources</a> '
            rows += f'<form method="POST" action="/panel/content/{cid}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        parent_field = f'<input type="hidden" name="parent_id" value="{pid}">' if pid else ''
        body = f"""<h1>📁 My Content</h1>{flash(msg)}{bc}
        <div class="card"><h3 style="margin-bottom:12px">Create New</h3>
        <form method="POST" action="/panel/content/create" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
          {parent_field}
          <div class="form-group" style="flex:1;min-width:200px"><label>Title</label><input type="text" name="title" required placeholder="Naruto Episode 1"></div>
          <div class="form-group" style="min-width:120px"><label>Category</label><select name="category"><option>anime</option><option>movie</option><option>series</option><option>general</option></select></div>
          <button class="btn btn-primary" type="submit">Create</button></form></div>
        <table><tr><th>Content</th><th>Type</th><th>Actions</th></tr>{rows}</table>"""
        return panel_html(body, user, "Content", "content")

    @app.post("/panel/content/create")
    async def panel_content_create(request: Request, title: str = Form(...), category: str = Form("general"), parent_id: int = Form(0)):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        cc = db.count_content_by_owner(user["telegram_id"])
        if cc >= user["max_content"]:
            return RedirectResponse(f"/panel/content?msg=Limit reached ({user['max_content']})", 303)
        slug = slugify(title)
        if not slug:
            slug = f"content-{secrets.token_hex(4)}"
        pid = parent_id if parent_id > 0 else None
        try:
            db.create_content(user["telegram_id"], title, slug, category, parent_id=pid)
            redir = f"/panel/content?parent={pid}&msg=Created: {title}" if pid else f"/panel/content?msg=Created: {title}"
            return RedirectResponse(redir, 303)
        except Exception:
            slug = f"{slug}-{secrets.token_hex(3)}"
            try:
                db.create_content(user["telegram_id"], title, slug, category, parent_id=pid)
                redir = f"/panel/content?parent={pid}&msg=Created: {title}" if pid else f"/panel/content?msg=Created: {title}"
                return RedirectResponse(redir, 303)
            except Exception as e:
                return RedirectResponse(f"/panel/content?msg=Error: {e}", 303)

    @app.post("/panel/content/{cid}/delete")
    async def panel_content_del(cid: int, request: Request):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.delete_content(cid, user["telegram_id"])
        return RedirectResponse("/panel/content?msg=Deleted", 303)

    @app.get("/panel/content/{cid}/sources")
    async def panel_sources(cid: int, request: Request, msg: str = ""):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        content = db.get_content_by_id(cid)
        if not content or content["owner_id"] != user["telegram_id"]:
            raise HTTPException(404)
        sources = db.get_sources_by_content(cid)
        rows = ""
        for s in sources:
            fid_short = s["file_id"][:35]
            rows += f'<tr><td>{s["language"]}</td><td>{s["quality"]}</td><td>{s["width"]}x{s["height"]}</td><td>{fmt_size(s["file_size"])}</td>'
            rows += f'<td class="mono" style="max-width:180px;overflow:hidden;text-overflow:ellipsis">{fid_short}...</td>'
            rows += f'<td><form method="POST" action="/panel/source/{s["id"]}/delete" style="display:inline"><input type="hidden" name="cid" value="{cid}"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        ct = he(content['title'])
        body = f"""<h1>📁 {ct} — Sources</h1>
        <p style="margin-bottom:16px"><a href="/panel/content" style="color:#a78bfa">← Back</a></p>{flash(msg)}
        <div class="card"><h3 style="margin-bottom:12px">Add Source</h3>
        <form method="POST" action="/panel/source/add" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
          <input type="hidden" name="cid" value="{cid}">
          <div class="form-group" style="flex:2;min-width:200px"><label>File ID</label><input type="text" name="file_id" required></div>
          <div class="form-group" style="flex:1;min-width:100px"><label>Language</label><input type="text" name="language" value="Hindi" required></div>
          <div class="form-group" style="min-width:80px"><label>Quality</label><select name="quality"><option>480p</option><option selected>720p</option><option>1080p</option><option>2160p</option></select></div>
          <div class="form-group" style="min-width:80px"><label>Size (bytes)</label><input type="number" name="file_size" value="0"></div>
          <button class="btn btn-primary" type="submit">Add</button></form></div>
        <table><tr><th>Lang</th><th>Quality</th><th>Res</th><th>Size</th><th>File ID</th><th></th></tr>{rows}</table>"""
        return panel_html(body, user, "Sources", "content")

    @app.post("/panel/source/add")
    async def panel_source_add(request: Request, cid: int = Form(...), file_id: str = Form(...),
                               language: str = Form("Hindi"), quality: str = Form("720p"), file_size: int = Form(0)):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        content = db.get_content_by_id(cid)
        if not content or content["owner_id"] != user["telegram_id"]:
            raise HTTPException(403)
        db.add_source(cid, file_id.strip(), language.strip(), quality.strip(), file_size=file_size)
        return RedirectResponse(f"/panel/content/{cid}/sources?msg=Added", 303)

    @app.post("/panel/source/{sid}/delete")
    async def panel_source_del(sid: int, request: Request, cid: int = Form(...)):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.delete_source(sid)
        return RedirectResponse(f"/panel/content/{cid}/sources?msg=Deleted", 303)

    # ── Embeds ───────────────────────────────────────────────

    @app.get("/panel/embeds")
    async def panel_embeds(request: Request):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        items = db.list_content_by_owner(user["telegram_id"])
        base = BASE()
        rows = ""
        for c in items:
            rows += f'<tr><td>{he(c["title"])}</td><td>{c.get("source_count",0)}</td><td><a href="{base}/watch/{c["slug"]}" target="_blank" style="color:#a78bfa">{base}/watch/{c["slug"]}</a></td>'
            rows += f'<td><a href="/panel/embeds/{c["id"]}" class="btn btn-primary btn-sm">Get Code</a></td></tr>'
        body = f'<h1>🔗 Embed Links</h1><table><tr><th>Content</th><th>Sources</th><th>Watch URL</th><th></th></tr>{rows}</table>'
        return panel_html(body, user, "Embeds", "embeds")

    @app.get("/panel/embeds/{cid}")
    async def panel_embed_code_page(cid: int, request: Request):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        content = db.get_content_by_id(cid)
        if not content or content["owner_id"] != user["telegram_id"]:
            raise HTTPException(404)
        base = BASE()
        body = panel_embed_code(he(content["title"]), f"{base}/watch/{content['slug']}", f"{base}/embed/{content['slug']}")
        return panel_html(body, user, "Embed Code", "embeds")

    # ── Ads ──────────────────────────────────────────────────

    @app.get("/panel/ads")
    async def panel_ads(request: Request, msg: str = ""):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        plan_allows_ads = False
        if user.get("plan_id"):
            plan = db.get_plan_by_id(user["plan_id"])
            if plan:
                plan_allows_ads = bool(plan.get("can_ads"))
        ads = db.get_ads_by_owner(user["telegram_id"])
        rows = ""
        for a in ads:
            ab = "badge-ok" if a["is_active"] else "badge-err"
            at = "Active" if a["is_active"] else "Off"
            rows += f'<tr><td>{he(a["name"])}</td><td>{a["ad_type"]}</td><td>{a["position"]}</td><td>{a["duration"]}s</td>'
            rows += f'<td><span class="badge {ab}">{at}</span></td>'
            rows += f'<td><form method="POST" action="/panel/ads/{a["id"]}/toggle" style="display:inline"><button class="btn btn-primary btn-sm">Toggle</button></form> '
            rows += f'<form method="POST" action="/panel/ads/{a["id"]}/delete" style="display:inline"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        notice = '<div class="card" style="border-color:#ef4444"><p style="color:#ef4444"><b>Your plan does not include ads.</b> Upgrade to use ads.</p></div>' if not plan_allows_ads else ""
        body = f"""<h1>📢 My Ads</h1>{flash(msg)}{notice}
        <div class="card"><h3 style="margin-bottom:12px">Create Ad</h3>
        <form method="POST" action="/panel/ads/create">
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px">
            <div class="form-group" style="flex:1;min-width:150px"><label>Name</label><input type="text" name="name" required></div>
            <div class="form-group" style="min-width:100px"><label>Type</label><select name="ad_type"><option value="vast">VAST</option><option value="custom">Custom</option></select></div>
            <div class="form-group" style="min-width:80px"><label>Position</label><select name="position"><option value="pre">Pre</option><option value="mid">Mid</option></select></div>
            <div class="form-group" style="min-width:60px"><label>Sec</label><input type="number" name="duration" value="5"></div></div>
          <div class="form-group"><label>VAST URL</label><input type="text" name="ad_url"></div>
          <div class="form-group"><label>Custom HTML</label><textarea name="ad_html" rows="2"></textarea></div>
          <button class="btn btn-primary" type="submit">Create</button></form></div>
        <table><tr><th>Name</th><th>Type</th><th>Pos</th><th>Dur</th><th>Active</th><th></th></tr>{rows}</table>"""
        return panel_html(body, user, "Ads", "ads")

    @app.post("/panel/ads/create")
    async def panel_ads_create(request: Request, name: str = Form(...), ad_type: str = Form("custom"),
            ad_url: str = Form(""), ad_html: str = Form(""), position: str = Form("pre"), duration: int = Form(5)):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.create_ad(user["telegram_id"], name, ad_type, ad_url, ad_html, position, duration)
        return RedirectResponse("/panel/ads?msg=Created", 303)

    @app.post("/panel/ads/{aid}/toggle")
    async def panel_ads_toggle(aid: int, request: Request):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.toggle_ad(aid, user["telegram_id"])
        return RedirectResponse("/panel/ads", 303)

    @app.post("/panel/ads/{aid}/delete")
    async def panel_ads_delete(aid: int, request: Request):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.delete_ad(aid, user["telegram_id"])
        return RedirectResponse("/panel/ads?msg=Deleted", 303)

    # ── Subscription + Payment ───────────────────────────────

    @app.get("/panel/subscription")
    async def panel_sub(request: Request, msg: str = ""):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        plans = db.list_plans()
        plan_cards = ""
        for p in plans:
            is_current = user.get("plan_id") == p["id"]
            border = "border:2px solid #a78bfa;" if is_current else ""
            tag = '<span class="badge badge-ok" style="margin-left:8px">Current</span>' if is_current else ""
            can_ads = "Ads: Yes" if p["can_ads"] else "Ads: No"
            plan_cards += f'<div class="card" style="{border}"><h3>{he(p["name"])}{tag}</h3>'
            plan_cards += f'<div class="stat-value" style="font-size:1.5rem;margin:8px 0">₹{p["price"]}</div>'
            plan_cards += f'<p style="color:#7777aa;font-size:.82rem">{p["max_content"]} content | {p["max_views_day"]} views/day | {p["max_sources"]} sources | {can_ads} | {p["duration_days"]}d</p>'
            if not is_current and p["slug"] != "free" and float(p["price"]) > 0:
                plan_cards += f'<a href="/panel/subscription/pay/{p["slug"]}" class="btn btn-primary" style="margin-top:10px">Buy {he(p["name"])} — ₹{p["price"]}</a>'
            plan_cards += '</div>'
        body = f"""<h1>💳 Subscription</h1>{flash(msg)}
        <div class="card"><p>Current: <b>{user.get("plan_name") or "Free"}</b> | Expires: <b>{str(user.get("plan_expires") or "Never")[:10]}</b></p></div>
        <h3 style="margin:20px 0 12px">Available Plans</h3>
        <div class="grid">{plan_cards}</div>"""
        return panel_html(body, user, "Subscription", "subscription")

    @app.get("/panel/subscription/pay/{plan_slug}")
    async def panel_pay(plan_slug: str, request: Request):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        plan = db.get_plan(plan_slug)
        if not plan:
            raise HTTPException(404)
        methods = db.list_payment_methods(active_only=True)
        method_cards = ""
        for m in methods:
            icon = {"upi": "💳", "bank": "🏦", "razorpay": "💰", "paypal": "🌐", "crypto": "₿", "custom": "📋"}.get(m["method_type"], "💳")
            det = he(m["details"] or "").replace("\n", "<br>")
            qr = f'<img src="{m["qr_image_url"]}" style="max-width:200px;border-radius:8px;margin-top:8px">' if m.get("qr_image_url") else ""
            method_cards += f'<div class="card"><h3>{icon} {he(m["title"])}</h3><p style="margin-top:8px;word-break:break-all">{det}</p>{qr}</div>'
        if not method_cards:
            method_cards = '<div class="card"><p style="color:#7777aa">No payment methods configured yet. Contact admin.</p></div>'
        body = f"""<h1>💰 Pay for {he(plan["name"])} — ₹{plan["price"]}</h1>
        <p style="margin-bottom:16px"><a href="/panel/subscription" style="color:#a78bfa">← Back to Plans</a></p>
        <h3 style="margin-bottom:12px">Step 1: Make Payment</h3>
        <div class="grid">{method_cards}</div>
        <h3 style="margin:20px 0 12px">Step 2: Submit Proof</h3>
        <div class="card">
        <form method="POST" action="/panel/subscription/submit">
          <input type="hidden" name="plan_slug" value="{plan_slug}">
          <div class="form-group"><label>Payment Method Used</label>
            <select name="method_type"><option value="">Select...</option>{"".join(f'<option value="{m["method_type"]}">{he(m["title"])}</option>' for m in methods)}</select></div>
          <div class="form-group"><label>Transaction ID / UTR Number</label><input type="text" name="transaction_id" required placeholder="Enter UTR or Transaction ID"></div>
          <div class="form-group"><label>Your Telegram ID</label><input type="text" name="tg_id_confirm" value="{user['telegram_id']}" readonly></div>
          <div class="form-group"><label>Additional Notes (optional)</label><textarea name="notes" rows="2" placeholder="Any additional info..."></textarea></div>
          <p style="color:#7777aa;font-size:.82rem;margin-bottom:12px">💡 Send payment screenshot to the bot using /proof command</p>
          <button class="btn btn-primary" type="submit">Submit Payment Proof</button>
        </form></div>"""
        return panel_html(body, user, "Payment", "subscription")

    @app.post("/panel/subscription/submit")
    async def panel_sub_submit(request: Request, plan_slug: str = Form(...), method_type: str = Form(""),
            transaction_id: str = Form(""), notes: str = Form(""), tg_id_confirm: str = Form("")):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        plan = db.get_plan(plan_slug)
        if not plan:
            return RedirectResponse("/panel/subscription?msg=Plan not found", 303)
        screenshot_fid = _pending_proofs.get(user["telegram_id"], "")
        db.create_payment_request(user["telegram_id"], plan["id"], float(plan["price"]),
            method_type, transaction_id.strip(), screenshot_fid, notes)
        tg_client = ctx.get("tg_client")
        if tg_client:
            try:
                if MAIN_ADMIN_TELEGRAM_ID:
                    uname = user.get("username", "") or str(user["telegram_id"])
                    msg_text = (f"📩 **New Payment Request**\n\n"
                        f"User: @{uname} (`{user['telegram_id']}`)\n"
                        f"Plan: **{plan['name']}** — ₹{plan['price']}\n"
                        f"Method: {method_type or '—'}\n"
                        f"TxnID: `{transaction_id or '—'}`\n\n"
                        f"Review in admin panel: {BASE()}/{AP}/requests")
                    await tg_client.send_message(MAIN_ADMIN_TELEGRAM_ID, msg_text)
            except Exception:
                pass
        if screenshot_fid:
            del _pending_proofs[user["telegram_id"]]
        return RedirectResponse("/panel/subscription?msg=Payment proof submitted! Admin will review shortly.", 303)

    # ── Profile ──────────────────────────────────────────────

    @app.get("/panel/profile")
    async def panel_profile(request: Request, msg: str = ""):
        user = get_panel_user(request)
        if not user:
            return RedirectResponse("/panel/login")
        uname = he(user.get("username", "") or "—")
        body = f"""<h1>👤 Profile</h1>{flash(msg)}
        <div class="card"><p>Telegram ID: <b class="mono">{user["telegram_id"]}</b></p>
          <p>Username: <b>@{uname}</b></p><p>Plan: <b>{user.get("plan_name") or "Free"}</b></p>
          <p>API Key: <span class="mono">{user.get("api_key","") or "—"}</span></p></div>
        <div class="card"><h3 style="margin-bottom:12px">Change Password</h3>
        <form method="POST" action="/panel/profile/password" style="display:flex;gap:10px;align-items:end">
          <div class="form-group" style="flex:1"><label>New Password</label><input type="password" name="password" required minlength="4"></div>
          <button class="btn btn-primary" type="submit">Update</button></form></div>
        <div class="card"><a href="/panel/logout" class="btn btn-danger">Logout</a></div>"""
        return panel_html(body, user, "Profile", "profile")

    @app.post("/panel/profile/password")
    async def panel_set_password(request: Request, password: str = Form(...)):
        user = get_panel_user(request)
        if not user:
            raise HTTPException(403)
        db.update_user(user["telegram_id"], password_hash=hash_password(password))
        return RedirectResponse("/panel/profile?msg=Password updated", 303)

    @app.get("/panel/logout")
    async def panel_logout():
        r = RedirectResponse("/panel/login", 303)
        r.delete_cookie("panel_tg_id")
        r.delete_cookie("panel_token")
        return r

    logger.info("Module: panel routes registered.")
