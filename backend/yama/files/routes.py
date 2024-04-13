from pathlib import PurePosixPath
from typing import Annotated, assert_never
from urllib.parse import urlencode, urlsplit, urlunsplit
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
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from yama.database.dependencies import get_connection
from yama.files import utils
from yama.files.dependencies import get_settings
from yama.files.models import (
    DirectoryCreateTuple,
    DirectoryReadDetail,
    DirectoryReadTuple,
    FileCreateTuple,
    FileName,
    FilePath,
    FileRead,
    FileReadDetail,
    FileTypeEnum,
    RegularFileCreateTuple,
    RegularFileReadTuple,
    RegularReadDetail,
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


# FIXME: Handle `utils.get_file` errors
# FIXME: Add security
# TODO: Return ID-based `content_url`
@router.post("/files/{path:path}")
async def get_file(
    *,
    path: FilePath,
    content: Annotated[bool, Query()] = False,
    type: Annotated[FileTypeEnum | None, Query()] = None,
    working_dir_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> FileReadDetail | FileResponse:
    file_out = await utils.get_file(
        path,
        type_=type,
        user_id=user_id or settings.public_user_id,
        working_dir_id=working_dir_id or settings.root_dir_id,
        files_dir=settings.files_dir,
        root_dir_id=settings.root_dir_id,
        connection=connection,
    )

    match file_out:
        case RegularFileReadTuple(
            id=id, type=type_, content_physical_path=content_physical_path
        ):
            if content:
                return FileResponse(content_physical_path)
            content_url = _make_content_url(
                path, files_base_url=settings.files_base_url
            )
            return RegularReadDetail(id=id, type=type_, content_url=content_url)
        case DirectoryReadTuple(id=id, type=type_, content=entries):
            if content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content cannot be requested for '{type}' type",
                )
            files = {e.name: FileRead(id=e.id, type=e.type) for e in entries}
            return DirectoryReadDetail(id=id, type=type_, files=files)
        case _:
            assert_never(file_out)


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


def _make_content_url(
    file_path: FilePath,
    /,
    *,
    files_base_url: str,
) -> str:
    scheme, netloc, files_base_path, _, _ = urlsplit(files_base_url)
    path = str(PurePosixPath(files_base_path) / file_path)
    query = urlencode({"content": True})
    return urlunsplit((scheme, netloc, path, query, ""))
