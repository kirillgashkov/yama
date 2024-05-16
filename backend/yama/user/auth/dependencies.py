from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from yama.user.auth.config import Config
from yama.user.auth.models import INVALID_TOKEN_EXCEPTION, GrantIn, GrantInAdapter
from yama.user.auth.utils import InvalidTokenError, access_token_to_user_id


# get_settings is a lifetime dependency that provides Settings created by the lifespan.
def get_settings(*, request: Request) -> Config:
    return request.state.user_auth_settings  # type: ignore[no-any-return]


def get_grant_in(
    *,
    grant_type: Annotated[Literal["password"] | Literal["refresh_token"], Form()],
    username: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    scope: Annotated[Literal[None], Form()] = None,
) -> GrantIn:
    try:
        return GrantInAdapter.validate_python(
            {
                "grant_type": grant_type,
                "username": username,
                "password": password,
                "refresh_token": refresh_token,
                "scope": scope,
            }
        )
    except ValidationError:
        raise HTTPException(400, "Invalid grant.")


_get_oauth2_token = OAuth2PasswordBearer(tokenUrl="/auth")
_get_oauth2_token_or_none = OAuth2PasswordBearer(tokenUrl="/auth", auto_error=False)


def get_current_user_id(
    *,
    token: Annotated[str, Depends(_get_oauth2_token)],
    settings: Annotated[Config, Depends(get_settings)],
) -> UUID:
    try:
        return access_token_to_user_id(token, settings=settings)
    except InvalidTokenError:
        raise INVALID_TOKEN_EXCEPTION


def get_current_user_id_or_none(
    *,
    token: Annotated[str | None, Depends(_get_oauth2_token_or_none)],
    settings: Annotated[Config, Depends(get_settings)],
) -> UUID | None:
    if token is None:
        return None
    try:
        return access_token_to_user_id(token, settings=settings)
    except InvalidTokenError:
        return None
