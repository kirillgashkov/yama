from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, Protocol
from uuid import UUID

from typing_extensions import override


class DriverFileTooLargeError(Exception): ...


class DriverFileNotFoundError(Exception):
    def __init__(self, id_: UUID, /) -> None:
        super().__init__()
        self.id_ = id_

    @override
    def __str__(self) -> str:
        return f"{self.id_}"


class AsyncReadable(Protocol):
    async def read(self, size: int = ..., /) -> bytes: ...


class Driver(ABC):
    @abstractmethod
    @asynccontextmanager
    def read_regular_content(self, id_: UUID, /) -> AsyncIterator[AsyncReadable]: ...

    @abstractmethod
    async def write_regular_content(
        self,
        content_stream: AsyncReadable,
        id_: UUID,
        /,
        *,
        chunk_size: int,
        max_file_size: int,
    ) -> int: ...

    @abstractmethod
    async def remove_regular_content(self, id_: UUID, /) -> None: ...
