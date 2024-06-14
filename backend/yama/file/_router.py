from collections.abc import AsyncIterator
from pathlib import PurePosixPath
from typing import Annotated, assert_never
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi import (
    File as FastAPIFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from yama import database, user
from yama.file.driver import Driver, get_driver
from yama.user import get_config as get_user_settings
from yama.user.auth import get_current_user_id, get_current_user_id_or_none

from ._config import Config
from ._models import (
    Directory,
    DirectoryContentFileOut,
    DirectoryContentOut,
    DirectoryOut,
    DirectoryWrite,
    File,
    FileOut,
    FilePath,
    FileType,
    FileWrite,
    Regular,
    RegularContentOut,
    RegularContentWrite,
    RegularOut,
    RegularWrite,
)
from ._service import get_config, read_file, remove_file, write_file

router = APIRouter()


@router.get(
    "/files/{path:path}",
    description="Read file's model or content depending on the regular_content query parameter.",
    response_model=FileOut,
    responses={200: {"content": {"*/*": {}}}},
)
async def _read_file(
    *,
    path: FilePath,
    content: Annotated[bool, Query()] = False,
    working_file_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Config, Depends(get_config)],
    user_settings: Annotated[user.Config, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut | StreamingResponse:
    if content:
        file = await read_file(
            path,
            max_depth=0,
            user_id=user_id or user_settings.public_user_id,
            working_file_id=working_file_id or settings.root_file_id,
            settings=settings,
            connection=connection,
        )
        match file:
            case Regular(id=id_):

                async def content_stream() -> AsyncIterator[bytes]:
                    async with driver.read_regular_content(id_) as f:
                        file_size = 0
                        while chunk := await f.read(
                            min(settings.chunk_size, settings.max_file_size - file_size)
                        ):
                            yield chunk
                            file_size += len(chunk)
                            if file_size >= settings.max_file_size:
                                break

                return StreamingResponse(content_stream())
            case Directory():
                raise HTTPException(
                    400,
                    "content query parameter with true value is not allowed for directories.",
                )
            case _:
                assert_never(file)

    file = await read_file(
        path,
        max_depth=1,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
    )
    file_out = _file_to_file_out(
        file, max_depth=1, files_base_url=settings.files_base_url
    )
    return file_out


@router.put("/files/{path:path}", description="Create or update file.")
async def _create_or_update_file(
    *,
    path: FilePath,
    working_file_id: Annotated[UUID | None, Query()] = None,
    exist_ok: Annotated[bool, Query()] = True,
    type: Annotated[FileType, Form()],
    content: Annotated[UploadFile | None, FastAPIFile()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Config, Depends(get_config)],
    user_settings: Annotated[user.Config, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut:
    file_write: FileWrite
    match type:
        case FileType.REGULAR:
            if content is None:
                raise HTTPException(
                    400, "content form parameter must be provided for regular files."
                )
            file_write = RegularWrite(
                type=type, content=RegularContentWrite(stream=content)
            )
        case FileType.DIRECTORY:
            if content is not None:
                raise HTTPException(
                    400, "content form parameter cannot be provided for directories."
                )
            file_write = DirectoryWrite(type=type)
        case _:
            assert_never(type)

    file = await write_file(
        file_write,
        path,
        exist_ok=exist_ok,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
        driver=driver,
    )
    file_out = _file_to_file_out(
        file, max_depth=0, files_base_url=settings.files_base_url
    )
    return file_out


@router.delete("/files/{path:path}", description="Delete file.")
async def _delete_file(
    *,
    path: FilePath,
    working_file_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Config, Depends(get_config)],
    user_settings: Annotated[user.Config, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(database.get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut:
    file = await remove_file(
        path,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
        driver=driver,
    )
    file_out = _file_to_file_out(
        file, max_depth=0, files_base_url=settings.files_base_url
    )
    return file_out


def _file_to_file_out(
    file: File, /, *, max_depth: int | None, files_base_url: str
) -> FileOut:
    match file:
        case Regular(id=id_, type=type_):
            return RegularOut(
                id=id_,
                type=type_,
                content=RegularContentOut(
                    url=_make_regular_content_url(id_, files_base_url=files_base_url)
                ),
            )
        case Directory(id=id_, type=type_, content=content):
            return DirectoryOut(
                id=id_,
                type=type_,
                content=(
                    DirectoryContentOut(
                        files=[
                            DirectoryContentFileOut(
                                name=content_file.name,
                                file=_file_to_file_out(
                                    content_file.file,
                                    max_depth=(
                                        max_depth - 1 if max_depth is not None else None
                                    ),
                                    files_base_url=files_base_url,
                                ),
                            )
                            for content_file in content.files
                        ]
                    )
                    if max_depth is None or max_depth > 0
                    else None
                ),
            )
        case _:
            assert_never(file)


def _make_regular_content_url(
    id_: UUID,
    /,
    *,
    files_base_url: str,
) -> str:
    scheme, netloc, files_base_path, _, _ = urlsplit(files_base_url)
    path = str(PurePosixPath(files_base_path)) + "/."
    query = urlencode({"content": True, "working_file_id": str(id_)})
    return urlunsplit((scheme, netloc, path, query, ""))
