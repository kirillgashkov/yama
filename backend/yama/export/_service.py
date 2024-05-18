import enum
import logging
import subprocess
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Self, assert_never

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from yama.file._service_models import FilePath, FilePathAdapter

logger = logging.getLogger(__name__)


class ExportParameterType(str, Enum):
    BOOL = "bool"
    STRING = "string"

    @enum.property
    def python_type(self) -> type:
        match self:
            case ExportParameterType.BOOL:
                return bool
            case ExportParameterType.STRING:
                return str
            case _:
                assert_never(self)


class ExportFilterType(str, Enum):
    JSON = "json"
    LUA = "lua"


class ExportParameter(BaseModel):
    name: str
    type: list[ExportParameterType] = Field(min_length=1)
    default: Any = None

    @model_validator(mode="after")
    def validate_default(self) -> Self:
        if self.default is None:
            return self
        self.default = validate_export_argument(self.default, self.type)
        return self


class ExportReader(BaseModel):
    name: FilePath = FilePathAdapter.validate_python("commonmark")
    metadata: dict[str, str] = Field(default_factory=dict)


class ExportFilter(BaseModel):
    name: FilePath
    type: ExportFilterType


class ExportWriter(BaseModel):
    name: FilePath = FilePathAdapter.validate_python("latex")
    template: FilePath | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class ExportConfig(BaseModel):
    parameters: list[ExportParameter] = Field(default_factory=list)
    reader: ExportReader = ExportReader()
    filters: list[ExportFilter] = Field(default_factory=list)
    writer: ExportWriter = ExportWriter()


def validate_export_argument(
    argument: Any, parameter_type: list[ExportParameterType]
) -> Any:
    python_type: type | UnionType = parameter_type[0].python_type
    for type_ in parameter_type[1:]:
        python_type |= type_.python_type

    type_adapter = TypeAdapter(python_type)
    return type_adapter.validate_python(argument, strict=True)


def export_pdf(
    file: Path,
    /,
    *,
    auxiliary_dir: Path,
    pandoc_executable: Path,
    pandoc_reader: Path,
    pandoc_writer: Path,
    pandoc_template: Path,
    pandoc_variables: dict[str, str],
    latexmk_executable: Path,
) -> Path:
    tex_file = auxiliary_dir / file.with_suffix(".tex").name
    pdf_dir = auxiliary_dir / "pdf"
    pdf_file = pdf_dir / tex_file.with_suffix(".pdf").name
    pandoc_out = auxiliary_dir / "pandoc.out"
    pandoc_err = auxiliary_dir / "pandoc.err"
    latexmk_out = auxiliary_dir / "latexmk.out"
    latexmk_err = auxiliary_dir / "latexmk.err"

    auxiliary_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Converting %s to %s", file, tex_file)
    with open(pandoc_out, "w") as out, open(pandoc_err, "w") as err:
        subprocess.run(
            [
                str(pandoc_executable),
                "--from",
                str(pandoc_reader),
                "--to",
                str(pandoc_writer),
                "--standalone",
                "--template",
                str(pandoc_template),
                *[
                    f"--variable={key}={value}"
                    for key, value in pandoc_variables.items()
                ],
                "--output",
                str(tex_file),
                str(file),
            ],
            stdout=out,
            stderr=err,
            check=True,
        )

    logger.info("Compiling %s to %s", tex_file, pdf_file)
    with open(latexmk_out, "w") as out, open(latexmk_err, "w") as err:
        subprocess.run(
            [
                str(latexmk_executable),
                "-xelatex",
                "-bibtex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                "-shell-escape",  # Needed for `minted`, has security implications
                "-output-directory=" + str(pdf_dir),
                str(tex_file),
            ],
            stdout=out,
            stderr=err,
            check=True,
        )

    return pdf_file
