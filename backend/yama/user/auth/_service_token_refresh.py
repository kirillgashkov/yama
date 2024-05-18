import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt
from sqlalchemy import DateTime, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import Mapped, mapped_column

from yama import database
from yama.user.auth import Config

from ._router import RefreshTokenGrantIn, _TokenOut
from ._service_token import InvalidTokenError
from ._service_token_access import make_access_token_and_expires_in


class RevokedRefreshTokenDb(database.BaseTable):
    __tablename__ = "revoked_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def make_token_out_from_refresh_token_grant_in(
    refresh_token_grant_in: RefreshTokenGrantIn,
    /,
    *,
    settings: Config,
    connection: AsyncConnection,
) -> _TokenOut:
    old_refresh_token = await parse_refresh_token(
        refresh_token_grant_in.refresh_token, settings=settings, connection=connection
    )

    access_token, expires_in = make_access_token_and_expires_in(
        old_refresh_token.user_id, settings=settings
    )
    new_refresh_token = make_refresh_token(old_refresh_token.user_id, settings=settings)
    token_out = _TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=new_refresh_token,
    )

    await revoke_refresh_token(old_refresh_token, connection=connection)
    return token_out


def make_refresh_token(
    user_id: UUID,
    /,
    *,
    settings: Config,
) -> str:
    now = datetime.now(UTC)
    expire_seconds = settings.refresh_token.expire_seconds

    claims = {
        "sub": str(user_id),
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        claims,
        key=settings.refresh_token.key,
        algorithm=settings.refresh_token.algorithm,
    )


@dataclasses.dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    expires_at: datetime


async def parse_refresh_token(
    token: str, /, *, settings: Config, connection: AsyncConnection
) -> RefreshToken:
    try:
        claims = jwt.decode(
            token,
            key=settings.refresh_token.key,
            algorithms=[settings.refresh_token.algorithm],
        )
    except JWTError:
        raise InvalidTokenError()

    id_ = UUID(claims["jti"])
    user_id = UUID(claims["sub"])
    expires_at = datetime.fromtimestamp(claims["exp"], UTC)
    if await _is_refresh_token_revoked_by_id(id_, connection=connection):
        raise InvalidTokenError()

    return RefreshToken(id=id_, user_id=user_id, expires_at=expires_at)


async def _is_refresh_token_revoked_by_id(
    id_: UUID, /, *, connection: AsyncConnection
) -> bool:
    query = select(exists().where(RevokedRefreshTokenDb.id == id_))
    return (await connection.execute(query)).scalar_one()


async def revoke_refresh_token(
    t: RefreshToken, /, *, connection: AsyncConnection
) -> None:
    query = (
        insert(RevokedRefreshTokenDb)
        .values(id=t.id, expires_at=t.expires_at)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await connection.execute(query)
    await connection.commit()
