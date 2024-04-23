from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID


# Satisfied by fastapi.UploadFile and aiofiles's files
class AsyncReadable(Protocol):
    async def read(self, size: int = ..., /) -> bytes:
        ...


class Driver(ABC):
    @abstractmethod
    async def read_regular(self, id_: UUID, /) -> AsyncReadable:
        ...

    @abstractmethod
    async def write_regular(self, content: AsyncReadable, id_: UUID, /) -> int:
        ...

    @abstractmethod
    async def remove_regular(self, id_: UUID, /) -> None:
        ...


class FileSystemDriver(Driver):
    async def read_regular(self, id_: UUID, /) -> AsyncReadable:
        ...

    async def write_regular(self, content: AsyncReadable, id_: UUID, /) -> int:
        ...

    async def remove_regular(self, id_: UUID, /) -> None:
        ...
