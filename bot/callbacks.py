"""
Bot callback query handler — Handles all inline button callbacks.
"""
import logging

from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from helpers import BASE, AP
from bot.upload_handler import (get_pending_batch, get_pending_videos,
                                create_hierarchy)

logger = logging.getLogger(__name__)


def _btn(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) if data else InlineKeyboardButton(text, url=url)
         for text, data, url in row] for row in rows])

def _b(text, data=None, url=None):
    return (text, data, url)


def register(tg_client, ctx):
    """Register callback query handler."""

    @tg_client.on_callback_query()
    async def on_callback(client, cq: CallbackQuery):
        data = cq.data or ""
        uid = cq.from_user.id
        _pending_batch = get_pending_batch()
        _pending_videos = get_pending_videos()

        # ── Smart Upload: Auto-Save ──────────────────────────
        if data.startswith("save:"):
            parts = data.split(":")
            if len(parts) < 3:
                return await cq.answer("Invalid", show_alert=True)
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx >= len(batch):
                return await cq.answer("Video expired", show_alert=True)
            entry = batch[idx]
            m = entry["meta"]
            title = m.get("title") or "Untitled"
            season = m.get("season")
            episode = m.get("episode")
            quality = m.get("quality") or "720p"
            languages = m.get("languages") or ["Hindi"]
            try:
                content_id, slug = create_hierarchy(uid, title, season, episode)
                for lang in languages:
                    db.add_source(content_id, entry["file_id"], lang, quality,
                        entry.get("file_unique_id", ""), entry.get("file_size", 0),
                        entry.get("duration", 0), entry.get("width", 0), entry.get("height", 0))
                path = title
                if season is not None:
                    path += f" → S{season:02d}"
                if episode is not None:
                    path += f" → E{episode:02d}"
                lang_str = " + ".join(languages)
                multi_warn = ""
                if len(languages) > 1:
                    multi_warn = ("\n\n⚠️ **Note:** This video will play only in its default audio language. "
                                  "The languages listed are reference labels. "
                                  "For actual language switching, upload separate files per language.")
                await cq.message.edit_text(
                    f"✅ **Saved Successfully!**\n\n"
                    f"📂 {path}\n"
                    f"📀 {quality} · 🔊 {lang_str}\n"
                    f"🏷 Slug: `{slug}`{multi_warn}",
                    reply_markup=_btn(
                        [_b("🔗 Get Links", f"links:{slug}"), _b("📁 My Content", "menu:content")]))
            except Exception as e:
                await cq.answer(f"Error: {str(e)[:100]}", show_alert=True)

        # ── Smart Upload: Edit ───────────────────────────────
        elif data.startswith("edit:"):
            parts = data.split(":")
            if len(parts) < 3:
                return await cq.answer("Invalid", show_alert=True)
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx >= len(batch):
                return await cq.answer("Video expired", show_alert=True)
            entry = batch[idx]
            m = entry["meta"]
            await cq.message.edit_text(
                f"✏️ **Edit Video Metadata**\n\n"
                f"Current:\n"
                f"📝 Title: **{m.get('title') or 'Unknown'}**\n"
                f"🎬 Season: **{m.get('season') or '—'}** · Episode: **{m.get('episode') or '—'}**\n"
                f"📀 Quality: **{m.get('quality') or '720p'}**\n"
                f"🔊 Language: **{' + '.join(m.get('languages') or ['Hindi'])}**\n\n"
                f"Choose what to change:",
                reply_markup=_btn(
                    [_b("📝 Set Title", f"set_title:{uid}:{idx}"), _b("🎬 Set Season/Ep", f"set_ep:{uid}:{idx}")],
                    [_b("🔊 Change Lang", f"elang:{uid}:{idx}"), _b("📀 Change Quality", f"equal:{uid}:{idx}")],
                    [_b("✅ Save As-Is", f"save:{uid}:{idx}"), _b("❌ Cancel", f"cancel:{uid}:{idx}")]
                ))

        # ── Change Language ──────────────────────────────────
        elif data.startswith("elang:"):
            parts = data.split(":")
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            common_langs = ["Hindi", "English", "Japanese", "Tamil", "Telugu", "Korean", "Dual Audio"]
            btns = [[_b(lang, f"setlang:{uid}:{idx}:{lang}") for lang in common_langs[i:i + 3]] for i in range(0, len(common_langs), 3)]
            btns.append([_b("← Back", f"edit:{uid}:{idx}")])
            await cq.message.edit_text("🔊 **Select Language:**", reply_markup=_btn(*btns))

        elif data.startswith("setlang:"):
            parts = data.split(":")
            target_uid, idx, lang = int(parts[1]), int(parts[2]), parts[3]
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx < len(batch):
                batch[idx]["meta"]["languages"] = [lang]
            await cq.answer(f"Language set to {lang}")
            entry = batch[idx] if idx < len(batch) else None
            if entry:
                m = entry["meta"]
                await cq.message.edit_text(
                    f"✏️ **Updated!** Language → **{lang}**\n\n"
                    f"📝 {m.get('title') or 'Unknown'} · 📀 {m.get('quality') or '720p'}",
                    reply_markup=_btn(
                        [_b("✅ Save Now", f"save:{uid}:{idx}"), _b("✏️ More Edits", f"edit:{uid}:{idx}")]))

        # ── Change Quality ───────────────────────────────────
        elif data.startswith("equal:"):
            parts = data.split(":")
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            qualities = ["480p", "720p", "1080p", "2160p"]
            btns = [[_b(q, f"setqual:{uid}:{idx}:{q}") for q in qualities]]
            btns.append([_b("← Back", f"edit:{uid}:{idx}")])
            await cq.message.edit_text("📀 **Select Quality:**", reply_markup=_btn(*btns))

        elif data.startswith("setqual:"):
            parts = data.split(":")
            target_uid, idx, qual = int(parts[1]), int(parts[2]), parts[3]
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx < len(batch):
                batch[idx]["meta"]["quality"] = qual
            await cq.answer(f"Quality set to {qual}")
            entry = batch[idx] if idx < len(batch) else None
            if entry:
                m = entry["meta"]
                await cq.message.edit_text(
                    f"✏️ **Updated!** Quality → **{qual}**\n\n"
                    f"📝 {m.get('title') or 'Unknown'} · 🔊 {' + '.join(m.get('languages') or ['Hindi'])}",
                    reply_markup=_btn(
                        [_b("✅ Save Now", f"save:{uid}:{idx}"), _b("✏️ More Edits", f"edit:{uid}:{idx}")]))

        elif data.startswith("set_title:"):
            await cq.answer("Send the title as a text message.\nFormat: Title or Title/Season 1/Episode 1", show_alert=True)

        elif data.startswith("set_ep:"):
            await cq.answer("Send season/episode as: S01E04\nOr use /new Title/Season 1/Episode 4", show_alert=True)

        # ── Cancel ───────────────────────────────────────────
        elif data.startswith("cancel:"):
            parts = data.split(":")
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx < len(batch):
                batch[idx] = None
            await cq.message.edit_text("❌ **Cancelled.**\n\nSend another video anytime.")

        # ── Batch Save All ───────────────────────────────────
        elif data.startswith("batch_save:"):
            target_uid = int(data.split(":")[1])
            if uid != target_uid:
                return await cq.answer("Not your batch", show_alert=True)
            batch = _pending_batch.get(uid, [])
            saved = 0
            errors = 0
            for entry in batch:
                if entry is None:
                    continue
                m = entry["meta"]
                title = m.get("title") or "Untitled"
                try:
                    content_id, slug = create_hierarchy(uid, title, m.get("season"), m.get("episode"))
                    for lang in (m.get("languages") or ["Hindi"]):
                        db.add_source(content_id, entry["file_id"], lang, m.get("quality", "720p"),
                            entry.get("file_unique_id", ""), entry.get("file_size", 0),
                            entry.get("duration", 0), entry.get("width", 0), entry.get("height", 0))
                    saved += 1
                except Exception:
                    errors += 1
            _pending_batch.pop(uid, None)
            _pending_videos.pop(uid, None)
            err_note = f"\n⚠️ {errors} failed" if errors else ""
            await cq.message.edit_text(
                f"✅ **Batch Complete!**\n\n"
                f"📦 {saved} videos saved{err_note}\n\n"
                f"All content has been organized automatically.",
                reply_markup=_btn([_b("📁 My Content", "menu:content"), _b("🖥 Panel", url=f"{BASE()}/panel/content")]))

        # ── Batch Cancel All ─────────────────────────────────
        elif data.startswith("batch_cancel:"):
            target_uid = int(data.split(":")[1])
            if uid != target_uid:
                return await cq.answer("Not your batch", show_alert=True)
            _pending_batch.pop(uid, None)
            _pending_videos.pop(uid, None)
            await cq.message.edit_text("❌ **Batch cancelled.** All pending videos removed.")

        elif data.startswith("batch_edit:"):
            target_uid = int(data.split(":")[1])
            if uid != target_uid:
                return await cq.answer("Not your batch", show_alert=True)
            await cq.answer("Edit each video individually using the Edit button on each message.", show_alert=True)

        # ── Menu Callbacks ───────────────────────────────────
        elif data == "menu:content":
            items = db.list_content_by_owner(uid, 10)
            if not items:
                await cq.answer("No content yet. Send a video!", show_alert=True)
                return
            lines = "\n".join(f"📁 **{c['title']}** (`{c['slug']}`) — {c.get('source_count', 0)} src" for c in items)
            await cq.message.edit_text(f"📁 **My Content:**\n\n{lines}",
                reply_markup=_btn([_b("📹 Upload Video", "menu:upload_help"), _b("🖥 Panel", url=f"{BASE()}/panel/content")]))

        elif data == "menu:plans":
            plans = db.list_plans()
            lines = "\n".join(f"{'🆓' if p['slug'] == 'free' else '💎'} **{p['name']}** — ₹{p['price']} | {p['max_content']} content | {p['duration_days']}d" for p in plans)
            await cq.message.edit_text(f"💳 **Plans:**\n\n{lines}\n\nUse /subscribe for details.",
                reply_markup=_btn([_b("💳 Subscribe", "menu:subscribe_detail")]))

        elif data == "menu:subscribe_detail":
            await cq.answer("Use /subscribe command", show_alert=True)

        elif data == "menu:status":
            c = tg_client.is_connected
            cc = db.count_content_by_owner(uid)
            await cq.answer(f"Streaming: {'ON' if c else 'OFF'} | Content: {cc}", show_alert=True)

        elif data == "menu:upload_help":
            await cq.answer(
                "Just send a video!\n"
                "Add caption with Title/Season/Episode.\n"
                "Bot auto-detects everything.", show_alert=True)

        elif data == "menu:new_help":
            await cq.answer("Use: /new Title or /new Title/Season/Episode", show_alert=True)

        elif data == "menu:trial":
            await cq.answer("Use /trial command", show_alert=True)

        elif data.startswith("links:"):
            slug = data[6:]
            content = db.get_content_by_slug(slug)
            if not content:
                return await cq.answer("Not found", show_alert=True)
            base = BASE()
            await cq.message.edit_text(
                f"🔗 **{content['title']}**\n\n▶️ `{base}/watch/{slug}`",
                reply_markup=_btn([_b("▶️ Watch", url=f"{base}/watch/{slug}"), _b("🖥 Panel", url=f"{base}/panel/login")]))

        elif data.startswith("buy:"):
            plan_slug = data[4:]
            base = BASE()
            await cq.message.edit_text(
                f"💳 **Purchase Plan**\n\nComplete payment on the panel:",
                reply_markup=_btn([_b("💰 Pay Now", url=f"{base}/panel/subscription/pay/{plan_slug}"), _b("← Back", "menu:plans")]))

        # ── Queue Operations ─────────────────────────────────
        elif data.startswith("qsave:"):
            # Queue-save: add video to upload queue instead of instant save
            parts = data.split(":")
            if len(parts) < 3:
                return await cq.answer("Invalid", show_alert=True)
            target_uid, idx = int(parts[1]), int(parts[2])
            if uid != target_uid:
                return await cq.answer("Not your video", show_alert=True)
            batch = _pending_batch.get(uid, [])
            if idx >= len(batch):
                return await cq.answer("Video expired", show_alert=True)
            entry = batch[idx]
            m = entry["meta"]
            import json as _json
            try:
                task_id = db.queue_add(
                    user_id=uid,
                    file_id=entry["file_id"],
                    file_unique_id=entry.get("file_unique_id", ""),
                    file_size=entry.get("file_size", 0),
                    file_name=entry.get("file_name", ""),
                    caption="",
                    metadata_json=_json.dumps(m),
                    content_type="streaming",
                    language=(m.get("languages") or ["Hindi"])[0],
                    quality=m.get("quality") or "720p",
                    priority=0
                )
                title = m.get("title") or "Video"
                await cq.message.edit_text(
                    f"📦 **Added to Queue!**\n\n"
                    f"📁 {title}\n"
                    f"🆔 Queue ID: `#{task_id}`\n\n"
                    f"Your video will be processed automatically.\n"
                    f"Use /queue to check status.",
                    reply_markup=_btn([_b("📦 My Queue", "menu:queue"), _b("📁 Content", "menu:content")]))
            except Exception as e:
                await cq.answer(f"Queue error: {str(e)[:100]}", show_alert=True)

        elif data == "queue:retry_all":
            try:
                items = db.queue_list_by_user(uid, status="failed", limit=50)
                retried = 0
                for item in items:
                    if db.queue_retry(item["id"]):
                        retried += 1
                await cq.answer(f"🔄 Retrying {retried} failed upload(s)", show_alert=True)
            except Exception as e:
                await cq.answer(f"Error: {str(e)[:100]}", show_alert=True)

        elif data == "queue:cancel_all":
            try:
                items = db.queue_list_by_user(uid, status="pending", limit=100)
                cancelled = 0
                for item in items:
                    if db.queue_cancel(item["id"], uid):
                        cancelled += 1
                await cq.answer(f"❌ Cancelled {cancelled} pending upload(s)", show_alert=True)
            except Exception as e:
                await cq.answer(f"Error: {str(e)[:100]}", show_alert=True)

        elif data == "menu:queue":
            try:
                stats = db.queue_stats_by_user(uid)
            except Exception:
                stats = {}
            pending = stats.get("pending", 0)
            processing = stats.get("processing", 0)
            completed = stats.get("completed", 0)
            failed = stats.get("failed", 0)
            await cq.message.edit_text(
                f"📦 **Upload Queue**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ Pending: **{pending}**\n"
                f"⚙️ Processing: **{processing}**\n"
                f"✅ Completed: **{completed}**\n"
                f"❌ Failed: **{failed}**\n\n"
                f"Use /queue for full details.",
                reply_markup=_btn([_b("📁 My Content", "menu:content")]))

        else:
            await cq.answer("Unknown action", show_alert=True)

    logger.info("Bot: callback handler registered.")

