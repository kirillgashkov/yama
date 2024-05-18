from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeAlias

from yama import function


class AsyncReadable(Protocol):
    async def read(self, size: int = ..., /) -> bytes: ...


class AsyncWritable(Protocol):
    async def write(self, buffer: bytes, /) -> int: ...


@dataclass
class InputFile:
    path: Path
    content_reader: AsyncReadable


@dataclass
class OutputFile:
    path: Path
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
    async def execute(
        self,
        command: list[str],
        /,
        *,
        input_files: list[InputFile],
        output_files: list[OutputFile],
        function_config: function.Config,
    ) -> StartedProcess: ...

    @abstractmethod
    async def wait(self, process: StartedProcess, /) -> StoppedProcess: ...
