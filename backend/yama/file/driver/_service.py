from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator, Protocol, assert_never
from uuid import UUID

from fastapi import Depends
from starlette.requests import Request
from typing_extensions import override

from ._config import Config
from ._service_file_system import FileSystemDriver


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.file_driver_settings  # type: ignore[no-any-return]


class DriverFileError(Exception): ...


class DriverFileTooLargeError(DriverFileError): ...


class DriverFileNotFoundError(DriverFileError):
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


def get_driver(*, settings: Annotated[Config, Depends(get_config)]) -> Driver:
    """A dependency."""
    match settings.type:
        case "file-system":
            return FileSystemDriver(file_system_dir=settings.file_system_dir)
        case _:
            assert_never(settings.driver)
