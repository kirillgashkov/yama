from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.security.dependencies import get_current_user_id
from yama.security.utils import hash_password
from yama.user._models import User, UserIn, UserOut
from yama.user.utils import user_exists

router = APIRouter()


@router.get("/users/current")
async def get_current_user(
    *,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    query = select(User.id, User.username).where(User.id == current_user_id)
    row = (await connection.execute(query)).mappings().one()
    return UserOut(**row)


@router.get("/users")
async def get_users(
    *, connection: Annotated[AsyncConnection, Depends(get_connection)]
) -> list[UserOut]:
    query = select(User.id, User.username)
    rows = (await connection.execute(query)).mappings()
    return [UserOut(**row) for row in rows]


@router.post("/users")
async def create_user(
    *,
    user_in: UserIn,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    if await user_exists(handle=user_in.username, connection=connection):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User already exists",
        )

    password_hash = hash_password(user_in.password)

    query = (
        insert(User)
        .values(username=user_in.username, password_hash=password_hash)
        .returning(User.id, User.username)
    )
    row = (await connection.execute(query)).mappings().one()
    await connection.commit()

    return UserOut(**row)
