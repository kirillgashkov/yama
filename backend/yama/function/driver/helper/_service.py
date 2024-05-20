import asyncio
import pathlib
import typing

import aiofiles
import aiofiles.os
import pydantic


class FileIn(pydantic.BaseModel):
    path: pathlib.Path
    content: bytes


class FileOkOut(pydantic.BaseModel):
    path: pathlib.Path
    content: bytes


class FileErrorOut(pydantic.BaseModel):
    path: pathlib.Path
    error: str


FileOut: typing.TypeAlias = FileOkOut | FileErrorOut


class HelperIn(pydantic.BaseModel):
    files: list[FileIn]
    stdin: bytes


class HelperOut(pydantic.BaseModel):
    files: list[FileOut]
    stdout: bytes
    stderr: bytes
    exit_code: int


async def execute(
    command: list[str], /, *, helper_in: HelperIn, output_files: list[pathlib.Path]
) -> HelperOut:
    async with aiofiles.tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = pathlib.Path(temp_dir_str)

        for file in helper_in.files:
            await aiofiles.os.makedirs((temp_dir / file.path).parent, exist_ok=True)
            async with aiofiles.open(temp_dir / file.path, "wb") as f:
                await f.write(file.content)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir,
        )
        stdout, stderr = await process.communicate(input=helper_in.stdin)
        exit_code = await process.wait()

        files: list[FileOut] = []
        for file_path in output_files:
            try:
                async with aiofiles.open(temp_dir / file_path, "rb") as f:
                    content = await f.read()
                    files.append(FileOkOut(path=file_path, content=content))
            except FileNotFoundError:
                files.append(FileErrorOut(path=file_path, error="File not found"))
            except IsADirectoryError:
                files.append(FileErrorOut(path=file_path, error="Is a directory"))
            except OSError:
                files.append(FileErrorOut(path=file_path, error="Unknown error"))

        return HelperOut(files=files, stdout=stdout, stderr=stderr, exit_code=exit_code)
