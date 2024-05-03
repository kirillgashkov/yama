from enum import Enum
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import AfterValidator
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from yama.database.models import TableBase
from yama.model.models import ModelBase
from yama.user.settings import MAX_HANDLE_LENGTH, MIN_HANDLE_LENGTH


def _check_handle(handle: str, /) -> str:
    assert len(handle.encode()) >= MIN_HANDLE_LENGTH, "Handle is too short."
    assert len(handle.encode()) <= MAX_HANDLE_LENGTH, "Handle is too long."
    assert handle.isprintable(), "Handle contains non-printable characters."
    assert "/" not in handle, 'Handle contains "/".'
    assert handle != "current", 'Handle "current" is reserved.'
    return handle


Handle: TypeAlias = Annotated[str, AfterValidator(_check_handle)]


class UserType(str, Enum):
    USER = "user"
    GROUP = "group"


class UserOut(ModelBase):
    id: UUID
    type: UserType
    handle: Handle


class UserCreateIn(ModelBase):
    type: Literal[UserType.USER]
    handle: Handle
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
