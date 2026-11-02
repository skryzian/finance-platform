from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class StorageUnavailable(RuntimeError):
    pass


class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, *, file_name: str, content: BinaryIO, content_type: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, *, file_name: str) -> None:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str = ".storage"):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload_file(self, *, file_name: str, content: BinaryIO, content_type: str) -> str:
        target = (self.base_path / file_name).resolve()
        if not target.is_relative_to(self.base_path):
            raise ValueError("Storage path must remain inside the configured storage directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as file:
            file.write(content.read())
        return str(target)

    def delete_file(self, *, file_name: str) -> None:
        target = (self.base_path / file_name).resolve()
        if not target.is_relative_to(self.base_path):
            raise ValueError("Storage path must remain inside the configured storage directory")
        if target.exists():
            target.unlink()


def get_storage_provider() -> StorageProvider:
    if settings.storage_provider.lower() != "local":
        raise StorageUnavailable("Configured storage provider is not available")
    return LocalStorageProvider()
