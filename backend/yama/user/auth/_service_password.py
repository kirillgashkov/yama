from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.status import HTTP_401_UNAUTHORIZED

from yama.user._service import UserDb
from yama.user._service_password import (
    hash_password,
    is_password_valid,
    should_rehash_password_with_hash,
)
from yama.user.auth import Config
from yama.user.auth._router import PasswordGrantIn, _TokenOut
from yama.user.auth._service_token_access import make_access_token_and_expires_in
from yama.user.auth._service_token_refresh import make_refresh_token

INVALID_USERNAME_OR_PASSWORD_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid username or password."
)


class InvalidUsernameOrPasswordError(Exception): ...


async def password_grant_in_to_token_out(
    password_grant_in: PasswordGrantIn,
    /,
    *,
    settings: Config,
    connection: AsyncConnection,
) -> _TokenOut:
    query = select(UserDb).where(
        func.lower(UserDb.handle) == func.lower(password_grant_in.username)
    )
    row = (await connection.execute(query)).mappings().one_or_none()
    user_db = UserDb(**row) if row is not None else None

    if (
        user_db is None
        or user_db.password_hash is None
        or not is_password_valid(password_grant_in.password, user_db.password_hash)
    ):
        raise InvalidUsernameOrPasswordError()

    if should_rehash_password_with_hash(user_db.password_hash):
        update_password_hash = hash_password(password_grant_in.password)
        update_query = (
            update(UserDb)
            .values(
                password_hash=update_password_hash,
            )
            .where(UserDb.id == user_db.id)
            .returning(UserDb)
        )
        update_row = (await connection.execute(update_query)).mappings().one_or_none()
        if update_row is None:
            ...  # TODO: Log
        await connection.commit()

    access_token, expires_in = make_access_token_and_expires_in(
        user_db.id, settings=settings
    )
    refresh_token = make_refresh_token(user_db.id, settings=settings)
    return _TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )
