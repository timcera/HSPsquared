"""
IOManager classes for HSP2 model parameter and time series management.

This module provides the base IOManager class and validation functionality for
HSP2 models. For specific implementations, see:
- HDF5IOManager in io_classes.py for HDF5 file format
- UCIIOManager in io_classes.py for UCI control files with WDM/HBN time series
- CSVIOManager in io_classes.py for CSV-based data storage
"""

import functools
from pathlib import Path, PurePath
from textwrap import dedent
from typing import List, Union

import pandas as pd

from hsp2.hsp2.model import Model
from hsp2.hsp2.utilities import pandas_offset_by_version
from hsp2.hsp2io.protocols import (
    Category,
    SupportsReadParameters,
    SupportsReadTS,
    SupportsWriteLogging,
    SupportsWriteTS,
)
from hsp2.hsp2io.control_file_readers.read_hdf_parameters import read_hdf_parameters
from hsp2.hsp2io.control_file_readers.read_uci_parameters import read_uci_parameters
from hsp2.hsp2io.control_file_readers.read_csv_parameters import read_csv_parameters
from hsp2.hsp2io.time_series_readers import read_hdf_ts
from hsp2.hsp2io.time_series_writers import write_hdf_ts


class IOManager:
    """Management class for IO operations needed to execute the HSP2 model"""

    def __init__(
        self,
        io_combined: Union[
            SupportsReadParameters, SupportsReadTS, SupportsWriteTS, None
        ] = None,
        parameter_source: Union[str, Path, None] = None,
        ts_source: Union[SupportsReadTS, None] = None,
        ts_target: Union[SupportsReadTS, SupportsWriteTS, None] = None,
        log: Union[SupportsWriteLogging, None] = None,
    ) -> None:
        """
        Initialize the IOManager for HSP2 model IO operations.

        Parameters
        ----------
        io_combined : SupportsReadParameters or SupportsReadTS or SupportsWriteTS or None, optional
            Object that combines protocols for Parameters, Input, Output, and
            Log. If `read_parameters`, `ts_source`, `ts_target`, or `log` are not
            specified, this argument will be used as the default for those.
        parameter_source
        ts_source
        ts_target
        log

        +------------------+-------+------+--------+--------+------+------------+
        | Parameter        | .hdf5 | .uci | .uci   | .wdm   | .csv | IOManager  |
        |                  | .h5   |      | (WDM1- | (WDM1- |      | compatible |
        |                  |       |      | WDM4)  | WDM4)  |      | class      |
        +==================+=======+======+========+========+======+============+
        | io_combined      | X     |      |        |        |      | X          |
        +------------------+-------+------+--------+--------+------+------------+
        | parameter_source | X     | X    |        |        | X    |            |
        +------------------+-------+------+--------+--------+------+------------+
        | ts_source        | X     |      |        |        |      |            |
        +------------------+-------+------+--------+--------+------+------------+
        | ts_target        | X     |      |        |        |      |            |
        +------------------+-------+------+--------+--------+------+------------+
        | write_parameters | X     |      |        |        | X    |            |
        +------------------+-------+------+--------+--------+------+------------+
        | log              | X     |      |        |        |      |            |
        +------------------+-------+------+--------+--------+------+------------+

        `parameter_source`, `ts_source`, `ts_target`, are all required if
        `io_combined` is None.

        Attributes
        ----------
        self._store : dict
            A dictionary storing parameter data read from the source. Keys are
            HDF styled paths within the data source, and values are pandas
            DataFrames.
        self.model : Model
            An instance of the HSP2 Model class populated with parameters
            read from self._store.
        """
        if io_combined is None and any(
            v is None for v in [parameter_source, ts_source, ts_target]
        ):
            raise ValueError(
                dedent("""\

                Either io_combined, or all of the keyword arguments
                parameter_source, ts_source, and ts_target must be provided.

                """)
            )

        if io_combined is not None:
            if isinstance(io_combined, (str, PurePath)):
                if Path(io_combined).suffix.lower() in [".h5", ".hdf5"]:
                    self._read_parameters = read_hdf_parameters
                    self._input = read_hdf_ts
                    self._output = write_hdf_ts
                else:
                    raise ValueError(
                        dedent(f"""\

                        Unsupported file type: {Path(io_combined).suffix}
                        Currently only HDF5 format files are supported as
                        a combined IO source and target for parameters and time
                        series.  The allowable file name extensions are .h5 and
                        .hdf5.

                        """)
                    )
            elif (
                io_combined.hasattr("read_parameters")
                and io_combined.hasattr("read_ts")
                and io_combined.hasattr("write_ts")
            ):
                self._read_parameters = io_combined.read_parameters
                self._input = io_combined.read_ts
                self._output = io_combined.write_ts
        else:
            parameter_source_suffix = Path(parameter_source).suffix.lower()
            if parameter_source_suffix == ".uci":
                if ts_source is not None:
                    raise ValueError(
                        dedent("""\

                        When using UCI control files for parameter input, the
                        time series input sources WDM1, WDM2, WDM3, and/or WDM4
                        is read from the UCI file and don't need to be supplied
                        separately.

                        """)
                    )
                self._read_parameters = read_uci_parameters
            elif parameter_source_suffix == ".csv":
                self._read_parameters = read_csv_parameters
            elif parameter_source_suffix in [".h5", ".hdf5"]:
                self._read_parameters = read_hdf_parameters
            else:
                raise ValueError(
                    dedent(f"""\

                    Unsupported file type: {parameter_source_suffix}
                    Currently only .uci, .csv, .h5 and .hdf5 are supported for
                    parameter sources.

                    """)
                )

            ts_source_suffix = Path(ts_source).suffix.lower()
            if ts_source_suffix in [".h5", ".hdf5"]:
                self._input = functools.partialmethod(read_hdf_ts, ts_source)
            else:
                raise ValueError(
                    dedent(f"""\

                    Unsupported file type: {ts_source_suffix}
                    Currently only .h5, and .hdf5
                    are supported for time series input sources.

                    """)
                )

            ts_target_suffix = Path(ts_target).suffix.lower()
            if ts_target_suffix in [".h5", ".hdf5"]:
                self._output = functools.partialmethod(write_hdf_ts, ts_target)
            else:
                raise ValueError(
                    dedent(f"""\

                    Unsupported file type: {ts_target_suffix}
                    Currently only .h5 and .hdf5 are supported for time series
                    output targets.

                    """)
                )

        self._in_memory = {}

        self._store = self._read_parameters(parameter_source)

    def read_parameters(self) -> Model:
        """
        Read parameters from self._store and populate Model instance.
        """
        model = Model()
        for path in self._store.keys():
            op, module, *other = path[1:].split(sep="/", maxsplit=3)
            s = "_".join(other)
            if op == "CONTROL":
                if module == "GLOBAL":
                    temp = self._store[path].to_dict()["Info"]
                    model.siminfo["start"] = pd.Timestamp(temp["Start"])
                    model.siminfo["stop"] = pd.Timestamp(temp["Stop"])
                    model.siminfo["units"] = 1
                    if "Units" in temp:
                        if int(temp["Units"]):
                            model.siminfo["units"] = int(temp["Units"])
                elif module == "LINKS":
                    for row in self._store[path].fillna("").itertuples():
                        if row.TVOLNO != "":
                            model.ddlinks[f"{row.TVOLNO}"].append(row)
                        else:
                            model.ddlinks[f"{row.TOPFST}"].append(row)

                elif module == "MASS_LINKS":
                    for row in self._store[path].replace("na", "").itertuples():
                        model.ddmasslinks[row.MLNO].append(row)
                elif module == "EXT_SOURCES":
                    for row in self._store[path].replace("na", "").itertuples():
                        model.ddext_sources[(row.TVOL, row.TVOLNO)].append(row)
                elif module == "OP_SEQUENCE":
                    model.opseq = self._store[path]
            elif op in {"PERLND", "IMPLND", "RCHRES"}:
                for op_id, vdict in self._store[path].to_dict("index").items():
                    model.model[(op, module, op_id)][s] = vdict
            elif op == "GENER":
                for row in self._store[path].itertuples():
                    if len(row.OPNID.split()) == 1:
                        start = int(row.OPNID)
                        stop = start
                    else:
                        start, stop = row.OPNID.split()
                    for i in range(int(start), int(stop) + 1):
                        if module != "COEFFS":
                            model.ddgener[module][f"G{i:03d}"] = row[2]
                        else:
                            for it in range(1, 8):
                                model.ddgener[f"K{it:01d}"][f"G{i:03d}"] = row[it + 1]
            elif op == "FTABLES":
                model.ftables[module] = self._store[path]
            elif op == "SPEC_ACTIONS":
                model.specactions[module] = self._store[path]
            elif op == "MONTHDATA":
                if not model.monthdata:
                    model.monthdata = {}
                model.monthdata[f"{op}/{module}"] = self._store[path]
        return model

    def write_ts(
        self,
        data_frame: pd.DataFrame,
        save_columns: List[str],
        category: Category,
        operation: Union[str, None] = None,
        segment: Union[str, None] = None,
        activity: Union[str, None] = None,
        outstep: int = 2,
        *args,
        **kwargs,
    ) -> None:
        key = (category, operation, segment, activity)
        self._in_memory[key] = data_frame.copy(deep=True)

        drop_columns = [c for c in data_frame.columns if c not in save_columns]
        if drop_columns:
            data_frame = data_frame.drop(columns=drop_columns)

        if not isinstance(data_frame.index, pd.core.indexes.datetimes.DatetimeIndex):
            data_frame = data_frame.to_timestamp()

        if outstep == 3:
            # change time step of output to daily
            sumdf1 = data_frame.resample("D", origin="start").sum()
            lastdf2 = data_frame.resample("D", origin="start").last()
            meandf3 = data_frame.resample("D", origin="start").mean()
            data_frame = pd.merge(
                lastdf2.add_suffix("_last"),
                sumdf1.add_suffix("_sum"),
                left_index=True,
                right_index=True,
            )
            data_frame = pd.merge(
                data_frame,
                meandf3.add_suffix("_aver"),
                left_index=True,
                right_index=True,
            )
        elif outstep == 4:
            # change to monthly
            sumdf1 = data_frame.resample(
                pandas_offset_by_version("ME"), origin="start"
            ).sum()
            lastdf2 = data_frame.resample(
                pandas_offset_by_version("ME"), origin="start"
            ).last()
            meandf3 = data_frame.resample(
                pandas_offset_by_version("ME"), origin="start"
            ).mean()
            data_frame = pd.merge(
                lastdf2.add_suffix("_last"),
                sumdf1.add_suffix("_sum"),
                left_index=True,
                right_index=True,
            )
            data_frame = pd.merge(
                data_frame,
                meandf3.add_suffix("_aver"),
                left_index=True,
                right_index=True,
            )
        elif outstep == 5:
            # change to annual
            sumdf1 = data_frame.resample(
                pandas_offset_by_version("YE"), origin="start"
            ).sum()
            lastdf2 = data_frame.resample(
                pandas_offset_by_version("YE"), origin="start"
            ).last()
            meandf3 = data_frame.resample(
                pandas_offset_by_version("YE"), origin="start"
            ).mean()
            data_frame = pd.merge(
                lastdf2.add_suffix("_last"),
                sumdf1.add_suffix("_sum"),
                left_index=True,
                right_index=True,
            )
            data_frame = pd.merge(
                data_frame,
                meandf3.add_suffix("_aver"),
                left_index=True,
                right_index=True,
            )
        self._output.write_ts(data_frame, category, operation, segment, activity)

    def read_ts(
        self,
        category: Category,
        operation: Union[str, None] = None,
        segment: Union[str, None] = None,
        activity: Union[str, None] = None,
        *args,
        **kwargs,
    ) -> pd.DataFrame:
        data_frame = self._get_in_memory(category, operation, segment, activity)
        if data_frame is not None:
            return data_frame
        if category == Category.INPUTS:
            data_frame = self._input.read_ts(category, operation, segment, activity)
            key = (category, operation, segment, activity)
            self._in_memory[key] = data_frame.copy(deep=True)
            return data_frame
        return pd.DataFrame

    def write_log(self, data_frame) -> None:
        if self._log:
            self._log.write_log(data_frame)

    def write_versioning(self, data_frame) -> None:
        if self._log:
            self._log.write_versioning(data_frame)

    def _get_in_memory(
        self,
        category: Category,
        operation: Union[str, None] = None,
        segment: Union[str, None] = None,
        activity: Union[str, None] = None,
    ) -> Union[pd.DataFrame, None]:
        key = (category, operation, segment, activity)
        try:
            return self._in_memory[key].copy(deep=True)
        except KeyError:
            return None
