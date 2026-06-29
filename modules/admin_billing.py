"""
Admin Billing module — Payment Requests, Payment Methods.
Extracted from server.py admin panel routes.
"""
import logging
from html import escape as he

from fastapi import Request, HTTPException, Form
from fastapi.responses import RedirectResponse

from config import MAIN_ADMIN_TELEGRAM_ID
import database as db
from helpers import AP, is_admin, admin_html, flash

logger = logging.getLogger(__name__)


def register(app, ctx):
    """Register admin billing routes (requests, payment methods)."""

    # ── Payment Requests ─────────────────────────────────────

    @app.get(f"/{AP}/requests")
    async def admin_requests(request: Request, status: str = "pending", msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        reqs = db.list_payment_requests(status if status != "all" else None)
        tabs = ""
        for s in ["pending", "approved", "rejected", "all"]:
            cls = "active" if s == status else ""
            tabs += f'<a href="/{AP}/requests?status={s}" class="tab {cls}">{s.title()}</a>'
        rows = ""
        for r in reqs:
            rb = {"pending": "badge-warn", "approved": "badge-ok", "rejected": "badge-err"}.get(r["status"], "badge-acc")
            uname = he(r.get("username", "") or r.get("display_name", "") or str(r.get("user_id", "")))
            pname = he(r.get("plan_name", "") or "—")
            rows += f'<tr><td>@{uname}<br><span class="mono">{r.get("user_id","")}</span></td><td>{pname}</td><td>₹{r["amount"]}</td>'
            rows += f'<td>{he(r.get("method_type","") or "—")}</td><td><span class="mono">{he(r.get("transaction_id","") or "—")}</span></td>'
            rows += f'<td><span class="badge {rb}">{r["status"]}</span></td><td>{r["created_at"]}</td><td>'
            if r["status"] == "pending":
                rows += f'<form method="POST" action="/{AP}/requests/{r["id"]}/approve" style="display:inline"><button class="btn btn-ok btn-sm">Approve</button></form> '
                rows += f'<form method="POST" action="/{AP}/requests/{r["id"]}/reject" style="display:inline"><input type="hidden" name="notes" value=""><button class="btn btn-danger btn-sm">Reject</button></form>'
            elif r.get("admin_notes"):
                rows += f'<span class="mono" style="font-size:.7rem">{he(r["admin_notes"][:30])}</span>'
            rows += '</td></tr>'
        body = f"""<h1>📩 Payment Requests</h1>{flash(msg)}
        <div class="tabs">{tabs}</div>
        <table><tr><th>User</th><th>Plan</th><th>Amount</th><th>Method</th><th>TxnID</th><th>Status</th><th>Date</th><th>Actions</th></tr>{rows}</table>"""
        return admin_html(body, "Requests", "requests")

    @app.post(f"/{AP}/requests/{{rid}}/approve")
    async def admin_req_approve(rid: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        req = db.get_payment_request(rid)
        if not req or req["status"] != "pending":
            return RedirectResponse(f"/{AP}/requests?msg=Invalid request", 303)
        db.approve_payment_request(rid, MAIN_ADMIN_TELEGRAM_ID or 0)
        plan = db.get_plan_by_id(req["plan_id"])
        if plan:
            dur = plan.get("duration_days", 30) or 30
            db.set_user_plan(req["user_id"], plan["id"], dur)
            tg_client = ctx.get("tg_client")
            if tg_client:
                try:
                    await tg_client.send_message(req["user_id"],
                        f"🎉 **Payment Approved!**\n\nYour **{plan['name']}** plan is now active!\nValid for {dur} days.\n\nEnjoy premium features! ⚡")
                except Exception:
                    pass
        return RedirectResponse(f"/{AP}/requests?msg=Approved and plan activated", 303)

    @app.post(f"/{AP}/requests/{{rid}}/reject")
    async def admin_req_reject(rid: int, request: Request, notes: str = Form("")):
        if not is_admin(request):
            raise HTTPException(403)
        req = db.get_payment_request(rid)
        if not req or req["status"] != "pending":
            return RedirectResponse(f"/{AP}/requests?msg=Invalid", 303)
        db.reject_payment_request(rid, MAIN_ADMIN_TELEGRAM_ID or 0, notes)
        tg_client = ctx.get("tg_client")
        if tg_client:
            try:
                reason = f"\nReason: {notes}" if notes else ""
                await tg_client.send_message(req["user_id"],
                    f"❌ **Payment Request Rejected**\n\nYour payment request has been rejected.{reason}\n\nContact admin for help.")
            except Exception:
                pass
        return RedirectResponse(f"/{AP}/requests?msg=Rejected", 303)

    # ── Payment Methods ──────────────────────────────────────

    @app.get(f"/{AP}/payments")
    async def admin_payments(request: Request, msg: str = ""):
        if not is_admin(request):
            return RedirectResponse(f"/{AP}/login")
        methods = db.list_payment_methods()
        rows = ""
        for m in methods:
            ab = "badge-ok" if m["is_active"] else "badge-err"
            at = "Active" if m["is_active"] else "Off"
            det = he((m["details"] or "")[:60])
            rows += f'<tr><td>{he(m["title"])}</td><td>{he(m["method_type"])}</td><td style="max-width:200px;overflow:hidden">{det}</td>'
            rows += f'<td><span class="badge {ab}">{at}</span></td>'
            rows += f'<td><form method="POST" action="/{AP}/payments/{m["id"]}/toggle" style="display:inline"><button class="btn btn-primary btn-sm">Toggle</button></form> '
            rows += f'<form method="POST" action="/{AP}/payments/{m["id"]}/delete" style="display:inline" onsubmit="return confirm(\'Delete?\')"><button class="btn btn-danger btn-sm">Del</button></form></td></tr>'
        body = f"""<h1>💰 Payment Methods</h1>{flash(msg)}
        <table><tr><th>Title</th><th>Type</th><th>Details</th><th>Active</th><th></th></tr>{rows}</table>
        <div class="card"><h3 style="margin-bottom:12px">Add Payment Method</h3>
        <form method="POST" action="/{AP}/payments/create">
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            <div class="form-group" style="flex:1;min-width:150px"><label>Title</label><input type="text" name="title" required placeholder="UPI Payment"></div>
            <div class="form-group" style="min-width:120px"><label>Type</label><select name="method_type"><option value="upi">UPI</option><option value="bank">Bank Transfer</option><option value="razorpay">Razorpay</option><option value="paypal">PayPal</option><option value="crypto">Crypto</option><option value="custom">Custom</option></select></div>
            <div class="form-group" style="min-width:60px"><label>Order</label><input type="number" name="sort_order" value="0"></div></div>
          <div class="form-group"><label>Details (UPI ID / Account / Link / Instructions)</label><textarea name="details" rows="3" placeholder="admin@paytm or https://paypal.me/..."></textarea></div>
          <div class="form-group"><label>QR Image URL (optional)</label><input type="url" name="qr_image_url" placeholder="https://..."></div>
          <button class="btn btn-primary" type="submit">Add Method</button></form></div>"""
        return admin_html(body, "Payments", "payments")

    @app.post(f"/{AP}/payments/create")
    async def admin_pm_create(request: Request, title: str = Form(...), method_type: str = Form("upi"),
            details: str = Form(""), qr_image_url: str = Form(""), sort_order: int = Form(0)):
        if not is_admin(request):
            raise HTTPException(403)
        db.create_payment_method(method_type, title, details, qr_image_url, sort_order)
        return RedirectResponse(f"/{AP}/payments?msg=Added", 303)

    @app.post(f"/{AP}/payments/{{pm_id}}/toggle")
    async def admin_pm_toggle(pm_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.toggle_payment_method(pm_id)
        return RedirectResponse(f"/{AP}/payments?msg=Toggled", 303)

    @app.post(f"/{AP}/payments/{{pm_id}}/delete")
    async def admin_pm_delete(pm_id: int, request: Request):
        if not is_admin(request):
            raise HTTPException(403)
        db.delete_payment_method(pm_id)
        return RedirectResponse(f"/{AP}/payments?msg=Deleted", 303)

    logger.info("Module: admin_billing routes registered.")
