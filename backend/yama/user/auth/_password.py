from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.user.auth import Config
from yama.user.auth._access_token import make_access_token_and_expires_in
from yama.user.auth._exception import InvalidUsernameOrPasswordError
from yama.user.auth._refresh_token import make_refresh_token
from yama.user.auth._router import PasswordGrantIn, _TokenOut
from yama.user.models import UserDb
from yama.user.utils import is_password_valid


async def password_grant_in_to_token_out(
    password_grant_in: PasswordGrantIn,
    /,
    *,
    settings: Config,
    connection: AsyncConnection,
) -> _TokenOut:
    query = select(UserDb).where(
        func.lower(UserDb.handle) == func.lower(password_grant_in.username)
    )
    row = (await connection.execute(query)).mappings().one_or_none()
    user_db = UserDb(**row) if row is not None else None

    if (
        user_db is None
        or user_db.password_hash is None
        or not is_password_valid(password_grant_in.password, user_db.password_hash)
    ):
        raise InvalidUsernameOrPasswordError()

    access_token, expires_in = make_access_token_and_expires_in(
        user_db.id, settings=settings
    )
    refresh_token = make_refresh_token(user_db.id, settings=settings)
    return _TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
    )
