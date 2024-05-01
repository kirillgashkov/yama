import enum
from enum import Enum
from types import UnionType
from typing import Any, Self, assert_never

from pydantic import Field, TypeAdapter, model_validator

from yama.file.models import FilePath, FilePathAdapter
from yama.model.models import ModelBase


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


class ExportParameter(ModelBase):
    name: str
    type: list[ExportParameterType] = Field(min_length=1)
    default: Any = None

    @model_validator(mode="after")
    def validate_default(self) -> Self:
        if self.default is None:
            return self
        self.default = validate_export_argument(self.default, self.type)
        return self


class ExportReader(ModelBase):
    name: FilePath = FilePathAdapter.validate_python("commonmark")
    metadata: dict[str, str] = Field(default_factory=dict)


class ExportFilter(ModelBase):
    name: FilePath
    type: ExportFilterType


class ExportWriter(ModelBase):
    name: FilePath = FilePathAdapter.validate_python("latex")
    template: FilePath | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class ExportConfig(ModelBase):
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
