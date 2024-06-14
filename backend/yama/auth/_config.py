from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request


class TokenConfig(BaseSettings):
    algorithm: str = "HS256"
    key: str
    expire_seconds: int


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yama__auth__", env_nested_delimiter="__"
    )

    access_token: TokenConfig
    refresh_token: TokenConfig


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.auth_config  # type: ignore[no-any-return]
