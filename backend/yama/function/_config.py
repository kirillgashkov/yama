from dataclasses import dataclass


@dataclass
class Config:
    yama_executable: list[str]
