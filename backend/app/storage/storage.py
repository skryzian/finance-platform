from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, *, file_name: str, content: BinaryIO, content_type: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, *, file_name: str) -> None:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str = ".storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload_file(self, *, file_name: str, content: BinaryIO, content_type: str) -> str:
        target = self.base_path / file_name
        with target.open("wb") as file:
            file.write(content.read())
        return str(target)

    def delete_file(self, *, file_name: str) -> None:
        target = self.base_path / file_name
        if target.exists():
            target.unlink()


def get_storage_provider() -> StorageProvider:
    return LocalStorageProvider()
