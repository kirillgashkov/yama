import asyncio
import logging
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, TypeAlias, assert_never
from uuid import UUID, uuid4

import aiofiles.tempfile
import fastapi
import pydantic
from sqlalchemy.ext.asyncio import AsyncConnection

from yama import auth, database, file
from yama.function.helper import FileInout, HelperIn, HelperOut

from ._config import Config, get_config

logger = logging.getLogger(__name__)

router = fastapi.APIRouter()


class OkExportFunctionOut(pydantic.BaseModel):
    status: Literal["ok"] = "ok"
    output_file: file.Regular
    stdout: bytes
    stderr: bytes


class ErrorFunctionOut(pydantic.BaseModel):
    status: Literal["error"] = "error"
    message: str
    stdout: bytes
    stderr: bytes


ExportFunctionOut: TypeAlias = OkExportFunctionOut | ErrorFunctionOut


@router.post("/functions/export")
async def handle_export(
    *,
    file_path: Annotated[file.FilePath, fastapi.Query(alias="file")],
    working_file_id: Annotated[UUID | None, fastapi.Query()] = None,
    user_id: Annotated[UUID, fastapi.Depends(auth.get_current_user_id)],
    config: Annotated[Config, fastapi.Depends(get_config)],
    file_config: Annotated[file.Config, fastapi.Depends(file.get_config)],
    connection: Annotated[AsyncConnection, fastapi.Depends(database.get_connection)],
    driver: Annotated[file.Driver, fastapi.Depends(file.get_driver)],
) -> ExportFunctionOut:
    # Read the input files.
    input_files = await _read_input_files(
        file_path=file_path,
        user_id=user_id,
        working_file_id=working_file_id or file_config.root_file_id,
        file_config=file_config,
        connection=connection,
        driver=driver,
    )
    helper_in = HelperIn(files=input_files)

    # Run the export command via the helper.
    async with aiofiles.tempfile.TemporaryDirectory() as tempdir:
        # HACK: At most one output file from the helper is supported.
        # HACK: Assumes input_files presents file_path relative to the temporary
        # directory and as its direct child.
        input_path = file_path.name
        output_path = file_path.with_suffix(".pdf").name
        p = await asyncio.create_subprocess_exec(
            *[
                "python",
                "-m",
                "yama.function.helper",
                "-o",
                output_path,
                "--",
                *config.export_command_base,
                "-o",
                output_path,
                input_path,
            ],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tempdir,
        )
        stdout, stderr = await p.communicate(input=helper_in.model_dump_json().encode())
        exit_code = await p.wait()
        assert isinstance(exit_code, int)

        if stderr:
            logger.warning("Helper stderr: %s", stderr)
        assert exit_code == 0

    # Get the output files from the helper.
    helper_out = HelperOut.model_validate_json(stdout)
    output_files = helper_out.files

    if helper_out.exit_code != 0:
        return ErrorFunctionOut(message="Export failed", stdout=stdout, stderr=stderr)

    # Write the output files.
    output_dir = await _write_output_files(
        output_files,
        user_id=user_id,
        working_file_id=working_file_id or file_config.root_file_id,
        config=config,
        file_config=file_config,
        connection=connection,
        driver=driver,
    )

    # Read the exported file.
    output_file = await file.read_file(
        PurePosixPath(output_path),
        max_depth=0,
        user_id=user_id,
        working_file_id=output_dir.id,
        config=file_config,
        connection=connection,
    )

    return OkExportFunctionOut(output_file=output_file, stdout=stdout, stderr=stderr)


async def _read_input_files(
    *,
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


async def _write_output_files(
    output_files: list[FileInout],
    /,
    *,
    user_id: UUID,
    working_file_id: UUID,
    config: Config,
    file_config: file.Config,
    connection: AsyncConnection,
    driver: file.Driver,
) -> file.File:
    """
    Writes all output files to the file module. Returns the output directory.

    Current implementation supports only one output file.
    """
    # Create the output directory.
    output_dir = await file.write_file(
        file.DirectoryWrite(type=file.FileType.DIRECTORY),
        PurePosixPath(uuid4().hex),  # The output directory gets a random name...
        exist_ok=False,
        user_id=config.output_user_id,
        working_file_id=config.output_file_id,  # ...inside the global output directory.
        config=file_config,
        connection=connection,
        driver=driver,
    )

    if not output_files:
        return output_dir

    assert len(output_files) == 1
    output_file = output_files[0]

    try:
        # Create the output file.
        content_stream = fastapi.UploadFile(BytesIO(output_file.content))
        file_write = file.RegularWrite(
            type=file.FileType.REGULAR,
            content=file.RegularContentWrite(stream=content_stream),
        )
        await file.write_file(
            file_write,
            PurePosixPath(output_file.path.name),  # The file gets the same name...
            exist_ok=False,
            user_id=config.output_user_id,
            working_file_id=output_dir.id,  # ...inside the output directory.
            config=file_config,
            connection=connection,
            driver=driver,
        )

        # Share the output file with the user.
        await file.share_file(
            PurePosixPath("."),
            share_type=file.FileShareType.READ,
            to_user_id=user_id,
            from_user_id=config.output_user_id,
            working_file_id=working_file_id or file_config.root_file_id,
            config=file_config,
            connection=connection,
        )
    except Exception as e:
        logger.error("Failed to write output file '%s': %s", output_file.path, e)

    return output_dir
