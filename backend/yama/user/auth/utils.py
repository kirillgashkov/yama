from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.status import HTTP_401_UNAUTHORIZED

from yama.user.auth.models import (
    PasswordGrantIn,
    RefreshTokenGrantIn,
    RevokedRefreshTokenDb,
    TokenOut,
)
from yama.user.models import UserDb
from yama.user.settings import Settings
from yama.user.utils import is_password_valid


async def password_grant_in_to_token_out(
    password_grant_in: PasswordGrantIn,
    /,
    *,
    settings: Settings,
    connection: AsyncConnection,
) -> TokenOut:
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
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Invalid username or password."
        )

    access_token, expires_in = make_access_token_and_expires_in(
        user_db.id, settings=settings
    )
    refresh_token = make_refresh_token(user_db.id, settings=settings)
    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )


async def refresh_token_grant_in_to_token_out(
    refresh_token_grant_in: RefreshTokenGrantIn,
    /,
    *,
    settings: Settings,
    connection: AsyncConnection,
) -> TokenOut:
    try:
        refresh_token_id, user_id, refresh_token_expires_at = (
            refresh_token_to_id_and_user_id_and_expires_at(
                refresh_token_grant_in.refresh_token, settings=settings
            )
        )
        await check_refresh_token_is_not_revoked_by_id(
            refresh_token_id, connection=connection
        )
    except InvalidTokenError:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    access_token, expires_in = make_access_token_and_expires_in(
        user_id, settings=settings
    )
    new_refresh_token = make_refresh_token(user_id, settings=settings)
    token_out = TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=new_refresh_token,
    )

    await ensure_refresh_token_is_revoked_by_id(
        refresh_token_id, expires_at=refresh_token_expires_at, connection=connection
    )
    return token_out


def make_access_token_and_expires_in(
    user_id: UUID,
    /,
    *,
    settings: Settings,
) -> tuple[str, int]:
    now = datetime.now(UTC)
    expire_seconds = settings.auth.access_token.expire_seconds

    claims = {
        "sub": str(user_id),
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
    }

    token = jwt.encode(
        claims,
        key=settings.auth.access_token.key,
        algorithm=settings.auth.access_token.algorithm,
    )
    return token, expire_seconds


def make_refresh_token(
    user_id: UUID,
    /,
    *,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    expire_seconds = settings.auth.refresh_token.expire_seconds

    claims = {
        "sub": str(user_id),
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        claims,
        key=settings.auth.refresh_token.key,
        algorithm=settings.auth.refresh_token.algorithm,
    )


def access_token_to_user_id(token: str, /, *, settings: Settings) -> UUID:
    try:
        claims = jwt.decode(
            token,
            key=settings.auth.access_token.key,
            algorithms=[settings.auth.access_token.algorithm],
        )
    except JWTError:
        raise InvalidTokenError()

    return UUID(claims["sub"])


def refresh_token_to_id_and_user_id_and_expires_at(
    token: str, /, *, settings: Settings
) -> tuple[UUID, UUID, datetime]:
    try:
        claims = jwt.decode(
            token,
            key=settings.auth.refresh_token.key,
            algorithms=[settings.auth.refresh_token.algorithm],
        )
    except JWTError:
        raise InvalidTokenError()

    return (
        UUID(claims["jti"]),
        UUID(claims["sub"]),
        datetime.fromtimestamp(claims["exp"], UTC),
    )


async def check_refresh_token_is_not_revoked_by_id(
    id_: UUID,
    /,
    *,
    connection: AsyncConnection,
) -> None:
    query = select(exists().where(RevokedRefreshTokenDb.id == id_))
    is_revoked = (await connection.execute(query)).scalar_one()
    if is_revoked:
        raise InvalidTokenError()


async def ensure_refresh_token_is_revoked_by_id(
    id_: UUID,
    /,
    *,
    expires_at: datetime,
    connection: AsyncConnection,
) -> None:
    query = (
        insert(RevokedRefreshTokenDb)
        .values(id=id_, expires_at=expires_at)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await connection.execute(query)
    await connection.commit()


class InvalidTokenError(Exception): ...
