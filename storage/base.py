"""
Abstract base class for storage providers.
All providers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class StorageProvider(ABC):
    """Abstract storage provider interface."""

    @abstractmethod
    async def get_file_size(self, file_ref: str) -> int:
        """Get file size in bytes."""

    @abstractmethod
    async def stream_file(self, file_ref: str, offset: int = 0,
                          end: Optional[int] = None) -> AsyncGenerator[bytes, None]:
        """Stream file content as async byte generator."""

    @abstractmethod
    def cache_file_size(self, file_ref: str, size: int):
        """Cache a known file size."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def max_file_size(self) -> int:
        """Maximum file size supported (0 = unlimited)."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the provider is currently connected."""
