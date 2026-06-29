"""
Bot user commands — /start, /setpassword, /panel, /subscribe, /trial, /myplan,
/new, /links, /myvideos, /delete, /proof, /status, /add, /help.
"""
import secrets
import asyncio
import logging

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import MAIN_ADMIN_TELEGRAM_ID
import database as db
from helpers import BASE, slugify, hash_password, fmt_size

logger = logging.getLogger(__name__)


def _btn(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) if data else InlineKeyboardButton(text, url=url)
         for text, data, url in row] for row in rows])

def _b(text, data=None, url=None):
    return (text, data, url)


def register(tg_client, ctx):
    """Register user-facing bot commands."""

    @tg_client.on_message(filters.private & filters.command("start"))
    async def cmd_start(_c, m: Message):
        uid = m.from_user.id
        user = db.get_user(uid)
        if not user:
            db.create_user(uid, m.from_user.username or "", m.from_user.first_name or "")
            free = db.get_plan("free")
            if free:
                db.set_user_plan(uid, free["id"], 0)
        name = m.from_user.first_name or "there"
        is_ma = uid == MAIN_ADMIN_TELEGRAM_ID if MAIN_ADMIN_TELEGRAM_ID else False
        admin_hint = "\n🔑 **Admin:** /users /grant /stats /broadcast" if is_ma else ""
        await m.reply_text(
            f"👋 **Welcome, {name}!**\n\n"
            f"🎬 **Stream Platform — Premium Video Hosting**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📹 **Just send videos** → auto-detected!\n"
            f"📁 **/new** `Title/Season/Episode` — Manual create\n"
            f"🔗 **/links** `slug` — Get embed links\n"
            f"📋 **/myvideos** — My content\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 **/subscribe** — Plans & pricing\n"
            f"📊 **/myplan** — Current plan\n"
            f"🔐 **/setpassword** `pass` — Panel access\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ **No file size limit · HD streaming**{admin_hint}",
            reply_markup=_btn(
                [_b("📁 My Content", "menu:content"), _b("💳 Plans", "menu:plans")],
                [_b("🖥 Open Panel", url=f"{BASE()}/panel/login"), _b("📊 Status", "menu:status")]))

    @tg_client.on_message(filters.private & filters.command("setpassword"))
    async def cmd_setpw(_c, m: Message):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: `/setpassword YourPassword`\n\nMinimum 4 characters.")
        pw = parts[1].strip()
        if len(pw) < 4:
            return await m.reply_text("❌ Password must be at least 4 characters.")
        user = db.get_user(m.from_user.id)
        if not user:
            return await m.reply_text("Send /start first.")
        db.update_user(m.from_user.id, password_hash=hash_password(pw))
        await m.reply_text(
            f"✅ **Password Set!**\n\n"
            f"🖥 Panel: {BASE()}/panel/login\n"
            f"🆔 Your ID: `{m.from_user.id}`",
            reply_markup=_btn([_b("🖥 Open Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("panel"))
    async def cmd_panel(_c, m: Message):
        await m.reply_text(
            f"🖥 **Sub-Admin Panel**\n\n"
            f"Link: {BASE()}/panel/login\n"
            f"Your ID: `{m.from_user.id}`\n\n"
            f"Set password first: /setpassword",
            reply_markup=_btn([_b("🖥 Open Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("subscribe"))
    async def cmd_subscribe(_c, m: Message):
        plans = db.list_plans()
        lines = ""
        buttons = []
        for p in plans:
            emoji = {"free": "🆓", "trial": "🎁", "basic": "⭐", "pro": "👑"}.get(p["slug"], "💎")
            lines += f"\n{emoji} **{p['name']}** — ₹{p['price']}\n"
            lines += f"   {p['max_content']} content · {p['max_views_day']} views/day · {p['duration_days']}d\n"
            if p["slug"] not in ("free",) and float(p["price"]) > 0:
                buttons.append(_b(f"💳 {p['name']} ₹{p['price']}", f"buy:{p['slug']}"))
        btn_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        btn_rows.append([_b("🎁 Free Trial", "menu:trial")])
        await m.reply_text(
            f"💳 **Subscription Plans**\n"
            f"━━━━━━━━━━━━━━━━━━━━{lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Select a plan below to purchase:",
            reply_markup=_btn(*btn_rows))

    @tg_client.on_message(filters.private & filters.command("trial"))
    async def cmd_trial(_c, m: Message):
        user = db.get_user(m.from_user.id)
        if not user:
            return await m.reply_text("Send /start first.")
        if user.get("plan_slug") == "trial" or (user.get("plan_expires") and str(user.get("plan_expires")) > "2020"):
            return await m.reply_text("⚠️ You already have an active plan or used trial.")
        trial = db.get_plan("trial")
        if trial:
            db.set_user_plan(m.from_user.id, trial["id"], trial["duration_days"])
            await m.reply_text(
                "🎉 **7-Day Trial Activated!**\n\n"
                "✅ 20 content · 5000 views/day · Ads enabled\n"
                "⏰ Expires in 7 days\n\n"
                "📹 Just send videos to start!",
                reply_markup=_btn([_b("📹 Upload Video", "menu:upload_help"), _b("🖥 Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("myplan"))
    async def cmd_myplan(_c, m: Message):
        user = db.get_user(m.from_user.id)
        if not user:
            return await m.reply_text("Send /start first.")
        cc = db.count_content_by_owner(m.from_user.id)
        stats = db.get_view_stats_by_owner(m.from_user.id)
        await m.reply_text(
            f"📋 **Your Plan**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Plan: **{user.get('plan_name') or 'Free'}**\n"
            f"📅 Expires: {user.get('plan_expires') or 'Never'}\n"
            f"📁 Content: {cc}/{user['max_content']}\n"
            f"📊 Views: {stats['total']} total · {stats['today']} today\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=_btn([_b("💳 Upgrade", "menu:plans"), _b("🖥 Panel", url=f"{BASE()}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("new"))
    async def cmd_new(_c, m: Message):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text(
                "📁 **Create Content**\n\n"
                "Usage:\n"
                "`/new Naruto Episode 1`\n"
                "`/new Kaiju No.8/Season 1/Episode 1`\n\n"
                "The `/` creates nested structure automatically!\n\n"
                "💡 **Tip:** Just send a video — metadata is auto-detected!")
        user = db.get_user(m.from_user.id)
        if not user:
            return await m.reply_text("Send /start first.")
        raw_title = parts[1].strip()
        path_parts = [p.strip() for p in raw_title.split("/") if p.strip()]
        if not path_parts:
            return await m.reply_text("❌ Invalid title.")
        cc = db.count_content_by_owner(m.from_user.id)
        if cc + len(path_parts) > user["max_content"] + 5:
            return await m.reply_text(f"❌ Content limit reached ({user['max_content']}). Upgrade plan.")
        parent_id = None
        created_slugs = []
        for part_title in path_parts:
            slug = slugify(part_title)
            if not slug:
                slug = f"content-{secrets.token_hex(4)}"
            existing = db.get_content_by_slug(slug)
            if existing and existing["owner_id"] == m.from_user.id:
                parent_id = existing["id"]
                created_slugs.append((part_title, slug, False))
                continue
            try:
                new_id = db.create_content(m.from_user.id, part_title, slug, parent_id=parent_id)
                parent_id = new_id
                created_slugs.append((part_title, slug, True))
            except Exception:
                slug = f"{slug}-{secrets.token_hex(3)}"
                try:
                    new_id = db.create_content(m.from_user.id, part_title, slug, parent_id=parent_id)
                    parent_id = new_id
                    created_slugs.append((part_title, slug, True))
                except Exception as e:
                    return await m.reply_text(f"❌ Error: {e}")
        last_slug = created_slugs[-1][1]
        path_display = " → ".join(f"**{t}**" for t, _, _ in created_slugs)
        new_items = sum(1 for _, _, is_new in created_slugs if is_new)
        await m.reply_text(
            f"✅ **Content Created!**\n\n"
            f"📂 {path_display}\n"
            f"🏷 Slug: `{last_slug}`\n"
            f"📦 {new_items} new item(s)\n\n"
            f"📹 Now send a video — it will be auto-detected!",
            reply_markup=_btn(
                [_b("🔗 Get Links", f"links:{last_slug}"), _b("📁 My Content", "menu:content")]))

    @tg_client.on_message(filters.private & filters.command("links"))
    async def cmd_links(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/links slug`")
        content = db.get_content_by_slug(parts[1])
        if not content:
            return await m.reply_text("❌ Not found.")
        sources = db.get_sources_by_content(content["id"])
        base = BASE()
        langs = {}
        for s in sources:
            langs.setdefault(s["language"], []).append(s["quality"])
        ss = "\n".join(f"  🎬 {l}: {', '.join(q)}" for l, q in langs.items())
        watch_url = f"{base}/watch/{content['slug']}"
        await m.reply_text(
            f"🔗 **{content['title']}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"▶️ **Player:**\n`{watch_url}`\n\n"
            f"🖼 **iFrame:**\n`<iframe src=\"{base}/embed/{content['slug']}\" width=\"720\" height=\"405\" allowfullscreen></iframe>`\n\n"
            f"📺 **Sources:**\n{ss}",
            disable_web_page_preview=True,
            reply_markup=_btn([_b("▶️ Watch", url=watch_url), _b("🖥 Panel", url=f"{base}/panel/login")]))

    @tg_client.on_message(filters.private & filters.command("myvideos"))
    async def cmd_myvideos(_c, m: Message):
        items = db.list_content_by_owner(m.from_user.id, 20)
        if not items:
            return await m.reply_text("📭 No content yet.\n\n📹 Just send a video to start!",
                reply_markup=_btn([_b("📹 How to Upload", "menu:upload_help")]))
        lines = "\n".join(f"📁 **{c['title']}** (`{c['slug']}`) — {c.get('source_count', 0)} src" for c in items)
        await m.reply_text(
            f"📁 **My Content ({len(items)})**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n{lines}",
            reply_markup=_btn([_b("📹 Upload Video", "menu:upload_help"), _b("🖥 Panel", url=f"{BASE()}/panel/content")]))

    @tg_client.on_message(filters.private & filters.command("delete"))
    async def cmd_delete(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/delete slug`")
        content = db.get_content_by_slug(parts[1])
        if not content:
            return await m.reply_text("❌ Not found.")
        is_ma = m.from_user.id == MAIN_ADMIN_TELEGRAM_ID if MAIN_ADMIN_TELEGRAM_ID else False
        if content["owner_id"] != m.from_user.id and not is_ma:
            return await m.reply_text("❌ Not your content.")
        db.delete_content(content["id"])
        await m.reply_text(f"🗑 Deleted: **{content['title']}**")

    @tg_client.on_message(filters.private & filters.command("proof"))
    async def cmd_proof(_c, m: Message):
        from modules.panel import get_pending_proofs
        proofs = get_pending_proofs()
        if m.reply_to_message and m.reply_to_message.photo:
            fid = m.reply_to_message.photo.file_id
            proofs[m.from_user.id] = fid
            await m.reply_text("✅ **Screenshot saved!**\n\nNow go to the payment page and submit your proof.")
        else:
            await m.reply_text(
                "📸 **Submit Payment Proof**\n\n"
                "1. Send payment screenshot as a photo\n"
                "2. Reply to that photo with /proof\n"
                "3. Go to payment page and fill the form")

    @tg_client.on_message(filters.private & filters.command("status"))
    async def cmd_status(_c, m: Message):
        c = tg_client.is_connected
        cc = db.count_content_by_owner(m.from_user.id)
        stats = db.get_view_stats_by_owner(m.from_user.id)
        await m.reply_text(
            f"📊 **Server Status**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔌 Streaming: {'✅ Connected' if c else '❌ Disconnected'}\n"
            f"📦 File Limit: **None (unlimited)**\n"
            f"📁 My content: {cc}\n"
            f"👁 Views: {stats['total']} total · {stats['today']} today\n"
            f"🌐 Server: {BASE()}")

    @tg_client.on_message(filters.private & filters.command("add"))
    async def cmd_add(_c, m: Message):
        parts = m.text.split()
        if len(parts) < 4:
            return await m.reply_text(
                "Usage: `/add slug Language Quality`\n\nSend video first!\n\n"
                "💡 **Tip:** Just send a video — it's auto-detected now!")
        slug, lang, qual = parts[1], parts[2], parts[3]
        from bot.upload_handler import get_pending_videos
        pending = get_pending_videos().get(m.from_user.id)
        if not pending:
            return await m.reply_text("⚠️ Send a video first.")
        content = db.get_content_by_slug(slug)
        if not content:
            return await m.reply_text(f"❌ `{slug}` not found. Create with /new.")
        if content["owner_id"] != m.from_user.id:
            return await m.reply_text("❌ Not your content.")
        try:
            db.add_source(content["id"], pending["file_id"], lang, qual, pending.get("file_unique_id", ""),
                pending.get("file_size", 0), pending.get("duration", 0), pending.get("width", 0), pending.get("height", 0))
            get_pending_videos().pop(m.from_user.id, None)
            sources = db.get_sources_by_content(content["id"])
            ss = " · ".join(f"{s['language']} {s['quality']}" for s in sources)
            await m.reply_text(
                f"✅ **Source Added!**\n\n"
                f"📁 {content['title']}\n"
                f"🎬 {lang} {qual}\n"
                f"📺 All: {ss}",
                reply_markup=_btn([_b("🔗 Get Links", f"links:{slug}"), _b("📁 Content", "menu:content")]))
        except Exception as e:
            await m.reply_text(f"❌ Error: {e}")

    @tg_client.on_message(filters.private & filters.command("queue"))
    async def cmd_queue(_c, m: Message):
        """Show user's upload queue status."""
        uid = m.from_user.id
        try:
            stats = db.queue_stats_by_user(uid)
        except Exception:
            stats = {}
        pending = stats.get("pending", 0)
        processing = stats.get("processing", 0)
        completed = stats.get("completed", 0)
        failed = stats.get("failed", 0)
        total = stats.get("total", 0)

        if total == 0:
            return await m.reply_text(
                "📦 **Upload Queue**\n\n"
                "Your queue is empty.\n"
                "Send a video and tap 📦 Queue to add it!",
                reply_markup=_btn([_b("📹 Upload Video", "menu:upload_help")]))

        # Get recent queue items
        try:
            items = db.queue_list_by_user(uid, limit=10)
        except Exception:
            items = []

        lines = []
        for item in items[:10]:
            status_emoji = {"pending": "⏳", "processing": "⚙️", "completed": "✅",
                           "failed": "❌", "cancelled": "🚫"}.get(item["status"], "❓")
            fname = item.get("file_name", "")[:30] or "Video"
            lines.append(f"{status_emoji} {fname} — **{item['status']}**")

        items_text = "\n".join(lines) if lines else "No items"

        btns = []
        if failed > 0:
            btns.append(_b(f"🔄 Retry Failed ({failed})", "queue:retry_all"))
        if pending > 0:
            btns.append(_b(f"❌ Cancel Pending ({pending})", "queue:cancel_all"))
        btn_rows = [btns] if btns else []
        btn_rows.append([_b("📁 My Content", "menu:content")])

        await m.reply_text(
            f"📦 **Upload Queue**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Pending: **{pending}**\n"
            f"⚙️ Processing: **{processing}**\n"
            f"✅ Completed: **{completed}**\n"
            f"❌ Failed: **{failed}**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 **Recent:**\n{items_text}",
            reply_markup=_btn(*btn_rows) if btn_rows else None)

    logger.info("Bot: user commands registered.")

