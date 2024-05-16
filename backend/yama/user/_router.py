from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.user.auth.dependencies import get_current_user_id
from yama.user.models import Handle, UserCreateIn, UserDb, UserOut, UserType
from yama.user.utils import (
    hash_password,
    user_exists,
)

router = APIRouter()


@router.post("/users")
async def create_user(
    *,
    user_create_in: UserCreateIn,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    if await user_exists(handle=user_create_in.handle, connection=connection):
        raise HTTPException(status_code=400, detail="User already exists.")

    password_hash = hash_password(user_create_in.password)

    query = (
        insert(UserDb)
        .values(
            type=user_create_in.type.value,
            handle=user_create_in.handle,
            password_hash=password_hash,
        )
        .returning(UserDb)
    )
    row = (await connection.execute(query)).mappings().one()
    user_db = UserDb(**row)
    await connection.commit()

    return _user_db_to_user_out(user_db)


@router.get("/users/current")
async def read_current_user(
    *,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    query = select(UserDb).where(UserDb.id == current_user_id)
    row = (await connection.execute(query)).mappings().one_or_none()
    if row is None:
        raise HTTPException(400, "User not found.")
    user_db = UserDb(**row)

    return _user_db_to_user_out(user_db)


@router.get("/users/{handle}")
async def read_user(
    *,
    handle: Handle,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    query = select(UserDb).where(func.lower(UserDb.handle) == func.lower(handle))
    row = (await connection.execute(query)).mappings().one_or_none()
    if row is None:
        raise HTTPException(400, "User not found.")
    user_db = UserDb(**row)

    return _user_db_to_user_out(user_db)


@router.get("/users")
async def read_users(
    *, connection: Annotated[AsyncConnection, Depends(get_connection)]
) -> list[UserOut]:
    query = select(UserDb)
    rows = (await connection.execute(query)).mappings()
    users_db = [UserDb(**row) for row in rows]

    return [_user_db_to_user_out(u) for u in users_db]


def _user_db_to_user_out(u: UserDb, /) -> UserOut:
    return UserOut(id=u.id, type=UserType(u.type), handle=u.handle)