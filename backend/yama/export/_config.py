from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__export__")

    latexmk_executable: Path = Path("latexmk")
    pandoc_executable: Path = Path("pandoc")
