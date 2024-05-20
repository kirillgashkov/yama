from typing import Annotated, assert_never

from fastapi import Depends
from starlette.requests import Request

from ._config import Config
from ._service_base import Driver
from ._service_file_system import FileSystemDriver


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.file_driver_settings  # type: ignore[no-any-return]


def get_driver(*, settings: Annotated[Config, Depends(get_config)]) -> Driver:
    """A dependency."""
    match settings.type:
        case "file-system":
            return FileSystemDriver(file_system_dir=settings.file_system_dir)
        case _:
            assert_never(settings.driver)
