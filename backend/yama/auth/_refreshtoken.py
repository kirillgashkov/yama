import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import DateTime, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import Mapped, mapped_column

from yama import database

from ._accesstoken import _make_access_token_and_expires_in
from ._config import Config
from ._token import _InvalidTokenError, _TokenOut


class _RefreshTokenGrantIn(BaseModel):
    """https://datatracker.ietf.org/doc/html/rfc6749#section-6."""

    grant_type: Literal["refresh_token"]
    refresh_token: str
    scope: Literal[None] = None


class _RevokedRefreshTokenDb(database.BaseTable):
    __tablename__ = "revoked_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def _make_token_out_from_refresh_token_grant_in(
    refresh_token_grant_in: _RefreshTokenGrantIn,
    /,
    *,
    config: Config,
    connection: AsyncConnection,
) -> _TokenOut:
    old_refresh_token = await _parse_refresh_token(
        refresh_token_grant_in.refresh_token, config=config, connection=connection
    )

    access_token, expires_in = _make_access_token_and_expires_in(
        old_refresh_token.user_id, config=config
    )
    new_refresh_token = _make_refresh_token(old_refresh_token.user_id, config=config)
    token_out = _TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=new_refresh_token,
    )

    await _revoke_refresh_token(old_refresh_token, connection=connection)
    return token_out


def _make_refresh_token(
    user_id: UUID,
    /,
    *,
    config: Config,
) -> str:
    now = datetime.now(UTC)
    expire_seconds = config.refresh_token.expire_seconds

    claims = {
        "sub": str(user_id),
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        claims,
        key=config.refresh_token.key,
        algorithm=config.refresh_token.algorithm,
    )


@dataclasses.dataclass
class _RefreshToken:
    id: UUID
    user_id: UUID
    expires_at: datetime


async def _parse_refresh_token(
    token: str, /, *, config: Config, connection: AsyncConnection
) -> _RefreshToken:
    try:
        claims = jwt.decode(
            token,
            key=config.refresh_token.key,
            algorithms=[config.refresh_token.algorithm],
        )
    except JWTError:
        raise _InvalidTokenError()

    id_ = UUID(claims["jti"])
    user_id = UUID(claims["sub"])
    expires_at = datetime.fromtimestamp(claims["exp"], UTC)
    if await _is_refresh_token_revoked_by_id(id_, connection=connection):
        raise _InvalidTokenError()

    return _RefreshToken(id=id_, user_id=user_id, expires_at=expires_at)


async def _is_refresh_token_revoked_by_id(
    id_: UUID, /, *, connection: AsyncConnection
) -> bool:
    query = select(exists().where(_RevokedRefreshTokenDb.id == id_))
    return (await connection.execute(query)).scalar_one()


async def _revoke_refresh_token(
    t: _RefreshToken, /, *, connection: AsyncConnection
) -> None:
    query = (
        insert(_RevokedRefreshTokenDb)
        .values(id=t.id, expires_at=t.expires_at)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await connection.execute(query)
    await connection.commit()
