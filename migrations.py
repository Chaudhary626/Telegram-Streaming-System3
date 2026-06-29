"""
Versioned database migration system.

Tracks schema version in tg_migrations table.
Automatically applies pending migrations on startup.
Supports rollback of individual migrations.
"""
import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)

_db = None


def _get_db():
    global _db
    if _db is None:
        import database as db
        _db = db
    return _db


# ── Migration Definitions ─────────────────────────────────────
# Each migration has: version, name, up (SQL list), down (SQL list)
# Versions are applied in order. Each version is applied at most once.

MIGRATIONS = [
    {
        "version": "001",
        "name": "initial_baseline",
        "up": [
            # No-op: base tables are created by ensure_tables()
            # This migration marks the starting point.
        ],
        "down": []
    },
    {
        "version": "002",
        "name": "add_content_type",
        "up": [
            "ALTER TABLE tg_content ADD COLUMN content_type VARCHAR(20) DEFAULT 'streaming'",
        ],
        "down": [
            "ALTER TABLE tg_content DROP COLUMN content_type",
        ]
    },
    {
        "version": "003",
        "name": "add_plan_features",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_plan_features (
                id INT AUTO_INCREMENT PRIMARY KEY,
                plan_id INT NOT NULL,
                feature_key VARCHAR(50) NOT NULL,
                enabled TINYINT(1) DEFAULT 1,
                UNIQUE KEY uk_plan_feat (plan_id, feature_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_plan_features",
        ]
    },
    {
        "version": "004",
        "name": "add_addons",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_addons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(50) NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                price DECIMAL(10,2) DEFAULT 0,
                duration_days INT DEFAULT 30,
                features TEXT DEFAULT '[]',
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS tg_user_addons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                addon_id INT NOT NULL,
                expires_at DATETIME DEFAULT NULL,
                assigned_by BIGINT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_user_addons",
            "DROP TABLE IF EXISTS tg_addons",
        ]
    },
    {
        "version": "005",
        "name": "add_payment_addon_ids",
        "up": [
            "ALTER TABLE tg_payment_requests ADD COLUMN addon_ids VARCHAR(255) DEFAULT ''",
        ],
        "down": [
            "ALTER TABLE tg_payment_requests DROP COLUMN addon_ids",
        ]
    },
    {
        "version": "006",
        "name": "enhance_channels",
        "up": [
            "ALTER TABLE tg_channels ADD COLUMN priority INT DEFAULT 0",
            "ALTER TABLE tg_channels ADD COLUMN file_count INT DEFAULT 0",
            "ALTER TABLE tg_channels ADD COLUMN total_size_bytes BIGINT DEFAULT 0",
            "ALTER TABLE tg_channels ADD COLUMN max_files INT DEFAULT 500000",
            "ALTER TABLE tg_channels ADD COLUMN last_upload_at DATETIME DEFAULT NULL",
            "ALTER TABLE tg_channels ADD COLUMN description VARCHAR(255) DEFAULT ''",
        ],
        "down": [
            "ALTER TABLE tg_channels DROP COLUMN priority",
            "ALTER TABLE tg_channels DROP COLUMN file_count",
            "ALTER TABLE tg_channels DROP COLUMN total_size_bytes",
            "ALTER TABLE tg_channels DROP COLUMN max_files",
            "ALTER TABLE tg_channels DROP COLUMN last_upload_at",
            "ALTER TABLE tg_channels DROP COLUMN description",
        ]
    },
    {
        "version": "007",
        "name": "add_upload_queue",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_upload_queue (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                file_id VARCHAR(512) NOT NULL,
                file_unique_id VARCHAR(128) DEFAULT '',
                file_size BIGINT DEFAULT 0,
                file_name VARCHAR(512) DEFAULT '',
                caption TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                content_type VARCHAR(20) DEFAULT 'streaming',
                target_content_id INT DEFAULT NULL,
                target_channel_id BIGINT DEFAULT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT DEFAULT '',
                retry_count INT DEFAULT 0,
                priority INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at DATETIME DEFAULT NULL,
                completed_at DATETIME DEFAULT NULL,
                INDEX idx_user (user_id),
                INDEX idx_status (status),
                INDEX idx_priority (priority, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_upload_queue",
        ]
    },
    {
        "version": "008",
        "name": "add_download_logs",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_download_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id INT DEFAULT NULL,
                source_id INT DEFAULT NULL,
                user_id BIGINT DEFAULT 0,
                ip_hash VARCHAR(64) DEFAULT '',
                user_agent VARCHAR(255) DEFAULT '',
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_content (content_id),
                INDEX idx_user (user_id),
                INDEX idx_date (downloaded_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_download_logs",
        ]
    },
    {
        "version": "009",
        "name": "add_tags",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_tags (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id INT NOT NULL,
                tag VARCHAR(50) NOT NULL,
                INDEX idx_content (content_id),
                INDEX idx_tag (tag),
                UNIQUE KEY uk_content_tag (content_id, tag)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_tags",
        ]
    },
    {
        "version": "010",
        "name": "add_player_events",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_player_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                content_id INT NOT NULL,
                source_id INT DEFAULT NULL,
                session_id VARCHAR(64) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                event_data TEXT DEFAULT '{}',
                ip_hash VARCHAR(64) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_content (content_id),
                INDEX idx_session (session_id),
                INDEX idx_type (event_type),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_player_events",
        ]
    },
    {
        "version": "011",
        "name": "add_notifications",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                target_type VARCHAR(20) DEFAULT 'admin',
                target_id BIGINT DEFAULT 0,
                title VARCHAR(200) NOT NULL,
                message TEXT DEFAULT '',
                severity VARCHAR(10) DEFAULT 'info',
                is_read TINYINT(1) DEFAULT 0,
                action_url VARCHAR(512) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_target (target_type, target_id),
                INDEX idx_read (is_read),
                INDEX idx_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_notifications",
        ]
    },
    {
        "version": "012",
        "name": "add_roles",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                slug VARCHAR(50) NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                permissions TEXT DEFAULT '{}',
                is_system TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            "ALTER TABLE tg_users ADD COLUMN role_id INT DEFAULT NULL",
        ],
        "down": [
            "ALTER TABLE tg_users DROP COLUMN role_id",
            "DROP TABLE IF EXISTS tg_roles",
        ]
    },
    {
        "version": "013",
        "name": "add_backups",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_backups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_size BIGINT DEFAULT 0,
                backup_type VARCHAR(20) DEFAULT 'manual',
                tables_included TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_backups",
        ]
    },
    {
        "version": "014",
        "name": "add_error_logs",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_error_logs (
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_error_logs",
        ]
    },
    {
        "version": "015",
        "name": "add_deployments",
        "up": [
            """CREATE TABLE IF NOT EXISTS tg_deployments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(20) NOT NULL,
                git_hash VARCHAR(40) DEFAULT '',
                migration_version VARCHAR(20) DEFAULT '',
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active',
                notes TEXT DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ],
        "down": [
            "DROP TABLE IF EXISTS tg_deployments",
        ]
    },
    {
        "version": "016",
        "name": "add_video_hashes",
        "up": [
            "ALTER TABLE tg_videos ADD COLUMN file_hash_sha256 VARCHAR(64) DEFAULT ''",
            "ALTER TABLE tg_videos ADD COLUMN file_hash_md5 VARCHAR(32) DEFAULT ''",
            "ALTER TABLE tg_videos ADD COLUMN file_hash_crc32 VARCHAR(8) DEFAULT ''",
        ],
        "down": [
            "ALTER TABLE tg_videos DROP COLUMN file_hash_sha256",
            "ALTER TABLE tg_videos DROP COLUMN file_hash_md5",
            "ALTER TABLE tg_videos DROP COLUMN file_hash_crc32",
        ]
    },
    {
        "version": "017",
        "name": "add_fulltext_search",
        "up": [
            "ALTER TABLE tg_content ADD FULLTEXT INDEX ft_search (title, description)",
        ],
        "down": [
            "ALTER TABLE tg_content DROP INDEX ft_search",
        ]
    },
]


# ── Migrator Class ────────────────────────────────────────────

class Migrator:
    """Versioned database migration manager."""

    def __init__(self):
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        """Create tg_migrations table if it doesn't exist."""
        db = _get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("""CREATE TABLE IF NOT EXISTS tg_migrations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        version VARCHAR(20) NOT NULL UNIQUE,
                        name VARCHAR(200) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rollback_sql TEXT DEFAULT '',
                        status VARCHAR(20) DEFAULT 'applied'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        except Exception as e:
            logger.error(f"Migration table creation failed: {e}")

    def get_applied_versions(self) -> set:
        """Get set of already-applied migration versions."""
        db = _get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT version FROM tg_migrations WHERE status='applied'")
                    return {row["version"] for row in c.fetchall()}
        except Exception:
            return set()

    def get_current_version(self) -> Optional[str]:
        """Get the latest applied migration version."""
        db = _get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT version FROM tg_migrations WHERE status='applied' ORDER BY version DESC LIMIT 1")
                    row = c.fetchone()
                    return row["version"] if row else None
        except Exception:
            return None

    def get_pending(self) -> list:
        """Get list of migrations that haven't been applied yet."""
        applied = self.get_applied_versions()
        return [m for m in MIGRATIONS if m["version"] not in applied]

    def apply_one(self, migration: dict) -> bool:
        """Apply a single migration. Returns True on success."""
        db = _get_db()
        version = migration["version"]
        name = migration["name"]
        logger.info(f"Migration {version}: applying '{name}'...")

        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    for sql in migration["up"]:
                        if sql.strip():
                            try:
                                c.execute(sql)
                            except Exception as e:
                                # Ignore "column already exists" or "table already exists"
                                err_str = str(e).lower()
                                if "duplicate" in err_str or "already exists" in err_str or "1060" in str(e) or "1061" in str(e):
                                    logger.debug(f"Migration {version}: skipped (already exists): {e}")
                                else:
                                    raise
                    # Record migration
                    import json
                    rollback = json.dumps(migration.get("down", []))
                    c.execute(
                        "INSERT IGNORE INTO tg_migrations (version, name, rollback_sql, status) VALUES (%s, %s, %s, 'applied')",
                        (version, name, rollback)
                    )
            logger.info(f"Migration {version}: '{name}' applied successfully.")
            return True
        except Exception as e:
            logger.error(f"Migration {version}: FAILED — {e}")
            logger.error(traceback.format_exc())
            return False

    def apply_all(self) -> list:
        """Apply all pending migrations in order. Returns list of applied."""
        pending = self.get_pending()
        if not pending:
            logger.info("Migrations: all up to date.")
            return []

        applied = []
        for m in pending:
            if self.apply_one(m):
                applied.append(m)
            else:
                logger.error(f"Migration stopped at {m['version']}. Fix and retry.")
                break
        return applied

    def rollback_one(self, version: str) -> bool:
        """Rollback a specific migration version."""
        db = _get_db()
        import json
        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT rollback_sql FROM tg_migrations WHERE version=%s AND status='applied'", (version,))
                    row = c.fetchone()
                    if not row:
                        logger.warning(f"Migration {version}: not found or not applied.")
                        return False

                    down_sqls = json.loads(row["rollback_sql"] or "[]")
                    for sql in down_sqls:
                        if sql.strip():
                            try:
                                c.execute(sql)
                            except Exception as e:
                                logger.warning(f"Rollback {version}: statement failed (continuing): {e}")

                    c.execute("UPDATE tg_migrations SET status='rolled_back' WHERE version=%s", (version,))
            logger.info(f"Migration {version}: rolled back.")
            return True
        except Exception as e:
            logger.error(f"Rollback {version}: FAILED — {e}")
            return False

    def history(self) -> list:
        """Get full migration history."""
        db = _get_db()
        try:
            with db.get_connection() as conn:
                with conn.cursor() as c:
                    c.execute("SELECT * FROM tg_migrations ORDER BY version")
                    return c.fetchall()
        except Exception:
            return []
