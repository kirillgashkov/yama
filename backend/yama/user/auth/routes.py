from typing import Annotated, assert_never

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.user.auth.dependencies import get_grant_in
from yama.user.auth.models import (
    GrantIn,
    PasswordGrantIn,
    RefreshTokenGrantIn,
    TokenOut,
)
from yama.user.auth.utils import (
    password_grant_in_to_token_out,
    refresh_token_grant_in_to_token_out,
)
from yama.user.dependencies import get_settings
from yama.user.settings import Settings

router = APIRouter()


@router.post("/auth")
async def authorize(
    *,
    grant_in: Annotated[GrantIn, Depends(get_grant_in)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> TokenOut:
    match grant_in:
        case PasswordGrantIn():
            return await password_grant_in_to_token_out(
                grant_in, settings=settings, connection=connection
            )
        case RefreshTokenGrantIn():
            return await refresh_token_grant_in_to_token_out(
                grant_in, settings=settings, connection=connection
            )
        case _:
            assert_never(grant_in)


@router.post("/unauth")
async def unauthorize() -> ...: ...
