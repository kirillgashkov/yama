from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_HANDLE_LENGTH = 1
MAX_HANDLE_LENGTH = 255


class TokenSettings(BaseSettings):
    algorithm: str = "HS256"
    key: str
    expire_seconds: int


class AuthSettings(BaseSettings):
    access_token: TokenSettings
    refresh_token: TokenSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama_user__")

    public_user_id: UUID
    auth: AuthSettings
