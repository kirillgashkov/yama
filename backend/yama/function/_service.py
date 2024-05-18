from pathlib import Path

from pydantic import BaseModel


class FileInout(BaseModel):
    path: Path
    content: bytes


class FunctionIn(BaseModel):
    files: list[FileInout]


class FunctionOut(BaseModel):
    files: list[FileInout]


async def execute(command: list[str], /, *, function_in: FunctionIn) -> FunctionOut:
    raise NotImplementedError()
