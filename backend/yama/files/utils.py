from pathlib import Path

import aiofiles
from fastapi import UploadFile


class FileTooLargeError(Exception):
    ...


async def write_file(
    file_in: UploadFile, file_path: Path, /, *, chunk_size: int, max_file_size: int
) -> int:
    file_size = 0

    async with aiofiles.open(file_path, "wb") as file_out:
        while chunk := await file_in.read(chunk_size):
            file_size += len(chunk)

            if file_size > max_file_size:
                raise FileTooLargeError()

            await file_out.write(chunk)

    return file_size
