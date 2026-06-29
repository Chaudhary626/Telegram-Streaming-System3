"""
Module registry — mounts all route modules on the FastAPI app.
"""
import logging

logger = logging.getLogger(__name__)


def mount_all(app, ctx):
    """Register all route modules on the FastAPI app.
    
    Args:
        app: FastAPI application instance
        ctx: Shared context dict with 'tg_client', 'streamer', etc.
    """
    from modules.streaming import register as reg_streaming
    from modules.admin_core import register as reg_admin_core
    from modules.admin_content import register as reg_admin_content
    from modules.admin_billing import register as reg_admin_billing
    from modules.admin_system import register as reg_admin_system
    from modules.channels import register as reg_channels
    from modules.search import register as reg_search
    from modules.analytics import register as reg_analytics
    from modules.roles import register as reg_roles
    from modules.security import register as reg_security
    from modules.backups import register as reg_backups
    from modules.api_docs import register as reg_api_docs
    from modules.downloads import register as reg_downloads
    from modules.import_export import register as reg_import_export
    from modules.panel import register as reg_panel

    reg_streaming(app, ctx)
    reg_admin_core(app, ctx)
    reg_admin_content(app, ctx)
    reg_admin_billing(app, ctx)
    reg_admin_system(app, ctx)
    reg_channels(app, ctx)
    reg_search(app, ctx)
    reg_analytics(app, ctx)
    reg_roles(app, ctx)
    reg_security(app, ctx)
    reg_backups(app, ctx)
    reg_api_docs(app, ctx)
    reg_downloads(app, ctx)
    reg_import_export(app, ctx)
    reg_panel(app, ctx)

    logger.info(f"Modules: all registered.")


