from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.users.models import User, UserOut

router = APIRouter()


@router.get("/users")
async def get_users(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> list[UserOut]:
    statement = select(User.id, User.username)
    rows = (await connection.execute(statement)).mappings()
    return [UserOut(**row) for row in rows]
