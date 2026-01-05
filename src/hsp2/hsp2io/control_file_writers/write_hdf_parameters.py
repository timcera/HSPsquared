from pathlib import Path

import pandas as pd


pd.set_option("io.hdf.default_format", "table")

_data_dir = Path(__file__).parent.parent.parent / "data"
_parameters = pd.read_csv(_data_dir / "Parameters.csv")
_tables = pd.read_csv(_data_dir / "Tables.csv")

Lapse = pd.Series(
    [
        0.0035,
        0.0035,
        0.0035,
        0.0035,
        0.0035,
        0.0035,
        0.0037,
        0.0040,
        0.0041,
        0.0043,
        0.0046,
        0.0047,
        0.0048,
        0.0049,
        0.0050,
        0.0050,
        0.0048,
        0.0046,
        0.0044,
        0.0042,
        0.0040,
        0.0038,
        0.0037,
        0.0036,
    ]
)

Seasons = pd.Series([0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0]).astype(bool)

Svp = pd.Series(
    [
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.005,
        1.01,
        1.01,
        1.015,
        1.02,
        1.03,
        1.04,
        1.06,
        1.08,
        1.1,
        1.29,
        1.66,
        2.13,
        2.74,
        3.49,
        4.40,
        5.55,
        6.87,
        8.36,
        10.1,
        12.2,
        14.6,
        17.5,
        20.9,
        24.8,
        29.3,
        34.6,
        40.7,
        47.7,
        55.7,
        64.9,
    ]
)


# def _global(global_dataframe):
#     start = str(
#         pd.Timestamp(
#             int(global_dataframe.loc[0, "SYR"]),
#             int(global_dataframe.loc[0, "SMO"]),
#             int(global_dataframe.loc[0, "SDA"]),
#         )
#         + pd.Timedelta(int(global_dataframe.loc[0, "SHR"]), unit="h")
#         + pd.Timedelta(int(global_dataframe.loc[0, "SMI"]), unit="m"),
#     )[:16]
#     stop = str(
#         pd.Timestamp(
#             int(global_dataframe.loc[0, "EYR"]),
#             int(global_dataframe.loc[0, "EMO"]),
#             int(global_dataframe.loc[0, "EDA"]),
#         )
#         + pd.Timedelta(int(global_dataframe.loc[0, "EHR"]), unit="h")
#         + pd.Timedelta(int(global_dataframe.loc[0, "EMI"]), unit="m"),
#     )[:16]
#     data = [
#         global_dataframe.loc[0, "COMMENT"],
#         start,
#         stop,
#         str(global_dataframe.loc[0, "UFG"]),
#     ]
#     return pd.DataFrame(
#         data, index=["Comment", "Start", "Stop", "Units"], columns=["Info"]
#     )
#
#
# def _opn_sequence(opn_sequence_df):
#     mask = opn_sequence_df["OPERATION"].isin(ops)
#     opn_sequence_df.loc[mask, "SEGMENT"] = opn_sequence_df.loc[mask, "OPERATION"].str[
#         0
#     ] + opn_sequence_df.loc[mask, "SEGMENT"].apply(lambda x: f"{int(x):03d}")
#     return opn_sequence_df
#
#
# def _network(network_df):
#     if "SVOL" in network_df.columns and "TVOL" in network_df.columns:
#         network_df["SVOLNO"] = network_df["SVOL"].str[0] + network_df["SVOLNO"].apply(
#             lambda x: f"{int(x):03d}"
#         )
#     return network_df
#
#
# def _schematic(schematic_df):
#     if "SVOL" in schematic_df.columns and "TVOL" in schematic_df.columns:
#         schematic_df["MLNO"] = schematic_df["MLNO"].apply(lambda x: f"ML{int(x):03d}")
#         schematic_df["SVOLNO"] = schematic_df["SVOL"].str[0] + schematic_df[
#             "SVOLNO"
#         ].apply(lambda x: f"{int(x):03d}")
#         schematic_df["TVOLNO"] = schematic_df["TVOL"].str[0] + schematic_df[
#             "TVOLNO"
#         ].apply(lambda x: f"{int(x):03d}")
#     return schematic_df
#
#
# def _mass_link(mass_link_df):
#     mass_link_df["MLNO"] = mass_link_df["MLNO"].apply(lambda x: f"ML{int(x):03d}")
#     return mass_link_df
#
#
# def _ext_sources(ext_sources_df):
#     if "TVOL" in ext_sources_df.columns:
#         ext_sources_df["SVOLNO"] = ext_sources_df["SVOLNO"].apply(
#             lambda x: f"TS{x:03d}"
#         )
#         ext_sources_df["SVOL"] = "*"
#         ext_sources_df["TVOLNO"] = ext_sources_df["TVOL"].str[0] + ext_sources_df[
#             "TVOLNO"
#         ].apply(lambda x: f"{int(x):03d}")
#     return ext_sources_df


def write_hdf_parameters(hdf_fname, parameters, mode="w"):
    """
    Write hsp2/HSPF model parameters to an HDF5 file.

    Parameters
    ----------
    hdf_fname : str
        The name of the HDF5 file to write to.
    parameters : dict
        A dictionary of pandas DataFrames containing the model parameters.
    mode : str, optional
        The file mode, either 'a' for append or 'w' for write (default is 'a').
    """
    # Fixup the DataFrames
    # for key, function in (
    #     (("EXT SOURCES",), _ext_sources),
    #     (("GLOBAL",), _global),
    #     (("MASS-LINK",), _mass_link),
    #     (("NETWORK",), _network),
    #     (("OPN SEQUENCE",), _opn_sequence),
    #     (("SCHEMATIC",), _schematic),
    # ):
    #     if key in parameters:
    #         parameters[key] = function(parameters[key])

    with pd.HDFStore(hdf_fname, mode=mode) as hdf_store:
        Lapse.to_hdf(hdf_store, key="TIMESERIES/LAPSE_Table")
        Seasons.to_hdf(hdf_store, key="TIMESERIES/SEASONS_Table")
        Svp.to_hdf(hdf_store, key="TIMESERIES/Saturated_Vapor_Pressure_Table")

        for key, table in parameters.items():
            table.to_hdf(hdf_store, key=key, data_columns=True, format="table")
