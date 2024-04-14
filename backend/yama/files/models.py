from pathlib import PurePosixPath
from typing import Annotated, Any, TypeAlias

from pydantic import AfterValidator, ValidatorFunctionWrapHandler, WrapValidator

from yama.files.settings import MAX_FILE_NAME_LENGTH, MAX_FILE_PATH_LENGTH


def _check_file_name(name: str) -> str:
    assert len(name.encode()) <= MAX_FILE_NAME_LENGTH, "File name is too long"
    assert name.isprintable(), "File name contains non-printable characters"
    assert "/" not in name, "File name contains '/'"
    assert name != "..", "File name '..' is not supported"
    return name


def _check_file_path(
    path_data: Any, handler: ValidatorFunctionWrapHandler
) -> PurePosixPath:
    assert isinstance(path_data, str), "File path is not a string"
    assert len(path_data.encode()) <= MAX_FILE_PATH_LENGTH, "File path is too long"

    path = handler(path_data)
    if not isinstance(path, PurePosixPath):
        raise RuntimeError("File path is not a PurePosixPath")

    if path.is_absolute():
        names = path.parts[1:]
    else:
        names = path.parts

    for name in names:
        _check_file_name(name)

    return path


def _normalize_file_path_root(path: PurePosixPath) -> PurePosixPath:
    # POSIX allows treating a path beginning with two slashes in an
    # implementation-defined manner which is respected by Python's pathlib by not
    # collapsing the two slashes into one. We treat such paths as absolute paths.
    if path.parts and path.parts[0] == "//":
        return PurePosixPath("/", *path.parts[1:])
    return path


FileName: TypeAlias = Annotated[str, AfterValidator(_check_file_name)]
FilePath: TypeAlias = Annotated[
    PurePosixPath,
    AfterValidator(_normalize_file_path_root),
    WrapValidator(_check_file_path),
]
