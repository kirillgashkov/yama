from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.users._models import User


async def user_exists(username: str, connection: AsyncConnection) -> bool:
    statement = select(
        exists().where(func.lower(User.username) == func.lower(username))
    )
    return (await connection.execute(statement)).scalar_one()
