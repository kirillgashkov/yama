from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.files.models import FileName, FilePath, FileTypeEnum
from yama.security.dependencies import get_current_user_id, get_current_user_id_or_none

router = APIRouter()


@router.post("/files/{parent_path:path}")
async def create_file(
    parent_path: FilePath,
    *,
    name: Annotated[FileName, Form()],
    type: Annotated[FileTypeEnum, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:  # FIXME: Return type
    ...


@router.get("/files/{path:path}")
async def read_file(
    path: FilePath,
    *,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
) -> None:  # FIXME: Return type
    ...


@router.put("/files/{path:path}")
async def update_file(
    path: FilePath,
    *,
    name: Annotated[FileName, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:  # FIXME: Return type
    ...


@router.delete("/files/{path:path}")
async def delete_file(
    path: FilePath,
    *,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:  # FIXME: Return type
    ...
