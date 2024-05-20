import asyncio
import pathlib

import aiofiles
import aiofiles.os
import pydantic


class FileInout(pydantic.BaseModel):
    path: pathlib.Path
    content: bytes


class HelperIn(pydantic.BaseModel):
    files: list[FileInout]
    stdin: bytes


class HelperOut(pydantic.BaseModel):
    files: list[FileInout]
    stdout: bytes
    stderr: bytes
    exit_code: int


async def _execute(
    command: list[str], /, *, helper_in: HelperIn, output_files: list[pathlib.Path]
) -> HelperOut:
    for file in helper_in.files:
        await aiofiles.os.makedirs(file.path.parent, exist_ok=True)
        async with aiofiles.open(file.path, "wb") as f:
            await f.write(file.content)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=helper_in.stdin)
    exit_code = await process.wait()

    files: list[FileInout] = []
    for file_path in output_files:
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
            files.append(FileInout(path=file_path, content=content))

    return HelperOut(files=files, stdout=stdout, stderr=stderr, exit_code=exit_code)
