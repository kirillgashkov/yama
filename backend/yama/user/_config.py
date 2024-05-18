from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__user__")

    public_user_id: UUID
