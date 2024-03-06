from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.files.models import FileTypeEnum
from yama.security.dependencies import get_current_user_id

router = APIRouter()


@router.get("/files/{parent_path:path}")
async def create_file(
    parent_path: str,
    /,
    name: Annotated[str, Form()],
    type: Annotated[FileTypeEnum, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    *,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ...:
    ...


@router.get("/files/{path:path}")
async def read_file() -> None:
    ...


@router.get("/files/{path:path}")
async def update_file() -> None:
    ...


@router.get("/files/{path:path}")
async def delete_file() -> None:
    ...
