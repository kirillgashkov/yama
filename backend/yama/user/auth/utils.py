from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.auth.models import (
    PasswordGrantIn,
    RefreshTokenGrantIn,
    RevokedRefreshTokenDb,
    TokenOut,
)
from yama.user.models import UserDb
from yama.user.config import Config
from yama.user.utils import is_password_valid


async def password_grant_in_to_token_out(
    password_grant_in: PasswordGrantIn,
    /,
    *,
    settings: Config,
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
        raise InvalidUsernameOrPasswordError()

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
    settings: Config,
    connection: AsyncConnection,
) -> TokenOut:
    (
        refresh_token_id,
        user_id,
        refresh_token_expires_at,
    ) = await refresh_token_to_id_and_user_id_and_expires_at(
        refresh_token_grant_in.refresh_token, settings=settings, connection=connection
    )

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
    settings: Config,
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
    settings: Config,
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


def access_token_to_user_id(token: str, /, *, settings: Config) -> UUID:
    try:
        claims = jwt.decode(
            token,
            key=settings.auth.access_token.key,
            algorithms=[settings.auth.access_token.algorithm],
        )
    except JWTError:
        raise InvalidTokenError()

    return UUID(claims["sub"])


async def refresh_token_to_id_and_user_id_and_expires_at(
    token: str, /, *, settings: Config, connection: AsyncConnection
) -> tuple[UUID, UUID, datetime]:
    try:
        claims = jwt.decode(
            token,
            key=settings.auth.refresh_token.key,
            algorithms=[settings.auth.refresh_token.algorithm],
        )
    except JWTError:
        raise InvalidTokenError()

    id_ = UUID(claims["jti"])
    user_id = UUID(claims["sub"])
    expires_at = datetime.fromtimestamp(claims["exp"], UTC)
    if await _is_refresh_token_revoked_by_id(id_, connection=connection):
        raise InvalidTokenError()

    return id_, user_id, expires_at


async def _is_refresh_token_revoked_by_id(
    id_: UUID,
    /,
    *,
    connection: AsyncConnection,
) -> bool:
    query = select(exists().where(RevokedRefreshTokenDb.id == id_))
    return (await connection.execute(query)).scalar_one()


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


class InvalidUsernameOrPasswordError(Exception): ...


class InvalidTokenError(Exception): ...
