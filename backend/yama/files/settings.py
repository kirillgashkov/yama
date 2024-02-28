from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama_files_")

    files_dir: Path
    root_file_id: UUID
    max_chunk_size: int = 1024 * 1024 * 10  # 10 MiB
    max_file_size: int = 1024 * 1024 * 512  # 512 MiB
