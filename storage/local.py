"""
Local file storage provider.
Serves files from a local directory. Useful for development and testing.
"""
import os
import aiofiles
from typing import AsyncGenerator, Optional
from storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider."""

    def __init__(self, base_dir: str = "./media"):
        self._base_dir = os.path.abspath(base_dir)
        os.makedirs(self._base_dir, exist_ok=True)
        self._size_cache = {}

    @property
    def provider_name(self) -> str:
        return "Local"

    @property
    def max_file_size(self) -> int:
        return 0  # Unlimited

    @property
    def is_connected(self) -> bool:
        return os.path.isdir(self._base_dir)

    async def get_file_size(self, file_ref: str) -> int:
        if file_ref in self._size_cache:
            return self._size_cache[file_ref]
        path = os.path.join(self._base_dir, file_ref)
        if not os.path.exists(path):
            return 0
        size = os.path.getsize(path)
        self._size_cache[file_ref] = size
        return size

    async def stream_file(self, file_ref: str, offset: int = 0,
                          end: Optional[int] = None) -> AsyncGenerator[bytes, None]:
        path = os.path.join(self._base_dir, file_ref)
        if not os.path.exists(path):
            return
        chunk_size = 1024 * 1024  # 1MB chunks
        async with aiofiles.open(path, 'rb') as f:
            if offset > 0:
                await f.seek(offset)
            bytes_read = 0
            max_bytes = (end - offset) if end else None
            while True:
                read_size = chunk_size
                if max_bytes is not None:
                    read_size = min(chunk_size, max_bytes - bytes_read)
                    if read_size <= 0:
                        break
                chunk = await f.read(read_size)
                if not chunk:
                    break
                bytes_read += len(chunk)
                yield chunk

    def cache_file_size(self, file_ref: str, size: int):
        self._size_cache[file_ref] = size
