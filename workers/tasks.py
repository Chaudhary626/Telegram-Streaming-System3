"""
Background task definitions — upload queue processor and scheduler.
"""
import json
import asyncio
import logging
import secrets

logger = logging.getLogger(__name__)

# Reference to tg_client — set during startup
_tg_client = None


def set_client(client):
    """Set the Pyrogram client reference for sending notifications."""
    global _tg_client
    _tg_client = client


async def worker_loop():
    """Main worker loop — processes upload queue items."""
    from workers.queue import task_queue
    logger.info("Worker: upload processor started.")

    while True:
        try:
            task = task_queue.dequeue()
            if task:
                logger.info(f"Worker: processing task #{task['id']} — {task.get('file_name', '?')}")
                try:
                    result = await _process_upload(task)
                    task_queue.complete(task['id'], json.dumps(result) if result else '')
                    logger.info(f"Worker: task #{task['id']} completed successfully.")
                    # Notify user
                    if _tg_client and task.get('user_id'):
                        try:
                            slug = result.get('slug', '') if result else ''
                            title = result.get('title', task.get('file_name', 'Video')) if result else task.get('file_name', 'Video')
                            await _tg_client.send_message(
                                task['user_id'],
                                f"✅ **Upload Complete!**\n\n"
                                f"📁 {title}\n"
                                f"🏷 Slug: `{slug}`\n\n"
                                f"Your video has been processed and is ready for streaming.")
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Worker: task #{task['id']} failed: {e}")
                    task_queue.fail(task['id'], str(e)[:500])
                    # Notify user of failure
                    if _tg_client and task.get('user_id'):
                        retry_info = f"Retry {task.get('retry_count', 0)+1}/3" if task.get('retry_count', 0) < 2 else "No more retries"
                        try:
                            await _tg_client.send_message(
                                task['user_id'],
                                f"⚠️ **Upload Failed**\n\n"
                                f"📁 {task.get('file_name', 'Video')}\n"
                                f"❌ {str(e)[:200]}\n"
                                f"🔄 {retry_info}")
                        except Exception:
                            pass
            else:
                await asyncio.sleep(3)  # No tasks — wait 3s
        except asyncio.CancelledError:
            logger.info("Worker: upload processor stopped.")
            break
        except Exception as e:
            logger.error(f"Worker: loop error: {e}")
            await asyncio.sleep(5)


async def scheduler_loop():
    """Scheduler for periodic tasks."""
    from workers.queue import task_queue
    from cache import cache
    logger.info("Worker: scheduler started.")
    cycle = 0

    while True:
        try:
            await asyncio.sleep(60)
            cycle += 1

            # Every 5 minutes: cleanup stale queue tasks
            if cycle % 5 == 0:
                stale = task_queue.cleanup_stale()
                if stale:
                    logger.info(f"Scheduler: reset {stale} stale tasks")

            # Every 10 minutes: cleanup expired cache
            if cycle % 10 == 0:
                expired = cache.cleanup_expired()
                if expired:
                    logger.debug(f"Scheduler: cleaned {expired} expired cache entries")

            # Every hour: purge old completed tasks
            if cycle % 60 == 0:
                purged = task_queue.purge_completed(days=7)
                if purged:
                    logger.info(f"Scheduler: purged {purged} old completed queue items")

        except asyncio.CancelledError:
            logger.info("Worker: scheduler stopped.")
            break
        except Exception as e:
            logger.error(f"Scheduler: error: {e}")


async def _process_upload(task):
    """Process a single upload queue item — create content hierarchy and add source."""
    import database as db
    from helpers import slugify

    meta = json.loads(task.get('metadata_json', '{}') or '{}')
    user_id = task['user_id']
    file_id = task['file_id']
    language = task.get('language') or meta.get('language') or 'Hindi'
    quality = task.get('quality') or meta.get('quality') or '720p'
    target_slug = task.get('target_slug', '').strip()

    # Determine title
    title = meta.get('title') or task.get('file_name') or 'Untitled'
    season = meta.get('season')
    episode = meta.get('episode')

    # If target_slug is provided, use existing content
    if target_slug:
        content = db.get_content_by_slug(target_slug)
        if not content:
            raise ValueError(f"Content '{target_slug}' not found")
        if content['owner_id'] != user_id:
            raise ValueError(f"Content '{target_slug}' does not belong to user")
        content_id = content['id']
        slug = target_slug
    else:
        # Auto-create hierarchy
        content_id, slug = _create_hierarchy(user_id, title, season, episode)

    # Add source
    db.add_source(
        content_id, file_id, language, quality,
        task.get('file_unique_id', ''),
        task.get('file_size', 0),
        0,  # duration from metadata
        0, 0  # width, height
    )

    return {
        'content_id': content_id,
        'slug': slug,
        'title': title,
        'language': language,
        'quality': quality
    }


def _create_hierarchy(owner_id, title, season=None, episode=None):
    """Auto-create content hierarchy: Title → Season → Episode. Returns (content_id, slug)."""
    import database as db
    from helpers import slugify

    root_slug = slugify(title)
    if not root_slug:
        root_slug = f"content-{secrets.token_hex(4)}"

    existing = db.get_content_by_slug(root_slug)
    if existing and existing['owner_id'] == owner_id:
        parent_id = existing['id']
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
        if existing and existing['owner_id'] == owner_id:
            parent_id = existing['id']
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
        if existing and existing['owner_id'] == owner_id:
            parent_id = existing['id']
        else:
            try:
                parent_id = db.create_content(owner_id, e_title, e_slug, parent_id=parent_id)
            except Exception:
                e_slug = f"{e_slug}-{secrets.token_hex(3)}"
                parent_id = db.create_content(owner_id, e_title, e_slug, parent_id=parent_id)
        final_slug = e_slug

    return parent_id, final_slug
