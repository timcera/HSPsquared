from enum import Enum
from typing import TYPE_CHECKING, Dict, Protocol, Union, runtime_checkable

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from hsp2.hsp2.model import Model

TimeSeriesDict = Dict[str, np.float64]


class Category(Enum):
    RESULTS = "RESULT"
    INPUTS = "INPUT"


@runtime_checkable
class SupportsReadParameters(Protocol):
    def read_parameters(self) -> "Model": ...


@runtime_checkable
class SupportsWriteParameters(Protocol):
    def write_parameters(self, model: "Model") -> None: ...


@runtime_checkable
class SupportsReadTS(Protocol):
    def read_ts(
        self,
        category: Category,
        operation: Union[str, None] = None,
        segment: Union[str, None] = None,
        activity: Union[str, None] = None,
    ) -> pd.DataFrame: ...


@runtime_checkable
class SupportsWriteTS(Protocol):
    def write_ts(
        self,
        data_frame: pd.DataFrame,
        category: Category,
        operation: Union[str, None] = None,
        segment: Union[str, None] = None,
        activity: Union[str, None] = None,
    ) -> None: ...


@runtime_checkable
class SupportsWriteLogging(Protocol):
    def write_log(self, hsp2_log: pd.DataFrame) -> None: ...

    def write_versioning(self, versions: pd.DataFrame) -> None: ...
