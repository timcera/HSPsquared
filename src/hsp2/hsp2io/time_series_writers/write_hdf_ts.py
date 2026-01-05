from typing import Any

import pandas as pd

from hsp2.hsp2io.protocols import Category


def write_ts(
    hdffile: str,
    data_frame: pd.DataFrame,
    category: Category,
    operation: str,
    segment: str,
    activity: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Write time series data to an HDF5 file.

    Parameters
    ----------
    hdffile
        The name of the HDF5 file to write to.
    data_frame
        The time series data to write.
    category
        The category of the time series (e.g., INPUTS or RESULTS).
    operation
        The operation associated with the time series.
    segment
        The segment associated with the time series.
    activity
        The activity associated with the time series.
    """
    path = f"{operation}_{segment}/{activity}"
    if category:
        path = "RESULTS/" + path
    complevel = None
    if "compress" in kwargs:
        if kwargs["compress"]:
            complevel = 9
    data_frame.to_hdf(
        hdffile, key=path, format="t", data_columns=True, complevel=complevel
    )
