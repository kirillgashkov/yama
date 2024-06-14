from typing import Annotated, assert_never

from fastapi import Depends

from ._base import Driver
from ._config import Config, get_config
from ._filesystem import FileSystemDriver


def get_driver(*, settings: Annotated[Config, Depends(get_config)]) -> Driver:
    """A dependency."""
    match settings.type:
        case "file-system":
            return FileSystemDriver(file_system_dir=settings.file_system_dir)
        case _:
            assert_never(settings.driver)
