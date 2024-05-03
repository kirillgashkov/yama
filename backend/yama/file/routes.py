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

from yama.database.dependencies import get_connection
from yama.file import utils
from yama.file.dependencies import get_settings
from yama.file.driver.dependencies import get_driver
from yama.file.driver.utils import Driver
from yama.file.models import (
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
from yama.file.settings import Settings
from yama.security.dependencies import get_current_user_id, get_current_user_id_or_none
from yama.user.dependencies import get_settings as get_user_settings
from yama.user.settings import Settings as UserSettings

router = APIRouter()


@router.get(
    "/files/{path:path}",
    description="Read file's model or content depending on the regular_content query parameter.",
    response_model=FileOut,
    responses={200: {"content": {"*/*": {}}}},
)
async def read_file(
    *,
    path: FilePath,
    regular_content: Annotated[bool, Query()] = False,
    working_file_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_settings: Annotated[UserSettings, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut | StreamingResponse:
    if regular_content:
        file = await utils.read_file(
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
                    "regular_content query parameter with true value is not allowed for directories.",
                )
            case _:
                assert_never(file)

    file = await utils.read_file(
        path,
        max_depth=1,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
    )
    file_out = _make_file_out(file, files_base_url=settings.files_base_url)
    return file_out


@router.put("/files/{path:path}", description="Create or update file.")
async def create_or_update_file(
    *,
    path: FilePath,
    working_file_id: Annotated[UUID | None, Query()] = None,
    exist_ok: Annotated[bool, Query()] = True,
    type: Annotated[FileType, Form()],
    content: Annotated[UploadFile | None, FastAPIFile()] = None,
    user_id: Annotated[UUID | None, Depends(get_current_user_id_or_none)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_settings: Annotated[UserSettings, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut:
    file_write: FileWrite
    match type:
        case FileType.REGULAR:
            if content is None:
                raise HTTPException(
                    400, "content query parameter must be provided for regular files."
                )
            file_write = RegularWrite(
                type=type, content=RegularContentWrite(stream=content)
            )
        case FileType.DIRECTORY:
            if content is not None:
                raise HTTPException(
                    400, "content query parameter cannot be provided for directories."
                )
            file_write = DirectoryWrite(type=type)
        case _:
            assert_never(type)

    file = await utils.write_file(
        file_write,
        path,
        exist_ok=exist_ok,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
        driver=driver,
    )
    file_out = _make_file_out(file, files_base_url=settings.files_base_url)
    return file_out


@router.delete("/files/{path:path}", description="Delete file.")
async def delete_file(
    *,
    path: FilePath,
    working_file_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_settings: Annotated[UserSettings, Depends(get_user_settings)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    driver: Annotated[Driver, Depends(get_driver)],
) -> FileOut:
    file = await utils.remove_file(
        path,
        user_id=user_id or user_settings.public_user_id,
        working_file_id=working_file_id or settings.root_file_id,
        settings=settings,
        connection=connection,
        driver=driver,
    )
    file_out = _make_file_out(file, files_base_url=settings.files_base_url)
    return file_out


def _make_file_out(
    file: File, /, *, with_content: bool = True, files_base_url: str
) -> FileOut:
    match file:
        case Regular(id=id_, type=type_):
            return RegularOut(
                id=id_,
                type=type_,
                content=RegularContentOut(
                    url=_make_regular_content_url(id_, files_base_url=files_base_url)
                )
                if with_content
                else None,
            )
        case Directory(id=id_, type=type_, content=content):
            return DirectoryOut(
                id=id_,
                type=type_,
                content=DirectoryContentOut(
                    files=[
                        DirectoryContentFileOut(
                            name=content_file.name,
                            file=_make_file_out(
                                content_file.file, files_base_url=files_base_url
                            ),
                        )
                        for content_file in content.files
                    ]
                )
                if with_content
                else None,
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
    query = urlencode({"regular_content": True, "working_file_id": str(id_)})
    return urlunsplit((scheme, netloc, path, query, ""))
