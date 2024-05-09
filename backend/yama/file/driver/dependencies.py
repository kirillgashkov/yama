from typing import Annotated, assert_never

from fastapi import Depends, Request

from yama.file.driver.settings import Settings
from yama.file.driver.utils import Driver, FileSystemDriver


# get_settings is a lifetime dependency that provides Settings created by the lifespan.
def get_settings(*, request: Request) -> Settings:
    return request.state.file_driver_settings  # type: ignore[no-any-return]


async def get_driver(*, settings: Annotated[Settings, Depends(get_settings)]) -> Driver:
    match settings.type:
        case "file-system":
            return FileSystemDriver(file_system_dir=settings.file_system_dir)
        case _:
            assert_never(settings.driver)
