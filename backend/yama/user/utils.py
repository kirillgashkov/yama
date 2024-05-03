from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.models import UserDb


async def user_exists(*, handle: str, connection: AsyncConnection) -> bool:
    query = select(exists().where(func.lower(UserDb.handle) == func.lower(handle)))
    return (await connection.execute(query)).scalar_one()
