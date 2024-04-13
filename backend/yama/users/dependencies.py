from fastapi import Request

from yama.users.settings import Settings


# `get_settings()` is a lifetime dependency that provides
# `Settings` created by the lifespan
async def get_settings(request: Request) -> Settings:
    return request.state.users_settings  # type: ignore[no-any-return]
