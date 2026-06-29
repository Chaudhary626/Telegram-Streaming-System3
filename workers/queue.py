"""
DB-backed task queue for background processing.
Delegates to database.py queue_* functions.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

def _get_db():
    global _db
    if _db is None:
        import database as db
        _db = db
    return _db


class TaskQueue:
    """Database-backed async task queue."""

    def enqueue(self, task_type: str, payload: dict, user_id: int = 0, priority: int = 0) -> Optional[int]:
        """Add a task to the queue. Returns queue item ID."""
        db = _get_db()
        try:
            meta = payload.get('metadata', {})
            if isinstance(meta, dict):
                meta = json.dumps(meta)
            return db.queue_add(
                user_id=user_id,
                file_id=payload.get('file_id', ''),
                file_unique_id=payload.get('file_unique_id', ''),
                file_size=payload.get('file_size', 0),
                file_name=payload.get('file_name', ''),
                caption=payload.get('caption', ''),
                metadata_json=meta,
                content_type=payload.get('content_type', 'streaming'),
                target_slug=payload.get('target_slug', ''),
                language=payload.get('language', 'Hindi'),
                quality=payload.get('quality', '720p'),
                priority=priority
            )
        except Exception as e:
            logger.error(f"Queue: enqueue failed: {e}")
            return None

    def dequeue(self, status='pending') -> Optional[dict]:
        db = _get_db()
        try:
            return db.queue_dequeue()
        except Exception as e:
            logger.error(f"Queue: dequeue failed: {e}")
            return None

    def complete(self, task_id: int, result: str = ''):
        db = _get_db()
        try:
            db.queue_complete(task_id, result)
        except Exception as e:
            logger.error(f"Queue: complete failed: {e}")

    def fail(self, task_id: int, error: str, max_retries: int = 3):
        db = _get_db()
        try:
            db.queue_fail(task_id, error, max_retries)
        except Exception as e:
            logger.error(f"Queue: fail update failed: {e}")

    def cancel(self, task_id: int, user_id: int = None) -> int:
        db = _get_db()
        try:
            return db.queue_cancel(task_id, user_id)
        except Exception as e:
            logger.error(f"Queue: cancel failed: {e}")
            return 0

    def retry(self, task_id: int) -> int:
        db = _get_db()
        try:
            return db.queue_retry(task_id)
        except Exception as e:
            logger.error(f"Queue: retry failed: {e}")
            return 0

    def get_user_queue(self, user_id: int, status=None) -> list:
        db = _get_db()
        try:
            return db.queue_list_by_user(user_id, status)
        except Exception:
            return []

    def get_all(self, status=None) -> list:
        db = _get_db()
        try:
            return db.queue_list_all(status)
        except Exception:
            return []

    def get_stats(self) -> dict:
        db = _get_db()
        try:
            return db.queue_stats()
        except Exception:
            return {}

    def get_user_stats(self, user_id: int) -> dict:
        db = _get_db()
        try:
            return db.queue_stats_by_user(user_id)
        except Exception:
            return {}

    def cleanup_stale(self, timeout_minutes: int = 30):
        db = _get_db()
        try:
            return db.queue_cleanup_stale(timeout_minutes)
        except Exception:
            return 0

    def purge_completed(self, days: int = 7):
        db = _get_db()
        try:
            return db.queue_purge_completed(days)
        except Exception:
            return 0


# Global singleton
task_queue = TaskQueue()
