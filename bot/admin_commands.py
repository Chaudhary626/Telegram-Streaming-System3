"""
Bot admin commands — /users, /grant, /revoke, /ban, /unban, /stats, /broadcast,
/addchannel, /channels, /rmchannel. Main admin only.
"""
import logging

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import MAIN_ADMIN_TELEGRAM_ID
import database as db
from helpers import BASE, AP, detect_quality

logger = logging.getLogger(__name__)


def _btn(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) if data else InlineKeyboardButton(text, url=url)
         for text, data, url in row] for row in rows])

def _b(text, data=None, url=None):
    return (text, data, url)


def register(tg_client, ctx):
    """Register admin-only bot commands."""

    def is_ma(uid):
        return uid == MAIN_ADMIN_TELEGRAM_ID if MAIN_ADMIN_TELEGRAM_ID else False

    @tg_client.on_message(filters.private & filters.command("addchannel"))
    async def cmd_addchannel(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 3:
            return await m.reply_text("Usage: `/addchannel Name -100xxxx [category]`")
        db.create_channel(parts[1], int(parts[2]), parts[3] if len(parts) > 3 else "general")
        await m.reply_text(f"✅ Channel **{parts[1]}** added")

    @tg_client.on_message(filters.private & filters.command("channels"))
    async def cmd_channels(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        chs = db.list_channels()
        if not chs:
            return await m.reply_text("No channels.")
        lines = "\n".join(f"• **{c['name']}** `{c['channel_id']}` ({c['category']})" for c in chs)
        await m.reply_text(f"📺 **Channels:**\n\n{lines}")

    @tg_client.on_message(filters.private & filters.command("rmchannel"))
    async def cmd_rmchannel(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/rmchannel Name`")
        ch = db.get_channel_by_name(parts[1])
        if ch:
            db.delete_channel(ch["id"])
            await m.reply_text("🗑 Removed")
        else:
            await m.reply_text("Not found.")

    @tg_client.on_message(filters.private & filters.command("users"))
    async def cmd_users(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        users = db.list_users(20)
        lines = "\n".join(
            f"• @{u.get('username', '') or '—'} `{u['telegram_id']}` — {u.get('plan_name') or 'Free'} {'🔴' if not u['is_active'] else ''}"
            for u in users)
        await m.reply_text(f"👤 **Users ({len(users)}):**\n\n{lines}",
            reply_markup=_btn([_b("🖥 Admin Panel", url=f"{BASE()}/{AP}/users")]))

    @tg_client.on_message(filters.private & filters.command("grant"))
    async def cmd_grant(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 3:
            return await m.reply_text("Usage: `/grant telegram_id plan_slug`")
        plan = db.get_plan(parts[2])
        if not plan:
            return await m.reply_text("Plan not found.")
        db.set_user_plan(int(parts[1]), plan["id"], plan["duration_days"])
        await m.reply_text(f"✅ Granted **{plan['name']}** to `{parts[1]}`")
        try:
            await tg_client.send_message(int(parts[1]),
                f"🎉 Plan upgraded to **{plan['name']}**! Valid for {plan['duration_days']} days.")
        except Exception:
            pass

    @tg_client.on_message(filters.private & filters.command("revoke"))
    async def cmd_revoke(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/revoke telegram_id`")
        free = db.get_plan("free")
        if free:
            db.set_user_plan(int(parts[1]), free["id"], 0)
        await m.reply_text(f"✅ Revoked to Free: `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("ban"))
    async def cmd_ban(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/ban telegram_id`")
        db.ban_user(int(parts[1]))
        await m.reply_text(f"🚫 Banned `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("unban"))
    async def cmd_unban(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split()
        if len(parts) < 2:
            return await m.reply_text("Usage: `/unban telegram_id`")
        db.unban_user(int(parts[1]))
        await m.reply_text(f"✅ Unbanned `{parts[1]}`")

    @tg_client.on_message(filters.private & filters.command("stats"))
    async def cmd_stats(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        stats = db.get_view_stats_global()
        uc = db.count_users()
        pending = 0
        try:
            pending = db.count_pending_requests()
        except Exception:
            pass
        await m.reply_text(
            f"📊 **Global Stats**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Users: {uc}\n"
            f"👁 Views: {stats['total']} total · {stats['today']} today\n"
            f"🌐 Unique IPs: {stats['unique_ips']}\n"
            f"📩 Pending Requests: {pending}",
            reply_markup=_btn([_b("🖥 Admin Panel", url=f"{BASE()}/{AP}")]))

    @tg_client.on_message(filters.private & filters.command("broadcast"))
    async def cmd_broadcast(_c, m: Message):
        if not is_ma(m.from_user.id):
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: `/broadcast Your message`")
        msg = parts[1]
        users = db.list_users(500)
        sent = 0
        for u in users:
            try:
                await tg_client.send_message(u["telegram_id"], f"📢 **Broadcast:**\n\n{msg}")
                sent += 1
            except Exception:
                pass
        await m.reply_text(f"✅ Broadcast sent to {sent}/{len(users)} users.")

    # Channel video auto-save
    @tg_client.on_message(filters.channel & (filters.video | filters.document))
    async def on_channel_video(_c, m: Message):
        media = m.video or (m.document if m.document and (m.document.mime_type or "").startswith("video/") else None)
        if not media:
            return
        try:
            db.save_video({
                "file_id": media.file_id, "file_unique_id": media.file_unique_id,
                "file_size": media.file_size or 0,
                "duration": getattr(media, "duration", 0) or 0,
                "width": getattr(media, "width", 0) or 0,
                "height": getattr(media, "height", 0) or 0,
                "file_name": getattr(media, "file_name", "") or "",
                "mime_type": media.mime_type or "video/mp4",
                "caption": m.caption or "",
                "message_id": m.id, "channel_id": m.chat.id,
                "quality": detect_quality(getattr(media, "width", 0) or 0, getattr(media, "height", 0) or 0)
            })
        except Exception:
            pass

    logger.info("Bot: admin commands registered.")
