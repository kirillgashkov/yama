from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from yama.user.auth.models import INVALID_TOKEN_EXCEPTION
from yama.user.auth.utils import InvalidTokenError, access_token_to_user_id
from yama.user.settings import Settings


# get_settings is a lifetime dependency that provides Settings created by the lifespan.
async def get_settings(*, request: Request) -> Settings:
    return request.state.user_settings  # type: ignore[no-any-return]


_get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/auth")
_get_oauth2_token_or_none = OAuth2PasswordBearer(tokenUrl="/auth", auto_error=False)


def get_current_user_id(
    *,
    token: Annotated[str, Depends(_get_oauth2_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    try:
        return access_token_to_user_id(token, settings=settings)
    except InvalidTokenError:
        raise INVALID_TOKEN_EXCEPTION


def get_current_user_id_or_none(
    *,
    token: Annotated[str | None, Depends(_get_oauth2_token_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID | None:
    if token is None:
        return None
    try:
        return access_token_to_user_id(token, settings=settings)
    except InvalidTokenError:
        return None
