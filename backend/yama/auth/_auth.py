from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from ._accesstoken import _get_user_id_from_access_token
from ._config import Config, get_config
from ._token import _INVALID_TOKEN_EXCEPTION, _InvalidTokenError

_get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/auth")
_get_oauth2_token_or_none = OAuth2PasswordBearer(tokenUrl="/auth", auto_error=False)


def get_current_user_id(
    *,
    token: Annotated[str, Depends(_get_oauth2_token)],
    config: Annotated[Config, Depends(get_config)],
) -> UUID:
    """A dependency."""
    try:
        return _get_user_id_from_access_token(token, config=config)
    except _InvalidTokenError:
        raise _INVALID_TOKEN_EXCEPTION


def get_current_user_id_or_none(
    *,
    token: Annotated[str | None, Depends(_get_oauth2_token_or_none)],
    config: Annotated[Config, Depends(get_config)],
) -> UUID | None:
    """A dependency."""
    if token is None:
        return None
    try:
        return _get_user_id_from_access_token(token, config=config)
    except _InvalidTokenError:
        return None
