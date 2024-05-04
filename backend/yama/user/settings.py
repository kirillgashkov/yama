from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_HANDLE_LENGTH = 1
MAX_HANDLE_LENGTH = 255


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama_user__")

    public_user_id: UUID
