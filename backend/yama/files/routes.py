from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.files.dependencies import get_settings
from yama.files.models import FileName, FilePath, FileTypeEnum
from yama.files.settings import Settings
from yama.security.dependencies import get_current_user_id, get_current_user_id_or_none

router = APIRouter()


@router.post("/files/{parent_path:path}")
async def create_file(
    *,
    parent_path: FilePath,
    name: Annotated[FileName, Form()],
    type: Annotated[FileTypeEnum, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    working_dir: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...


@router.post("/files/{path:path}")
async def get_file(
    *,
    path: FilePath,
    type: Annotated[FileTypeEnum | None, Query()] = None,
    working_dir: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...


@router.put("/files/{path:path}")
async def create_or_update_file(
    *,
    path: FilePath,
    type: Annotated[FileTypeEnum, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    working_dir: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...


@router.delete("/files/{path:path}")
async def delete_file(
    *,
    path: FilePath,
    type: Annotated[FileTypeEnum | None, Query()] = None,
    working_dir: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...
