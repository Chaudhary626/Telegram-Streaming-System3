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

            c.execute("""CREATE TABLE IF NOT EXISTS tg_player_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id INT DEFAULT NULL,
                source_id INT DEFAULT NULL,
                owner_id BIGINT DEFAULT 0,
                event_type VARCHAR(30) DEFAULT '',
                ip_hash VARCHAR(64) DEFAULT '',
                user_agent VARCHAR(255) DEFAULT '',
                duration_sec INT DEFAULT 0,
                position_sec INT DEFAULT 0,
                quality VARCHAR(20) DEFAULT '',
                buffering_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_content (content_id),
                INDEX idx_owner (owner_id),
                INDEX idx_type (event_type),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(100) NOT NULL UNIQUE,
                setting_value TEXT DEFAULT '',
                setting_type VARCHAR(20) DEFAULT 'string',
                category VARCHAR(50) DEFAULT 'general',
                description VARCHAR(255) DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                role VARCHAR(30) NOT NULL DEFAULT 'user',
                permissions TEXT DEFAULT '',
                granted_by BIGINT DEFAULT 0,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY idx_user_role (user_id, role),
                INDEX idx_role (role)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_backups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_size BIGINT DEFAULT 0,
                backup_type VARCHAR(30) DEFAULT 'full',
                status VARCHAR(20) DEFAULT 'pending',
                tables_included TEXT DEFAULT '',
                created_by BIGINT DEFAULT 0,
                error_message TEXT DEFAULT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL DEFAULT NULL,
                INDEX idx_status (status),
                INDEX idx_date (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_error_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                module VARCHAR(50) DEFAULT '',
                error_type VARCHAR(100) DEFAULT '',
                message TEXT DEFAULT '',
                stack_trace TEXT DEFAULT '',
                user_id BIGINT DEFAULT NULL,
                request_path VARCHAR(512) DEFAULT '',
                ip_address VARCHAR(45) DEFAULT '',
                is_resolved TINYINT(1) DEFAULT 0,
                resolved_by BIGINT DEFAULT NULL,
                resolved_at DATETIME DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_module (module),
                INDEX idx_resolved (is_resolved),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            c.execute("""CREATE TABLE IF NOT EXISTS tg_notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                target_type VARCHAR(20) DEFAULT 'admin',
                target_id BIGINT DEFAULT 0,
                title VARCHAR(200) DEFAULT '',
                message TEXT DEFAULT '',
                severity VARCHAR(20) DEFAULT 'info',
                action_url VARCHAR(512) DEFAULT '',
                is_read TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_target (target_type, target_id),
                INDEX idx_unread (is_read)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

            c.execute("""CREATE TABLE IF NOT EXISTS tg_upload_queue (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL DEFAULT 0,
                file_id VARCHAR(512) NOT NULL DEFAULT '',
                file_unique_id VARCHAR(128) DEFAULT '',
                file_size BIGINT DEFAULT 0,
                file_name VARCHAR(512) DEFAULT '',
                caption TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                content_type VARCHAR(20) DEFAULT 'streaming',
                target_content_id INT DEFAULT NULL,
                target_slug VARCHAR(255) DEFAULT '',
                language VARCHAR(50) DEFAULT 'Hindi',
                quality VARCHAR(20) DEFAULT '720p',
                status VARCHAR(20) DEFAULT 'pending',
                priority INT DEFAULT 0,
                retry_count INT DEFAULT 0,
                max_retries INT DEFAULT 3,
                error_message TEXT DEFAULT '',
                result_json TEXT DEFAULT '{}',
                started_at DATETIME DEFAULT NULL,
                completed_at DATETIME DEFAULT NULL,
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
            _safe_add_column(c, "tg_channels", "max_storage_gb", "FLOAT DEFAULT 50")
            _safe_add_column(c, "tg_channels", "used_storage_gb", "FLOAT DEFAULT 0")
            _safe_add_column(c, "tg_channels", "sort_order", "INT DEFAULT 0")

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
            c.execute("SELECT * FROM tg_channels ORDER BY sort_order ASC, name ASC")
            return c.fetchall()

def delete_channel(ch_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_channels WHERE id=%s", (ch_id,))


def update_channel(ch_id, **kwargs):
    with get_connection() as conn:
        with conn.cursor() as c:
            sets = []
            vals = []
            for k, v in kwargs.items():
                if k in ('name', 'channel_id', 'category', 'is_active', 'max_storage_gb', 'used_storage_gb', 'sort_order'):
                    sets.append(f"{k}=%s")
                    vals.append(v)
            if not sets:
                return
            vals.append(ch_id)
            c.execute(f"UPDATE tg_channels SET {','.join(sets)} WHERE id=%s", tuple(vals))


def toggle_channel(ch_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_channels SET is_active = NOT is_active WHERE id=%s", (ch_id,))


def list_channels_by_category(category):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_channels WHERE category=%s AND is_active=1 ORDER BY sort_order ASC, id ASC", (category,))
            return c.fetchall()


def get_next_channel(category='general'):
    """Get next available channel for upload using round-robin."""
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM tg_channels WHERE category=%s AND is_active=1 "
                "ORDER BY used_storage_gb ASC, sort_order ASC LIMIT 1", (category,))
            return c.fetchone()


def increment_channel_storage(ch_id, bytes_added):
    with get_connection() as conn:
        with conn.cursor() as c:
            gb = bytes_added / (1024**3)
            c.execute("UPDATE tg_channels SET used_storage_gb = used_storage_gb + %s WHERE id=%s", (gb, ch_id))


def count_channels():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_channels")
            return c.fetchone()['cnt']


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

def get_activity_logs(limit=50, offset=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM tg_activity_logs ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset))
            return c.fetchall()

def count_activity_logs():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_activity_logs")
            return c.fetchone()['cnt']


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


# ══════════════════════════════════════════════════════════════
# GLOBAL SETTINGS
# ══════════════════════════════════════════════════════════════

def get_setting(key):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_settings WHERE setting_key=%s LIMIT 1", (key,))
            return c.fetchone()

def set_setting(key, value):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_settings SET setting_value=%s WHERE setting_key=%s", (value, key))

def get_all_settings():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_settings ORDER BY category, setting_key")
            return c.fetchall()

def insert_setting_if_not_exists(key, value, stype="string", category="general", description=""):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "INSERT IGNORE INTO tg_settings (setting_key, setting_value, setting_type, category, description) "
                "VALUES (%s, %s, %s, %s, %s)",
                (key, value, stype, category, description))


# ══════════════════════════════════════════════════════════════
# ERROR LOGGING
# ══════════════════════════════════════════════════════════════

def log_error(module="", error_type="", message="", stack_trace="",
              user_id=None, request_path="", ip_address=""):
    """Log an error to tg_error_logs table (created by migration 014)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO tg_error_logs "
                    "(module, error_type, message, stack_trace, user_id, request_path, ip_address) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (module[:50], error_type[:100], message, stack_trace,
                     user_id, request_path[:512], ip_address[:45]))
    except Exception:
        # If error table doesn't exist yet (pre-migration), silently ignore
        pass

def list_errors(resolved=None, module=None, limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            sql = "SELECT * FROM tg_error_logs WHERE 1=1"
            params = []
            if resolved is not None:
                sql += " AND is_resolved=%s"
                params.append(int(resolved))
            if module:
                sql += " AND module=%s"
                params.append(module)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            c.execute(sql, tuple(params))
            return c.fetchall()

def resolve_error(error_id, admin_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE tg_error_logs SET is_resolved=1, resolved_by=%s, "
                      "resolved_at=NOW() WHERE id=%s", (admin_id, error_id))


def get_error_logs(resolved=None, limit=50, offset=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            if resolved is not None:
                c.execute(
                    "SELECT * FROM tg_error_logs WHERE is_resolved=%s "
                    "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (int(resolved), limit, offset))
            else:
                c.execute(
                    "SELECT * FROM tg_error_logs ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset))
            return c.fetchall()


def count_errors(resolved=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if resolved is not None:
                c.execute("SELECT COUNT(*) AS cnt FROM tg_error_logs WHERE is_resolved=%s", (int(resolved),))
            else:
                c.execute("SELECT COUNT(*) AS cnt FROM tg_error_logs")
            return c.fetchone()['cnt']


def purge_old_errors(days=90):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "DELETE FROM tg_error_logs WHERE is_resolved=1 AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,))
            return c.rowcount


# ══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════

def create_notification(target_type="admin", target_id=0, title="", message="",
                        severity="info", action_url=""):
    """Create a notification (table created by migration 011)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute(
                    "INSERT INTO tg_notifications "
                    "(target_type, target_id, title, message, severity, action_url) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (target_type, target_id, title[:200], message, severity, action_url[:512]))
    except Exception:
        pass  # Table may not exist pre-migration

def list_notifications(target_type="admin", target_id=0, unread_only=False, limit=20):
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                sql = "SELECT * FROM tg_notifications WHERE target_type=%s AND target_id=%s"
                params = [target_type, target_id]
                if unread_only:
                    sql += " AND is_read=0"
                sql += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                c.execute(sql, tuple(params))
                return c.fetchall()
    except Exception:
        return []

def count_unread_notifications(target_type="admin", target_id=0):
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT COUNT(*) AS cnt FROM tg_notifications "
                          "WHERE target_type=%s AND target_id=%s AND is_read=0",
                          (target_type, target_id))
                return c.fetchone()["cnt"]
    except Exception:
        return 0

def mark_notification_read(notif_id):
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE tg_notifications SET is_read=1 WHERE id=%s", (notif_id,))
    except Exception:
        pass

def mark_all_notifications_read(target_type="admin", target_id=0):
    try:
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE tg_notifications SET is_read=1 "
                          "WHERE target_type=%s AND target_id=%s", (target_type, target_id))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# ROLES & PERMISSIONS
# ══════════════════════════════════════════════════════════════

def assign_role(user_id, role, granted_by=0, permissions=''):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO tg_roles (user_id, role, granted_by, permissions) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE permissions=%s, granted_by=%s",
                (user_id, role, granted_by, permissions, permissions, granted_by))


def remove_role(user_id, role):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_roles WHERE user_id=%s AND role=%s", (user_id, role))
            return c.rowcount > 0


def get_user_roles(user_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_roles WHERE user_id=%s", (user_id,))
            return c.fetchall()


def has_role(user_id, role):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM tg_roles WHERE user_id=%s AND role=%s", (user_id, role))
            return c.fetchone() is not None


def has_permission(user_id, permission):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT permissions FROM tg_roles WHERE user_id=%s", (user_id,))
            for row in c.fetchall():
                perms = (row.get('permissions') or '').split(',')
                if permission in perms or '*' in perms:
                    return True
            return False


def list_users_by_role(role, limit=100):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT r.*, u.username, u.display_name FROM tg_roles r "
                "LEFT JOIN tg_users u ON u.telegram_id=r.user_id "
                "WHERE r.role=%s ORDER BY r.granted_at DESC LIMIT %s", (role, limit))
            return c.fetchall()


def list_all_roles():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT role, COUNT(*) AS user_count FROM tg_roles "
                "GROUP BY role ORDER BY role")
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# PLAYER ANALYTICS
# ══════════════════════════════════════════════════════════════

def log_player_event(content_id=None, source_id=None, owner_id=0, event_type='play',
                     ip_hash='', user_agent='', duration_sec=0, position_sec=0,
                     quality='', buffering_count=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO tg_player_events "
                "(content_id,source_id,owner_id,event_type,ip_hash,user_agent,"
                "duration_sec,position_sec,quality,buffering_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (content_id, source_id, owner_id, event_type, ip_hash, user_agent,
                 duration_sec, position_sec, quality, buffering_count))


def get_analytics_overview(days=30):
    """Get overview analytics for admin dashboard."""
    with get_connection() as conn:
        with conn.cursor() as c:
            result = {}
            # Total views
            c.execute("SELECT COUNT(*) AS cnt FROM tg_view_logs")
            result['total_views'] = c.fetchone()['cnt']
            # Views today
            c.execute("SELECT COUNT(*) AS cnt FROM tg_view_logs WHERE DATE(viewed_at)=CURDATE()")
            result['views_today'] = c.fetchone()['cnt']
            # Views this week
            c.execute("SELECT COUNT(*) AS cnt FROM tg_view_logs WHERE viewed_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
            result['views_week'] = c.fetchone()['cnt']
            # Unique viewers today
            c.execute("SELECT COUNT(DISTINCT ip_hash) AS cnt FROM tg_view_logs WHERE DATE(viewed_at)=CURDATE()")
            result['unique_today'] = c.fetchone()['cnt']
            # Player events
            c.execute("SELECT event_type, COUNT(*) AS cnt FROM tg_player_events "
                      "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                      "GROUP BY event_type", (days,))
            result['events'] = {r['event_type']: r['cnt'] for r in c.fetchall()}
            # Views per day (last N days)
            c.execute(
                "SELECT DATE(viewed_at) AS day, COUNT(*) AS cnt FROM tg_view_logs "
                "WHERE viewed_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY DATE(viewed_at) ORDER BY day", (days,))
            result['daily_views'] = [(str(r['day']), r['cnt']) for r in c.fetchall()]
            # Top content
            c.execute(
                "SELECT c.title, c.slug, COUNT(v.id) AS views FROM tg_view_logs v "
                "JOIN tg_content c ON c.id=v.content_id "
                "WHERE v.viewed_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY v.content_id ORDER BY views DESC LIMIT 10", (days,))
            result['top_content'] = c.fetchall()
            return result


def get_analytics_by_owner(owner_id, days=30):
    """Get analytics for a specific owner (sub-admin panel)."""
    with get_connection() as conn:
        with conn.cursor() as c:
            result = {}
            c.execute("SELECT COUNT(*) AS cnt FROM tg_view_logs WHERE owner_id=%s", (owner_id,))
            result['total_views'] = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) AS cnt FROM tg_view_logs WHERE owner_id=%s AND DATE(viewed_at)=CURDATE()", (owner_id,))
            result['views_today'] = c.fetchone()['cnt']
            c.execute(
                "SELECT DATE(viewed_at) AS day, COUNT(*) AS cnt FROM tg_view_logs "
                "WHERE owner_id=%s AND viewed_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY DATE(viewed_at) ORDER BY day", (owner_id, days))
            result['daily_views'] = [(str(r['day']), r['cnt']) for r in c.fetchall()]
            c.execute(
                "SELECT c.title, c.slug, COUNT(v.id) AS views FROM tg_view_logs v "
                "JOIN tg_content c ON c.id=v.content_id "
                "WHERE v.owner_id=%s AND v.viewed_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY v.content_id ORDER BY views DESC LIMIT 10", (owner_id, days))
            result['top_content'] = c.fetchall()
            return result


def purge_old_player_events(days=90):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_player_events WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (days,))
            return c.rowcount


# ══════════════════════════════════════════════════════════════
# SEARCH & DUPLICATE DETECTION
# ══════════════════════════════════════════════════════════════

def search_content(query, owner_id=None, limit=20):
    """Search content by title/slug using LIKE. FULLTEXT can be added via migration."""
    with get_connection() as conn:
        with conn.cursor() as c:
            like = f"%{query}%"
            sql = ("SELECT c.*, COUNT(s.id) AS source_count FROM tg_content c "
                   "LEFT JOIN tg_sources s ON s.content_id=c.id WHERE "
                   "(c.title LIKE %s OR c.slug LIKE %s)")
            params = [like, like]
            if owner_id:
                sql += " AND c.owner_id=%s"
                params.append(owner_id)
            sql += " GROUP BY c.id ORDER BY c.created_at DESC LIMIT %s"
            params.append(limit)
            c.execute(sql, tuple(params))
            return c.fetchall()


def check_duplicate_source(file_unique_id):
    """Check if a source with this file_unique_id already exists."""
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT s.*, c.title, c.slug, c.owner_id FROM tg_sources s "
                "LEFT JOIN tg_content c ON c.id=s.content_id "
                "WHERE s.file_unique_id=%s LIMIT 1", (file_unique_id,))
            return c.fetchone()


def check_duplicate_video(file_unique_id):
    """Check legacy tg_videos table for duplicates."""
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_videos WHERE file_unique_id=%s LIMIT 1", (file_unique_id,))
            return c.fetchone()


def search_videos_legacy(query, limit=20):
    """Search legacy tg_videos by filename/caption."""
    with get_connection() as conn:
        with conn.cursor() as c:
            like = f"%{query}%"
            c.execute(
                "SELECT * FROM tg_videos WHERE file_name LIKE %s OR caption LIKE %s "
                "ORDER BY created_at DESC LIMIT %s", (like, like, limit))
            return c.fetchall()


# ══════════════════════════════════════════════════════════════
# UPLOAD QUEUE
# ══════════════════════════════════════════════════════════════

def queue_add(user_id, file_id, file_unique_id='', file_size=0, file_name='',
              caption='', metadata_json='{}', content_type='streaming',
              target_slug='', language='Hindi', quality='720p', priority=0):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO tg_upload_queue "
                "(user_id, file_id, file_unique_id, file_size, file_name, caption, "
                "metadata_json, content_type, target_slug, language, quality, status, priority) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)",
                (user_id, file_id, file_unique_id, file_size, file_name, caption,
                 metadata_json, content_type, target_slug, language, quality, priority))
            return c.lastrowid


def queue_get(task_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_upload_queue WHERE id=%s", (task_id,))
            return c.fetchone()


def queue_dequeue():
    """Atomically get next pending task and mark it processing."""
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT * FROM tg_upload_queue WHERE status='pending' "
                "ORDER BY priority DESC, created_at ASC LIMIT 1 FOR UPDATE")
            task = c.fetchone()
            if task:
                c.execute(
                    "UPDATE tg_upload_queue SET status='processing', "
                    "started_at=NOW() WHERE id=%s AND status='pending'",
                    (task['id'],))
            return task


def queue_complete(task_id, result=''):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE tg_upload_queue SET status='completed', "
                "completed_at=NOW(), result_json=%s WHERE id=%s",
                (result, task_id))


def queue_fail(task_id, error, max_retries=3):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT retry_count FROM tg_upload_queue WHERE id=%s", (task_id,))
            row = c.fetchone()
            if row and row['retry_count'] < max_retries:
                c.execute(
                    "UPDATE tg_upload_queue SET status='pending', "
                    "retry_count=retry_count+1, error_message=%s WHERE id=%s",
                    (error, task_id))
            else:
                c.execute(
                    "UPDATE tg_upload_queue SET status='failed', "
                    "completed_at=NOW(), error_message=%s WHERE id=%s",
                    (error, task_id))


def queue_cancel(task_id, user_id=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if user_id:
                c.execute(
                    "UPDATE tg_upload_queue SET status='cancelled' "
                    "WHERE id=%s AND user_id=%s AND status IN ('pending','failed')",
                    (task_id, user_id))
            else:
                c.execute(
                    "UPDATE tg_upload_queue SET status='cancelled' "
                    "WHERE id=%s AND status IN ('pending','failed')",
                    (task_id,))
            return c.rowcount


def queue_retry(task_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE tg_upload_queue SET status='pending', error_message='' "
                "WHERE id=%s AND status='failed'", (task_id,))
            return c.rowcount


def queue_list_by_user(user_id, status=None, limit=20):
    with get_connection() as conn:
        with conn.cursor() as c:
            sql = "SELECT * FROM tg_upload_queue WHERE user_id=%s"
            params = [user_id]
            if status:
                sql += " AND status=%s"
                params.append(status)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            c.execute(sql, tuple(params))
            return c.fetchall()


def queue_list_all(status=None, limit=50):
    with get_connection() as conn:
        with conn.cursor() as c:
            sql = ("SELECT q.*, u.username, u.display_name FROM tg_upload_queue q "
                   "LEFT JOIN tg_users u ON u.telegram_id=q.user_id WHERE 1=1")
            params = []
            if status:
                sql += " AND q.status=%s"
                params.append(status)
            sql += " ORDER BY q.created_at DESC LIMIT %s"
            params.append(limit)
            c.execute(sql, tuple(params))
            return c.fetchall()


def queue_stats():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT status, COUNT(*) AS cnt FROM tg_upload_queue GROUP BY status")
            rows = c.fetchall()
            stats = {r['status']: r['cnt'] for r in rows}
            c.execute("SELECT COUNT(*) AS total FROM tg_upload_queue")
            stats['total'] = c.fetchone()['total']
            return stats


def queue_stats_by_user(user_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "SELECT status, COUNT(*) AS cnt FROM tg_upload_queue "
                "WHERE user_id=%s GROUP BY status", (user_id,))
            rows = c.fetchall()
            stats = {r['status']: r['cnt'] for r in rows}
            c.execute(
                "SELECT COUNT(*) AS total FROM tg_upload_queue WHERE user_id=%s",
                (user_id,))
            stats['total'] = c.fetchone()['total']
            return stats


def queue_cleanup_stale(timeout_minutes=30):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "UPDATE tg_upload_queue SET status='pending' "
                "WHERE status='processing' AND started_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)",
                (timeout_minutes,))
            return c.rowcount


def queue_purge_completed(days=7):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "DELETE FROM tg_upload_queue "
                "WHERE status IN ('completed','cancelled') "
                "AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,))
            return c.rowcount


# ══════════════════════════════════════════════════════════════
# BACKUPS
# ══════════════════════════════════════════════════════════════

def create_backup_record(filename, backup_type='full', created_by=0, tables_included=''):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO tg_backups (filename, backup_type, status, tables_included, created_by) "
                "VALUES (%s, %s, 'running', %s, %s)",
                (filename, backup_type, tables_included, created_by))
            return c.lastrowid


def update_backup_status(backup_id, status, file_size=0, error_message=None):
    with get_connection() as conn:
        with conn.cursor() as c:
            if status == 'completed':
                c.execute(
                    "UPDATE tg_backups SET status=%s, file_size=%s, completed_at=NOW() WHERE id=%s",
                    (status, file_size, backup_id))
            else:
                c.execute(
                    "UPDATE tg_backups SET status=%s, error_message=%s WHERE id=%s",
                    (status, error_message, backup_id))


def list_backups(limit=20):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_backups ORDER BY started_at DESC LIMIT %s", (limit,))
            return c.fetchall()


def get_backup(backup_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM tg_backups WHERE id=%s", (backup_id,))
            return c.fetchone()


def delete_backup_record(backup_id):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("DELETE FROM tg_backups WHERE id=%s", (backup_id,))
            return c.rowcount > 0


def count_backups():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) AS cnt FROM tg_backups")
            return c.fetchone()['cnt']
