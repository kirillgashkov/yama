from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama__database__provision__",
    )

    database: str
    username: str
    password: str
    migrate_executable: Path
