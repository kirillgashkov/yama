from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__file__driver__")

    type: Literal["file-system"]
    file_system_dir: Path
