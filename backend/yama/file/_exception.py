from pathlib import PurePosixPath
from uuid import UUID

from starlette.requests import Request
from starlette.responses import JSONResponse
from typing_extensions import override

from yama.file.models import FilePath


class FilesFileError(Exception):
    def __init__(
        self, ancestor_id: UUID, descendant_path: FilePath | None = None, /
    ) -> None:
        super().__init__()
        if descendant_path is None:
            descendant_path = PurePosixPath(".")
        self.ancestor_id = ancestor_id
        self.descendant_path: FilePath = descendant_path

    @override
    def __str__(self) -> str:
        return f"'{self.descendant_path}' relative to {self.ancestor_id}"

    @property
    def detail(self) -> str:
        return f'Error with file at path "{self.descendant_path}" relative to {self.ancestor_id}.'


class FilesFileExistsError(FilesFileError):
    @property
    @override
    def detail(self) -> str:
        return f'File already exists at path "{self.descendant_path}" relative to {self.ancestor_id}.'


class FilesFileNotFoundError(FilesFileError):
    @property
    @override
    def detail(self) -> str:
        return f'File not found at path "{self.descendant_path}" relative to {self.ancestor_id}.'


class FilesIsADirectoryError(FilesFileError):
    @property
    @override
    def detail(self) -> str:
        return f'File is a directory at path "{self.descendant_path}" relative to {self.ancestor_id}.'


class FilesNotADirectoryError(FilesFileError):
    @property
    @override
    def detail(self) -> str:
        return f'File is not a directory at path "{self.descendant_path}" relative to {self.ancestor_id}.'


class FilesPermissionError(FilesFileError):
    @property
    @override
    def detail(self) -> str:
        return f'Permission denied for file at path "{self.descendant_path}" relative to {self.ancestor_id}.'


def _handle_files_file_error(_: Request, exc: FilesFileError, /) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.detail})


exception_handlers = [(FilesFileError, _handle_files_file_error)]
