from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.file.dependencies import get_settings
from yama.file.models import (
    FileName,
    FileOut,
    FilePath,
    FileType,
)
from yama.file.settings import Settings
from yama.security.dependencies import get_current_user_id, get_current_user_id_or_none
from yama.user.dependencies import get_settings as get_user_settings
from yama.user.settings import Settings as UserSettings

router = APIRouter()


@router.post("/files/{parent_path:path}", description="Create file.")
async def create_file(
    *,
    parent_path: FilePath,
    name: Annotated[FileName, Form()],
    type: Annotated[FileType, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileOut: ...


@router.get(
    "/files/{path:path}",
    description="Get file's model or content depending on the content query parameter.",
    response_model=FileOut,
    responses={200: {"content": {"*/*": {}}}},
)
async def get_file(
    *,
    path: FilePath,
    content: Annotated[bool, Query()] = False,
    type: Annotated[FileType | None, Query()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_settings: Annotated[UserSettings, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileOut | FileResponse: ...


@router.put("/files/{path:path}", description="Create or update file.")
async def create_or_update_file(
    *,
    path: FilePath,
    type: Annotated[FileType, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileOut: ...


@router.delete("/files/{path:path}", description="Delete file.")
async def delete_file(
    *,
    path: FilePath,
    type: Annotated[FileType | None, Query()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileOut: ...
