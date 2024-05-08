from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama_database__", env_nested_delimiter="__"
    )

    host: str
    port: int
    database: str
    username: str
    password: str
