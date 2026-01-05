from pathlib import Path

import pandas as pd

from hsp2.hsp2.main import main
from hsp2.hsp2io.io import IOManager
from hsp2.hsp2io.control_file_readers.read_uci_parameters import read_uci_parameters
from hsp2.hsp2io.control_file_writers.write_hdf_parameters import write_hdf_parameters
from hsp2.hsp2io.time_series_readers.read_wdm_ts import read_ts as read_wdm_ts
from hsp2.hsp2io.time_series_writers.write_hdf_ts import write_ts as write_hdf_ts

_data_dir = Path(__file__).parent.parent / "data"
_parameters = pd.read_csv(_data_dir / "Parameters.csv")
_tables = pd.read_csv(_data_dir / "Tables.csv")


def run(h5file, saveall=True, compress=True):
    """Run a HSPsquared model.

    Parameters
    ----------
    h5file: str
        HDF5 (path) filename used for both input and output.
    saveall: bool
        [optional] Default is True.
        Saves all calculated data ignoring SAVE tables.
    compression: bool
        [optional] Default is True.
        use compression on the save h5 file.
    """
    io_manager = IOManager
    main(io_manager(h5file), saveall=saveall, jupyterlab=compress)


def import_uci(ucifile, h5file):
    """
    Import UCI and WDM files into HDF5 file.

    Parameters
    ----------
    ucifile: str
        The UCI file to import into HDF file.
    h5file: str
        The destination HDF5 file.
    """
    pars = read_uci_parameters(ucifile)
    write_hdf_parameters(h5file, pars, mode="w")

    # Extract the FILES block from the UCI file that lists WDM files.
    with open(ucifile, encoding="ascii") as fp:
        uci = []
        for line in fp.readlines():
            if "***" in line[:81]:
                continue
            if not line[:81].strip():
                continue
            uci.append(line[:81].rstrip())
            if line[:81].rstrip() == "END FILES":
                break

    files_start = uci.index("FILES")
    files_end = uci.index("END FILES")

    uci_dir = Path(ucifile).parent
    files_block = pd.read_fwf(
        uci[files_start : files_end + 1], colspecs=[(0, 7), (8, 14), (16, 81)]
    )
    for idx, row in files_block.iterrows():
        if row[0].strip() in ["WDM", "WDM1", "WDM2", "WDM3", "WDM4"]:
            wdmfile = (uci_dir / row[2].strip()).resolve()
            if wdmfile.exists():
                time_series = read_wdm_ts(wdmfile)
                for key, series in time_series.items():
                    write_hdf_ts(h5file, series, dataset_name=key)
