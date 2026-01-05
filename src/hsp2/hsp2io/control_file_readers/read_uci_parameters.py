"""
Copyright 2020 by RESPEC, INC. - see License.txt with this HSP2 distribution
Author: Robert Heaphy, Ph.D.
"""

import re
import textwrap
import warnings
from collections import defaultdict
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from ..common import ops
from .utils import default_and_validation

wrapper = textwrap.TextWrapper()

# The SILT-CLAY-PM table appears twice in the UCI file, first for silt and
# second for clay.  Use this mapping to adjust the table name when reading.
# The SILT-CLAY-PM table is the only table that appears more than once in
# the UCI file with the same name.
_silt_clay_pm_map = {0: "silt", 1: "clay"}

_dirname = Path(__file__).parent.parent.parent
fill_table_name = {"HSPF_TABLE": ""}
_tables = pd.read_csv(_dirname / "data" / "Tables.csv").fillna(fill_table_name)
_parameters = pd.read_csv(_dirname / "data" / "Parameters.csv").fillna(fill_table_name)

# Bring over HDF_TABLE from _tables to _parameters.
_parameters = pd.merge(_parameters, _tables[[
    "HSPF_BLOCK",
    "HSPF_TABLE",
    "HDF_TABLE",
]], on=["HSPF_BLOCK", "HSPF_TABLE"], how="left")


def _reader(filename):
    # simple reader to return non blank, non comment and proper length lines
    with open(filename, encoding="ascii") as uci_file:
        for line_number, line in enumerate(uci_file):
            # UCI max line length is 80
            nline = line.rstrip()
            if len(nline) > 80:
                warnings.warn(
                    textwrap.dedent(f"""\
                        Everything after 80 characters in a UCI file is
                        completely ignored, even '***' comment identifier.

                        file: {filename}
                        line number: {line_number + 1}
                        length: {len(line)}
                        line:
                        '{line}'
                        """)
                )
            nline = nline[:81].rstrip()
            # If line is a comment or blank, skip it.
            if "***" in nline or not nline:
                continue
            yield nline


def read_uci_parameters(uciname) -> dict:
    block_names = _tables["HSPF_BLOCK"].unique()

    # Parse UCI File
    #
    # `collected` is a dictionary that will store the data from the UCI file,
    # key = (HSPF_BLOCK, HSPF_TABLE, table_num)
    # value = list of lines from the UCI file that belong to that table
    #
    # 'table_num' is only used for FTABLE and MASS-LINK tables.
    block_name = ""
    inside_block = False
    inside_table = False
    hspf_table = ""
    table_num = None
    collected = {}
    silt_clay_pm_index = 0

    # Special Actions have a logical condition that is built up as the
    # lines are read to establish whether an action is to be taken or not.
    spec_actions_if = [True]
    spec_actions_else_if = []
    condition = ""

    for line in _reader(uciname):
        # Identify the start of a block.
        if line in block_names and inside_block is False:
            inside_block = True
            block_name = line
            hspf_table = ""
            table_num = None

            # Find all the table names for this block from _tables
            parameter_table = _tables[(_tables["HSPF_BLOCK"] == block_name)]
            table_names = parameter_table["HSPF_TABLE"].unique()

            continue

        if inside_block is True:
            # Identify the end of a block.
            if line == f"END {block_name}":
                inside_block = False
                block_name = ""
                hspf_table = ""
                continue

            words = line.split()

            # Adjust table_name to make the first SILT-CLAY-PM table name
            # SILT-CLAY-PM_silt and the second SILT-CLAY-PM table name
            # SILT-CLAY-PM_clay.
            if words[0] == "SILT-CLAY-PM":
                words[0] = f"{words[0]}_{_silt_clay_pm_map[silt_clay_pm_index]}"
                silt_clay_pm_index = silt_clay_pm_index + 1

            # We are inside a block, now identify the start of a table.
            if words[0] in table_names and inside_table is False:
                inside_table = True
                hspf_table = words[0]
                table_num = None

                # For FTABLE and MASS-LINK tables, get the table number.
                if hspf_table in ["FTABLE", "MASS-LINK"]:
                    if len(words) == 2:
                        hspf_table = words[0]
                        try:
                            table_num = int(words[1])
                        except ValueError:
                            raise ValueError(
                                wrapper.wrap(
                                    textwrap.dedent(f"""\
                                        The table number "{words[1]}" following
                                        the "{hspf_table}" table name in the
                                        UCI file "{uciname}" is not an integer.
                                        """)
                                )
                            )
                    else:
                        raise ValueError(
                            wrapper.wrap(
                                textwrap.dedent(f"""\
                                    The "{hspf_table}" table in the UCI file
                                    "{uciname}" must have a number following it.
                                    """)
                            )
                        )
                continue

            # Identify the end of a table.
            # Have to use .startswith to accommodate FTABLEs and the
            # SILT-CLAY-PM tables.  FTABLEs might have something like "  END
            # FTABLE999" to end the FTABLE block so can't just match to
            # words[1] and similarly for SILT-CLAY-PM-silt and
            # SILT-CLAY-PM-clay.
            if (
                inside_table is True
                and words[0] == "END"
                and (
                    words[1].startswith(hspf_table)
                    or words[1].startswith("SILT-CLAY-PM")
                )
            ):
                inside_table = False
                hspf_table = ""
                continue

            if block_name == "OPN SEQUENCE":
                if "INDELT" in words:
                    # INDELT can be in minutes or hours:minutes and I convert
                    # here to total minutes.
                    s = words[-1].split(":")
                    indelt = int(s[0]) if len(s) == 1 else 60 * int(s[0]) + int(s[1])
                if "INGRP" in words:
                    continue
                # Add INDELT to the end of the line, until changed by another
                # INDELT line.  The "OPN SEQUENCE" block implicitly does this,
                # but we need to make it explicit here.
                line = f"{line:<80}{indelt:10d}"

            if block_name == "SPEC-ACTIONS":
                # The SPEC-ACTIONS block doesn't have explicit tables
                # identified, but can create implicit tables based on the
                # contents of the lines.  The implicit tables are: ACTION,
                # DISTRB, UVNAME, and UVQUAN.
                hspf_table = "ACTION"
                if words[0] in ["DISTRB", "UVNAME", "UVQUAN"]:
                    hspf_table = words[0]
                elif words[0] == "IF" or f"{words[0]} {words[1]}" == "ELSE IF":
                    continuation_lines = [" ".join(line.strip().split())]
                    while True:
                        loop_words = continuation_lines[-1].split()
                        if loop_words[-1] == "THEN":
                            continuation_line = " ".join(continuation_lines)
                            break
                        continuation_lines.append(" ".join(line.next().strip().split()))
                    if words[0] == "IF":
                        spec_actions_if.append(
                            f"({continuation_line.partition('IF ')[2].partition(' THEN')[0].strip()})"
                        )
                        condition = " and ".join(spec_actions_if)
                    elif f"{words[0]} {words[1]}" == "ELSE IF":
                        current_else_if = f"({continuation_line.partition('ELSE IF ')[2].partition(' THEN')[0].strip()})"
                        spec_actions_else_if.append(current_else_if)
                        if len(spec_actions_else_if) == 1:
                            condition = (
                                f" not {spec_actions_if[-1]} and {current_else_if}"
                            )
                        else:
                            condition = f" not {spec_actions_if[-1]} and not {' and not '.join(spec_actions_else_if[:-1])} and {current_else_if}"
                elif words[0] == "ELSE":
                    if spec_actions_else_if:
                        condition = f" not {spec_actions_if[-1]} and not {' and not '.join(spec_actions_else_if)}"
                    else:
                        condition = f" not {spec_actions_if[-1]}"
                elif f"{words[0]} {words[1]}" == "END IF":
                    spec_actions_if.pop()
                    spec_actions_else_if = []
                    condition = spec_actions_if[-1]
                condition = (
                    " ".join(condition.split())
                    .replace(" OR ", " or ")
                    .replace(" AND ", " and ")
                )
                line = f"{line:<80}{condition}"

            # Keep the key as (HSPF_BLOCK, HSPF_TABLE, table_num) until
            # finished processing the individual tables.
            key = (block_name, hspf_table, table_num)
            collected.setdefault(key, []).append(line)

    # At this point the entire UCI file has been read into the `collected`
    # dictionary, and now the `collected` dictionary will be processed.  The
    # values are just lists of lines from the UCI file keyed to (HSPF_BLOCK,
    # HSPF_TABLE, table_num).  The "table_num" is only used for FTABLE and
    # MASS-LINK tables.

    # Check for required tables.
    missing_requirements = []
    for block, table, table_num in collected:
        # Find the row in _tables for this block/table
        row = _tables[
            (_tables["HSPF_BLOCK"] == block) & (_tables["HSPF_TABLE"] == table)
        ]
        if not row.empty:
            require_str = row.iloc[0]["IF_HAVE_THEN_REQUIRE"]
            if isinstance(require_str, str) and require_str.strip():
                tokens = require_str.strip().split()
                if len(tokens) >= 2:
                    req_block, req_table = tokens[0], tokens[1]
                    required_key = (req_block, req_table, table_num)
                    if required_key not in collected:
                        missing_requirements.append(required_key)
    if missing_requirements:
        raise ValueError(
            f"Missing required tables in 'collected': {missing_requirements}"
        )

    # Handle PEST Supplemental File
    #
    # See if there is a Parameter ESTimation (PEST) supplemental file.  The
    # PESTSU line in the FILES block specifies the name of the supplemental
    # file.
    pestsu = ""
    for line in collected[("FILES", "", None)]:
        words = line.split()
        if words[0] == "PESTSU":
            pestsu = words[2]
    pest_sup = {}
    if pestsu:
        # Read entire PEST supplemental file into 'sfplines' which becomes the
        # 'pest_sup' dictionary with the record id as the key and list of
        # floats as the value.
        pestsu = Path(uciname).parent / pestsu
        with open(pestsu, encoding="ascii") as sfp:
            sfplines = sfp.readlines()

        sfplines = [i.strip() for i in sfplines if "***" not in i]
        sfplines = [i.strip() for i in sfplines if i]
        pest_sup = {
            key.split()[0]: [str(float(i)) for i in value.split()]
            for key, value in zip(sfplines[:-1:2], sfplines[1::2])
        }

    # Handle Tables With Continuation Lines
    #
    # GLOBAL has parameters spread over four continuation lines
    # GQ-PHOTPM has parameters spread over three continuation lines
    # GQ-ALPHA has parameters spread over three continuation lines
    # GQ-GAMMA has parameters spread over three continuation lines
    # GQ-DELTA has parameters spread over three continuation lines
    # GQ-CLDFACT has parameters spread over three continuation lines
    # LCONC has parameters spread over two continuation lines
    #
    # I handle these by combining the continuation lines into a single line.
    #
    # For example, the GLOBAL table has 4 lines.  I take collected[("GLOBAL",
    # "", None)] which is a list of those four lines and I combine them into
    # a single line of 320 characters (4 * 80).
    #
    # Later when converting to a DataFrame, the START and STOP columns in the
    # Parameters.csv table reflect the new column positions.
    for key, n_cont_lines in [
        (("GLOBAL", "", None), 4),
        (("RCHRES", "GQ-PHOTPM", None), 3),
        (("RCHRES", "GQ-ALPHA", None), 3),
        (("RCHRES", "GQ-GAMMA", None), 3),
        (("RCHRES", "GQ-DELTA", None), 3),
        (("RCHRES", "GQ-CLDFACT", None), 3),
        (("DURANL", "LCONC", None), 2),
        (("DURANL", "LEVELS", None), 2),
    ]:
        # The len(extended) should divide evenly by n_cont_lines.
        if key in collected:
            extended = collected[key]
            newlines = []
            for first in range(0, len(extended), n_cont_lines):
                newstr = "".join(
                    f"{extended[first + i]:<80}" for i in range(n_cont_lines)
                )
                newlines.append(newstr)
            collected[key] = newlines

    # FTABLE has a rows/columns row as the first line that we don't want as the
    # first line of the dataframe.  Append instead to each line in the table
    # and define the new 'rows' and 'columns' parameters in Parameters.csv.
    ftable_keys = [k for k in collected if k[0] == "FTABLES"]
    for key in ftable_keys:
        rows, cols = collected[key][0].split()
        nlines = [
            f"{line:<80}{int(rows):<10}{int(cols):<10}" for line in collected[key][1:]
        ]
        collected[key] = nlines

    # Need to add a MLNO column to the MASS-LINK that is the table_num.
    ml_keys = [k for k in collected if k[0] == "MASS-LINK"]
    for key in ml_keys:
        nlines = [f"{line:<80}{int(key[2]):<10}" for line in collected[key]]
        collected[key] = nlines

    # Process OPN SEQUENCE block
    collect_operations = {}
    for opsline in collected[("OPN SEQUENCE", "", None)]:
        words = opsline.split()
        if words[0] in ops:
            collect_operations.setdefault(words[0], []).append(int(words[1]))

    # Convert Dictionary of List of Strings to Dictionary of DataFrames
    #
    # `ncollected` is a dictionary that will store the data from the UCI file,
    # key = (HSPF_BLOCK, HSPF_TABLE, table_number)
    #       where HSPF_BLOCK and HSPF_TABLE are in the UCI file and additional
    #       metadata in the Parameters.csv file, and table_number is only used
    #       to identify FTABLE, and MASS-LINK.
    # value = pandas DataFrame with the data for that table from the UCI file
    #         with the columns named according to the Parameters.csv file and
    #         the missing values filled in with the default values from the
    #         Parameters.csv file.  Uses "explode" to expand the (OPNID,
    #         OPNIDLAST) into unique rows for each range of ids in (OPNID,
    #         OPNIDLAST).  The last row for duplicate OPNIDs is kept.
    ncollected = {}
    for key, lines in collected.items():
        hspf_block, hspf_table, table_num = key

        table_metadata = _parameters[
            (_parameters["HSPF_BLOCK"] == hspf_block)
            & (
                (_parameters["HSPF_TABLE"] == hspf_table)
                | (_parameters["HSPF_TABLE"].isna())
            )
        ]

        names = table_metadata["PARAMETER_NAME"].values

        if pest_sup and "OPNID" in names:
            # Have to read separately for PEST supplemental file and create two
            # DataFrames of the same shape as the table.
            #     * The PEST supplemental DataFrame will have parameter values
            #       filled in from the PEST supplemental file for each row that
            #       has a ~XXX~ in the UCI file (where XXX is the record number
            #       in the PEST supplemental file) and the rest of the values
            #       will be filled in with Nones.
            #     * The standard DataFrame will have all values filled in with
            #       the values read from the UCI file and blank values for the
            #       ~XXX~ rows.  When read with pd.read_fwf, the blanks in the
            #       ~XXX~ rows will be filled with Nones.
            #     * The two DataFrames will be combined with the ~XXX~ rows
            #       filled in with the values from the PEST supplemental file
            #       and the rest of the values filled in with the values from
            #       the UCI file.
            #     * Only HSPF_BLOCK/HSPF_TABLE that have an OPNID parameter can
            #       use entries in the PEST supplemental file.
            nlines = []
            pass_through_lines = []
            for line in lines:
                if tilde := re.match("~([0-9][0-9]*)~", line[10:]):
                    tilde = tilde[0][1:-1]
                    try:
                        nlines.append(",".join([line[:10]] + pest_sup[tilde]))
                    except KeyError:
                        raise ValueError(
                            wrapper.wrap(
                                textwrap.dedent(f"""\
                                    The record id ~{tilde}~ in the UCI file
                                    "{uciname}" is not in the Parameter ESTimation
                                    (PEST) supplemental file "{pestsu}".
                                    """)
                            )
                        )
                    pass_through_lines.append(line[:10])
                else:
                    nlines.append(",".join([line[:10]] + [""] * len(names)))
                    pass_through_lines.append(line)
            lines = pass_through_lines
            pest_sup_df = pd.read_csv(
                StringIO("\n".join(nlines)),
                names=names,
                index_col=False,
                na_values="na",
            )

        # Read the lines into a DataFrame using the START and STOP columns.
        starts = table_metadata["START"].values
        stops = table_metadata["STOP"].values
        ndf = pd.read_fwf(
            StringIO("\n".join(lines)), colspecs=list(zip(starts, stops)), names=names
        )

        # Merge in any values from the PEST supplemental file by using
        # combine_first to replace missing values in the ndf DataFrame with
        # values from the pest_sup_df DataFrame.
        if pest_sup and "OPNID" in names:
            ndf = ndf.combine_first(pest_sup_df)

        ndf = ndf.fillna({"FTYPE": ""})

        # Process DataFrames that have an OPNID/OPNIDLAST or TVOLNO/TOPLST
        # columns to use ranges of operations.  If there are ranges specified,
        # explode those ranges into individual rows and then drop duplicates
        # keeping the last row for each operation or target volume number.
        if len(ndf) > 0:
            for exploder_col, first, last in [
                ("OPNID", "OPNID", "OPNIDLAST"),
                ("TVOLNO", "TOPFST", "TOPLST"),
            ]:
                if first in ndf.columns and last in ndf.columns:
                    exploder = pd.DataFrame()
                    exploder["FIRSTID"] = pd.to_numeric(ndf[first]).astype(int)
                    exploder["LASTID"] = pd.to_numeric(
                        ndf[last].fillna(ndf[first])
                    ).astype(int)
                    ndf = ndf.drop(columns=[first, last])

                    exploder[exploder_col] = [
                        list(range(i, j + 1)) for i, j in exploder.values
                    ]
                    exploder = exploder.drop(columns=["FIRSTID", "LASTID"])

                    ndf = pd.concat([exploder, ndf], axis="columns")
                    ndf = ndf.explode(exploder_col)
                    ndf = ndf.drop_duplicates(subset=[exploder_col], keep="last")
                    ndf[exploder_col] = ndf[exploder_col].astype(int)

        # Right here I need to make sure I have a row for each operation in the
        # OPN SEQUENCE table.  If I don't have a row for an operation, I need
        # to add one so `default_and_validation` function will fill in any
        # missing values with the defaults.
        if "OPNID" in ndf.columns:
            ndf = ndf.set_index("OPNID")
            ndf = ndf.reindex(index=sorted(set(collect_operations[hspf_block])))
            ndf = ndf.loc[sorted(set(collect_operations[hspf_block])), :]
            ndf.index = hspf_block[0] + ndf.index.astype(str).str.zfill(3)

        ncollected[key] = ndf

    for _, row in _tables.iterrows():
        if str(row["DEFAULTABLE_TABLE"]).upper() == "TRUE":
            hspf_block = row["HSPF_BLOCK"]
            hspf_table = row["HSPF_TABLE"]
            key = (hspf_block, hspf_table, None)
            if key not in ncollected:
                # Get parameter names for this block/table
                param_names = _parameters.loc[
                    (_parameters["HSPF_BLOCK"] == hspf_block)
                    & (_parameters["HSPF_TABLE"] == hspf_table),
                    "PARAMETER_NAME",
                ].tolist()
                param_names = [
                    p for p in param_names if p not in ("OPNID", "OPNIDLAST")
                ]
                # Create empty DataFrame with those columns
                ncollected[key] = pd.DataFrame(columns=param_names)

    # Now need to merge {(HSFP_block, HSPF_table, table_num): dataframe} to
    # be {HDF_TABLE: dataframe} where HDF_TABLE is looked up from
    # _tables.

    # Create a mapping from (HSPF_BLOCK, HSPF_TABLE) to HDF_TABLE
    table_map = {
        (row["HSPF_BLOCK"], row["HSPF_TABLE"]): row["HDF_TABLE"]
        for _, row in _tables.iterrows()
    }

    # Prepare a defaultdict to collect DataFrames for each HDF_TABLE
    hdf_collected = defaultdict(list)

    for key, df in ncollected.items():
        hspf_block, hspf_table, table_num = key
        hdf_table = table_map[(hspf_block, hspf_table)]
        if hdf_table:
            if hspf_table == "FTABLE":
                hdf_table = f"{hdf_table}{table_num:03d}"
            hdf_collected[hdf_table].append(df)

    nhdf_collected = {}
    for hdf_table, list_dfs in hdf_collected.items():
        dfs = pd.DataFrame()
        for df in list_dfs:
            if hdf_table in ["/CONTROL/MASS_LINKS", "/CONTROL/LINKS"]:
                dfs = pd.concat([dfs, df], ignore_index=True)
            else:
                # For all other tables, merge on index
                dfs = dfs.merge(df, left_index=True, right_index=True, how="outer")
        nhdf_collected[hdf_table] = dfs

    cgl = nhdf_collected["/CONTROL/GLOBAL"]
    cgl["Comment"] = cgl["COMMENT"]
    cgl = cgl.fillna(
        {
            "SYR": 1900,
            "SMO": 1,
            "SDA": 1,
            "SHR": 0,
            "SMI": 0,
            "EYR": 1900,
            "EMO": 12,
            "EDA": 31,
            "EHR": 24,
            "EMI": 0,
        }
    )
    cgl["Start"] = str(
        pd.Timestamp(
            int(cgl.loc[0, "SYR"]), int(cgl.loc[0, "SMO"]), int(cgl.loc[0, "SDA"])
        )
        + pd.Timedelta(hours=int(cgl.loc[0, "SHR"]))
        + pd.Timedelta(minutes=int(cgl.loc[0, "SMI"]))
    )[:16]
    cgl["Stop"] = str(
        pd.Timestamp(
            int(cgl.loc[0, "EYR"]), int(cgl.loc[0, "EMO"]), int(cgl.loc[0, "EDA"])
        )
        + pd.Timedelta(hours=int(cgl.loc[0, "EHR"]))
        + pd.Timedelta(minutes=int(cgl.loc[0, "EMI"]))
    )[:16]
    cgl["Units"] = cgl.loc[0, "UFG"] or 1
    cgl = cgl[["Comment", "Start", "Stop", "Units"]].transpose()
    cgl.columns = ["Info"]
    cgl["Info"] = cgl["Info"].astype(str)
    nhdf_collected["/CONTROL/GLOBAL"] = cgl

    ext_sources = nhdf_collected["/CONTROL/EXT_SOURCES"]
    for svol, baseno in [
        ("WDM1", 100000),
        ("WDM2", 200000),
        ("WDM3", 300000),
        ("WDM4", 400000),
    ]:
        mask = ext_sources["SVOL"] == svol
        ext_sources.loc[mask, "SVOLNO"] = baseno + ext_sources.loc[mask, "SVOLNO"]
        ext_sources.loc[mask, "SVOLNO"] = ext_sources.loc[mask, "SVOLNO"].apply(
            lambda x: f"TS{int(x):06d}"
        )
    nhdf_collected["/CONTROL/EXT_SOURCES"] = ext_sources

    # HSPsquared in several tables require that operation and id be combined.
    # So ("PERLND", 101) is changed to "P001", ("IMLND", 67) becomes "I067",
    # ...etc.  Also, all MASS-LINK need the "ML" prefix added and all FTABLES
    # need the "FT" prefix added.
    for table, tlink, tlabel, iprefix in [
        ("/CONTROL/OP_SEQUENCE", "SEGMENT", "OPERATION", ""),
        ("/CONTROL/MASS_LINKS", "MLNO", "", "ML"),
        ("/CONTROL/LINKS", "MLNO", "", "ML"),
        ("/RCHRES/HYDR/PARAMETERS", "FTBUCI", "", "FT"),
    ]:
        ndf = nhdf_collected[table]
        if tlabel:
            ndf[tlink] = ndf[tlabel].str[0] + ndf[tlink].apply(
                lambda x: f"{int(x):03d}"
            )
        else:
            mask = np.isfinite(ndf[tlink])
            tmp_col = f"{tlink}_TMP"
            ndf[tmp_col] = ""
            ndf.loc[mask, tmp_col] = ndf.loc[mask, tlink].apply(
                lambda x: f"{iprefix}{int(x):03d}"
            )
            ndf[tlink] = ndf[tmp_col]
            ndf = ndf.drop(columns=[tmp_col])
        nhdf_collected[table] = ndf

    # nhdf_collected["/CONTROL/EXT_SOURCES"]["SVOL"] = "*"

    return default_and_validation(nhdf_collected)
