from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy.orm import Mapped, mapped_column
from starlette.status import HTTP_401_UNAUTHORIZED

from yama.database.models import TableBase
from yama.model.models import ModelBase

INVALID_USERNAME_OR_PASSWORD_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid username or password."
)

INVALID_TOKEN_EXCEPTION = HTTPException(
    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token."
)


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


# https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
class TokenOut(ModelBase):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    refresh_token: str | None = None
    scope: Literal[None] = None


class RevokedRefreshTokenDb(TableBase):
    __tablename__ = "revoked_refresh_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime]
