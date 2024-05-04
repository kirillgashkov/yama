from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProvisionSettings(BaseSettings):
    database: str
    username: str
    password: str
    migrate_executable: Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama_database__", env_nested_delimiter="__"
    )

    host: str
    port: int
    database: str
    username: str
    password: str
    provision: ProvisionSettings | None = None
