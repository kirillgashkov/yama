from fastapi import Request

from yama.user.config import Config


# get_settings is a lifetime dependency that provides Settings created by the lifespan.
def get_settings(*, request: Request) -> Config:
    return request.state.user_settings  # type: ignore[no-any-return]
