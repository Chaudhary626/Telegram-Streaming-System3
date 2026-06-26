"""
Database operations for TG Stream Server (Multi-Tenant).
12 tables, full CRUD with data isolation.
"""
import secrets
import pymysql
import logging
from contextlib import contextmanager
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS

logger = logging.getLogger(__name__)

@contextmanager
def get_connection():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True, connect_timeout=10, read_timeout=30)
    try:
        yield conn
    finally:
        conn.close()

# ══════════════════════════════════════════════════════════════
# TABLE CREATION
# ══════════════════════════════════════════════════════════════

def ensure_tables():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS tg_main_admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL UNIQUE,
                username VARCHAR(100) DEFAULT '',
                display_name VARCHAR(100) DEFAULT '',
                password_hash VARCHAR(255) NOT NULL DEFAULT '',
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL UNIQUE,
                username VARCHAR(100) DEFAULT '',
                display_name VARCHAR(100) DEFAULT '',
                password_hash VARCHAR(255) DEFAULT '',
                plan_id INT DEFAULT NULL,
                plan_expires DATETIME DEFAULT NULL,
                is_active TINYINT(1) DEFAULT 1,
                can_view_all TINYINT(1) DEFAULT 0,
                max_content INT DEFAULT 5,
                max_views_day INT DEFAULT 1000,
                api_key VARCHAR(64) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_tg (telegram_id),
                INDEX idx_api (api_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_plans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                slug VARCHAR(50) NOT NULL UNIQUE,
                price DECIMAL(10,2) DEFAULT 0,
                max_content INT DEFAULT 5,
                max_views_day INT DEFAULT 1000,
                max_sources INT DEFAULT 3,
                can_ads TINYINT(1) DEFAULT 0,
                can_view_all TINYINT(1) DEFAULT 0,
                duration_days INT DEFAULT 30,
                is_trial TINYINT(1) DEFAULT 0,
                is_active TINYINT(1) DEFAULT 1,
                features TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_channels (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                channel_id BIGINT NOT NULL,
                category VARCHAR(50) DEFAULT 'general',
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_cat (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                title VARCHAR(255) NOT NULL,
                slug VARCHAR(255) NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                thumbnail VARCHAR(512) DEFAULT '',
                category VARCHAR(50) DEFAULT 'general',
                channel_id INT DEFAULT NULL,
                embed_token VARCHAR(64) DEFAULT NULL,
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_owner (owner_id),
                INDEX idx_slug (slug),
                INDEX idx_token (embed_token)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_sources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id INT NOT NULL,
                file_id VARCHAR(512) NOT NULL,
                file_unique_id VARCHAR(128) DEFAULT '',
                file_size BIGINT DEFAULT 0,
                duration INT DEFAULT 0,
                width INT DEFAULT 0, height INT DEFAULT 0,
                language VARCHAR(50) NOT NULL DEFAULT 'Hindi',
                quality VARCHAR(20) NOT NULL DEFAULT '720p',
                label VARCHAR(100) DEFAULT '',
                channel_id INT DEFAULT NULL,
                message_id INT DEFAULT 0,
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_content (content_id),
                UNIQUE KEY uq_source (content_id, language, quality)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_ads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                name VARCHAR(100) NOT NULL,
                ad_type VARCHAR(20) DEFAULT 'custom',
                ad_url VARCHAR(512) DEFAULT '',
                ad_html TEXT DEFAULT '',
                position VARCHAR(10) DEFAULT 'pre',
                duration INT DEFAULT 5,
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_owner (owner_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_view_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id INT DEFAULT NULL,
                source_id INT DEFAULT NULL,
                owner_id BIGINT DEFAULT 0,
                ip_hash VARCHAR(64) DEFAULT '',
                user_agent VARCHAR(255) DEFAULT '',
                referer VARCHAR(512) DEFAULT '',
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_content (content_id),
                INDEX idx_owner (owner_id),
                INDEX idx_date (viewed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT DEFAULT 0,
                action VARCHAR(50) NOT NULL,
                details TEXT DEFAULT '',
                ip_address VARCHAR(45) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_videos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id VARCHAR(512) NOT NULL,
                file_unique_id VARCHAR(128) NOT NULL,
                file_size BIGINT DEFAULT 0,
                duration INT DEFAULT 0, width INT DEFAULT 0, height INT DEFAULT 0,
                file_name VARCHAR(512) DEFAULT '',
                mime_type VARCHAR(64) DEFAULT 'video/mp4',
                caption TEXT, message_id INT DEFAULT 0,
                channel_id BIGINT DEFAULT 0,
                quality VARCHAR(20) DEFAULT '720p',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_file_id (file_id(100)),
                INDEX idx_unique_id (file_unique_id(100))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_payment_methods (
                id INT AUTO_INCREMENT PRIMARY KEY,
                method_type VARCHAR(30) NOT NULL DEFAULT 'upi',
                title VARCHAR(100) NOT NULL DEFAULT '',
                details TEXT DEFAULT '',
                qr_image_url VARCHAR(512) DEFAULT '',
                is_active TINYINT(1) DEFAULT 1,
                sort_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_payment_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                plan_id INT NOT NULL,
                amount DECIMAL(10,2) DEFAULT 0,
                method_type VARCHAR(30) DEFAULT '',
                transaction_id VARCHAR(200) DEFAULT '',
                screenshot_file_id VARCHAR(512) DEFAULT '',
                notes TEXT DEFAULT '',
                status VARCHAR(20) DEFAULT 'pending',
                admin_notes TEXT DEFAULT '',
                reviewed_by BIGINT DEFAULT NULL,
                reviewed_at DATETIME DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id),
                INDEX idx_status (status),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    logger.info("All database tables created/verified.")
    _migrate_columns()


def _safe_add_column(cursor, table, column, definition):
    """Add column if it doesn't exist. Silently ignores if column already exists."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logger.info(f"Migration: Added {table}.{column}")
    except Exception as e:
        if "Duplicate column" in str(e) or "1060" in str(e):
            pass  # Column already exists — OK
        else:
            logger.warning(f"Migration skip {table}.{column}: {e}")


def _safe_add_index(cursor, table, index_name, columns):
    """Add index if it doesn't exist."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD INDEX {index_name} ({columns})")
    except:
        pass  # Index already exists


def _migrate_columns():
    """Auto-migrate: add any columns that might be missing from old DB versions."""
    with get_connection() as conn:
        with conn.cursor() as c:
            # ── tg_content: ensure all columns exist ──
            _safe_add_column(c, "tg_content", "owner_id", "BIGINT NOT NULL DEFAULT 0")
            _safe_add_column(c, "tg_content", "title", "VARCHAR(255) NOT NULL DEFAULT ''")
            _safe_add_column(c, "tg_content", "slug", "VARCHAR(255) NOT NULL DEFAULT ''")
            _safe_add_column(c, "tg_content", "description", "TEXT DEFAULT ''")
            _safe_add_column(c, "tg_content", "thumbnail", "VARCHAR(512) DEFAULT ''")
            _safe_add_column(c, "tg_content", "category", "VARCHAR(50) DEFAULT 'general'")
            _safe_add_column(c, "tg_content", "channel_id", "INT DEFAULT NULL")
            _safe_add_column(c, "tg_content", "embed_token", "VARCHAR(64) DEFAULT NULL")
            _safe_add_column(c, "tg_content", "is_active", "TINYINT(1) DEFAULT 1")
            _safe_add_index(c, "tg_content", "idx_owner", "owner_id")
            _safe_add_index(c, "tg_content", "idx_token", "embed_token")

            # ── tg_users: ensure all columns exist ──
            _safe_add_column(c, "tg_users", "plan_id", "INT DEFAULT NULL")
            _safe_add_column(c, "tg_users", "plan_expires", "DATETIME DEFAULT NULL")
            _safe_add_column(c, "tg_users", "is_active", "TINYINT(1) DEFAULT 1")
            _safe_add_column(c, "tg_users", "can_view_all", "TINYINT(1) DEFAULT 0")
            _safe_add_column(c, "tg_users", "max_content", "INT DEFAULT 5")
            _safe_add_column(c, "tg_users", "max_views_day", "INT DEFAULT 1000")
            _safe_add_column(c, "tg_users", "api_key", "VARCHAR(64) DEFAULT NULL")
            _safe_add_column(c, "tg_users", "password_hash", "VARCHAR(255) DEFAULT ''")
            _safe_add_column(c, "tg_users", "display_name", "VARCHAR(100) DEFAULT ''")

            # ── tg_plans: ensure all columns exist ──
            _safe_add_column(c, "tg_plans", "max_sources", "INT DEFAULT 3")
            _safe_add_column(c, "tg_plans", "can_ads", "TINYINT(1) DEFAULT 0")
            _safe_add_column(c, "tg_plans", "can_view_all", "TINYINT(1) DEFAULT 0")
            _safe_add_column(c, "tg_plans", "duration_days", "INT DEFAULT 30")
            _safe_add_column(c, "tg_plans", "is_trial", "TINYINT(1) DEFAULT 0")
            _safe_add_column(c, "tg_plans", "is_active", "TINYINT(1) DEFAULT 1")
            _safe_add_column(c, "tg_plans", "features", "TEXT DEFAULT '{}'")

            # ── tg_sources: ensure all columns exist ──
            _safe_add_column(c, "tg_sources", "file_unique_id", "VARCHAR(128) DEFAULT ''")
            _safe_add_column(c, "tg_sources", "file_size", "BIGINT DEFAULT 0")
            _safe_add_column(c, "tg_sources", "duration", "INT DEFAULT 0")
            _safe_add_column(c, "tg_sources", "width", "INT DEFAULT 0")
            _safe_add_column(c, "tg_sources", "height", "INT DEFAULT 0")
            _safe_add_column(c, "tg_sources", "label", "VARCHAR(100) DEFAULT ''")
            _safe_add_column(c, "tg_sources", "channel_id", "INT DEFAULT NULL")
            _safe_add_column(c, "tg_sources", "message_id", "INT DEFAULT 0")
            _safe_add_column(c, "tg_sources", "is_active", "TINYINT(1) DEFAULT 1")

            # ── tg_ads: ensure all columns exist ──
            _safe_add_column(c, "tg_ads", "owner_id", "BIGINT NOT NULL DEFAULT 0")
            _safe_add_column(c, "tg_ads", "ad_type", "VARCHAR(20) DEFAULT 'custom'")
            _safe_add_column(c, "tg_ads", "ad_url", "VARCHAR(512) DEFAULT ''")
            _safe_add_column(c, "tg_ads", "ad_html", "TEXT DEFAULT ''")
            _safe_add_column(c, "tg_ads", "position", "VARCHAR(10) DEFAULT 'pre'")
            _safe_add_column(c, "tg_ads", "duration", "INT DEFAULT 5")
            _safe_add_column(c, "tg_ads", "is_active", "TINYINT(1) DEFAULT 1")

            # ── tg_view_logs: ensure all columns exist ──
            _safe_add_column(c, "tg_view_logs", "owner_id", "BIGINT DEFAULT 0")
            _safe_add_column(c, "tg_view_logs", "content_id", "INT DEFAULT NULL")
            _safe_add_column(c, "tg_view_logs", "source_id", "INT DEFAULT NULL")
            _safe_add_column(c, "tg_view_logs", "ip_hash", "VARCHAR(64) DEFAULT ''")
            _safe_add_column(c, "tg_view_logs", "user_agent", "VARCHAR(255) DEFAULT ''")
            _safe_add_column(c, "tg_view_logs", "referer", "VARCHAR(512) DEFAULT ''")
            _safe_add_index(c, "tg_view_logs", "idx_owner", "owner_id")

            # ── tg_channels: ensure all columns exist ──
            _safe_add_column(c, "tg_channels", "category", "VARCHAR(50) DEFAULT 'general'")
            _safe_add_column(c, "tg_channels", "is_active", "TINYINT(1) DEFAULT 1")

            # ── tg_main_admins: ensure columns ──
            _safe_add_column(c, "tg_main_admins", "password_hash", "VARCHAR(255) NOT NULL DEFAULT ''")
            _safe_add_column(c, "tg_main_admins", "is_active", "TINYINT(1) DEFAULT 1")

            # ── tg_content: parent_id for hierarchy ──
            _safe_add_column(c, "tg_content", "parent_id", "INT DEFAULT NULL")
            _safe_add_index(c, "tg_content", "idx_parent", "parent_id")

    logger.info("Database migration complete — all columns verified.")


def seed_default_plans():
    """Insert default plans if they don't exist."""
    plans = [
        ("Free", "free", 0, 5, 1000, 3, 0, 0, 0, 0),
        ("Trial", "trial", 0, 20, 5000, 6, 1, 0, 7, 1),
        ("Basic", "basic", 299, 50, 25000, 9, 1, 0, 30, 0),
        ("Pro", "pro", 799, 999999, 999999, 999999, 1, 1, 30, 0),
    ]
    with get_connection() as conn:
        with conn.cursor() as c:
            for p in plans:
                c.execute(
                    "INSERT IGNORE INTO tg_plans "
                    "(name,slug,price,max_content,max_views_day,max_sources,can_ads,can_view_all,duration_days,is_trial) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", p)
    logger.info("Default plans seeded.")


# ══════════════════════════════════════════════════════════════
# MAIN ADMIN
# ══════════════════════════════════════════════════════════════

def create_main_admin(telegram_id, username="", password_hash=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT IGNORE INTO tg_main_admins (telegram_id,username,password_hash) VALUES (%s,%s,%s)",
                      (telegram_id, username, password_hash))
            return c.lastrowid

def get_main_admin(telegram_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_main_admins WHERE telegram_id=%s LIMIT 1", (telegram_id,))
            return c.fetchone()

def is_main_admin(telegram_id):
    return get_main_admin(telegram_id) is not None


# ══════════════════════════════════════════════════════════════
# USERS (Sub-Admins)
# ══════════════════════════════════════════════════════════════

def create_user(telegram_id, username="", display_name=""):
    api_key = secrets.token_hex(32)
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT IGNORE INTO tg_users (telegram_id,username,display_name,api_key) VALUES (%s,%s,%s,%s)",
                      (telegram_id, username, display_name, api_key))
            return c.lastrowid

def get_user(telegram_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT u.*, p.name AS plan_name, p.slug AS plan_slug FROM tg_users u "
                      "LEFT JOIN tg_plans p ON p.id=u.plan_id WHERE u.telegram_id=%s LIMIT 1", (telegram_id,))
            return c.fetchone()

def get_user_by_id(user_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT u.*, p.name AS plan_name FROM tg_users u "
                      "LEFT JOIN tg_plans p ON p.id=u.plan_id WHERE u.id=%s LIMIT 1", (user_id,))
            return c.fetchone()

def list_users(limit=100):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT u.*, p.name AS plan_name, "
                      "(SELECT COUNT(*) FROM tg_content WHERE owner_id=u.telegram_id) AS content_count "
                      "FROM tg_users u LEFT JOIN tg_plans p ON p.id=u.plan_id "
                      "ORDER BY u.created_at DESC LIMIT %s", (limit,))
            return c.fetchall()

def update_user(telegram_id, **kwargs):
    allowed = {"username","display_name","password_hash","plan_id","plan_expires",
               "is_active","can_view_all","max_content","max_views_day","api_key"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields: return
    s = ", ".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [telegram_id]
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(f"UPDATE tg_users SET {s} WHERE telegram_id=%s", vals)

def ban_user(telegram_id):
    update_user(telegram_id, is_active=0)

def unban_user(telegram_id):
    update_user(telegram_id, is_active=1)

def set_user_plan(telegram_id, plan_id, duration_days):
    with get_connection() as conn:
        with conn.cursor() as c:
            plan = get_plan_by_id(plan_id)
            if not plan: return
            if duration_days > 0:
                c.execute("UPDATE tg_users SET plan_id=%s, plan_expires=DATE_ADD(NOW(),INTERVAL %s DAY), "
                          "max_content=%s, max_views_day=%s, can_view_all=%s WHERE telegram_id=%s",
                          (plan_id, duration_days, plan["max_content"], plan["max_views_day"],
                           plan.get("can_view_all", 0), telegram_id))
            else:
                c.execute("UPDATE tg_users SET plan_id=%s, plan_expires=NULL, "
                          "max_content=%s, max_views_day=%s WHERE telegram_id=%s",
                          (plan_id, plan["max_content"], plan["max_views_day"], telegram_id))

def count_users():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_users")
            return c.fetchone()["cnt"]


# ══════════════════════════════════════════════════════════════
# PLANS
# ══════════════════════════════════════════════════════════════

def get_plan(slug):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_plans WHERE slug=%s LIMIT 1", (slug,))
            return c.fetchone()

def get_plan_by_id(plan_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_plans WHERE id=%s LIMIT 1", (plan_id,))
            return c.fetchone()

def list_plans():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_plans WHERE is_active=1 ORDER BY price")
            return c.fetchall()

def create_plan(name, slug, price=0, max_content=5, max_views_day=1000,
                max_sources=3, can_ads=0, duration_days=30, is_trial=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_plans (name,slug,price,max_content,max_views_day,"
                      "max_sources,can_ads,duration_days,is_trial) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (name, slug, price, max_content, max_views_day, max_sources, can_ads, duration_days, is_trial))
            return c.lastrowid

def delete_plan(plan_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_plans WHERE id=%s", (plan_id,))


# ══════════════════════════════════════════════════════════════
# CHANNELS
# ══════════════════════════════════════════════════════════════

def create_channel(name, channel_id, category="general"):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_channels (name,channel_id,category) VALUES (%s,%s,%s)",
                      (name, channel_id, category))
            return c.lastrowid

def get_channel_by_id(ch_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_channels WHERE id=%s LIMIT 1", (ch_id,))
            return c.fetchone()

def get_channel_by_name(name):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_channels WHERE name=%s LIMIT 1", (name,))
            return c.fetchone()

def list_channels():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_channels WHERE is_active=1 ORDER BY name")
            return c.fetchall()

def delete_channel(ch_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_channels WHERE id=%s", (ch_id,))


# ══════════════════════════════════════════════════════════════
# CONTENT (DATA ISOLATION via owner_id)
# ══════════════════════════════════════════════════════════════

def create_content(owner_id, title, slug, category="general", channel_id=None, parent_id=None):
    token = secrets.token_hex(16)
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_content (owner_id,title,slug,category,channel_id,embed_token,parent_id) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s)", (owner_id, title, slug, category, channel_id, token, parent_id))
            return c.lastrowid

def get_content_by_slug(slug):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_content WHERE slug=%s AND is_active=1 LIMIT 1", (slug,))
            return c.fetchone()

def get_content_by_id(content_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_content WHERE id=%s LIMIT 1", (content_id,))
            return c.fetchone()

def get_content_by_token(embed_token):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_content WHERE embed_token=%s AND is_active=1 LIMIT 1", (embed_token,))
            return c.fetchone()

def list_content_by_owner(owner_id, limit=100):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT c.*, COUNT(s.id) AS source_count FROM tg_content c "
                      "LEFT JOIN tg_sources s ON s.content_id=c.id AND s.is_active=1 "
                      "WHERE c.owner_id=%s GROUP BY c.id ORDER BY c.created_at DESC LIMIT %s",
                      (owner_id, limit))
            return c.fetchall()

def list_all_content(limit=100):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT c.*, COUNT(s.id) AS source_count, u.username AS owner_name "
                      "FROM tg_content c LEFT JOIN tg_sources s ON s.content_id=c.id AND s.is_active=1 "
                      "LEFT JOIN tg_users u ON u.telegram_id=c.owner_id "
                      "GROUP BY c.id ORDER BY c.created_at DESC LIMIT %s", (limit,))
            return c.fetchall()

def delete_content(content_id, owner_id=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if owner_id:
                c.execute("DELETE FROM tg_sources WHERE content_id=%s AND content_id IN "
                          "(SELECT id FROM tg_content WHERE id=%s AND owner_id=%s)",
                          (content_id, content_id, owner_id))
                c.execute("DELETE FROM tg_content WHERE id=%s AND owner_id=%s", (content_id, owner_id))
            else:
                c.execute("DELETE FROM tg_sources WHERE content_id=%s", (content_id,))
                c.execute("DELETE FROM tg_content WHERE id=%s", (content_id,))

def count_content_by_owner(owner_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_content WHERE owner_id=%s", (owner_id,))
            return c.fetchone()["cnt"]

def update_content(content_id, **kwargs):
    allowed = {"title","slug","description","thumbnail","category","is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields: return
    s = ", ".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [content_id]
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(f"UPDATE tg_content SET {s} WHERE id=%s", vals)


# ══════════════════════════════════════════════════════════════
# SOURCES
# ══════════════════════════════════════════════════════════════

def add_source(content_id, file_id, language, quality, file_unique_id="",
               file_size=0, duration=0, width=0, height=0, label="",
               channel_id=None, message_id=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_sources (content_id,file_id,file_unique_id,file_size,"
                      "duration,width,height,language,quality,label,channel_id,message_id) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                      "ON DUPLICATE KEY UPDATE file_id=VALUES(file_id),file_size=VALUES(file_size),"
                      "duration=VALUES(duration),width=VALUES(width),height=VALUES(height)",
                      (content_id, file_id, file_unique_id, file_size, duration, width, height,
                       language, quality, label, channel_id, message_id))
            return c.lastrowid

def get_sources_by_content(content_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_sources WHERE content_id=%s AND is_active=1 "
                      "ORDER BY language, FIELD(quality,'2160p','1080p','720p','480p','360p')",
                      (content_id,))
            return c.fetchall()

def get_source_by_id(source_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_sources WHERE id=%s LIMIT 1", (source_id,))
            return c.fetchone()

def delete_source(source_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_sources WHERE id=%s", (source_id,))

def count_sources_by_content(content_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_sources WHERE content_id=%s AND is_active=1", (content_id,))
            return c.fetchone()["cnt"]


# ══════════════════════════════════════════════════════════════
# ADS (per-user isolation)
# ══════════════════════════════════════════════════════════════

def create_ad(owner_id, name, ad_type="custom", ad_url="", ad_html="", position="pre", duration=5):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_ads (owner_id,name,ad_type,ad_url,ad_html,position,duration) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (owner_id, name, ad_type, ad_url, ad_html, position, duration))
            return c.lastrowid

def get_ads_by_owner(owner_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_ads WHERE owner_id=%s ORDER BY position,id", (owner_id,))
            return c.fetchall()

def get_active_ads_by_owner(owner_id, position=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if position:
                c.execute("SELECT * FROM tg_ads WHERE owner_id=%s AND is_active=1 AND position=%s",
                          (owner_id, position))
            else:
                c.execute("SELECT * FROM tg_ads WHERE owner_id=%s AND is_active=1 ORDER BY position,id",
                          (owner_id,))
            return c.fetchall()

def delete_ad(ad_id, owner_id=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if owner_id:
                c.execute("DELETE FROM tg_ads WHERE id=%s AND owner_id=%s", (ad_id, owner_id))
            else:
                c.execute("DELETE FROM tg_ads WHERE id=%s", (ad_id,))

def toggle_ad(ad_id, owner_id=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if owner_id:
                c.execute("UPDATE tg_ads SET is_active=1-is_active WHERE id=%s AND owner_id=%s", (ad_id, owner_id))
            else:
                c.execute("UPDATE tg_ads SET is_active=1-is_active WHERE id=%s", (ad_id,))

def list_all_ads():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT a.*, u.username AS owner_name FROM tg_ads a "
                      "LEFT JOIN tg_users u ON u.telegram_id=a.owner_id ORDER BY a.id")
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# VIEW LOGS
# ══════════════════════════════════════════════════════════════

def log_view(content_id=None, source_id=None, owner_id=0, ip_hash="", user_agent="", referer=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_view_logs (content_id,source_id,owner_id,ip_hash,user_agent,referer) "
                      "VALUES (%s,%s,%s,%s,%s,%s)",
                      (content_id, source_id, owner_id, ip_hash, user_agent[:255], referer[:512]))

def get_view_stats_global():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS total FROM tg_view_logs")
            total = c.fetchone()["total"]
            c.execute("SELECT COUNT(*) AS today FROM tg_view_logs WHERE DATE(viewed_at)=CURDATE()")
            today = c.fetchone()["today"]
            c.execute("SELECT COUNT(DISTINCT ip_hash) AS unique_ips FROM tg_view_logs")
            unique = c.fetchone()["unique_ips"]
            return {"total": total, "today": today, "unique_ips": unique}

def get_view_stats_by_owner(owner_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS total FROM tg_view_logs WHERE owner_id=%s", (owner_id,))
            total = c.fetchone()["total"]
            c.execute("SELECT COUNT(*) AS today FROM tg_view_logs WHERE owner_id=%s AND DATE(viewed_at)=CURDATE()", (owner_id,))
            today = c.fetchone()["today"]
            c.execute("SELECT COUNT(DISTINCT ip_hash) AS unique_ips FROM tg_view_logs WHERE owner_id=%s", (owner_id,))
            unique = c.fetchone()["unique_ips"]
            return {"total": total, "today": today, "unique_ips": unique}

def get_recent_logs(limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT l.*, c.title AS content_title FROM tg_view_logs l "
                      "LEFT JOIN tg_content c ON c.id=l.content_id ORDER BY l.viewed_at DESC LIMIT %s", (limit,))
            return c.fetchall()

def get_recent_logs_by_owner(owner_id, limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT l.*, c.title AS content_title FROM tg_view_logs l "
                      "LEFT JOIN tg_content c ON c.id=l.content_id "
                      "WHERE l.owner_id=%s ORDER BY l.viewed_at DESC LIMIT %s", (owner_id, limit))
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# ACTIVITY LOGS
# ══════════════════════════════════════════════════════════════

def log_activity(user_id, action, details="", ip_address=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_activity_logs (user_id,action,details,ip_address) VALUES (%s,%s,%s,%s)",
                      (user_id, action, details, ip_address[:45]))

def get_recent_activity(limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_activity_logs ORDER BY created_at DESC LIMIT %s", (limit,))
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# LEGACY
# ══════════════════════════════════════════════════════════════

def save_video(data):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_videos (file_id,file_unique_id,file_size,duration,width,height,"
                      "file_name,mime_type,caption,message_id,channel_id,quality) "
                      "VALUES (%(file_id)s,%(file_unique_id)s,%(file_size)s,%(duration)s,"
                      "%(width)s,%(height)s,%(file_name)s,%(mime_type)s,%(caption)s,"
                      "%(message_id)s,%(channel_id)s,%(quality)s) "
                      "ON DUPLICATE KEY UPDATE file_id=VALUES(file_id),file_size=VALUES(file_size),"
                      "duration=VALUES(duration),width=VALUES(width),height=VALUES(height)", data)
            return c.lastrowid

def get_video_by_file_id(file_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_videos WHERE file_id=%s LIMIT 1", (file_id,))
            row = c.fetchone()
            if row: return row
            c.execute("SELECT * FROM tg_sources WHERE file_id=%s LIMIT 1", (file_id,))
            row = c.fetchone()
            if row: return row
            try:
                c.execute("SELECT telegram_file_id AS file_id, file_size_mb FROM streaming_sources "
                          "WHERE telegram_file_id=%s LIMIT 1", (file_id,))
                row = c.fetchone()
                if row:
                    row["file_size"] = int(float(row.get("file_size_mb", 0)) * 1048576)
                    return row
            except: pass
    return None

def get_all_videos(limit=100):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_videos ORDER BY created_at DESC LIMIT %s", (limit,))
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# PAYMENT METHODS
# ══════════════════════════════════════════════════════════════

def create_payment_method(method_type, title, details="", qr_image_url="", sort_order=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_payment_methods (method_type,title,details,qr_image_url,sort_order) "
                      "VALUES (%s,%s,%s,%s,%s)", (method_type, title, details, qr_image_url, sort_order))
            return c.lastrowid

def list_payment_methods(active_only=False):
    with get_connection() as conn:
        with conn.cursor() as c:
            if active_only:
                c.execute("SELECT * FROM tg_payment_methods WHERE is_active=1 ORDER BY sort_order, id")
            else:
                c.execute("SELECT * FROM tg_payment_methods ORDER BY sort_order, id")
            return c.fetchall()

def get_payment_method(pm_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_payment_methods WHERE id=%s", (pm_id,))
            return c.fetchone()

def toggle_payment_method(pm_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_payment_methods SET is_active=1-is_active WHERE id=%s", (pm_id,))

def delete_payment_method(pm_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_payment_methods WHERE id=%s", (pm_id,))


# ══════════════════════════════════════════════════════════════
# PAYMENT REQUESTS
# ══════════════════════════════════════════════════════════════

def create_payment_request(user_id, plan_id, amount, method_type="", transaction_id="",
                           screenshot_file_id="", notes=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("INSERT INTO tg_payment_requests "
                      "(user_id,plan_id,amount,method_type,transaction_id,screenshot_file_id,notes) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (user_id, plan_id, amount, method_type, transaction_id, screenshot_file_id, notes))
            return c.lastrowid

def list_payment_requests(status=None, limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            if status:
                c.execute("SELECT r.*, u.username, u.display_name, u.telegram_id AS user_tg_id, "
                          "p.name AS plan_name, p.price AS plan_price "
                          "FROM tg_payment_requests r "
                          "LEFT JOIN tg_users u ON u.telegram_id=r.user_id "
                          "LEFT JOIN tg_plans p ON p.id=r.plan_id "
                          "WHERE r.status=%s ORDER BY r.created_at DESC LIMIT %s", (status, limit))
            else:
                c.execute("SELECT r.*, u.username, u.display_name, u.telegram_id AS user_tg_id, "
                          "p.name AS plan_name, p.price AS plan_price "
                          "FROM tg_payment_requests r "
                          "LEFT JOIN tg_users u ON u.telegram_id=r.user_id "
                          "LEFT JOIN tg_plans p ON p.id=r.plan_id "
                          "ORDER BY FIELD(r.status,'pending','approved','rejected'), r.created_at DESC LIMIT %s", (limit,))
            return c.fetchall()

def get_payment_request(req_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT r.*, u.username, u.display_name, p.name AS plan_name, p.price AS plan_price, "
                      "p.duration_days FROM tg_payment_requests r "
                      "LEFT JOIN tg_users u ON u.telegram_id=r.user_id "
                      "LEFT JOIN tg_plans p ON p.id=r.plan_id WHERE r.id=%s", (req_id,))
            return c.fetchone()

def count_pending_requests():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_payment_requests WHERE status='pending'")
            return c.fetchone()["cnt"]

def approve_payment_request(req_id, admin_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_payment_requests SET status='approved', reviewed_by=%s, "
                      "reviewed_at=NOW() WHERE id=%s", (admin_id, req_id))

def reject_payment_request(req_id, admin_id, admin_notes=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_payment_requests SET status='rejected', reviewed_by=%s, "
                      "reviewed_at=NOW(), admin_notes=%s WHERE id=%s", (admin_id, admin_notes, req_id))


# ══════════════════════════════════════════════════════════════
# CONTENT HIERARCHY
# ══════════════════════════════════════════════════════════════

def get_children(content_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT c.*, COUNT(s.id) AS source_count FROM tg_content c "
                      "LEFT JOIN tg_sources s ON s.content_id=c.id AND s.is_active=1 "
                      "WHERE c.parent_id=%s AND c.is_active=1 GROUP BY c.id ORDER BY c.title", (content_id,))
            return c.fetchall()

def get_breadcrumb(content_id):
    """Get parent chain for display: [root, ..., parent, self]"""
    chain = []
    with get_connection() as conn:
        with conn.cursor() as c:
            cid = content_id
            for _ in range(10):  # max depth guard
                c.execute("SELECT id, title, slug, parent_id FROM tg_content WHERE id=%s", (cid,))
                row = c.fetchone()
                if not row: break
                chain.insert(0, row)
                if not row.get("parent_id"): break
                cid = row["parent_id"]
    return chain

def get_content_tree(owner_id, parent_id=None):
    """Get content tree for an owner, one level at a time."""
    with get_connection() as conn:
        with conn.cursor() as c:
            if parent_id is None:
                c.execute("SELECT c.*, COUNT(s.id) AS source_count, "
                          "(SELECT COUNT(*) FROM tg_content ch WHERE ch.parent_id=c.id) AS child_count "
                          "FROM tg_content c LEFT JOIN tg_sources s ON s.content_id=c.id AND s.is_active=1 "
                          "WHERE c.owner_id=%s AND c.parent_id IS NULL AND c.is_active=1 "
                          "GROUP BY c.id ORDER BY c.title", (owner_id,))
            else:
                c.execute("SELECT c.*, COUNT(s.id) AS source_count, "
                          "(SELECT COUNT(*) FROM tg_content ch WHERE ch.parent_id=c.id) AS child_count "
                          "FROM tg_content c LEFT JOIN tg_sources s ON s.content_id=c.id AND s.is_active=1 "
                          "WHERE c.owner_id=%s AND c.parent_id=%s AND c.is_active=1 "
                          "GROUP BY c.id ORDER BY c.title", (owner_id, parent_id))
            return c.fetchall()
