from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.requests import Request


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="yama__function__")

    # The user ID used to save the output files as.
    output_user_id: UUID
    # The file ID of a directory used to save the output files to.
    output_file_id: UUID


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.function_config  # type: ignore[no-any-return]
