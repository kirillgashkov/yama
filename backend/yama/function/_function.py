from dataclasses import dataclass
from pathlib import Path

from yama.model.models import ModelBase


class FileInout(ModelBase):
    path: Path
    content: bytes


class FunctionIn(ModelBase):
    files: list[FileInout]


class FunctionOut(ModelBase):
    files: list[FileInout]


@dataclass
class Config:
    yama_executable: list[str]


async def execute(
    command: list[str],
    /,
    *,
    input_files: list[tuple[Path, bytes]],
    output_paths: list[Path],
) -> list[tuple[Path, bytes]]:
    # for file_inout in function_in.files:
    #     async with aiofiles.open(file_inout.path, "wb") as f:
    #         await f.write(file_inout.content)
    #
    # process = await asyncio.create_subprocess_exec(
    #     *command,
    #     stdin=sys.stdin.buffer,
    #     stdout=sys.stdout.buffer,
    #     stderr=sys.stderr.buffer,
    # )
    # exit_code = await process.wait()
    # if exit_code != 0:
    #     raise RuntimeError(f"Process exited with code {exit_code}")
    #
    # files = []
    # for file_inout in function_in.files:
    #     async with aiofiles.open(file_inout.path, "rb") as f:
    #         content = await f.read()
    #     files.append(FileInout(path=file_inout.path, content=content))
    ...
