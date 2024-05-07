from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypeAlias, assert_never
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, HTTPException
from jose import JWTError, jwt
from pydantic import TypeAdapter
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.status import HTTP_401_UNAUTHORIZED

from yama.database.dependencies import get_connection
from yama.model.models import ModelBase
from yama.user.auth.models import RevokedRefreshTokenDb
from yama.user.auth.utils import InvalidTokenError
from yama.user.dependencies import get_settings
from yama.user.models import UserDb
from yama.user.settings import Settings
from yama.user.utils import is_password_valid

router = APIRouter()


# https://datatracker.ietf.org/doc/html/rfc6749#section-4.3
class PasswordGrantIn(ModelBase):
    grant_type: Literal["password"]
    username: str
    password: str
    scope: Literal[None] = None


# https://datatracker.ietf.org/doc/html/rfc6749#section-6
class RefreshTokenGrantIn(ModelBase):
    grant_type: Literal["refresh_token"]
    refresh_token: str
    scope: Literal[None] = None


GrantIn: TypeAlias = PasswordGrantIn | RefreshTokenGrantIn
GrantInAdapter: TypeAdapter[GrantIn] = TypeAdapter(GrantIn)


def get_grant_in(
    *,
    grant_type: Annotated[Literal["password"] | Literal["refresh_token"], Form()],
    username: Annotated[str | None, Form()] = None,
    password: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    scope: Annotated[Literal[None], Form()] = None,
) -> GrantIn:
    return GrantInAdapter.validate_python(
        {
            "grant_type": grant_type,
            "username": username,
            "password": password,
            "refresh_token": refresh_token,
            "scope": scope,
        }
    )


# https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
class TokenOut(ModelBase):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    refresh_token: str | None = None
    scope: Literal[None] = None


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


@router.post("/auth")
async def authorize(
    *,
    grant_in: Annotated[GrantIn, Depends(get_grant_in)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> TokenOut:
    match grant_in:
        case PasswordGrantIn():
            return await password_grant_in_to_token_out(
                grant_in, settings=settings, connection=connection
            )
        case RefreshTokenGrantIn():
            return await refresh_token_grant_in_to_token_out(
                grant_in, settings=settings, connection=connection
            )
        case _:
            assert_never(grant_in)


@router.post("/unauth")
async def unauthorize() -> ...: ...
