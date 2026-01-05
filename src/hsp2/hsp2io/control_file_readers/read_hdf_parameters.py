"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.

License: LGPL2
"""
from typing import Union
from pathlib import Path

import pandas as pd

from .utils import default_and_validation


def read_hdf_parameters(hdfname: Union[str, Path]) -> dict:
    """
    Reads HSPsquared parameter tables from an HDF5 file.

    Parameters
    ----------
    hdfname : str
        Name/path of HDF5 file to read.

    Returns
    -------
    df
        Returns HSP2 Model object populated with data from HDF5 file.
    """
    _dirname = Path(__file__).parent.parent.parent
    _tables = pd.read_csv(_dirname / "data" / "Tables.csv")

    table_names = _tables["HDF_TABLE"].dropna().unique()
    collect = {}
    with pd.HDFStore(hdfname, "r") as hdf:
        for table_name in table_names:
            if table_name in hdf:
                collect[table_name] = hdf[table_name]
    return default_and_validation(collect)
