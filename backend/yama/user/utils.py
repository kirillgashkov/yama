from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.models import UserDb


async def user_exists(*, handle: str, connection: AsyncConnection) -> bool:
    query = select(exists().where(func.lower(UserDb.handle) == func.lower(handle)))
    return (await connection.execute(query)).scalar_one()


def hash_password(password: str) -> str:
    # FIXME: Use Argon2id
    return f"hash({password})"


def is_password_valid(password: str, password_hash: str) -> bool:
    # FIXME: Use Argon2id
    return hash_password(password) == password_hash


def create_access_token(user_id: UUID) -> str:
    # FIXME: Use JWT
    return f"access_token({user_id})"


def is_access_token_valid(access_token: str) -> bool:
    # FIXME: Use JWT
    return access_token.startswith("access_token(") and access_token.endswith(")")


def get_user_id_from_access_token(access_token: str) -> UUID:
    # FIXME: Use JWT
    return UUID(access_token.removeprefix("access_token(").removesuffix(")"))
