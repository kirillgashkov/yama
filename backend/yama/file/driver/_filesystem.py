from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

import aiofiles.os
from typing_extensions import override

from ._base import (
    AsyncReadable,
    Driver,
    DriverFileNotFoundError,
    DriverFileTooLargeError,
)


class FileSystemDriver(Driver):
    def __init__(self, /, *, file_system_dir: Path) -> None:
        super().__init__()
        self.file_system_dir = file_system_dir

    @override
    @asynccontextmanager
    async def read_regular_content(self, id_: UUID, /) -> AsyncIterator[AsyncReadable]:
        path = _id_to_path(id_, file_system_dir=self.file_system_dir)

        try:
            async with aiofiles.open(path, "rb") as f:
                yield f
        except FileNotFoundError as e:
            raise DriverFileNotFoundError(id_) from e

    @override
    async def write_regular_content(
        self,
        content_stream: AsyncReadable,
        id_: UUID,
        /,
        *,
        chunk_size: int,
        max_file_size: int,
    ) -> int:
        await aiofiles.os.makedirs(self.file_system_dir, exist_ok=True)

        incomplete_path = _id_to_incomplete_path(
            id_, file_system_dir=self.file_system_dir
        )
        complete_path = _id_to_path(id_, file_system_dir=self.file_system_dir)

        try:
            file_size = 0
            async with aiofiles.open(incomplete_path, "wb") as f:
                while chunk := await content_stream.read(chunk_size):
                    file_size += len(chunk)

                    if file_size > max_file_size:
                        raise DriverFileTooLargeError()

                    _ = await f.write(chunk)

            _ = incomplete_path.rename(complete_path)
        finally:
            incomplete_path.unlink(missing_ok=True)

        return file_size

    @override
    async def remove_regular_content(self, id_: UUID, /) -> None:
        path = _id_to_path(id_, file_system_dir=self.file_system_dir)

        try:
            await aiofiles.os.remove(path)
        except FileNotFoundError as e:
            raise DriverFileNotFoundError(id_) from e


def _id_to_path(id_: UUID, /, *, file_system_dir: Path) -> Path:
    return file_system_dir / id_.hex


def _id_to_incomplete_path(id_: UUID, /, *, file_system_dir: Path) -> Path:
    return file_system_dir / (id_.hex + ".incomplete")
