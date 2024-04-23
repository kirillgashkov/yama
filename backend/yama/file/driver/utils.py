from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol
from uuid import UUID

import aiofiles


# Satisfied by fastapi.UploadFile and aiofiles's files
class AsyncReadable(Protocol):
    async def read(self, size: int = ..., /) -> bytes:
        ...


class Driver(ABC):
    @abstractmethod
    async def read_regular_content(self, id_: UUID, /) -> AsyncIterator[AsyncReadable]:
        ...

    @abstractmethod
    async def write_regular_content(
        self, content_stream: AsyncReadable, id_: UUID, /
    ) -> int:
        ...

    @abstractmethod
    async def remove_regular_content(self, id_: UUID, /) -> None:
        ...


class FileSystemDriver(Driver):
    def __init__(
        self, /, *, chunk_size: int, file_system_dir: Path, max_file_size: int
    ) -> None:
        self.chunk_size = chunk_size
        self.file_system_dir = file_system_dir
        self.max_file_size = max_file_size

    async def read_regular_content(self, id_: UUID, /) -> AsyncIterator[AsyncReadable]:
        ...

    async def write_regular_content(
        self, content_stream: AsyncReadable, id_: UUID, /
    ) -> int:
        self.file_system_dir.mkdir(parents=True, exist_ok=True)

        incomplete_path = _id_to_incomplete_path(
            id_, file_system_dir=self.file_system_dir
        )
        complete_path = _id_to_path(id_, file_system_dir=self.file_system_dir)

        try:
            file_size = 0
            async with aiofiles.open(incomplete_path, "wb") as f:
                while chunk := await content_stream.read(self.chunk_size):
                    file_size += len(chunk)

                    if file_size > self.max_file_size:
                        raise FileTooLargeError()

                    await f.write(chunk)

            incomplete_path.rename(complete_path)
        finally:
            incomplete_path.unlink(missing_ok=True)

        return file_size

    async def remove_regular_content(self, id_: UUID, /) -> None:
        ...


def _id_to_path(id_: UUID, /, *, file_system_dir: Path) -> Path:
    return file_system_dir / id_.hex


def _id_to_incomplete_path(id_: UUID, /, *, file_system_dir: Path) -> Path:
    return file_system_dir / (id_.hex + ".incomplete")


class FileTooLargeError(Exception):
    ...
