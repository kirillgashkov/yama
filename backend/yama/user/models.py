from enum import Enum
from typing import Literal
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.model.models import ModelBase


class UserType(str, Enum):
    USER = "user"
    GROUP = "group"


class UserOut(ModelBase):
    id: UUID
    type: UserType
    handle: str


class UserCreateIn(ModelBase):
    type: Literal[UserType.USER]
    handle: str
    password: str


class UserTypeDb(TableBase):
    __tablename__ = "user_types"

    type: Mapped[str] = mapped_column(primary_key=True)


class UserDb(TableBase):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("user_types.type"))
    handle: Mapped[str]
    password_hash: Mapped[str | None]


class UserAncestorUserDescendantDb(TableBase):
    __tablename__ = "user_ancestors_user_descendants"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    descendant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    descendant_depth: Mapped[int]
