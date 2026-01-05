"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.
License: LGPL2
"""

from pathlib import Path

import pandas as pd

from .utils import default_and_validation

_dirname = Path(__file__).parent.parent.parent
_parameters = pd.read_csv(_dirname / "data" / "Parameters.csv")


def read_csv_parameters(run_csvname):
    """
    Reads a set of CSV files into a dictionary of DataFrames.

    Parameters
    ----------
    run_csvname : str
        The *RUN.csv file is a file that is a marker for a set of CSV files
        named in the form using
        {HSPF_block}_{HSPF_table}_{HSPF_table_number}.csv.

        The *RUN.csv file can be empty, but must exist.

        You can organize your CSV files in a directory structure
        that makes sense to you, but the *RUN.csv file must be in the
        same directory as the other CSV files.

        Example 1, if `run_csvname` is '/path/to/Black_Creek/RUN.csv' ::

            /path/to/Black_Creek/RUN.csv
            /path/to/Black_Creek/FTABLES_FTABLE_1.csv
            /path/to/Black_Creek/FTABLES_FTABLE_2.csv
            /path/to/Black_Creek/MASS-LINK_MASS-LINK_1.csv
            /path/to/Black_Creek/PERLND_PWAT-PARM1.csv
            /path/to/Black_Creek/PERLND_PWAT-PARM2.csv
            /path/to/Black_Creek/RCHRES_HYDR-PARM1.csv
            /path/to/Black_Creek/RCHRES_HYDR-PARM2.csv

        You can also organize your CSV files with a prefix that would allow you
        to keep multiple models in a single directory.

        Example 2, if `run_csvname` is '/different/path/Black_Creek_RUN.csv' ::

            /different/path/Black_Creek_RUN.csv
            /different/path/Black_Creek_FTABLES_FTABLE_1.csv
            /different/path/Black_Creek_FTABLES_FTABLE_2.csv
            /different/path/Black_Creek_MASS-LINK_MASS-LINK_1.csv
            /different/path/Black_Creek_PERLND_PWAT-PARM1.csv
            /different/path/Black_Creek_PERLND_PWAT-PARM2.csv
            /different/path/Black_Creek_RCHRES_HYDR-PARM1.csv
            /different/path/Black_Creek_RCHRES_HYDR-PARM2.csv

    Returns
    -------
    dict
        A dictionary of DataFrames, keyed on (HSPF_block, (HSPF_table,
        HSPF_table_number)).
    """
    if not run_csvname.lower().endswith("run.csv"):
        raise ValueError(f"{run_csvname} must be named *RUN.csv")

    ifiles = Path(run_csvname[: -len("RUN.csv")]).glob("*.csv")

    ncollected = {}
    for ifile in ifiles:
        if ifile.name.lower().endswith("run.csv"):
            continue
        words = ifile.stem.split("_")
        if len(words) == 3:
            hspf_block = words[0]
            hspf_table = words[1]
            hspf_table_number = words[2]
        elif len(words) == 2:
            hspf_block = words[0]
            hspf_table = words[1]
            hspf_table_number = None
        elif len(words) == 1:
            hspf_block = words[0]
            hspf_table = None
            hspf_table_number = None
        else:
            raise ValueError(
                f"{ifile} does not follow the naming convention "
                "{HSPF_block}_{HSPF_table}_{HSPF_table_number}.csv"
            )
        ncollected[(hspf_block, (hspf_table, hspf_table_number))] = pd.read_csv(ifile)
    return default_and_validation(ncollected, _parameters)
