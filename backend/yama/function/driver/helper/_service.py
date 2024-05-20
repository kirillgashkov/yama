from pathlib import Path

from pydantic import BaseModel


class FileInout(BaseModel):
    path: Path
    content: bytes


class HelperIn(BaseModel):
    files: list[FileInout]


class HelperOut(BaseModel):
    files: list[FileInout]


async def execute(command: list[str], /, *, helper_in: HelperIn) -> HelperOut:
    print(command)
    print(helper_in)
    return HelperOut(files=[])
