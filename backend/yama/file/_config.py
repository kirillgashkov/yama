from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request


class DriverConfig(BaseSettings):
    type: Literal["file-system"]
    file_system_dir: Path


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama__file__", env_nested_delimiter="__"
    )

    chunk_size: int = 1024 * 1024 * 10  # 10 MiB
    max_file_size: int = 1024 * 1024 * 512  # 512 MiB
    files_base_url: str
    root_file_id: UUID

    driver: DriverConfig


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.file_config  # type: ignore[no-any-return]
