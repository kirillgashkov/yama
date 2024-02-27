from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.security.utils import hash_password
from yama.users.models import User, UserIn, UserOut
from yama.users.utils import user_exists

router = APIRouter()


@router.get("/users")
async def get_users(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> list[UserOut]:
    statement = select(User.id, User.username)
    rows = (await connection.execute(statement)).mappings()
    return [UserOut(**row) for row in rows]


@router.post("/users")
async def create_user(
    user_in: UserIn,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> UserOut:
    if await user_exists(user_in.username, connection):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="User already exists",
        )

    password_hash = hash_password(user_in.password)

    statement = (
        insert(User)
        .values(username=user_in.username, password_hash=password_hash)
        .returning(User.id, User.username)
    )
    row = (await connection.execute(statement)).mappings().one()
    await connection.commit()

    return UserOut(**row)
