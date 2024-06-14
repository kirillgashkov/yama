from enum import Enum
from typing import Annotated, TypeAlias

from pydantic import AfterValidator
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.database import UserDb

_MIN_HANDLE_LENGTH = 1
_MAX_HANDLE_LENGTH = 255


async def _user_exists(*, handle: str, connection: AsyncConnection) -> bool:
    query = select(exists().where(func.lower(UserDb.handle) == func.lower(handle)))
    return (await connection.execute(query)).scalar_one()


def _check_handle(handle: str, /) -> str:
    assert len(handle.encode()) >= _MIN_HANDLE_LENGTH, "Handle is too short."
    assert len(handle.encode()) <= _MAX_HANDLE_LENGTH, "Handle is too long."
    assert handle.isprintable(), "Handle contains non-printable characters."
    assert "/" not in handle, 'Handle contains "/".'
    assert handle != "current", 'Handle "current" is reserved.'
    return handle


Handle: TypeAlias = Annotated[str, AfterValidator(_check_handle)]


class UserType(str, Enum):
    REGULAR = "regular"
    GROUP = "group"
