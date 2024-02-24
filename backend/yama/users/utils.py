from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.users.models import User


async def user_exists(username: str, connection: AsyncConnection) -> bool:
    statement = select(User.id).where(func.lower(User.username) == func.lower(username))
    row = await connection.execute(statement)
    return bool(row.scalar())
