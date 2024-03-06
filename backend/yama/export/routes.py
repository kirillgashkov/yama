from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.security.dependencies import get_current_user_id

router = APIRouter()


@router.post("/functions/export")
async def export(
    path: str,  # FIXME: Use the type from `files`
    *,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    ...
