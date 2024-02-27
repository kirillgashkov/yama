from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestFormStrict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.security.models import Token
from yama.security.utils import create_access_token, is_password_valid
from yama.users.models import User

router = APIRouter()


@router.post("/security/tokens")
async def create_token(
    password_grant_form: Annotated[OAuth2PasswordRequestFormStrict, Depends()],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> Token:
    statement = select(User.id, User.password_hash).where(
        func.lower(User.username) == func.lower(password_grant_form.username)
    )
    row = (await connection.execute(statement)).mappings().one_or_none()

    if row is None or not is_password_valid(
        password_grant_form.password, row["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(row["id"])
    return Token(access_token=access_token, token_type="bearer")
