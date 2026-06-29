"""
Bot handler registry — registers all Telegram bot handlers.
"""
import logging

logger = logging.getLogger(__name__)


def register_all(tg_client, ctx):
    """Register all bot command and message handlers.
    
    Args:
        tg_client: Pyrogram Client instance
        ctx: Shared context dict
    """
    from bot.commands import register as reg_commands
    from bot.admin_commands import register as reg_admin
    from bot.upload_handler import register as reg_upload
    from bot.callbacks import register as reg_callbacks

    reg_commands(tg_client, ctx)
    reg_admin(tg_client, ctx)
    reg_upload(tg_client, ctx)
    reg_callbacks(tg_client, ctx)

    logger.info("Bot: all handlers registered.")
