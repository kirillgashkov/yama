from typing import Annotated, assert_never
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.files import utils
from yama.files.dependencies import get_settings
from yama.files.models import (
    DirectoryCreateTuple,
    FileCreateTuple,
    FileName,
    FilePath,
    FileRead,
    FileTypeEnum,
    RegularFileCreateTuple,
)
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
    working_dir_id: Annotated[UUID | None, Query()] = None,
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
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...


# FIXME: Handle `utils.create_file` errors
# FIXME: Implement file update
# FIXME: Add security
# FIXME: Get created file instead of constructing it
# TODO: Return FileReadDetail
@router.put("/files/{path:path}")
async def create_or_update_file(
    *,
    path: FilePath,
    type: Annotated[FileTypeEnum, Form()],
    content: Annotated[UploadFile | None, File()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileRead:
    file_in: FileCreateTuple
    match type:
        case FileTypeEnum.DIRECTORY:
            if content is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content cannot be provided for '{type}' type",
                )
            file_in = DirectoryCreateTuple(type=type)
        case FileTypeEnum.REGULAR:
            if content is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content must be provided for '{type}' type",
                )
            file_in = RegularFileCreateTuple(type=type, content=content)
        case _:
            assert_never(type)

    file_id = await utils.create_file(
        path,
        file_in=file_in,
        user_id=user_id,
        working_dir_id=working_dir_id or settings.root_dir_id,
        files_dir=settings.files_dir,
        root_dir_id=settings.root_dir_id,
        upload_chunk_size=settings.upload_chunk_size,
        upload_max_file_size=settings.upload_max_file_size,
        connection=connection,
    )

    return FileRead(id=file_id, type=type)


@router.delete("/files/{path:path}")
async def delete_file(
    *,
    path: FilePath,
    type: Annotated[FileTypeEnum | None, Query()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> None:
    ...
