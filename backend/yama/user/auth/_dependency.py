from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from starlette.requests import Request

from yama.user.auth import Config
from yama.user.auth._access_token import get_user_id_from_access_token
from yama.user.auth._exception import INVALID_TOKEN_EXCEPTION, InvalidTokenError

_get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/auth")
_get_oauth2_token_or_none = OAuth2PasswordBearer(tokenUrl="/auth", auto_error=False)


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.user_auth_settings  # type: ignore[no-any-return]


def get_current_user_id(
    *,
    token: Annotated[str, Depends(_get_oauth2_token)],
    settings: Annotated[Config, Depends(get_config)],
) -> UUID:
    """A dependency."""
    try:
        return get_user_id_from_access_token(token, settings=settings)
    except InvalidTokenError:
        raise INVALID_TOKEN_EXCEPTION


def get_current_user_id_or_none(
    *,
    token: Annotated[str | None, Depends(_get_oauth2_token_or_none)],
    settings: Annotated[Config, Depends(get_config)],
) -> UUID | None:
    """A dependency."""
    if token is None:
        return None
    try:
        return get_user_id_from_access_token(token, settings=settings)
    except InvalidTokenError:
        return None
