from pathlib import Path
from uuid import UUID

import aiofiles
import pytest

from yama.file.driver.utils import DriverFileNotFound, FileSystemDriver


async def test_file_system_driver_read_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.read_regular_content method."""
    # Given
    file_system_dir = tmp_path / "file-system"
    driver = FileSystemDriver(
        chunk_size=64, file_system_dir=file_system_dir, max_file_size=512
    )

    file_system_dir.mkdir()
    async with aiofiles.open(
        file_system_dir / "42bd9c321c96485faf69b48536bc3c4a", "wb"
    ) as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    # When
    async with driver.read_regular_content(
        UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a")
    ) as f:
        content = await f.read()

    # Then
    assert content == b"# Foo\n\nBar.\n"

    # When & Then
    with pytest.raises(DriverFileNotFound):
        async with driver.read_regular_content(
            UUID("00bd9c32-1c96-485f-af69-b48536bc3c4a")
        ) as _:
            assert False


async def test_file_system_driver_write_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.write_regular_content method."""
    # Given
    file_system_dir = tmp_path / "file-system"
    driver = FileSystemDriver(
        chunk_size=64, file_system_dir=file_system_dir, max_file_size=512
    )

    content_file = tmp_path / "some-file.md"
    async with aiofiles.open(content_file, "wb") as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    # When
    async with aiofiles.open(content_file, "rb") as f:
        _ = await driver.write_regular_content(
            f, UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a")
        )

    # Then
    async with aiofiles.open(
        file_system_dir / "42bd9c321c96485faf69b48536bc3c4a", "rb"
    ) as f:
        content = await f.read()
    assert content == b"# Foo\n\nBar.\n"
