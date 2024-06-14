from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__file__driver__")

    type: Literal["file-system"]
    file_system_dir: Path


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.file_driver_settings  # type: ignore[no-any-return]
