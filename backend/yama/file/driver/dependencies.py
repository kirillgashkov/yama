from typing import Annotated, assert_never

from fastapi import Depends

from yama.file.dependencies import get_settings
from yama.file.driver.utils import Driver, FileSystemDriver
from yama.file.settings import FileSystemDriverSettings, Settings


async def get_driver(*, settings: Annotated[Settings, Depends(get_settings)]) -> Driver:
    match settings.driver:
        case FileSystemDriverSettings(file_system_dir=file_system_dir):
            return FileSystemDriver(file_system_dir=file_system_dir)
        case _:
            assert_never(settings.driver)
