"""
Stream Server — Multi-Tenant Streaming Platform v3.0

Slim app loader — initializes FastAPI, Pyrogram client, and mounts all modules.
All route handlers and bot commands are in modules/ and bot/ packages.
"""
import urllib.request
import logging
import traceback
from typing import Optional
from html import escape as he

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client

from config import (
    API_ID, API_HASH, BOT_TOKEN,
    STREAM_HOST, STREAM_PORT,
    ALLOWED_ORIGINS, ADMIN_PASSWORD,
    MAIN_ADMIN_TELEGRAM_ID, ADMIN_SECRET_PATH,
    validate as validate_config,
)
from streamer import TelegramStreamer
import database as db
from helpers import hash_password

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("tg-stream")

# ── Pyrogram Client ──────────────────────────────────────────

tg_client = Client(
    name="stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    no_updates=False
)
streamer: Optional[TelegramStreamer] = None

# ── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="AnimeGalaxyHub Stream API",
    description="Telegram-backed video streaming platform API.",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_methods=["GET", "HEAD", "OPTIONS", "POST"],
    allow_headers=["Range", "Content-Type"],
    expose_headers=["Content-Range", "Content-Length", "Accept-Ranges", "Content-Type"]
)

# ── Shared context dict ─────────────────────────────────────
# Passed to all modules so they can access tg_client, streamer, etc.
ctx = {
    "tg_client": tg_client,
    "streamer": None,
}

# ── Global exception handler ────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}\n{traceback.format_exc()}")
    # Log to DB error monitor
    try:
        db.log_error(
            module="server",
            error_type=type(exc).__name__,
            message=str(exc),
            stack_trace=traceback.format_exc()[:2000],
            request_path=str(request.url.path)[:512],
            ip_address=(request.client.host or "")[:45]
        )
    except Exception:
        pass
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Error</title>
<style>body{{background:#0d0d1a;color:#d0d0e8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#141425;border:1px solid #2a2a48;border-radius:16px;padding:40px;max-width:500px;text-align:center}}
h1{{color:#ef4444;font-size:1.3rem}}p{{color:#7777aa;margin-top:12px}}</style></head><body>
<div class="card"><h1>⚠️ Server Error</h1><p>{he(str(exc))}</p><p style="margin-top:16px"><a href="/" style="color:#a78bfa">Home</a></p></div>
</body></html>""", status_code=500)

# ── Root + Health ────────────────────────────────────────────

@app.get("/")
async def root():
    return JSONResponse({"service": "Stream Server", "status": "running", "version": "3.0"})

@app.get("/health")
async def health():
    c = tg_client.is_connected if tg_client else False
    return JSONResponse({
        "status": "ok" if c else "degraded",
        "streaming": "connected" if c else "disconnected",
        "protocol": "direct",
        "max_file": "4GB",
        "version": "3.0"
    })

# ── Block old /admin path ────────────────────────────────────

@app.get("/admin")
@app.get("/admin/{path:path}")
async def block_old_admin(path: str = ""):
    raise HTTPException(404)

# ── Mount all modules ────────────────────────────────────────

from modules import mount_all
mount_all(app, ctx)

# ── Startup / Shutdown ───────────────────────────────────────

@app.on_event("startup")
async def startup():
    global streamer
    errors = validate_config()
    if errors:
        for e in errors:
            logger.error(f"Config: {e}")
        return

    # Delete webhook
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=false",
            timeout=10)
    except Exception:
        pass

    # Register all bot handlers
    from bot import register_all as register_bot
    register_bot(tg_client, ctx)

    # Start Telegram client
    await tg_client.start()
    streamer = TelegramStreamer(tg_client)
    ctx["streamer"] = streamer

    # Database initialization
    try:
        db.ensure_tables()
        db.seed_default_plans()
        if MAIN_ADMIN_TELEGRAM_ID:
            db.create_main_admin(MAIN_ADMIN_TELEGRAM_ID, "", hash_password(ADMIN_PASSWORD))
    except Exception as e:
        logger.warning(f"DB init: {e}")

    # Run migrations
    try:
        from migrations import Migrator
        migrator = Migrator()
        applied = migrator.apply_all()
        if applied:
            logger.info(f"Migrations: applied {len(applied)} migration(s): {', '.join(applied)}")
    except Exception as e:
        logger.warning(f"Migration: {e}")

    # Seed default settings
    try:
        from settings import seed_defaults
        seed_defaults()
    except Exception as e:
        logger.warning(f"Settings seed: {e}")

    # Start background workers
    try:
        from workers.tasks import set_client as set_worker_client
        set_worker_client(tg_client)
        from workers import start_workers
        start_workers(app)
    except Exception as e:
        logger.warning(f"Workers: {e}")

    me = await tg_client.get_me()
    AP = ADMIN_SECRET_PATH
    logger.info(f"Started | Bot: @{me.username} | Admin: /{AP} | Streaming: ON | Port: {STREAM_PORT} | v3.0")


@app.on_event("shutdown")
async def shutdown():
    # Stop workers
    try:
        from workers import stop_workers
        stop_workers()
    except Exception:
        pass
    # Disconnect Telegram
    if tg_client.is_connected:
        await tg_client.stop()
    logger.info("Shutdown complete.")


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=STREAM_HOST, port=STREAM_PORT, log_level="info")
