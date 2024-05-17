from pydantic_settings import BaseSettings, SettingsConfigDict


class TokenConfig(BaseSettings):
    algorithm: str = "HS256"
    key: str
    expire_seconds: int


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama__user__auth__", env_nested_delimiter="__"
    )

    access_token: TokenConfig
    refresh_token: TokenConfig
