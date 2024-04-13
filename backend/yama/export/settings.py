from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama_export_")

    latexmk_executable: Path = Path("latexmk")
    pandoc_executable: Path = Path("pandoc")
