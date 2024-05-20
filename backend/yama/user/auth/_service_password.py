from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.status import HTTP_401_UNAUTHORIZED

from yama.user._service import _UserDb
from yama.user._service_password import (
    hash_password,
    is_password_valid,
    should_rehash_password_with_hash,
)

from ._config import Config
from ._service_token import _TokenOut
from ._service_token_access import _make_access_token_and_expires_in
from ._service_token_refresh import _make_refresh_token

_INVALID_USERNAME_OR_PASSWORD_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid username or password."
)


class _InvalidUsernameOrPasswordError(Exception): ...


class _PasswordGrantIn(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-4.3."""

    grant_type: Literal["password"]
    username: str
    password: str
    scope: Literal[None] = None


async def _password_grant_in_to_token_out(
    password_grant_in: _PasswordGrantIn,
    /,
    *,
    settings: Config,
    connection: AsyncConnection,
) -> _TokenOut:
    query = select(_UserDb).where(
        func.lower(_UserDb.handle) == func.lower(password_grant_in.username)
    )
    row = (await connection.execute(query)).mappings().one_or_none()
    user_db = _UserDb(**row) if row is not None else None

    if (
        user_db is None
        or user_db.password_hash is None
        or not is_password_valid(password_grant_in.password, user_db.password_hash)
    ):
        raise _InvalidUsernameOrPasswordError()

    if should_rehash_password_with_hash(user_db.password_hash):
        update_password_hash = hash_password(password_grant_in.password)
        update_query = (
            update(_UserDb)
            .values(
                password_hash=update_password_hash,
            )
            .where(_UserDb.id == user_db.id)
            .returning(_UserDb)
        )
        update_row = (await connection.execute(update_query)).mappings().one_or_none()
        if update_row is None:
            ...  # TODO: Log
        await connection.commit()

    access_token, expires_in = _make_access_token_and_expires_in(
        user_db.id, settings=settings
    )
    refresh_token = _make_refresh_token(user_db.id, settings=settings)
    return _TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )
