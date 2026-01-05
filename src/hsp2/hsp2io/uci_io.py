"""
UCI IO Manager for HSP2 model parameters and time series
"""

from hsp2.hsp2io.control_file_readers.read_uci_parameters import read_uci_parameters
from hsp2.hsp2io.io import IOManager
from hsp2.hsp2io.time_series_readers.read_wdm_ts import read_wdm_ts
from hsp2.hsp2io.time_series_writers.write_hdf_ts import write_hdf_ts

ops = {"COPY", "DISPLY", "GENER", "IMPLND", "PERLND", "RCHRES"}
conlike = {"CONS": "NCONS", "PQUAL": "NQUAL", "IQUAL": "NQUAL", "GQUAL": "NQUAL"}
_silt_clay_pm_map = {1: "silt", 2: "clay"}

UCIIOManager = IOManager(
    read_parameters=read_uci_parameters,
    read_ts=read_wdm_ts,
    write_ts=write_hdf_ts,
    log=None,
)
