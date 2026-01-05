"""
hdf IO Manager for HSP2 model parameters and time series
"""

from hsp2.hsp2io.control_file_readers.read_hdf_parameters import read_hdf_parameters
from hsp2.hsp2io.io import IOManager
from hsp2.hsp2io.time_series_readers.read_hdf_ts import read_hdf_ts
from hsp2.hsp2io.time_series_writers.write_hdf_ts import write_hdf_ts

HDFIOManager = IOManager(
    read_parameters=read_hdf_parameters,
    read_ts=read_hdf_ts,
    write_ts=write_hdf_ts,
    log=None,
)
