"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.
License: LGPL2

Conversion of HSPF HIMPGAS.FOR module into Python"""

from numba import njit
from numpy import float64, full, int64, where, zeros

from hsp2.hsp2.utilities import hourflag, initm, make_numba_dict

ERRMSG = []

# english system
# parameters for variables with energy units
EFACTA = 407960.0

# parameters for variables with temperature units
TFACTA = 1.8
TFACTB = 32.0

# parameters for variables for dissolved gases with mass units
MFACTA = 0.2266


def iwtgas(io_manager, siminfo, uci, ts):
    """Estimate water temperature, dissolved oxygen, and carbon dioxide in the outflows
    from a impervious land segment. calculate associated fluxes through exit gate

    # state variables with concentration units do not have to be converted
    # fluxes - energy units
    PCFLX1 = IGCF1(1,LEV) * EFACTA
    # fluxes - mass units
    PCFLX2 = IGCF1(2,LEV) * MFACTA
    PCFLX3 = IGCF1(3,LEV) * MFACTA
    """

    simlen = siminfo["steps"]

    ui = make_numba_dict(uci)
    ui["simlen"] = siminfo["steps"]
    ui["uunits"] = siminfo["units"]
    ui["errlen"] = len(ERRMSG)

    u = uci["PARAMETERS"]
    if "WTFVFG" in u:
        ts["AWTF"] = initm(siminfo, uci, u["WTFVFG"], "MONTHLY_AWTF", u["AWTF"])
        ts["BWTF"] = initm(siminfo, uci, u["WTFVFG"], "MONTHLY_BWTF", u["BWTF"])
    else:
        ts["AWTF"] = full(simlen, u["AWTF"])
        ts["BWTF"] = full(simlen, u["BWTF"])

    for name in ["AIRTMP", "WYIELD", "SURO", "SURLI"]:
        if name not in ts:
            ts[name] = zeros(simlen)

    ts["DAYFG"] = hourflag(siminfo, 0, dofirst=True).astype(float64)

    ############################################################################
    errors = _iwtgas_(ui, ts)  # run IWTGAS simulation code
    ############################################################################

    return errors, ERRMSG


@njit(cache=True)
def _iwtgas_(ui, ts):
    """Estimate water temperature, dissolved oxygen, and carbon dioxide in the outflows
    from a impervious land segment. calculate associated fluxes through exit gate"""

    errorsV = zeros(int(ui["errlen"])).astype(int64)

    uunits = ui["uunits"]
    simlen = int(ui["simlen"])
    # delt60 = ui['delt60']

    slifac = ui["SLIFAC"]  # from LAT_FACTOR table
    sotmp = ui["SOTMP"]
    sodox = ui["SODOX"]
    soco2 = ui["SOCO2"]
    elev = ui["ELEV"]
    if uunits == 2:
        sotmp = (sotmp * 9.0 / 5.0) + 32.0
        elev = elev * 3.281  # m to ft
    elevgc = ((288.0 - 0.00198 * elev) / 288.0) ** 5.256

    AIRTMP = ts["AIRTMP"]
    WYIELD = ts["WYIELD"]
    SURO = ts["SURO"]
    SURLI = ts["SURLI"]

    # get surface lateral inflow temp and concentrations
    for name in ["SLITMP", "SLIDOX", "SLICO2"]:
        if name not in ts:
            ts[name] = full(simlen, -1.0e30)
    SLITMP = ts["SLITMP"]
    SLIDOX = ts["SLIDOX"]
    SLICO2 = ts["SLICO2"]

    AWTF = ts["AWTF"]
    BWTF = ts["BWTF"]

    # preallocate output arrays
    SOTMP = ts["SOTMP"] = full(simlen, -1.0e30)
    SODOX = ts["SODOX"] = full(simlen, -1.0e30)
    SOCO2 = ts["SOCO2"] = full(simlen, -1.0e30)
    SOHT = ts["SOHT"] = zeros(simlen)
    SODOXM = ts["SODOXM"] = zeros(simlen)
    SOCO2M = ts["SOCO2M"] = zeros(simlen)

    DAYFG = ts["DAYFG"].astype(int64)

    if uunits == 2:
        AWTF = (AWTF * 9.0 / 5.0) + 32.0
        WYIELD = WYIELD * 0.0394  # / 25.4
        SURO = SURO * 0.0394  # mm to inches

    awtf = AWTF[0]
    bwtf = BWTF[0]

    for loop in range(simlen):
        airtc = (AIRTMP[loop] - 32.0) * 0.555  # convert to centigrade
        suro = SURO[loop]
        wyield = WYIELD[loop]
        surli = SURLI[loop]
        slitmp = SLITMP[loop]
        slidox = SLIDOX[loop]
        slico2 = SLICO2[loop]

        # obtain latest values for temperature calculation parameters
        if DAYFG[loop] == 1:
            awtf = (AWTF[loop] - 32.0) * 0.555
            bwtf = BWTF[loop]

        if suro > 0.0:  # there is surface outflow
            sotmp = (
                awtf + bwtf * airtc
            )  # calculate impervious surface outflow temperature - in deg. c
            if sotmp < 0.5:
                sotmp = 0.5  # don't let water temp drop below 0.5 deg c
            if wyield > 0.0:  # snowmelt is occuring - use min temp
                sotmp = 0.5

            # calculate dissolved oxygen -  nits are mg/l of do
            dummy = sotmp * (0.007991 - 0.77774e-4 * sotmp)
            sodox = (14.652 + sotmp * (-0.41022 + dummy)) * elevgc

            # calculate carbon dioxide calculation - units are mg c/l of co2
            abstmp = sotmp + 273.16
            dummy = 2385.73 / abstmp - 14.0184 + 0.0152642 * abstmp
            soco2 = 10.0**dummy * 3.16e-04 * elevgc * 12000.0

            if (
                surli > 0.0 and slifac > 0.0 and slitmp >= -1.0e10
            ):  # there is temperature of surface lateral inflow
                # check for effects of lateral inflow
                sotmp = slitmp * slifac + sotmp * (1.0 - slifac)
                if slidox >= 0.0:  # there is do conc of surface lateral inflow
                    sodox = slidox * slifac + sodox * (1.0 - slifac)
                if slico2 >= 0.0:  # there is co2 conc of surface lateral inflow
                    soco2 = slico2 * slifac + soco2 * (1.0 - slifac)

            SOHT[loop] = (
                sotmp * suro * EFACTA
            )  # compute outflow of heat energy in water - units are deg. c-in./ivl
            SODOXM[loop] = (
                sodox * suro * MFACTA
            )  # calculate outflow mass of dox - units are mg-in./l-ivl
            SOCO2M[loop] = (
                soco2 * suro * MFACTA
            )  # calculate outflow mass of co2 - units are mg-in./l-ivl
            if uunits != 2:
                SOTMP[loop] = (sotmp * 9.0 / 5.0) + 32.0
            else:
                SOTMP[loop] = sotmp
            SODOX[loop] = sodox
            SOCO2[loop] = soco2

        else:
            sotmp = -1.0e30
            sodox = -1.0e30
            soco2 = -1.0e30

            SOHT[loop] = 0.0
            SODOXM[loop] = 0.0
            SOCO2M[loop] = 0.0
            SOTMP[loop] = sotmp
            SODOX[loop] = sodox
            SOCO2[loop] = soco2

        if uunits == 2:
            SOHT[loop] = SOHT[loop] / 3.96567 * 2.471  # btu/ac to kcal/ha
            SODOXM[loop] = SODOXM[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            SOCO2M[loop] = SOCO2M[loop] / 2.205 * 2.471  # lbs/ac to kg/ha

    return errorsV
