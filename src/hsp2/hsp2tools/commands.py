from pathlib import Path

from hsp2.hsp2.main import main
from hsp2.hsp2io.hdf import HDF5
from hsp2.hsp2io.io import IOManager
from hsp2.hsp2tools.readUCI import readUCI
from hsp2.hsp2tools.readWDM import readWDM


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
    hdf5_instance = HDF5(h5file)
    io_manager = IOManager(hdf5_instance)
    main(io_manager, saveall=saveall, jupyterlab=compress)


def import_uci(ucifile, h5file):
    """Import UCI and WDM files into HDF5 file.

    Parameters
    ----------
    ucifile: str
        The UCI file to import into HDF file.
    h5file: str
        The destination HDF5 file.
    """

    readUCI(ucifile, h5file)

    with open(ucifile) as fp:
        uci = []
        for line in fp.readlines():
            if "***" in line[:81]:
                continue
            if not line[:81].strip():
                continue
            uci.append(line[:81].rstrip())

    files_start = uci.index("FILES")
    files_end = uci.index("END FILES")

    uci_dir = Path(ucifile).parent
    for nline in uci[files_start : files_end + 1]:
        if (nline[:10].strip())[:3] == "WDM":
            wdmfile = (uci_dir / nline[16:].strip()).resolve()
            if wdmfile.exists():
                readWDM(wdmfile, h5file)
