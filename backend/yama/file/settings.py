from pathlib import Path
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_FILE_NAME_LENGTH = 255
MAX_FILE_PATH_LENGTH = 4095


class FileSystemDriverSettings(BaseSettings):
    type: Literal["file-system"]
    file_system_dir: Path
    chunk_size: int = 1024 * 1024 * 10  # 10 MiB
    max_file_size: int = 1024 * 1024 * 512  # 512 MiB


DriverSettings: TypeAlias = FileSystemDriverSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama_file_")

    driver: DriverSettings
    root_file_id: UUID
