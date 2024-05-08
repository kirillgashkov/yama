from pathlib import Path

from pydantic_settings import BaseSettings


class ProvisionSettings(BaseSettings):
    database: str
    username: str
    password: str
    migrate_executable: Path
