import logging
from pathlib import Path, PurePosixPath
from typing import Annotated, assert_never
from uuid import UUID

import fastapi
import pydantic
from sqlalchemy.ext.asyncio import AsyncConnection

from yama import auth, database, file
from yama.function.helper import FileInout

logger = logging.getLogger(__name__)

router = fastapi.APIRouter()


class FunctionOut(pydantic.BaseModel):
    id: UUID


@router.post("/functions/export")
async def handle_export(
    *,
    file_path: Annotated[file.FilePath, fastapi.Query(alias="file")],
    working_file_id: Annotated[UUID | None, fastapi.Query()] = None,
    user_id: Annotated[UUID, fastapi.Depends(auth.get_current_user_id)],
    file_config: Annotated[file.Config, fastapi.Depends(file.get_config)],
    connection: Annotated[AsyncConnection, fastapi.Depends(database.get_connection)],
    driver: Annotated[file.Driver, fastapi.Depends(file.get_driver)],
) -> FunctionOut:
    return FunctionOut(id=UUID("00000000-0000-0000-0000-000000000000"))


async def _make_input_files(
    file_path: Annotated[file.FilePath, fastapi.Query(alias="file")],
    user_id: UUID,
    working_file_id: UUID,
    file_config: file.Config,
    connection: AsyncConnection,
    driver: file.Driver,
) -> list[FileInout]:
    """
    Gets all dependency files for a file with path as input files.

    Current implementation assumes the file doesn't depend on files outside its
    directory and simply returns everything in this directory.
    """
    input_files = []

    async for p, f in file.walk_parent(
        file_path,
        user_id=user_id,
        working_file_id=working_file_id,
        config=file_config,
        connection=connection,
    ):
        if p == PurePosixPath("."):
            continue
        match f:
            case file.Regular(id=id_):
                try:
                    async with driver.read_regular_content(id_) as reader:
                        content = await reader.read()
                except file.DriverFileError:
                    logger.error("Failed to read regular content '%s'", id_)
                    content = b""
                input_files.append(FileInout(path=Path(p), content=content))
            case file.Directory():
                ...
            case _:
                assert_never(f)

    return input_files
