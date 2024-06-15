from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama__database__", env_nested_delimiter="__"
    )

    host: str
    port: int
    database: str
    username: str
    password: str
