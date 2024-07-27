"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.
License: LGPL2

Conversion of HSPF HPERGAS.FOR module into Python"""

from numba import njit
from numpy import float64, full, int64, where, zeros

from hsp2.hsp2.utilities import hourflag, initm, make_numba_dict

ERRMSG = []

# english system
# parameters for variables with energy units
EFACTA = 407960.0
EFACTB = 0.0

# parameters for variables with temperature units
TFACTA = 1.8
TFACTB = 32.0

# parameters for variables for dissolved gases with mass units
MFACTA = 0.2266
MFACTB = 0.0


def pwtgas(io_manager, siminfo, uci, ts):
    """Estimate water temperature, dissolved oxygen, and carbon dioxide in the outflows
    from a pervious landsegment. calculate associated fluxes through exit gates"""
    simlen = siminfo["steps"]

    ui = make_numba_dict(uci)
    ui["simlen"] = siminfo["steps"]
    ui["uunits"] = siminfo["units"]
    ui["errlen"] = len(ERRMSG)

    u = uci["PARAMETERS"]
    if "IDVFG" in u:
        ts["IDOXP"] = initm(siminfo, uci, u["IDVFG"], "MONTHLY_IDOXP", u["IDOXP"])
    else:
        ts["IDOXP"] = full(simlen, u["IDOXP"])
    if "ICVFG" in u:
        ts["ICO2P"] = initm(siminfo, uci, u["ICVFG"], "MONTHLY_ICO2P", u["ICO2P"])
    else:
        ts["ICO2P"] = full(simlen, u["ICO2P"])
    if "GDVFG" in u:
        ts["ADOXP"] = initm(siminfo, uci, u["GDVFG"], "MONTHLY_ADOXP", u["ADOXP"])
    else:
        ts["ADOXP"] = full(simlen, u["ADOXP"])
    if "GCVFG" in u:
        ts["ACO2P"] = initm(siminfo, uci, u["GCVFG"], "MONTHLY_ACO2P", u["ACO2P"])
    else:
        ts["ACO2P"] = full(simlen, u["ACO2P"])

    ts["DAYFG"] = hourflag(siminfo, 0, dofirst=True).astype(float64)

    ############################################################################
    errors = _pwtgas_(ui, ts)  # run PWTGAS simulation code
    ############################################################################

    return errors, ERRMSG


@njit(cache=True)
def _pwtgas_(ui, ts):
    """Estimate water temperature, dissolved oxygen, and carbon dioxide in the outflows
    from a pervious landsegment. calculate associated fluxes through exit gates"""

    errorsV = zeros(int(ui["errlen"])).astype(int64)

    uunits = ui["uunits"]
    simlen = int(ui["simlen"])

    CSNOFG = int(ui["CSNOFG"])
    sotmp = ui["SOTMP"]
    iotmp = ui["IOTMP"]
    aotmp = ui["AOTMP"]
    sodox = ui["SODOX"]
    soco2 = ui["SOCO2"]
    iodox = ui["IODOX"]
    ioco2 = ui["IOCO2"]
    aodox = ui["AODOX"]
    aoco2 = ui["AOCO2"]
    sdlfac = ui["SDLFAC"]
    slifac = ui["SLIFAC"]
    ilifac = ui["ILIFAC"]
    alifac = ui["ALIFAC"]
    elev = ui["ELEV"]
    if uunits == 2:
        sotmp = (sotmp * 9.0 / 5.0) + 32.0
        iotmp = (iotmp * 9.0 / 5.0) + 32.0
        aotmp = (aotmp * 9.0 / 5.0) + 32.0
        elev = elev * 3.281  # m to ft
    elevgc = ((288.0 - 0.00198 * elev) / 288.0) ** 5.256

    if "GDVFG" in ui:
        gdvfg = ui["GDVFG"]
    else:
        gdvfg = 0

    IDOXP = ts["IDOXP"]
    ICO2P = ts["ICO2P"]
    ADOXP = ts["ADOXP"]
    ACO2P = ts["ACO2P"]

    for name in ["WYIELD", "SURO", "IFWO", "AGWO", "SURLI", "IFWLI", "AGWLI"]:
        if name not in ts:
            ts[name] = zeros(simlen)
    WYIELD = ts["WYIELD"]
    SURO = ts["SURO"]
    IFWO = ts["IFWO"]
    AGWO = ts["AGWO"]
    SURLI = ts["SURLI"]
    IFWLI = ts["IFWLI"]
    AGWLI = ts["AGWLI"]

    for name in ["SLTMP", "ULTMP", "LGTMP", "SLITMP", "SLIDOX", "SLICO2"]:
        if name not in ts:
            ts[name] = full(simlen, -1.0e30)
    SLTMP = ts["SLTMP"]
    ULTMP = ts["ULTMP"]
    LGTMP = ts["LGTMP"]
    SLITMP = ts["SLITMP"]
    SLIDOX = ts["SLIDOX"]
    SLICO2 = ts["SLICO2"]

    for name in ["ILITMP", "ILIDOX", "ILICO2"]:
        if name not in ts:
            ts[name] = full(simlen, -1.0e30)
    ILITMP = ts["ILITMP"]
    ILIDOX = ts["ILIDOX"]
    ILICO2 = ts["ILICO2"]

    for name in ["ALITMP", "ALIDOX", "ALICO2"]:
        if name not in ts:
            ts[name] = full(simlen, -1.0e30)
    ALITMP = ts["ALITMP"]
    ALIDOX = ts["ALIDOX"]
    ALICO2 = ts["ALICO2"]

    # preallocate output arrays
    SOTMP = ts["SOTMP"] = zeros(simlen)
    IOTMP = ts["IOTMP"] = zeros(simlen)
    AOTMP = ts["AOTMP"] = zeros(simlen)
    SODOX = ts["SODOX"] = zeros(simlen)
    SOCO2 = ts["SOCO2"] = zeros(simlen)
    IODOX = ts["IODOX"] = zeros(simlen)
    IOCO2 = ts["IOCO2"] = zeros(simlen)
    AODOX = ts["AODOX"] = zeros(simlen)
    AOCO2 = ts["AOCO2"] = zeros(simlen)
    SOHT = ts["SOHT"] = zeros(simlen)
    IOHT = ts["IOHT"] = zeros(simlen)
    AOHT = ts["AOHT"] = zeros(simlen)
    POHT = ts["POHT"] = zeros(simlen)
    SODOXM = ts["SODOXM"] = zeros(simlen)
    SOCO2M = ts["SOCO2M"] = zeros(simlen)
    IODOXM = ts["IODOXM"] = zeros(simlen)
    IOCO2M = ts["IOCO2M"] = zeros(simlen)
    AODOXM = ts["AODOXM"] = zeros(simlen)
    AOCO2M = ts["AOCO2M"] = zeros(simlen)
    PODOXM = ts["PODOXM"] = zeros(simlen)
    POCO2M = ts["POCO2M"] = zeros(simlen)

    DAYFG = ts["DAYFG"].astype(int64)

    if uunits == 2:
        SLTMP = (SLTMP * 9.0 / 5.0) + 32.0
        ULTMP = (ULTMP * 9.0 / 5.0) + 32.0
        LGTMP = (LGTMP * 9.0 / 5.0) + 32.0
        WYIELD = WYIELD * 0.0394  # / 25.4
        SURO = SURO * 0.0394  # mm to inches
        IFWO = IFWO * 0.0394  # mm to inches
        AGWO = AGWO * 0.0394  # mm to inches

    for loop in range(simlen):
        dayfg = DAYFG[loop]
        suro = SURO[loop]
        wyield = WYIELD[loop]
        ifwo = IFWO[loop]
        agwo = AGWO[loop]
        surli = SURLI[loop]
        ifwli = IFWLI[loop]
        agwli = AGWLI[loop]
        sltmp = SLTMP[loop]
        slitmp = SLITMP[loop]
        slidox = SLIDOX[loop]
        slico2 = SLICO2[loop]
        ultmp = ULTMP[loop]
        idoxp = IDOXP[loop]
        ico2p = ICO2P[loop]
        adoxp = ADOXP[loop]
        aco2p = ACO2P[loop]

        sotmp = -1.0e30
        sodox = -1.0e30
        soco2 = -1.0e30
        if suro > 0.0:  # there is surface outflow
            # local surface outflow temp equals surface soil temp
            sotmp = (sltmp - 32.0) * 5.0 / 9.0
            if sotmp < 0.5:
                sotmp = 0.5  # min water temp
            if CSNOFG:  # effects of snow are considered
                # adjust surface outflow temperature if snowmelt is occurring
                if wyield > 0.0:
                    sotmp = 0.5  # snowmelt is occuring - use min temp

            # oxygen calculation
            dummy = sotmp * (0.007991 - 0.77774e-4 * sotmp)
            sodox = (14.652 + sotmp * (-0.41022 + dummy)) * elevgc

            # carbon dioxide calculation
            abstmp = sotmp + 273.16
            dummy = 2385.73 / abstmp - 14.0184 + 0.0152642 * abstmp
            soco2 = 10.0**dummy * 3.16e-04 * elevgc * 12000.0

            if surli > 0.0 and slifac > 0.0:  # check for effects of lateral inflow
                if slitmp >= -1.0e10:  # there is temperature of surface lateral inflow
                    sotmp = slitmp * slifac + sotmp * (1.0 - slifac)
                if slidox >= 0.0:  # there is do conc of surface lateral inflow
                    sodox = slidox * slifac + sodox * (1.0 - slifac)
                if slico2 >= 0.0:  # there is co2 conc of surface lateral inflow
                    soco2 = slico2 * slifac + soco2 * (1.0 - slifac)

        # get interflow lateral inflow temp and concentrations
        ilitmp = -1.0e30
        ilidox = -1.0e30
        ilico2 = -1.0e30
        if ifwli > 0.0:  # there is lateral inflow
            ilitmp = ILITMP[loop]
            ilidox = ILIDOX[loop]
            ilico2 = ILICO2[loop]

        if dayfg:  # it is the first interval of the day
            idoxp = IDOXP[loop]
            ico2p = ICO2P[loop]

        iotmp = -1.0e30
        iodox = -1.0e30
        ioco2 = -1.0e30
        if ifwo > 0.0:  # there is interflow outflow
            # local interflow outflow temp equals upper soil temp
            iotmp = (ultmp - 32.0) * 5.0 / 9.0
            if iotmp < 0.5:
                iotmp = 0.5  # min water temp

            iodox = idoxp
            ioco2 = ico2p

            if ifwli > 0.0 and ilifac > 0.0:
                # check for effects of lateral inflow
                if (
                    ilitmp >= -1.0e10
                ):  # there is temperature of interflow lateral inflow
                    iotmp = ilitmp * ilifac + iotmp * (1.0 - ilifac)
                if ilidox >= 0.0:  # there is do conc of interflow lateral inflow
                    iodox = ilidox * ilifac + iodox * (1.0 - ilifac)
                if ilico2 >= 0.0:  # there is co2 conc of interflow lateral inflow
                    ioco2 = ilico2 * ilifac + ioco2 * (1.0 - ilifac)

        # get baseflow lateral inflow temp and concentrations
        alitmp = -1.0e30
        alidox = -1.0e30
        alico2 = -1.0e30
        if agwli > 0.0:
            alitmp = ALITMP[loop]
            alidox = ALIDOX[loop]
            alico2 = ALICO2[loop]

        if dayfg:  # it is the first interval of the day
            if gdvfg:
                adoxp = ADOXP[loop]
                aco2p = ACO2P[loop]

        aotmp = -1.0e30
        aodox = -1.0e30
        aoco2 = -1.0e30
        if agwo > 0.0:  # there is baseflow
            aotmp = (
                (LGTMP[loop] - 32.0) * 5.0 / 9.0
            )  # local baseflow temp equals lower/gw soil temp
            if aotmp < 0.5:  # min water temp
                aotmp = 0.5

            aodox = adoxp
            aoco2 = aco2p
            if agwli > 0.0 and alifac > 0.0:  # check for effects of lateral inflow
                if alitmp >= -1.0e10:  # there is temperature of baseflow lateral inflow
                    aotmp = alitmp * alifac + aotmp * (1.0 - alifac)
                if alidox >= 0.0:  # there is do conc of baseflow lateral inflow
                    aodox = alidox * alifac + aodox * (1.0 - alifac)
                if alico2 >= 0.0:  # there is co2 conc of baseflow lateral inflow
                    aoco2 = alico2 * alifac + aoco2 * (1.0 - alifac)

        # compute the outflow of heat energy in water - units are deg. c-in./ivl
        soht = sotmp * suro * EFACTA
        ioht = iotmp * ifwo * EFACTA
        aoht = aotmp * agwo * EFACTA
        POHT[loop] = soht + ioht + aoht

        # calculate outflow mass of dox - units are mg-in./l-ivl
        sodoxm = sodox * suro * MFACTA
        iodoxm = iodox * ifwo * MFACTA
        aodoxm = aodox * agwo * MFACTA
        PODOXM[loop] = sodoxm + iodoxm + aodoxm

        # calculate outflow mass of co2 - units are mg-in./l-ivl
        soco2m = soco2 * suro * MFACTA
        ioco2m = ioco2 * ifwo * MFACTA
        aoco2m = aoco2 * agwo * MFACTA
        POCO2M[loop] = soco2m + ioco2m + aoco2m

        SOTMP[loop] = sotmp
        if sotmp > -1e28 and uunits != 2:
            SOTMP[loop] = (sotmp * 9.0 / 5.0) + 32.0

        IOTMP[loop] = iotmp
        if iotmp > -1e28 and uunits != 2:
            IOTMP[loop] = (iotmp * 9.0 / 5.0) + 32.0

        AOTMP[loop] = aotmp
        if aotmp > -1e28 and uunits != 2:
            AOTMP[loop] = (aotmp * 9.0 / 5.0) + 32.0

        SODOX[loop] = sodox
        SOCO2[loop] = soco2
        IODOX[loop] = iodox
        IOCO2[loop] = ioco2
        AODOX[loop] = aodox
        AOCO2[loop] = aoco2
        SOHT[loop] = soht
        IOHT[loop] = ioht
        AOHT[loop] = aoht

        SODOXM[loop] = sodoxm
        SOCO2M[loop] = soco2m
        IODOXM[loop] = iodoxm
        IOCO2M[loop] = ioco2m
        AODOXM[loop] = aodoxm
        AOCO2M[loop] = aoco2m

        if uunits == 2:
            SOHT[loop] = SOHT[loop] / 3.96567 * 2.471  # btu/ac to kcal/ha
            IOHT[loop] = IOHT[loop] / 3.96567 * 2.471  # btu/ac to kcal/ha
            AOHT[loop] = AOHT[loop] / 3.96567 * 2.471  # btu/ac to kcal/ha
            POHT[loop] = POHT[loop] / 3.96567 * 2.471  # btu/ac to kcal/ha
            SODOXM[loop] = SODOXM[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            SOCO2M[loop] = SOCO2M[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            IODOXM[loop] = IODOXM[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            IOCO2M[loop] = IOCO2M[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            AODOXM[loop] = AODOXM[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            AOCO2M[loop] = AOCO2M[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            PODOXM[loop] = PODOXM[loop] / 2.205 * 2.471  # lbs/ac to kg/ha
            POCO2M[loop] = POCO2M[loop] / 2.205 * 2.471  # lbs/ac to kg/ha

    return errorsV
