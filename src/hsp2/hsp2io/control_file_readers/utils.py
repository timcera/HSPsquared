from pathlib import Path
import textwrap

import numpy as np
import pandas as pd

wrapper = textwrap.TextWrapper()

_dirname = Path(__file__).parent.parent.parent
_parameters = pd.read_csv(_dirname / "data" / "Parameters.csv")
_tables = pd.read_csv(_dirname / "data" / "Tables.csv")

# Bring over HDF_TABLE from _tables to _parameters.
_parameters = pd.merge(_parameters, _tables[[
    "HSPF_BLOCK",
    "HSPF_TABLE",
    "HDF_TABLE",
]], on=["HSPF_BLOCK", "HSPF_TABLE"], how="left")


def default_and_validation(parameters):
    """
    Fill in default values and validate parameter values.

    Parameters
    ----------
    parameters : dict of pd.DataFrame
        Dictionary of HDF table names to DataFrames of parameters.

    Returns
    -------
    nparameters : dict of pd.DataFrame
        Dictionary of HDF table names to DataFrames of parameters with
        defaults filled in and validated.
    """
    # Need to find the units to extract default, min, and max for float and
    # integer parameters.
    units = parameters["/CONTROL/GLOBAL"].loc["Units", "Info"]
    if not units or int(units) == 1:
        units = "ENGL"
    elif int(units) == 2:
        units = "METR"

    nparameters = {}
    for hdf_table, parms in parameters.items():
        if hdf_table == "/CONTROL/GLOBAL":
            nparameters[hdf_table] = parms
            continue

        if hdf_table.startswith("/FTABLES/FT"):
            table_name = "/FTABLES/FT"
        else:
            table_name = hdf_table

        parameter_data = _parameters[
            _parameters["HDF_TABLE"] == table_name
        ]

        parameter_data = parameter_data.set_index("PARAMETER_NAME")

        cols = parms.columns.drop(["TVOLNO", "TOPFST", "TOPLST"], errors="ignore")
        parameter_data = parameter_data.loc[cols]

        # Need to ignore these parameters because they are only used to
        # calculate OPNID and TVOL.
        parameter_data = parameter_data.loc[
            ~parameter_data.index.isin(["OPNIDLAST", "TOPLST"])
        ]

        # Set the numerical defaults from DEFAULT_ENGL or DEFAULT_METR from the
        # Parameters.csv file and then use fillna.
        defaults = parameter_data[
            [f"DEFAULT_{units}", f"MIN_{units}", f"MAX_{units}"]
        ].astype(float)
        defaults.columns = ["DEFAULT", "MIN", "MAX"]

        # Set the types.
        nparms = parms.astype(
            dict(zip(parameter_data.index, parameter_data["TYPE"].values)),
            errors="ignore",
        )

        # Fill in the numerical defaults.
        nparms = nparms.fillna(dict(zip(defaults.index, defaults["DEFAULT"].values)))

        # Fill in the text defaults.
        defaults_text = parameter_data[["DEFAULT_TEXT"]].dropna().astype(str)
        nparms = nparms.fillna(
            dict(zip(defaults_text.index, defaults_text["DEFAULT_TEXT"].values))
        )

        # Only fill string-like columns with empty string.  Avoid filling
        # numeric or other dtypes which could coerce types or mask missing
        # numeric values. Use both 'object' and pandas 'string' dtypes so
        # this works whether convert_dtypes produced Python object columns
        # or pandas StringDtype columns.
        str_cols = nparms.select_dtypes(include=["object", "string"]).columns
        if len(str_cols):
            nparms[str_cols] = nparms[str_cols].fillna("")
            nparms[str_cols] = nparms[str_cols].replace("nan", "")
            nparms[str_cols] = nparms[str_cols].astype(object)

        for name, series in nparms.items():
            loop_series = series.dropna()
            if loop_series.empty:
                continue

            if pd.api.types.is_string_dtype(loop_series):
                loop_series = loop_series.str.replace("[a-zA-Z]", "", regex=True)
                loop_series = pd.to_numeric(loop_series, errors="coerce").dropna()

            # Check that values are within the allowed range.
            left = defaults.loc[parameter_data.index == name, "MIN"]
            if left.empty:
                left = np.nan
            else:
                left = left.values[0]
            if np.isfinite(left):
                lmask = loop_series >= left
            else:
                lmask = pd.Series([True] * len(loop_series), index=loop_series.index)

            right = defaults.loc[parameter_data.index == name, "MAX"]
            if right.empty:
                right = np.nan
            else:
                right = right.values[0]
            if np.isfinite(right):
                rmask = loop_series <= right
            else:
                rmask = pd.Series([True] * len(loop_series), index=loop_series.index)

            testdf = lmask & rmask
            if not testdf.all():
                raise ValueError(
                    wrapper.wrap(
                        textwrap.dedent(f"""\
                            Values for hdf_table={hdf_table}, and
                            parameter={name} are outside of the allowed range.
                            min={left}, max={right}, series={loop_series.values}.
                            """)
                    )
                )

        for name, series in nparms.items():
            # Check that string values are VALID.
            allowed = parameter_data.loc[parameter_data.index == name, "VALID"]
            if len(allowed) == 0:
                continue
            allowed = allowed.values[0]
            if isinstance(allowed, str):
                allowed = eval(allowed)
            else:
                continue
            try:
                lseries = series.str.replace("nan", "").str.strip()
            except AttributeError:
                lseries = series
            if not lseries.isin(allowed).all():
                raise ValueError(
                    wrapper.wrap(
                        textwrap.dedent(f"""\
                            Values for hdf_table={hdf_table}, and
                            parameter={name} are outside of the allowed set.
                            allowed={allowed}, values={lseries.values}.
                            """)
                    )
                )

        if "Unnamed: 0" in nparms.columns:
            nparms = nparms.drop(columns=["Unnamed: 0"])

        # Select only used rows and columns.
        if hdf_table.startswith("/FTABLES/FT"):
            rows, cols = nparms.loc[0, ["rows", "cols"]]
            nparms = nparms.iloc[: int(rows), : int(cols)]

        if not nparms.empty:
            nparameters[hdf_table] = nparms
    return nparameters
