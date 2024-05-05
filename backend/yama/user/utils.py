from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.models import UserDb

_password_hasher = PasswordHasher()


async def user_exists(*, handle: str, connection: AsyncConnection) -> bool:
    query = select(exists().where(func.lower(UserDb.handle) == func.lower(handle)))
    return (await connection.execute(query)).scalar_one()


def is_password_valid(password: str, password_hash: str, /) -> bool:
    try:
        _password_hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def should_rehash_password_with_hash(password_hash: str, /) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def hash_password(password: str, /) -> str:
    return _password_hasher.hash(password)


def create_access_token(user_id: UUID) -> str:
    # FIXME: Use JWT
    return f"access_token({user_id})"


def is_access_token_valid(access_token: str) -> bool:
    # FIXME: Use JWT
    return access_token.startswith("access_token(") and access_token.endswith(")")


def get_user_id_from_access_token(access_token: str) -> UUID:
    # FIXME: Use JWT
    return UUID(access_token.removeprefix("access_token(").removesuffix(")"))
