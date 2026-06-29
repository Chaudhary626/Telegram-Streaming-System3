"""
Telegram MTProto storage provider.
Wraps the existing TelegramStreamer for the StorageProvider interface.
"""
from typing import AsyncGenerator, Optional
from storage.base import StorageProvider
from streamer import TelegramStreamer


class TelegramStorageProvider(StorageProvider):
    """Telegram MTProto-based storage provider."""

    def __init__(self, tg_client):
        self._client = tg_client
        self._streamer = TelegramStreamer(tg_client)

    @property
    def provider_name(self) -> str:
        return "Telegram"

    @property
    def max_file_size(self) -> int:
        return 4 * 1024 ** 3  # 4 GB

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected if self._client else False

    @property
    def streamer(self) -> TelegramStreamer:
        return self._streamer

    async def get_file_size(self, file_ref: str) -> int:
        return await self._streamer.get_file_size(file_ref)

    async def stream_file(self, file_ref: str, offset: int = 0,
                          end: Optional[int] = None) -> AsyncGenerator[bytes, None]:
        async for chunk in self._streamer.stream(file_ref, offset=offset, end=end):
            yield chunk

    def cache_file_size(self, file_ref: str, size: int):
        self._streamer.cache_file_size(file_ref, size)
