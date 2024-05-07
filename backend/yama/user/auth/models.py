from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.model.models import ModelBase


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
