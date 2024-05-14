from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Protocol, TypeAlias


class AsyncReadable(Protocol):
    async def read(self, size: int = ..., /) -> bytes: ...


class AsyncWritable(Protocol):
    async def write(self, buffer: bytes, /) -> int: ...


@dataclass
class InputFile:
    path: PurePosixPath
    content_reader: AsyncReadable


@dataclass
class OutputFile:
    path: PurePosixPath
    content_writer: AsyncWritable


@dataclass
class StartedProcess:
    id: str
    started_at: datetime


@dataclass
class StoppedProcess:
    id: str
    started_at: datetime
    stopped_at: datetime
    stdout: bytes
    stderr: bytes
    returncode: int


Process: TypeAlias = StartedProcess | StoppedProcess


class Driver(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        /,
        *,
        input_files: list[InputFile],
        output_files: list[OutputFile],
    ) -> StartedProcess: ...

    @abstractmethod
    def wait(self, process: StartedProcess, /) -> StoppedProcess: ...
