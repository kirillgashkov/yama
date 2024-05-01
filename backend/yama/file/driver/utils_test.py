from pathlib import Path
from uuid import UUID

import aiofiles
import pytest

from yama.file.driver.utils import DriverFileNotFound, FileSystemDriver


async def test_file_system_driver_read_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.read_regular_content method."""
    driver = FileSystemDriver(
        chunk_size=64, file_system_dir=tmp_path, max_file_size=512
    )
    async with aiofiles.open(
        tmp_path / "42bd9c32-1c96-485f-af69-b48536bc3c4a", "wb"
    ) as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    async with driver.read_regular_content(
        UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a")
    ) as f:
        content = await f.read()

    assert content == b"# Foo\n\nBar.\n"


async def test_file_system_driver_read_regular_content__file_not_found(
    *, tmp_path: Path
) -> None:
    """Tests the FileSystemDriver.read_regular_content method where the file is missing."""
    driver = FileSystemDriver(
        chunk_size=64, file_system_dir=tmp_path, max_file_size=512
    )
    with pytest.raises(DriverFileNotFound):
        async with driver.read_regular_content(
            UUID("00bd9c32-1c96-485f-af69-b48536bc3c4a")
        ) as _:
            assert False
