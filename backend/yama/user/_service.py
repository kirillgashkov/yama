from enum import Enum
from typing import Annotated, TypeAlias
from uuid import UUID

from pydantic import AfterValidator
from sqlalchemy import ForeignKey, exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import Mapped, mapped_column
from starlette.requests import Request

from yama import database

from ._config import Config

_MIN_HANDLE_LENGTH = 1
_MAX_HANDLE_LENGTH = 255


def get_config(*, request: Request) -> Config:
    """A lifetime dependency."""
    return request.state.user_settings  # type: ignore[no-any-return]


async def user_exists(*, handle: str, connection: AsyncConnection) -> bool:
    query = select(exists().where(func.lower(_UserDb.handle) == func.lower(handle)))
    return (await connection.execute(query)).scalar_one()


def _check_handle(handle: str, /) -> str:
    assert len(handle.encode()) >= _MIN_HANDLE_LENGTH, "Handle is too short."
    assert len(handle.encode()) <= _MAX_HANDLE_LENGTH, "Handle is too long."
    assert handle.isprintable(), "Handle contains non-printable characters."
    assert "/" not in handle, 'Handle contains "/".'
    assert handle != "current", 'Handle "current" is reserved.'
    return handle


_Handle: TypeAlias = Annotated[str, AfterValidator(_check_handle)]


class _UserType(str, Enum):
    REGULAR = "regular"
    GROUP = "group"


class _UserTypeDb(database.BaseTable):
    __tablename__ = "user_types"

    type: Mapped[str] = mapped_column(primary_key=True)


class _UserDb(database.BaseTable):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    type: Mapped[str] = mapped_column(ForeignKey("user_types.type"))
    handle: Mapped[str]
    password_hash: Mapped[str | None]


class UserAncestorUserDescendantDb(database.BaseTable):
    __tablename__ = "user_ancestors_user_descendants"

    id: Mapped[UUID] = mapped_column(
        server_default=func.uuid_generate_v4(), primary_key=True
    )
    ancestor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    descendant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    descendant_depth: Mapped[int]
