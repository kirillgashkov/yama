from pathlib import Path
from uuid import UUID

import aiofiles
import pytest

from ._driver import DriverFileNotFoundError, DriverFileTooLargeError
from ._filesystem import FileSystemDriver


async def test_file_system_driver_read_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.read_regular_content method."""
    file_system_dir = tmp_path / "file-system"
    driver = FileSystemDriver(file_system_dir=file_system_dir)

    # Case about reading an existing file.

    file_system_dir.mkdir()
    async with aiofiles.open(
        file_system_dir / "42bd9c321c96485faf69b48536bc3c4a", "wb"
    ) as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    async with driver.read_regular_content(
        UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a")
    ) as f:
        content = await f.read()

    assert content == b"# Foo\n\nBar.\n"

    # Case about reading a missing file.

    with pytest.raises(DriverFileNotFoundError):
        async with driver.read_regular_content(
            UUID("00bd9c32-1c96-485f-af69-b48536bc3c4a")
        ) as _:
            assert False


async def test_file_system_driver_write_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.write_regular_content method."""
    file_system_dir = tmp_path / "file-system"
    driver = FileSystemDriver(file_system_dir=file_system_dir)

    # Case about writing a file.

    content_file = tmp_path / "some-file.md"
    async with aiofiles.open(content_file, "wb") as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    async with aiofiles.open(content_file, "rb") as f:
        _ = await driver.write_regular_content(
            f,
            UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a"),
            chunk_size=64,
            max_file_size=512,
        )

    async with aiofiles.open(
        file_system_dir / "42bd9c321c96485faf69b48536bc3c4a", "rb"
    ) as f:
        content = await f.read()
    assert content == b"# Foo\n\nBar.\n"

    # Case about writing a file that is too large.

    too_large_content_file = tmp_path / "some-too-large-file.md"
    async with aiofiles.open(too_large_content_file, "wb") as f:
        _ = await f.write(b"x" * 513)

    with pytest.raises(DriverFileTooLargeError):
        async with aiofiles.open(too_large_content_file, "rb") as f:
            _ = await driver.write_regular_content(
                f,
                UUID("24bd9c32-1c96-485f-af69-b48536bc3c4a"),
                chunk_size=64,
                max_file_size=512,
            )


async def test_file_system_driver_remove_regular_content(*, tmp_path: Path) -> None:
    """Tests the FileSystemDriver.remove_regular_content method."""
    file_system_dir = tmp_path / "file-system"
    driver = FileSystemDriver(file_system_dir=file_system_dir)

    # Case about removing an existing file.

    file_system_dir.mkdir()
    async with aiofiles.open(
        file_system_dir / "42bd9c321c96485faf69b48536bc3c4a", "wb"
    ) as f:
        _ = await f.write(b"# Foo\n\nBar.\n")

    await driver.remove_regular_content(UUID("42bd9c32-1c96-485f-af69-b48536bc3c4a"))

    assert not (file_system_dir / "42bd9c321c96485faf69b48536bc3c4a").exists()

    # Case about removing a missing file.

    with pytest.raises(DriverFileNotFoundError):
        await driver.remove_regular_content(
            UUID("00bd9c32-1c96-485f-af69-b48536bc3c4a")
        )
