"""
Storage provider factory.
Currently uses Telegram MTProto. Designed for future S3/R2/B2 support.
"""
import os
import logging

logger = logging.getLogger(__name__)

_provider = None


def get_provider():
    """Get the active storage provider instance."""
    global _provider
    if _provider is None:
        provider_type = os.getenv("STORAGE_PROVIDER", "telegram")
        if provider_type == "telegram":
            logger.info("Storage: using Telegram provider")
        else:
            logger.warning(f"Storage: unknown provider '{provider_type}', falling back to Telegram")
    return _provider


def init_provider(tg_client):
    """Initialize the storage provider with a Telegram client."""
    global _provider
    from storage.telegram import TelegramStorageProvider
    _provider = TelegramStorageProvider(tg_client)
    logger.info("Storage: Telegram provider initialized.")
    return _provider
