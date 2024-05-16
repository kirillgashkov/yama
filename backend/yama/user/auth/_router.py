from typing import Annotated, assert_never

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.user.auth.dependencies import get_grant_in, get_settings
from yama.user.auth.models import (
    INVALID_TOKEN_EXCEPTION,
    INVALID_USERNAME_OR_PASSWORD_EXCEPTION,
    GrantIn,
    PasswordGrantIn,
    RefreshTokenGrantIn,
    TokenOut,
)
from yama.user.auth.utils import (
    InvalidTokenError,
    InvalidUsernameOrPasswordError,
    ensure_refresh_token_is_revoked_by_id,
    password_grant_in_to_token_out,
    refresh_token_grant_in_to_token_out,
    refresh_token_to_id_and_user_id_and_expires_at,
)

from ._config import Config

router = APIRouter()


@router.post("/auth")
async def authorize(
    *,
    grant_in: Annotated[GrantIn, Depends(get_grant_in)],
    settings: Annotated[Config, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> TokenOut:
    match grant_in:
        case PasswordGrantIn():
            try:
                return await password_grant_in_to_token_out(
                    grant_in, settings=settings, connection=connection
                )
            except InvalidUsernameOrPasswordError:
                raise INVALID_USERNAME_OR_PASSWORD_EXCEPTION
        case RefreshTokenGrantIn():
            try:
                return await refresh_token_grant_in_to_token_out(
                    grant_in, settings=settings, connection=connection
                )
            except InvalidTokenError:
                raise INVALID_TOKEN_EXCEPTION
        case _:
            assert_never(grant_in)


@router.post("/unauth")
async def unauthorize(
    *,
    refresh_token: Annotated[str, Form()],
    settings: Annotated[Config, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    try:
        id_, _, expires_at = await refresh_token_to_id_and_user_id_and_expires_at(
            refresh_token, settings=settings, connection=connection
        )
    except InvalidTokenError:
        raise INVALID_TOKEN_EXCEPTION

    await ensure_refresh_token_is_revoked_by_id(
        id_, expires_at=expires_at, connection=connection
    )
