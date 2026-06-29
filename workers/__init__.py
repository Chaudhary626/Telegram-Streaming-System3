"""
Background worker system.
Manages async task queue and scheduled jobs.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_tasks = []


def start_workers(app):
    """Start background workers as asyncio tasks."""
    from workers.tasks import worker_loop, scheduler_loop
    
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(worker_loop()))
    _tasks.append(loop.create_task(scheduler_loop()))
    logger.info(f"Workers: {len(_tasks)} background tasks started.")


def stop_workers():
    """Cancel all background worker tasks."""
    for t in _tasks:
        t.cancel()
    _tasks.clear()
    logger.info("Workers: all tasks stopped.")


def get_status():
    """Get worker status."""
    active = sum(1 for t in _tasks if not t.done())
    return {"total": len(_tasks), "active": active, "crashed": len(_tasks) - active}
