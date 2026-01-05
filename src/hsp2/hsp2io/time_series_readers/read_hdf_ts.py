"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.

Based on MATLAB program by Seth Kenner, RESPEC
License: LGPL2
"""

from typing import Union

import pandas as pd

from hsp2.hsp2io.protocols import Category


def read_hdf_ts(
    hdffile,
    category: Category,
    operation: Union[str, None] = None,
    segment: Union[str, None] = None,
    activity: Union[str, None] = None,
) -> pd.DataFrame:
    """Read time series from HDF5 file"""
    try:
        path = ""
        if category == category.INPUTS:
            path = f"TIMESERIES/{segment}"
        elif category == category.RESULTS:
            path = f"RESULTS/{operation}_{segment}/{activity}"
        return pd.read_hdf(hdffile, path)
    except KeyError:
        return pd.DataFrame()
