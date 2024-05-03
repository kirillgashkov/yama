from typing import assert_never

from yama.file.driver.utils import Driver, FileSystemDriver
from yama.file.settings import FileSystemDriverSettings, Settings


async def get_driver(*, settings: Settings) -> Driver:
    match settings.driver:
        case FileSystemDriverSettings(file_system_dir=file_system_dir):
            return FileSystemDriver(file_system_dir=file_system_dir)
        case _:
            assert_never(settings.driver)
