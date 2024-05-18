from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama import database
from yama.user.auth import get_current_user_id

from ._service import _Handle, _UserDb, _UserType, user_exists
from ._service_password import hash_password

router = APIRouter()


class _UserCreateIn(BaseModel):
    type: Literal[_UserType.REGULAR]
    handle: _Handle
    password: str


class _UserOut(BaseModel):
    id: UUID
    type: _UserType
    handle: _Handle


@router.post("/users")
async def _create_user(
    *,
    user_create_in: _UserCreateIn,
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
) -> _UserOut:
    if await user_exists(handle=user_create_in.handle, connection=connection):
        raise HTTPException(status_code=400, detail="User already exists.")

    password_hash = hash_password(user_create_in.password)

    query = (
        insert(_UserDb)
        .values(
            type=user_create_in.type.value,
            handle=user_create_in.handle,
            password_hash=password_hash,
        )
        .returning(_UserDb)
    )
    row = (await connection.execute(query)).mappings().one()
    user_db = _UserDb(**row)
    await connection.commit()

    return _user_db_to_user_out(user_db)


@router.get("/users/current")
async def _read_current_user(
    *,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
) -> _UserOut:
    query = select(_UserDb).where(_UserDb.id == current_user_id)
    row = (await connection.execute(query)).mappings().one_or_none()
    if row is None:
        raise HTTPException(400, "User not found.")
    user_db = _UserDb(**row)

    return _user_db_to_user_out(user_db)


@router.get("/users/{handle}")
async def _read_user(
    *,
    handle: _Handle,
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
) -> _UserOut:
    query = select(_UserDb).where(func.lower(_UserDb.handle) == func.lower(handle))
    row = (await connection.execute(query)).mappings().one_or_none()
    if row is None:
        raise HTTPException(400, "User not found.")
    user_db = _UserDb(**row)

    return _user_db_to_user_out(user_db)


@router.get("/users")
async def _read_users(
    *, connection: Annotated[AsyncConnection, Depends(database.get_connection)]
) -> list[_UserOut]:
    query = select(_UserDb)
    rows = (await connection.execute(query)).mappings()
    users_db = [_UserDb(**row) for row in rows]

    return [_user_db_to_user_out(u) for u in users_db]


def _user_db_to_user_out(u: _UserDb, /) -> _UserOut:
    return _UserOut(id=u.id, type=_UserType(u.type), handle=u.handle)
