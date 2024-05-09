from fastapi import Request

from yama.user.settings import Settings


# get_settings is a lifetime dependency that provides Settings created by the lifespan.
def get_settings(*, request: Request) -> Settings:
    return request.state.user_settings  # type: ignore[no-any-return]
