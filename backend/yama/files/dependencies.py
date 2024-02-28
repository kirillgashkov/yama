from fastapi import Request

from yama.files.settings import Settings


# `get_settings()` is a lifetime dependency that provides
# `Settings` created by the lifespan
async def get_settings(request: Request) -> Settings:
    return request.state.files_settings  # type: ignore[no-any-return]
