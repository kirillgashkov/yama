from pathlib import Path

from pydantic_settings import BaseSettings


class ProvisionSettings(BaseSettings):
    username: str
    password: str
    database: str
    migrate_executable: Path
    migrate_migrations_dir: Path


class Settings(BaseSettings):
    host: str
    port: int
    username: str
    password: str
    database: str

    provision: ProvisionSettings | None = None
