from typing import Annotated, Literal, TypeAlias, assert_never

from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from yama import database

from ._config import Config
from ._service import get_config
from ._service_password import (
    INVALID_USERNAME_OR_PASSWORD_EXCEPTION,
    InvalidUsernameOrPasswordError,
    password_grant_in_to_token_out,
)
from ._service_token import INVALID_TOKEN_EXCEPTION, InvalidTokenError
from ._service_token_refresh import (
    make_token_out_from_refresh_token_grant_in,
    parse_refresh_token,
    revoke_refresh_token,
)

router = APIRouter()


class PasswordGrantIn(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-4.3."""

    grant_type: Literal["password"]
    username: str
    password: str
    scope: Literal[None] = None


class RefreshTokenGrantIn(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-6."""

    grant_type: Literal["refresh_token"]
    refresh_token: str
    scope: Literal[None] = None


_GrantIn: TypeAlias = PasswordGrantIn | RefreshTokenGrantIn
_GrantInAdapter: TypeAdapter[_GrantIn] = TypeAdapter(_GrantIn)


class _TokenOut(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-5.1."""

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    refresh_token: str | None = None
    scope: Literal[None] = None


def _get_grant_in(
    *,
    grant_type: Annotated[Literal["password"] | Literal["refresh_token"], Form()],
    username: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    scope: Annotated[Literal[None], Form()] = None,
) -> _GrantIn:
    """A dependency."""
    try:
        return _GrantInAdapter.validate_python(
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


@router.post("/auth")
async def _authorize(
    *,
    grant_in: Annotated[_GrantIn, Depends(_get_grant_in)],
    settings: Annotated[Config, Depends(get_config)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
) -> _TokenOut:
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
                return await make_token_out_from_refresh_token_grant_in(
                    grant_in, settings=settings, connection=connection
                )
            except InvalidTokenError:
                raise INVALID_TOKEN_EXCEPTION
        case _:
            assert_never(grant_in)


@router.post("/unauth")
async def _unauthorize(
    *,
    refresh_token: Annotated[str, Form()],
    settings: Annotated[Config, Depends(get_config)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
) -> None:
    try:
        t = await parse_refresh_token(
            refresh_token, settings=settings, connection=connection
        )
    except InvalidTokenError:
        raise INVALID_TOKEN_EXCEPTION

    await revoke_refresh_token(t, connection=connection)
