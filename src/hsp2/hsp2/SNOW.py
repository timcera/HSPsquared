"""Copyright (c) 2020 by RESPEC, INC.
Author: Robert Heaphy, Ph.D.
License: LGPL2
Conversion of HSPF 12.2 HPERSNO module into Python

pack, pakin, pakdif not saved since trival recalulation from saved data
    pack = packf + packw
    pakin = snowf + prain
    pakdif = pakin - (snowe + wyield)
"""

from math import floor, sqrt

from numba import njit
from numpy import full, int64, nan, ones, zeros

from hsp2.hsp2.utilities import (
    SEASONS,
    SVP,
    hourflag,
    hoursval,
    initm,
    make_numba_dict,
    monthval,
)
from hsp2.hsp2io.protocols import Category, SupportsReadTS

ERRMSGS = (
    "Snow simulation cannot function properly with delt> 360",  # ERRMSG0
)


def snow(io_manager: SupportsReadTS, siminfo, uci, ts):
    """high level driver for SNOW module
    CALL: snow(store, general, ui, ts)
       store is the Pandas/PyTable open store
       siminfo is a dictionary with simulation level infor (OP_SEQUENCE for example)
       ui is a dictionary with segment specific HSPF UCI like data
       ts is a dictionary with segment specific timeseries"""

    steps = siminfo["steps"]  # number of simulation timesteps
    UUNITS = siminfo["units"]

    ts["SVP"] = SVP
    ts["SEASONS"] = monthval(siminfo, SEASONS)

    cloudfg = "CLOUD" in ts

    # insure defined, but can't be used accidently
    for name in ["AIRTMP", "CLOUD", "DTMPG", "PREC", "SOLRAD", "WINMOV"]:
        if name not in ts:
            ts[name] = full(steps, nan)

    # Replace fixed parameters in HSPF with time series
    for name in [
        "CCFACT",
        "COVIND",
        "MGMELT",
        "MWATER",
        "SHADE",
        "SNOEVP",
        "SNOWCF",
        "KMELT",
    ]:
        if name not in ts and name in uci["PARAMETERS"]:
            ts[name] = full(steps, uci["PARAMETERS"][name])

    # true the first time and at 6am and earlier every day of simulation
    ts["HR6IND"] = hour6flag(siminfo, dofirst=True).astype(float)

    # true the first time and at every hour of simulation
    ts["HRFG"] = hoursval(siminfo, ones(24), dofirst=True).astype(float)

    # make ICEFG available to PWATER later.
    siminfo["ICEFG"] = 0
    if "FLAGS" in uci:
        if "ICEFG" in uci["FLAGS"]:
            siminfo["ICEFG"] = uci["FLAGS"]["ICEFG"]

    ui = make_numba_dict(uci)  # Note: all values coverted to float automatically
    ui["steps"] = steps
    ui["uunits"] = UUNITS
    ui["delt"] = siminfo["delt"]
    ui["errlen"] = len(ERRMSGS)
    ui["cloudfg"] = cloudfg

    u = uci["PARAMETERS"]

    vkmfg = 0
    if "FLAGS" in uci:
        uf = uci["FLAGS"]
        if "VKMFG" in uf:
            vkmfg = uf["VKMFG"]
    ts["KMELT"] = initm(siminfo, uci, vkmfg, "MONTHLY_KMELT", u["KMELT"])

    ############################################################################
    errors = _snow_(ui, ts)
    ############################################################################

    if siminfo["delt"] > 360 and int(siminfo["ICEFLG"]):
        errors[0] += 1

    return errors, ERRMSGS


@njit(cache=True)
def _snow_(ui, ts):
    """SNOW processing"""
    errors = zeros(int(ui["errlen"])).astype(int64)

    steps = int(ui["steps"])  # number of simulation points
    delt = ui["delt"]  # simulation interval in minutes
    delt60 = delt / 60.0  # hours in simulation interval
    uunits = ui["uunits"]

    cloudfg = int(ui["cloudfg"])
    covinx = ui["COVINX"]
    dull = ui["DULL"]

    icefg = 0
    if "ICEFG" in ui:
        icefg = int(ui["ICEFG"])

    melev = ui["MELEV"]
    packf = ui["PACKF"] + ui["PACKI"]
    packi = ui["PACKI"]
    packw = ui["PACKW"]
    paktmp = ui["PAKTMP"]
    if uunits == 2:
        packf = packf / 25.4
        packi = packi / 25.4
        packw = packw / 25.4
        covinx = covinx / 25.4
        paktmp = (paktmp * 9.0 / 5.0) + 32.0
        melev = melev * 3.28084
    rdcsn = ui["RDCSN"]
    rdenpf = ui["RDENPF"]
    skyclr = ui["SKYCLR"]

    snopfg = 0
    if "SNOPFG" in ui:
        snopfg = int(ui["SNOPFG"])

    tbase = ui["TBASE"]
    tsnow = ui["TSNOW"]
    if uunits == 2:
        tbase = (tbase * 9.0 / 5.0) + 32.0
        tsnow = (tsnow * 9.0 / 5.0) + 32.0

    xlnmlt = ui["XLNMLT"]

    # get required time series
    AIRTMP = ts["AIRTMP"]
    CCFACT = ts["CCFACT"]
    CLOUD = ts["CLOUD"]
    COVIND = ts["COVIND"]
    DTMPG = ts["DTMPG"]
    HR6IND = ts["HR6IND"].astype(int64)
    HRFG = ts["HRFG"].astype(int64)
    KMELT = ts["KMELT"] * delt / 1440.0  # time conversion
    MGMELT = ts["MGMELT"] * delt / 1440.0  # time conversion
    MWATER = ts["MWATER"]
    PREC = ts["PREC"]
    SEASONS = ts["SEASONS"].astype(int64)
    SHADE = ts["SHADE"]
    SNOEVP = ts["SNOEVP"]
    SNOWCF = ts["SNOWCF"]
    SOLRAD = ts["SOLRAD"]
    SVP = ts["SVP"]
    WINMOV = ts["WINMOV"]

    if uunits == 2:
        COVIND = COVIND / 25.4
        MGMELT = MGMELT / 25.4

    # like MATLAB, much faster to preallocate arrays! Storing in ts Dict
    ts["ALBEDO"] = ALBEDO = zeros(steps)
    ts["COVINX"] = COVINX = zeros(steps)
    ts["DEWTMP"] = DEWTMP = zeros(steps)
    ts["DULL"] = DULL = zeros(steps)
    ts["MELT"] = MELT = zeros(steps)  # not initialized
    ts["NEGHTS"] = NEGHTS = zeros(steps)
    ts["PACKF"] = PACKF = zeros(steps)
    ts["PACKI"] = PACKI = zeros(steps)
    ts["PACKW"] = PACKW = zeros(steps)
    ts["PACK"] = PACK = zeros(steps)
    ts["PAKTMP"] = PAKTMP = zeros(steps)
    ts["PDEPTH"] = PDEPTH = zeros(steps)
    ts["PRAIN"] = PRAIN = zeros(steps)  # not initialized
    ts["RAINF"] = RAINF = zeros(steps)
    ts["RDENPF"] = RDENPF = zeros(steps)
    ts["SKYCLR"] = SKYCLR = zeros(steps)
    ts["SNOCOV"] = SNOCOV = zeros(steps)
    ts["SNOTMP"] = SNOTMP = zeros(steps)
    ts["SNOWE"] = SNOWE = zeros(steps)  # not initialized
    ts["SNOWF"] = SNOWF = zeros(steps)
    ts["WYIELD"] = WYIELD = zeros(steps)  # not initialized
    ts["XLNMLT"] = XLNMLT = zeros(steps)

    if packf + packw <= 1.0e-5:  # reset state variables
        # NOPACK
        albedo = 0.0
        covinx = 0.1 * COVIND[0]
        dull = 0.0
        neghts = 0.0
        packf = 0.0
        packi = 0.0
        packw = 0.0
        paktmp = 32.0
        pdepth = 0.0
        rdenpf = nan
        snocov = 0.0
        snowe = 0.0
        snowep = 0.0
        # END NOPACK
    else:
        if covinx < 1.0e-5:
            covinx = 0.1 * COVIND[0]
        pdepth = packf / rdenpf
        snocov = packf / covinx if packf < covinx else 1.0
        neghts = (32.0 - paktmp) * 0.00695 * packf

    melt = 0.0
    mneghs = 0.0
    packwc = 0.0
    prain = 0.0
    prec = 0.0
    snotmp = tsnow
    snowe = 0.0
    wyield = 0.0

    # needed by Numba 0.31
    albedo = 0.0
    compct = 0.0
    dewtmp = 0.0
    gmeltr = 0.0
    mostht = 0.0
    neght = 0.0
    rdnsn = 0.0
    satvap = 0.0
    snowep = 0.0
    vap = 0.0

    if HR6IND[0] > 0:
        hr6fg = 1
    else:
        hr6fg = 0

    # MAIN LOOP
    for step in range(steps):
        oldprec = prec

        # pay for indexing once per loop
        mgmelt = MGMELT[step]
        airtmp = AIRTMP[step]
        covind = COVIND[step]
        dtmpg = DTMPG[step]
        hr6ind = HR6IND[step]
        hrfg = HRFG[step]
        mwater = MWATER[step]
        prec = PREC[step]
        shade = SHADE[step]
        snowcf = SNOWCF[step]
        solrad = SOLRAD[step]
        winmov = WINMOV[step]

        reltmp = airtmp - 32.0  # needed in many places, compute once

        ""
        # METEOR
        if prec > 0.0:
            fprfg = oldprec == 0.0
        else:
            fprfg = False

        if hrfg:  # estimate the dewpoint
            dewtmp = (
                airtmp if (prec > 0.0 and airtmp > tsnow) or dtmpg > airtmp else dtmpg
            )

        if prec > 0.0:
            # find the temperature which divides snow from rain, and compute snow or rain fall
            if hrfg or fprfg:
                dtsnow = (airtmp - dewtmp) * (0.12 + 0.008 * airtmp)
                snotmp = tsnow + min(1.0, dtsnow)
            if snopfg == 0:
                skyclr = 0.15

            if airtmp < snotmp:
                snowf = prec * snowcf
                rainf = 0.0
                if hrfg or fprfg:
                    rdnsn = rdcsn + (airtmp / 100.0) ** 2 if airtmp > 0.0 else rdcsn
            else:
                rainf = prec
                snowf = 0.0
        else:
            rainf = 0.0
            snowf = 0.0
            if snopfg == 0 and skyclr < 1.0:
                skyclr += 0.0004 * delt
                if skyclr > 1.0:
                    skyclr = 1.0

        if snopfg == 0 and cloudfg:
            skyclr = max(0.15, 1.0 - (CLOUD[step] / 10.0))
        # END METEOR

        if packf > 0.0 or snowf > 0.0:
            # there is a snowpack or it is snowing,
            # simulate snow accumulation and melt
            if packf == 0.0:
                iregfg = 1
                if snopfg == 0:
                    dull = 0.0
            else:
                iregfg = hrfg

            # EFFPRC
            if snowf > 0.0:
                packf += snowf
                pdepth += snowf / rdnsn
                if packf > covinx:
                    covinx = covind if packf > covind else packf
                if snopfg == 0:
                    dummy = 1000.0 * snowf
                    dull = 0.0 if dummy >= dull else dull - dummy
                prain = 0.0
            else:
                prain = rainf * snocov if rainf > 0.0 else 0.0
            if snopfg == 0:
                if dull < 800:
                    dull += delt60
            # END EFFPRC

            # COMPAC
            if iregfg:
                rdenpf = packf / pdepth
                dummy = 1.0 - (0.00002 * delt60 * pdepth * (0.55 - rdenpf))
                compct = dummy if rdenpf < 0.55 else 1.0
            if compct < 1.0:
                pdepth *= compct
            # END COMPAC

            if snopfg == 0:
                # SNOWEV
                if iregfg:
                    vap = vapor(SVP, dewtmp)
                    satvap = vapor(SVP, airtmp)
                    dummy = SNOEVP[step] * 0.0002 * winmov * (satvap - vap) * snocov
                    snowep = 0.0 if vap >= 6.108 else dummy

                if snowep >= packf:
                    snowe = packf
                    pdepth = 0.0
                    packi = 0.0
                    packf = 0.0
                else:
                    pdepth *= 1.0 - snowep / packf
                    packf -= snowep
                    snowe = snowep
                    if packi > packf:
                        packi = packf
                # END SNOWEV
            else:
                snowe = 0.0

            if iregfg:
                if snopfg == 0:
                    # HEXCHR
                    factr = CCFACT[step] * 0.00026 * winmov
                    dummy = 8.59 * (vap - 6.108)
                    condht = dummy * factr if vap > 6.108 else 0.0

                    dummy = reltmp * (1.0 - 0.3 * melev / 10000.0) * factr
                    convht = dummy if airtmp > 32.0 else 0.0

                    # ALBEDO
                    dummy = sqrt(dull / 24.0)
                    summer = float(max(0.45, 0.80 - 0.10 * dummy))
                    winter = float(max(0.60, 0.85 - 0.07 * dummy))
                    albedo = summer if SEASONS[step] else winter
                    # END ALBEDO

                    k = (1.0 - shade) * delt60
                    long1 = (shade * 0.26 * reltmp) + k * (0.20 * reltmp - 6.6)
                    long2 = (shade * 0.20 * reltmp) + k * (0.17 * reltmp - 6.6)
                    long_ = long1 if reltmp > 0.0 else long2
                    if long_ < 0.0:  # back radiation
                        long_ *= skyclr

                    short = solrad * (1.0 - albedo) * (1.0 - shade)
                    mostht = (short + long_) / 203.2 + convht + condht
                    # END HEXCHR
                else:
                    # DEGDAY
                    mostht = KMELT[step] * (airtmp - tbase)
                    # END DEGDAY

            rnsht = reltmp * rainf / 144.0 if rainf > 0.0 else 0.0
            sumht = mostht + rnsht

            # back in PSNOW
            if snocov < 1.0:
                sumht = sumht * snocov
            paktmp = 32.0 if neghts <= 0.0 else 32.0 - neghts / (0.00695 * packf)

            # COOLER
            if iregfg:
                mneghs = 0.0 if reltmp > 0.0 else -reltmp * 0.00695 * packf / 2.0
                neght = 0.0 if paktmp <= airtmp else 0.0007 * (paktmp - airtmp) * delt60

            if sumht < 0.0:
                if paktmp > AIRTMP[step]:
                    neghts = min(mneghs, neghts + neght)
                sumht = 0.0

            # back in PSNOW
            if neghts > 0.0:
                # WARMUP
                if sumht > 0.0:
                    if sumht > neghts:
                        sumht -= neghts
                        neghts = 0.0
                    else:
                        neghts -= sumht
                        sumht = 0.0
                if prain > 0.0:
                    if prain > neghts:
                        rnfrz = neghts
                        packf += rnfrz
                        neghts = 0.0
                    else:
                        rnfrz = prain
                        neghts -= prain
                        packf += prain

                    if packf > pdepth:
                        pdepth = packf
                else:
                    rnfrz = 0.0
            else:
                rnfrz = 0.0

            # MELTER
            if sumht >= packf:
                melt = packf
                packf = 0.0
                pdepth = 0.0
                packi = 0.0
            elif sumht > 0.0:
                melt = sumht
                pdepth *= 1.0 - melt / packf
                packf -= melt
                if packi > packf:
                    packi = packf
            else:
                melt = 0.0

            # LIQUID
            if iregfg and packf > 0.0:
                rdenpf = packf / pdepth
                if rdenpf <= 0.6:
                    packwc = mwater
                else:
                    dummyf = 3.0 - 3.33 * rdenpf
                    packwc = mwater * dummyf if dummyf >= 0.0 else 0.0
            pwsupy = packw + melt + prain - rnfrz
            mpws = packwc * packf
            if (pwsupy - mpws) > (0.01 * delt60):
                wyield = pwsupy - mpws
                packw = mpws
            else:
                packw = pwsupy
                wyield = 0.0

            # back in psnow
            if icefg:
                # ICING
                if hr6ind < 1:
                    if hr6fg != 0:
                        if snocov < 1.0:
                            xlnem = -reltmp * 0.01
                            if xlnem > xlnmlt:
                                xlnmlt = xlnem
                        hr6fg = 0
                else:
                    # set the flag so that the freezing capacity will be updated next time 6 am is passed
                    hr6fg = 1

                if wyield > 0.0 and xlnmlt > 0.0:
                    if wyield < xlnmlt:
                        freeze = wyield
                        xlnmlt -= wyield
                        wyield = 0.0
                    else:
                        freeze = xlnmlt
                        wyield -= xlnmlt
                        xlnmlt = 0.0
                    packf += freeze
                    packi += freeze
                    pdepth += freeze

            # GMELT
            if iregfg:
                if paktmp >= 32.0:
                    gmeltr = mgmelt
                elif paktmp > 5.0:
                    gmeltr = mgmelt * (1.0 - 0.03 * (32.0 - paktmp))
                else:
                    gmeltr = mgmelt * 0.19
            if packf <= gmeltr:
                wyield = wyield + packf + packw
                packf = 0.0
                packi = 0.0
                packw = 0.0
                pdepth = 0.0
                neghts = 0.0
            else:
                dummy = 1.0 - (gmeltr / packf)
                packw += gmeltr
                pdepth *= dummy
                neghts *= dummy
                packf -= gmeltr
                packi = packi - gmeltr if packi > gmeltr else 0.0
            # END GMELT

            if packf > 0.005:
                rdenpf = packf / pdepth
                paktmp = 32.0 if neghts == 0.0 else 32.0 - neghts / (0.00695 * packf)
                snocov = packf / covinx if packf < covinx else 1.0
            else:
                melt += packf
                wyield += packf + packw

                # NOPACK
                hr6fg = 1
                packf = 0.0
                packi = 0.0
                packw = 0.0
                pdepth = 0.0
                rdenpf = nan
                covinx = 0.1 * covind
                snocov = 0.0
                xlnmlt = 0.0
                mneghs = nan
                paktmp = 32.0
                neghts = 0.0

                # pbd -- need this set for energy balance method?
                dull = -1.0e30
                albedo = -1.0e30
                snowep = -1.0e30
                vap = -1.0e30
        else:
            # there is no snow or pack
            prain = 0.0
            snowe = 0.0
            wyield = 0.0
            melt = 0.0
            # RAINF[step] = prec

        # save calculations
        ALBEDO[step] = albedo
        COVINX[step] = covinx
        DEWTMP[step] = dewtmp
        DULL[step] = dull
        MELT[step] = melt
        NEGHTS[step] = neghts
        PACKF[step] = packf
        PACKI[step] = packi
        PACKW[step] = packw
        PACK[step] = packf + packw  # + packi
        PAKTMP[step] = paktmp
        PDEPTH[step] = pdepth
        PRAIN[step] = prain
        RAINF[step] = rainf
        RDENPF[step] = rdenpf
        SKYCLR[step] = skyclr
        SNOCOV[step] = snocov
        SNOTMP[step] = snotmp
        SNOWE[step] = snowe
        SNOWF[step] = snowf
        WYIELD[step] = wyield
        XLNMLT[step] = xlnmlt
        if uunits == 2:
            PAKTMP[step] = (paktmp * 0.555) - 17.777  # convert to C
            DEWTMP[step] = (dewtmp * 0.555) - 17.777  # convert to C
            SNOTMP[step] = (snotmp * 0.555) - 17.777  # convert to C
            PACKF[step] = packf * 25.4
            PACKI[step] = packi * 25.4
            PACKW[step] = packw * 25.4
            PACK[step] = PACKF[step] + PACKW[step]
            PDEPTH[step] = pdepth * 25.4
            NEGHTS[step] = neghts * 25.4
            COVINX[step] = covinx * 25.4
            SNOWE[step] = snowe * 25.4
            SNOWF[step] = snowf * 25.4
            WYIELD[step] = wyield * 25.4
            XLNMLT[step] = xlnmlt * 25.4
            MELT[step] = melt * 25.4
            PRAIN[step] = prain * 25.4
    return errors


@njit(cache=True)
def vapor(SVP, temp):
    indx = (temp + 100.0) * 0.2 - 1.0
    lower = int(floor(indx))
    if lower < 0:
        return 1.005
    upper = lower + 1
    if upper > 39:
        return 64.9
    return SVP[lower] + (indx - lower) * (SVP[upper] - SVP[lower])


def hour6flag(siminfo, dofirst=False):
    """timeseries with 1 at 6am and earlier each day, and zero otherwise"""
    hours24 = zeros(24)
    hours24[0] = 1.0
    hours24[1] = 1.0
    hours24[2] = 1.0
    hours24[3] = 1.0
    hours24[4] = 1.0
    hours24[5] = 1.0
    return hoursval(siminfo, hours24, dofirst)
