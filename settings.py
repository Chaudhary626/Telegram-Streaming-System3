"""
DB-backed global settings with cache layer.

Provides get/set interface for platform configuration.
Settings are stored in tg_settings table and cached in memory.
Admin can edit settings from the admin panel without touching .env files.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Late imports to avoid circular dependency
_db = None
_cache = None


def _get_db():
    global _db
    if _db is None:
        import database as db
        _db = db
    return _db


def _get_cache():
    global _cache
    if _cache is None:
        from cache import cache
        _cache = cache
    return _cache


def _cast(value: str, type_name: str) -> Any:
    """Cast string value to the appropriate Python type."""
    if value is None:
        return None
    if type_name == "boolean":
        return value.lower() in ("true", "1", "yes", "on")
    if type_name == "number":
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return 0
    if type_name == "json":
        import json
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return value  # string


def get(key: str, default: Any = None) -> Any:
    """Get a setting value (cached). Returns default if not found."""
    c = _get_cache()
    cache_key = f"settings:{key}"
    cached = c.get(cache_key)
    if cached is not None:
        return cached

    db = _get_db()
    try:
        row = db.get_setting(key)
        if row is None:
            return default
        val = _cast(row["setting_value"], row.get("setting_type", "string"))
        c.set(cache_key, val, ttl=1800)  # 30-minute cache
        return val
    except Exception as e:
        logger.warning(f"Settings: failed to read '{key}': {e}")
        return default


def set_value(key: str, value: Any):
    """Set a setting value and invalidate cache."""
    db = _get_db()
    c = _get_cache()
    try:
        db.set_setting(key, str(value))
        c.delete(f"settings:{key}")
        logger.info(f"Settings: updated '{key}'")
    except Exception as e:
        logger.error(f"Settings: failed to set '{key}': {e}")


def get_all() -> list:
    """Get all settings as a list of dicts."""
    db = _get_db()
    try:
        return db.get_all_settings()
    except Exception as e:
        logger.warning(f"Settings: failed to load all: {e}")
        return []


def get_by_category() -> dict:
    """Get all settings grouped by category."""
    all_settings = get_all()
    grouped = {}
    for s in all_settings:
        cat = s.get("category", "general")
        grouped.setdefault(cat, []).append(s)
    return grouped


def seed_defaults():
    """Insert default settings if they don't exist."""
    db = _get_db()
    defaults = [
        # General
        ("site_name", "Stream Platform", "string", "general", "Platform display name"),
        ("site_logo_url", "", "string", "general", "Logo URL for branding"),
        ("site_icon_url", "", "string", "general", "Favicon URL"),
        # Appearance
        ("default_theme", "dark", "string", "appearance", "Default theme (dark/light)"),
        ("default_language", "en", "string", "appearance", "Default UI language"),
        # Player
        ("player_branding", "Stream Player", "string", "player", "Player brand name"),
        ("player_footer_text", "Powered by Stream Player", "string", "player", "Player footer text"),
        # Download
        ("download_enabled", "true", "boolean", "download", "Enable download system"),
        ("download_countdown_sec", "30", "number", "download", "Download page countdown seconds"),
        # Upload
        ("upload_max_queue", "50", "number", "upload", "Max items in upload queue"),
        ("upload_max_file_size_gb", "4", "number", "upload", "Max file size in GB"),
        ("batch_wait_seconds", "10", "number", "upload", "Batch upload wait time"),
        # System
        ("maintenance_mode", "false", "boolean", "system", "Enable maintenance mode"),
        ("maintenance_message", "We are performing scheduled maintenance. Please check back soon.", "string", "system", "Maintenance page message"),
        ("maintenance_eta", "", "string", "system", "Estimated maintenance completion time"),
        ("maintenance_whitelist", "", "string", "system", "Comma-separated IPs allowed during maintenance"),
        # Security
        ("rate_limit_per_minute", "60", "number", "security", "API rate limit per IP per minute"),
        ("login_max_attempts", "5", "number", "security", "Max login attempts before lockout"),
        ("session_expiry_hours", "8", "number", "security", "Session cookie expiry in hours"),
        ("admin_2fa_enabled", "false", "boolean", "security", "Enable 2FA for admin login"),
        ("admin_ip_whitelist", "", "string", "security", "Comma-separated admin IP whitelist (empty=all)"),
    ]
    try:
        for key, value, stype, category, desc in defaults:
            db.insert_setting_if_not_exists(key, value, stype, category, desc)
        logger.info(f"Settings: {len(defaults)} defaults verified.")
    except Exception as e:
        logger.warning(f"Settings: seed failed: {e}")
