"""
Bot upload handler — Smart auto-upload, batch processing, hierarchy creation.
"""
import secrets
import asyncio
import logging

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import metadata as meta
from helpers import slugify, detect_quality

logger = logging.getLogger(__name__)

# Shared state
_pending_videos: dict = {}   # uid -> single pending video info
_pending_batch: dict = {}    # uid -> list of pending video entries
_batch_timers: dict = {}     # uid -> asyncio.Task for batch timer


def get_pending_videos():
    return _pending_videos

def get_pending_batch():
    return _pending_batch


def _btn(*rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) if data else InlineKeyboardButton(text, url=url)
         for text, data, url in row] for row in rows])

def _b(text, data=None, url=None):
    return (text, data, url)


def create_hierarchy(owner_id, title, season=None, episode=None):
    """Auto-create content hierarchy: Title → Season X → Episode Y. Returns (content_id, slug)."""
    root_slug = slugify(title)
    if not root_slug:
        root_slug = f"content-{secrets.token_hex(4)}"
    existing = db.get_content_by_slug(root_slug)
    if existing and existing["owner_id"] == owner_id:
        parent_id = existing["id"]
    else:
        try:
            parent_id = db.create_content(owner_id, title, root_slug)
        except Exception:
            root_slug = f"{root_slug}-{secrets.token_hex(3)}"
            parent_id = db.create_content(owner_id, title, root_slug)
    final_slug = root_slug

    if season is not None:
        s_title = f"Season {season}"
        s_slug = f"{root_slug}-s{season:02d}"
        existing = db.get_content_by_slug(s_slug)
        if existing and existing["owner_id"] == owner_id:
            parent_id = existing["id"]
        else:
            try:
                parent_id = db.create_content(owner_id, s_title, s_slug, parent_id=parent_id)
            except Exception:
                s_slug = f"{s_slug}-{secrets.token_hex(3)}"
                parent_id = db.create_content(owner_id, s_title, s_slug, parent_id=parent_id)
        final_slug = s_slug

    if episode is not None:
        e_title = f"Episode {episode}"
        e_slug = f"{final_slug}-e{episode:02d}" if season is not None else f"{root_slug}-e{episode:02d}"
        existing = db.get_content_by_slug(e_slug)
        if existing and existing["owner_id"] == owner_id:
            parent_id = existing["id"]
        else:
            try:
                parent_id = db.create_content(owner_id, e_title, e_slug, parent_id=parent_id)
            except Exception:
                e_slug = f"{e_slug}-{secrets.token_hex(3)}"
                parent_id = db.create_content(owner_id, e_title, e_slug, parent_id=parent_id)
        final_slug = e_slug

    return parent_id, final_slug


def register(tg_client, ctx):
    """Register video upload handler."""

    async def _process_batch(uid):
        """Process batch after 10s timeout."""
        await asyncio.sleep(10)
        batch = _pending_batch.get(uid, [])
        if not batch:
            return
        if uid in _batch_timers:
            del _batch_timers[uid]

        if len(batch) == 1:
            return

        lines = []
        for i, entry in enumerate(batch):
            m = entry["meta"]
            title = m.get("title") or "Unknown"
            season = m.get("season")
            episode = m.get("episode")
            quality = m.get("quality") or "720p"
            langs = " + ".join(m.get("languages") or ["Hindi"])
            path = title
            if season is not None:
                path += f" / S{season:02d}"
            if episode is not None:
                path += f" / E{episode:02d}"
            lines.append(f"**{i + 1}.** {path}\n   📀 {quality} · 🔊 {langs}")

        summary = "\n".join(lines)
        try:
            await tg_client.send_message(uid,
                f"📦 **Batch Upload — {len(batch)} videos**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n{summary}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Tap below to save all videos at once:",
                reply_markup=_btn(
                    [_b(f"✅ Save All ({len(batch)})", f"batch_save:{uid}")],
                    [_b("✏️ Edit One", f"batch_edit:{uid}"), _b("❌ Cancel All", f"batch_cancel:{uid}")]
                ))
        except Exception as e:
            logger.error(f"Batch summary error: {e}")

    @tg_client.on_message(filters.private & (filters.video | filters.document))
    async def on_video(_c, m: Message):
        media = m.video or (m.document if m.document and (m.document.mime_type or "").startswith("video/") else None)
        if not media:
            return

        uid = m.from_user.id
        user = db.get_user(uid)
        if not user:
            db.create_user(uid, m.from_user.username or "", m.from_user.first_name or "")
            user = db.get_user(uid)

        caption = m.caption or ""
        fname = getattr(media, "file_name", "") or ""
        width = getattr(media, "width", 0) or 0
        height = getattr(media, "height", 0) or 0
        parsed = meta.parse_video_metadata(caption, fname, width, height)

        # Duplicate detection
        try:
            dup = db.check_duplicate_source(media.file_unique_id)
            if dup:
                dup_title = dup.get("title", "Unknown")
                dup_slug = dup.get("slug", "?")
                dup_lang = dup.get("language", "?")
                dup_qual = dup.get("quality", "?")
                await m.reply_text(
                    f"⚠️ **Duplicate Detected!**\n\n"
                    f"This file already exists as:\n"
                    f"📁 **{dup_title}** (`{dup_slug}`)\n"
                    f"🎬 {dup_lang} {dup_qual}\n\n"
                    f"If you want to add it as a new source, use /add `slug` `lang` `quality`.",
                    quote=True)
                return
        except Exception:
            pass  # If check fails, continue normally

        entry = {
            "file_id": media.file_id,
            "file_unique_id": media.file_unique_id,
            "file_size": media.file_size or 0,
            "duration": getattr(media, "duration", 0) or 0,
            "width": width, "height": height,
            "file_name": fname,
            "meta": parsed,
        }

        q = meta.detect_quality_from_resolution(width, height) if (width or height) else "720p"
        try:
            db.save_video({"file_id": media.file_id, "file_unique_id": media.file_unique_id,
                "file_size": media.file_size or 0, "duration": entry["duration"],
                "width": width, "height": height, "file_name": fname,
                "mime_type": media.mime_type or "video/mp4", "caption": caption,
                "message_id": m.id, "channel_id": m.chat.id, "quality": q})
        except Exception:
            pass

        _pending_videos[uid] = entry

        if uid not in _pending_batch:
            _pending_batch[uid] = []
        _pending_batch[uid].append(entry)

        if uid in _batch_timers:
            _batch_timers[uid].cancel()

        card_text = meta.format_metadata_card(parsed, media.file_size or 0, entry["duration"])
        entry_idx = len(_pending_batch[uid]) - 1

        await m.reply_text(
            card_text,
            quote=True,
            reply_markup=_btn(
                [_b("✅ Auto-Save", f"save:{uid}:{entry_idx}"), _b("✏️ Edit", f"edit:{uid}:{entry_idx}")],
                [_b("🔄 Change Lang", f"elang:{uid}:{entry_idx}"), _b("🔄 Change Quality", f"equal:{uid}:{entry_idx}")],
                [_b("📦 Queue", f"qsave:{uid}:{entry_idx}"), _b("❌ Cancel", f"cancel:{uid}:{entry_idx}")]
            ))

        _batch_timers[uid] = asyncio.create_task(_process_batch(uid))

    logger.info("Bot: upload handler registered.")

