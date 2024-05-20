from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeAlias

from ._config import Config


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
    exit_code: int


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
        config: Config,
    ) -> StartedProcess: ...

    @abstractmethod
    async def wait(self, process: StartedProcess, /) -> StoppedProcess: ...
