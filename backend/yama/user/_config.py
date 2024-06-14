from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__user__")

    public_user_id: UUID


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.user_settings  # type: ignore[no-any-return]
