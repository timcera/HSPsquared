"""Copyright (c) 2020 by RESPEC, INC.
Authors: Robert Heaphy, Ph.D. and Paul Duda
License: LGPL2
"""

from math import exp

from numba import njit
from numpy import array, int64, zeros

from hsp2.hsp2.ADCALC import advect, oxrea
from hsp2.hsp2.utilities import dayval, hoursval, initm, make_numba_dict

ERRMSGS = (
    "GQUAL: one or more gquals are sediment-associated, but section sedtrn not active",  # ERRMSG0
    "GQUAL: simulation of photolysis requires aux1fg to be on to calculate average depth",  # ERRMSG1
    "GQUAL: simulation of volatilization in a free flowing stream requires aux3fg on",  # ERRMSG2
    "GQUAL: simulation of volatilization in a lake requires aux1fg on to calculate average depth",  # ERRMSG3
    "GQUAL: in advqal, the value of denom is zero, and ISQAL and RSQALS should also be zero",  # ERRMSG4
    "GQUAL: in advqal, the value of bsed is zero, and DSQAL and RBQALS should also be zero",  # ERRMSG5
    "GQUAL: the value of tempfg is 1, but timeseries TW is not available as input",  # ERRMSG6
    "GQUAL: the value of phflag is 1, but timeseries PHVAL is not available as input",  # ERRMSG7
    "GQUAL: the value of roxfg is 1, but timeseries ROC is not available as input",  # ERRMSG8
    "GQUAL: the value of cldfg is 1, but timeseries CLOUD is not available as input",  # ERRMSG9
    "GQUAL: the value of sdfg is 1, but timeseries SSED4 is not available as input",  # ERRMSG10
    "GQUAL: the value of phytfg is 1, but timeseries PHYTO is not available as input",
)  # ERRMSG11


def gqual(io_manager, siminfo, uci, ts):
    """Simulate the behavior of a generalized quality constituent"""

    errors = zeros(len(ERRMSGS)).astype(int64)

    delt60 = siminfo["delt"] / 60  # delt60 - simulation time interval in hours
    simlen = siminfo["steps"]
    delts = siminfo["delt"] * 60
    uunits = siminfo["units"]

    AFACT = 43560.0
    if uunits == 2:
        # si units conversion
        AFACT = 1000000.0

    advectData = uci["advectData"]
    (nexits, vol, VOL, SROVOL, EROVOL, SOVOL, EOVOL) = advectData
    svol = vol * AFACT

    ts["VOL"] = VOL
    ts["SROVOL"] = SROVOL
    ts["EROVOL"] = EROVOL
    for i in range(nexits):
        ts["SOVOL" + str(i + 1)] = SOVOL[:, i]
        ts["EOVOL" + str(i + 1)] = EOVOL[:, i]

    ui = make_numba_dict(uci)
    ui["simlen"] = siminfo["steps"]
    ui["uunits"] = siminfo["units"]
    ui["svol"] = svol
    ui["vol"] = vol
    ui["delt60"] = delt60
    ui["delts"] = delts
    ui["errlen"] = len(ERRMSGS)

    # table-type gq-gendata
    ngqual = 1
    tempfg = 2
    phflag = 2
    roxfg = 2
    cldfg = 2
    sdfg = 2
    phytfg = 2

    # ui = uci['PARAMETERS']
    if "NGQUAL" in ui:
        ngqual = int(ui["NGQUAL"])
        tempfg = ui["TEMPFG"]
        phflag = ui["PHFLAG"]
        roxfg = ui["ROXFG"]
        cldfg = ui["CLDFG"]
        sdfg = ui["SDFG"]
        phytfg = ui["PHYTFG"]
    ui["ngqual"] = ngqual

    ts["HRFG"] = hour24Flag(siminfo).astype(float)

    ui_base = ui  # save base ui dict before adding qual specific parms

    for index in range(1, ngqual + 1):
        ui = ui_base
        ui["index"] = index
        # update UI values for this constituent here!
        ui_parms = uci["GQUAL" + str(index)]

        if "GQADFG" + str((index * 2) - 1) in ui_parms:
            # get atmos dep timeseries
            gqadfgf = ui_parms["GQADFG" + str((index * 2) - 1)]
            if gqadfgf > 0:
                ts["GQADFX"] = initm(
                    siminfo, uci, gqadfgf, "GQUAL" + str(index) + "_MONTHLY/GQADFX", 0.0
                )
            elif gqadfgf == -1:
                ts["GQADFX"] = ts["GQADFX" + str(index) + " 1"]
            gqadfgc = ui_parms["GQADFG" + str(index * 2)]
            if gqadfgc > 0:
                ts["GQADCN"] = initm(
                    siminfo, uci, gqadfgc, "GQUAL" + str(index) + "_MONTHLY/GQADCN", 0.0
                )
            elif gqadfgc == -1:
                ts["GQADCN"] = ts["GQADCN" + str(index) + " 1"]

            if "GQADFX" in ts:
                ts["GQADFX"] *= delt60 / (24.0 * AFACT)

        if "GQADFX" not in ts:
            ts["GQADFX"] = zeros(simlen)
        if "GQADCN" not in ts:
            ts["GQADCN"] = zeros(simlen)

        # table-type gq-flg2
        gqpm2 = zeros(8)
        gqpm2[7] = 2
        if "GQPM21" in ui_parms:
            gqpm2[1] = ui_parms["GQPM21"]
            gqpm2[2] = ui_parms["GQPM22"]
            gqpm2[3] = ui_parms["GQPM23"]
            gqpm2[4] = ui_parms["GQPM24"]
            gqpm2[5] = ui_parms["GQPM25"]
            gqpm2[6] = ui_parms["GQPM26"]
            gqpm2[7] = ui_parms["GQPM27"]

        biop = 0.0
        qalfg5 = ui_parms["QALFG5"]
        if qalfg5 == 1:  # qual undergoes biodegradation
            # BIOPM(1,I)  # table-type gq-biopm
            biop = ui_parms["BIO"]
            ts["BIO"] = zeros(simlen)
            ts["BIO"].fill(biop)
            # specifies source of biomass data using GQPM2(7,I)
            if gqpm2[7] == 1 or gqpm2[7] == 3:
                # BIOM = # from ts, monthly, constant
                ts["BIO"] = initm(
                    siminfo,
                    uci,
                    ui_parms["GQPM27"],
                    "GQUAL" + str(index) + "_MONTHLY/BIO",
                    ui_parms["BIO"],
                )

        # table-type gq-values
        if tempfg == 2 and "TWAT" in ui_parms:
            twat = ui_parms["TWAT"]
        else:
            twat = 60.0
        if phflag == 2 and "PHVAL" in ui_parms:
            phval = ui_parms["PHVAL"]
        else:
            phval = 7.0
        if roxfg == 2 and "ROC" in ui_parms:
            roc = ui_parms["ROC"]
        else:
            roc = 0.0
        if cldfg == 2 and "CLD" in ui_parms:
            cld = ui_parms["CLD"]
        else:
            cld = 0.0
        if sdfg == 2 and "SDCNC" in ui_parms:
            sdcnc = ui_parms["SDCNC"]
        else:
            sdcnc = 0.0
        if phytfg == 2 and "PHY" in ui_parms:
            phy = ui_parms["PHY"]
        else:
            phy = 0.0

        # for the following, if the flag value is 1 the timeseries should already be available as input
        if tempfg == 2 or tempfg == 3:
            ts["TW_GQ"] = initm(
                siminfo, uci, tempfg, "GQUAL" + str(index) + "_MONTHLY/WATEMP", twat
            )
        if phflag == 2 or phflag == 3:
            ts["PHVAL_GQ"] = initm(
                siminfo, uci, phflag, "GQUAL" + str(index) + "_MONTHLY/PHVAL", phval
            )
        if roxfg == 2 or roxfg == 3:
            ts["ROC_GQ"] = initm(
                siminfo, uci, roxfg, "GQUAL" + str(index) + "_MONTHLY/ROXYGEN", roc
            )
        if cldfg == 2 or cldfg == 3:
            ts["CLOUD_GQ"] = initm(
                siminfo, uci, cldfg, "GQUAL" + str(index) + "_MONTHLY/CLOUD", cld
            )
        if sdfg == 2 or sdfg == 3:
            ts["SDCNC_GQ"] = initm(
                siminfo, uci, sdfg, "GQUAL" + str(index) + "_MONTHLY/SEDCONC", sdcnc
            )
        if phytfg == 2 or phytfg == 3:
            ts["PHYTO_GQ"] = initm(
                siminfo, uci, phytfg, "GQUAL" + str(index) + "_MONTHLY/PHYTO", phy
            )
        # if any of these flags are 1 and the timeseries does not exist, that's a problem -- trigger message

        ts["DAYVAL"] = dayval(siminfo, [4, 4, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4])

        qalfg3 = ui_parms["QALFG3"]
        if qalfg3 == 1:  # qual undergoes photolysis
            # PHOTPM(1,I) # table-type gq-photpm
            if "EXTENDEDS_PHOTPM" in uci:
                ttable = uci["EXTENDEDS_PHOTPM"]
                for i in range(1, 21):
                    ui["photpm" + str(i)] = ttable["PHOTPM" + str(i - 1)]
            #  table-type gq-alpha
            if "EXTENDEDS_ALPH" in uci:
                ttable = uci["EXTENDEDS_ALPH"]
                for i in range(1, 19):
                    ui["alph" + str(i)] = ttable["ALPH" + str(i - 1)]
            #  table-type gq-gamma
            if "EXTENDEDS_GAMM" in uci:
                ttable = uci["EXTENDEDS_GAMM"]
                for i in range(1, 19):
                    ui["gamm" + str(i)] = ttable["GAMM" + str(i - 1)]
            #  table-type gq-delta
            if "EXTENDEDS_DEL" in uci:
                ttable = uci["EXTENDEDS_DEL"]
                for i in range(1, 19):
                    ui["delta" + str(i)] = ttable["DEL" + str(i - 1)]
            #  table-type gq-cldfact
            if "EXTENDEDS_KCLD" in uci:
                ttable = uci["EXTENDEDS_KCLD"]
                for i in range(1, 19):
                    ui["kcld" + str(i)] = ttable["KCLD" + str(i - 1)]

        # add contents of ui_parms to ui
        for key, value in ui_parms.items():
            if type(value) in {int, float}:
                ui[key] = float(value)
        # ui_combined = {**ui, **ui_parms}

        ############################################################################
        errors = _gqual_(ui, ts)  # run GQUAL simulation code
        ############################################################################

        if nexits > 1:
            u = uci["SAVE"]
            name = "GQUAL" + str(index)  # arbitrary identification
            key1 = name + "_ODQAL"
            for i in range(nexits):
                u[f"{key1}{i + 1}"] = u["ODQAL"]
            del u["ODQAL"]
            key1 = name + "_OSQAL1"
            for i in range(nexits):
                u[f"{key1}{i + 1}"] = u["OSQAL"]
            key1 = name + "_OSQAL2"
            for i in range(nexits):
                u[f"{key1}{i + 1}"] = u["OSQAL"]
            key1 = name + "_OSQAL3"
            for i in range(nexits):
                u[f"{key1}{i + 1}"] = u["OSQAL"]
            del u["OSQAL"]
            key1 = name + "_TOSQAL"
            for i in range(nexits):
                u[f"{key1}{i + 1}"] = u["TOSQAL"]
            del u["TOSQAL"]

    return errors, ERRMSGS


# @njit(cache=True)
def _gqual_(ui, ts):
    """Simulate the behavior of a generalized quality constituent"""
    errors = zeros(int(ui["errlen"])).astype(int64)

    simlen = int(ui["simlen"])
    nexits = int(ui["NEXITS"])
    uunits = int(ui["uunits"])
    delt60 = ui["delt60"]
    delts = ui["delts"]
    index = int(ui["index"])
    ngqual = int(ui["ngqual"])

    ddqal = zeros((8, ngqual + 1))

    AFACT = 43560.0
    if uunits == 2:
        # si units conversion
        AFACT = 1000000.0

    tempfg = 2
    phflag = 2
    roxfg = 2
    cldfg = 2
    sdfg = 2
    phytfg = 2
    if "TEMPFG" in ui:
        tempfg = int(ui["TEMPFG"])
        phflag = int(ui["PHFLAG"])
        roxfg = int(ui["ROXFG"])
        cldfg = int(ui["CLDFG"])
        sdfg = int(ui["SDFG"])
        phytfg = int(ui["PHYTFG"])
        lat = int(ui["LAT"])
    lkfg = int(ui["LKFG"])

    len_ = 0.0
    delth = 0.0
    if "LEN" in ui:
        len_ = ui["LEN"] * 5280.0  # mi to feet
        delth = ui["DELTH"]
        if uunits == 2:
            len_ = ui["LEN"] * 1000.0  # length of reach, in meters

    HRFG = ts["HRFG"].astype(int64)

    # table-type gq-qaldata
    # qualid = ui['GQID']
    dqal = ui["DQAL"]
    # concid = ui['CONCID']
    conv = ui["CONV"]
    # qtyid = ui['QTYID']

    vol = ui["vol"]
    svol = ui["svol"]
    rdqal = dqal * vol
    cinv = 1.0 / conv  # get reciprocal of unit conversion factor

    # process flags for this constituent

    # table-type gq-qalfg
    qalfg = zeros(8)
    qalfg[1] = ui["QALFG1"]
    qalfg[2] = ui["QALFG2"]
    qalfg[3] = ui["QALFG3"]
    qalfg[4] = ui["QALFG4"]
    qalfg[5] = ui["QALFG5"]
    qalfg[6] = ui["QALFG6"]
    qalfg[7] = ui["QALFG7"]

    # table-type gq-flg2
    gqpm2 = zeros(8)
    gqpm2[7] = 2
    if "GQPM21" in ui:
        gqpm2[1] = ui["GQPM21"]
        gqpm2[2] = ui["GQPM22"]
        gqpm2[3] = ui["GQPM23"]
        gqpm2[4] = ui["GQPM24"]
        gqpm2[5] = ui["GQPM25"]
        gqpm2[6] = ui["GQPM26"]
        gqpm2[7] = ui["GQPM27"]

    # process parameters for this constituent
    ka = 0.0
    kb = 0.0
    kn = 0.0
    thhyd = 0.0
    kox = 0.0
    thox = 0.0
    if qalfg[1] == 1:  # qual undergoes hydrolysis
        # HYDPM(1,I)  # table-type gq-hydpm
        ka = ui["KA"] * delts  # convert rates from /sec to /ivl
        kb = ui["KB"] * delts
        kn = ui["KN"] * delts
        thhyd = ui["THHYD"]

    if qalfg[2] == 1:  # qual undergoes oxidation by free radical processes
        # ROXPM(1,I)  # table-type gq-roxpm
        kox = ui["KOX"] * delts  # convert rates from /sec to /ivl
        thox = ui["THOX"]

    photpm = zeros(21)
    if qalfg[3] == 1:  # qual undergoes photolysis
        # PHOTPM(1,I) # table-type gq-photpm
        if "photpm1" in ui:
            for i in range(1, 21):
                photpm[i] = ui["photpm" + str(i)]

    cfgas = 0.0
    if qalfg[4] == 1:  # qual undergoes volatilization
        cfgas = ui["CFGAS"]  # table-type gq-cfgas

    biocon = 0.0
    thbio = 0.0
    biop = 0.0
    if qalfg[5] == 1:  # qual undergoes biodegradation
        # BIOPM(1,I)  # table-type gq-biopm
        biocon = ui["BIOCON"] * delt60 / 24.0  # convert rate from /day to /ivl
        thbio = ui["THBIO"]
        biop = ui["BIO"]

    fstdec = 0.0
    thfst = 0.0
    if qalfg[6] == 1:  #  qual undergoes "general" decay
        # GENPM(1,I)) # table-type gq-gendecay
        fstdec = ui["FSTDEC"] * delt60 / 24.0  # convert rate from /day to /ivl
        thfst = ui["THFST"]

    adpm1 = zeros(7)
    adpm2 = zeros(7)
    adpm3 = zeros(7)
    rsed = zeros(7)
    sqal = zeros(7)
    if qalfg[7] == 1:  # constituent is sediment-associated
        # get all required additional input
        # ADDCPM      # table-type gq-seddecay
        # convert rates from /day to /ivl
        addcpm1 = ui["ADDCP1"] * delt60 / 24.0  # convert rate from /day to /ivl
        addcpm2 = ui["ADDCP2"]
        addcpm3 = ui["ADDCP3"] * delt60 / 24.0  # convert rate from /day to /ivl
        addcpm4 = ui["ADDCP4"]

        # table-type gq-kd
        adpm1[1] = ui["ADPM11"]
        adpm1[2] = ui["ADPM21"]
        adpm1[3] = ui["ADPM31"]
        adpm1[4] = ui["ADPM41"]
        adpm1[5] = ui["ADPM51"]
        adpm1[6] = ui["ADPM61"]

        # gq-adrate
        adpm2[1] = ui["ADPM12"] * delt60 / 24.0  # convert rate from /day to /ivl
        adpm2[2] = ui["ADPM22"] * delt60 / 24.0  # convert rate from /day to /ivl
        adpm2[3] = ui["ADPM32"] * delt60 / 24.0  # convert rate from /day to /ivl
        adpm2[4] = ui["ADPM42"] * delt60 / 24.0  # convert rate from /day to /ivl
        adpm2[5] = ui["ADPM52"] * delt60 / 24.0  # convert rate from /day to /ivl
        adpm2[6] = ui["ADPM62"] * delt60 / 24.0  # convert rate from /day to /ivl

        # table-type gq-adtheta
        if "ADPM13" in ui:
            adpm3[1] = ui["ADPM13"]
            adpm3[2] = ui["ADPM23"]
            adpm3[3] = ui["ADPM33"]
            adpm3[4] = ui["ADPM43"]
            adpm3[5] = ui["ADPM53"]
            adpm3[6] = ui["ADPM63"]
        else:
            adpm3[1] = 1.07
            adpm3[2] = 1.07
            adpm3[3] = 1.07
            adpm3[4] = 1.07
            adpm3[5] = 1.07
            adpm3[6] = 1.07

        # table-type gq-sedconc
        sqal[1] = ui["SQAL1"]
        sqal[2] = ui["SQAL2"]
        sqal[3] = ui["SQAL3"]
        sqal[4] = ui["SQAL4"]
        sqal[5] = ui["SQAL5"]
        sqal[6] = ui["SQAL6"]

        # find the total quantity of material on various forms of sediment
        RSED1 = ts["RSED1"]  # sediment storages - suspended sand
        RSED2 = ts["RSED2"]  # sediment storages - suspended silt
        RSED3 = ts["RSED3"]  # sediment storages - suspended clay
        RSED4 = ts["RSED4"]  # sediment storages - bed sand
        RSED5 = ts["RSED5"]  # sediment storages - bed silt
        RSED6 = ts["RSED6"]  # sediment storages - bed clay

        rsed1 = RSED1[0]
        rsed2 = RSED2[0]
        rsed3 = RSED3[0]
        if "SSED1" in ui:
            rsed1 = ui["SSED1"]
            rsed2 = ui["SSED2"]
            rsed3 = ui["SSED3"]

        if uunits == 1:
            rsed[1] = RSED1[0] / 3.121e-08
            rsed[2] = RSED2[0] / 3.121e-08
            rsed[3] = RSED3[0] / 3.121e-08
            rsed[4] = RSED4[0] / 3.121e-08
            rsed[5] = RSED5[0] / 3.121e-08
            rsed[6] = RSED6[0] / 3.121e-08
        else:
            rsed[1] = RSED1[0] / 1e-06  # 2.83E-08
            rsed[2] = RSED2[0] / 1e-06
            rsed[3] = RSED3[0] / 1e-06
            rsed[4] = RSED4[0] / 1e-06
            rsed[5] = RSED5[0] / 1e-06
            rsed[6] = RSED6[0] / 1e-06

        rsqal1 = sqal[1] * rsed1 * svol
        rsqal2 = sqal[2] * rsed2 * svol
        rsqal3 = sqal[3] * rsed3 * svol
        rsqal4 = rsqal1 + rsqal2 + rsqal3
        rsqal5 = sqal[4] * rsed[4]
        rsqal6 = sqal[5] * rsed[5]
        rsqal7 = sqal[6] * rsed[6]
        rsqal8 = rsqal5 + rsqal6 + rsqal7
        rsqal9 = rsqal1 + rsqal5
        rsqal10 = rsqal2 + rsqal6
        rsqal11 = rsqal3 + rsqal7
        rsqal12 = rsqal9 + rsqal10 + rsqal11
    else:
        # qual not sediment-associated
        rsqal1 = 0.0
        rsqal2 = 0.0
        rsqal3 = 0.0
        rsqal4 = 0.0
        rsqal5 = 0.0
        rsqal6 = 0.0
        rsqal7 = 0.0
        rsqal8 = 0.0
        rsqal9 = 0.0
        rsqal10 = 0.0
        rsqal11 = 0.0
        rsqal12 = 0.0

    # find total quantity of qual in the rchres
    rrqal = rdqal + rsqal12
    gqst1 = rrqal

    # find values for global flags

    # gqalfg indicates whether any qual undergoes each of the decay processes or is sediment-associated

    # qalgfg indicates whether a qual undergoes any of the 6 decay processes
    qalgfg = 0
    if (
        qalfg[1] > 0
        or qalfg[2] > 0
        or qalfg[3] > 0
        or qalfg[4] > 0
        or qalfg[5] > 0
        or qalfg[6] > 0
    ):
        qalgfg = 1

    # gdaufg indicates whether any constituent is a "daughter" compound through each of the 6 possible decay processes
    gdaufg = 0
    if (
        gqpm2[1] > 0
        or gqpm2[2] > 0
        or gqpm2[3] > 0
        or gqpm2[4] > 0
        or gqpm2[5] > 0
        or gqpm2[6] > 0
    ):
        gdaufg = 1

    # daugfg indicates whether or not a given qual is a daughter compound
    daugfg = 0
    if (
        gqpm2[1] > 0
        or gqpm2[2] > 0
        or gqpm2[3] > 0
        or gqpm2[4] > 0
        or gqpm2[5] > 0
        or gqpm2[6] > 0
    ):
        daugfg = 1

    # get initial value for all inputs which can be constant,
    # vary monthly, or be a time series-some might be over-ridden by
    # monthly values or time series

    alph = zeros(19)
    gamm = zeros(19)
    delta = zeros(19)
    kcld = zeros(19)
    fact1 = 0.0
    light = 1
    if qalfg[3] == 1:
        #  table-type gq-alpha
        if "alph1" in ui:
            for i in range(1, 19):
                alph[i] = ui["alph" + str(i)]
        #  table-type gq-gamma
        if "gamm1" in ui:
            for i in range(1, 19):
                gamm[i] = ui["gamm" + str(i)]
        #  table-type gq-delta
        if "delta1" in ui:
            for i in range(1, 19):
                delta[i] = ui["delta" + str(i)]
        #  table-type gq-cldfact
        if "kcld1" in ui:
            for i in range(1, 19):
                kcld[i] = ui["kcld" + str(i)]

        cfsaex = 1.0
        if "CFSAEX" in ui:
            cfsaex = ui["CFSAEX"]

        # fact1 is a pre-calculated value used in photolysis simulation
        fact1 = cfsaex * delt60 / 24.0

        # decide which set of light data to use
        light = (abs(int(lat)) + 5) // 10
        if light == 0:  # no table for equation, so use 10 deg table
            light = 1
        lset_month = ts["DAYVAL"]

    reamfg = 0
    cforea = 0.0
    tcginv = 0.0
    reak = 0.0
    reakt = 0.0
    expred = 0.0
    exprev = 0.0
    if qalfg[4] == 1:
        # one or more constituents undergoes volatilization process- input required to compute reaeration coefficient

        # flags - table-type ox-flags
        reamfg = 2
        if "REAMFG" in ui:
            reamfg = ui["REAMFG"]
        dopfg = 0
        if "DOPFG" in ui:
            dopfg = ui["DOPFG"]

        htfg = int(ui["HTFG"])
        if htfg == 0:
            elev = ui["ELEV"]
            cfpres = ((288.0 - 0.001981 * elev) / 288.0) ** 5.256

        lkfg = int(ui["LKFG"])
        if lkfg == 1:
            # table-type ox-cforea
            cforea = 1.0
            if "CFOREA" in ui:
                cforea = ui["CFOREA"]
            if "CFOREA" in ui:
                cforea = ui["CFOREA"]
        else:
            if reamfg == 1:
                # tsivoglou method - table-type ox-tsivoglou
                reakt = ui["REAKT"]
                tcginv = ui["TCGINV"]
            elif reamfg == 2:
                # owen/churchill/o'connor-dobbins  # table-type ox-tcginv
                tcginv = 1.047
                if "TCGINV" in ui:
                    tcginv = ui["TCGINV"]
            elif reamfg == 3:
                # user formula - table-type ox-reaparm
                tcginv = ui["TCGINV"]
                reak = ui["REAK"]
                expred = ui["EXPRED"]
                exprev = ui["EXPREV"]

    # process tables specifying relationship between "parent" and "daughter" compounds
    # table-type gq-daughter
    c = zeros((8, 7))
    if "C21" in ui:
        c[2, 1] = ui["C21"]
        c[3, 1] = ui["C31"]
        c[4, 1] = ui["C41"]
        c[5, 1] = ui["C51"]
        c[6, 1] = ui["C61"]
        c[7, 1] = ui["C71"]
        c[3, 2] = ui["C32"]
        c[4, 2] = ui["C42"]
        c[5, 2] = ui["C52"]
        c[6, 2] = ui["C62"]
        c[7, 2] = ui["C72"]
        c[4, 3] = ui["C43"]
        c[5, 3] = ui["C53"]
        c[6, 3] = ui["C63"]
        c[7, 3] = ui["C73"]
        c[5, 4] = ui["C54"]
        c[6, 4] = ui["C64"]
        c[7, 4] = ui["C74"]
        c[6, 5] = ui["C65"]
        c[7, 5] = ui["C75"]
        c[7, 6] = ui["C76"]

    if qalfg[7] == 1:  #  one or more quals are sediment-associated
        sedfg = int(ui["SEDFG"])
        if sedfg == 0:  # section sedtrn not active
            # ERRMSG
            errors[0] += (
                1  # ERRMSG0: one or more gquals are sediment-associated, but section sedtrn not active
            )

    hydrfg = int(ui["HYDRFG"])
    aux1fg = int(ui["AUX1FG"])
    aux2fg = int(ui["AUX2FG"])
    if hydrfg == 1:  # check that required options in section hydr have been selected
        if qalfg[3] == 1 and aux1fg == 0:
            errors[1] += (
                1  # ERRMSG1: simulation of photolysis requires aux1fg to be on to calculate average depth
            )
        if qalfg[4] == 1:
            lkfg = int(ui["LKFG"])
            if lkfg == 0:
                if aux2fg == 0:
                    errors[2] += (
                        1  # ERRMSG2: simulation of volatilization in a free flowing stream requires aux3fg on
                    )
            else:
                if aux1fg == 0:
                    errors[3] += (
                        1  # ERRMSG3: simulation of volatilization in a lake requires aux1fg on to calculate average depth
                    )

    #####################  end PGQUAL

    if tempfg == 1:
        if "TW" not in ts:
            errors[6] += 1  # ERRMSG6: timeseries not available
            ts["TW_GQ"] = zeros(simlen)
        else:
            ts["TW_GQ"] = ts["TW"]
    if phflag == 1:
        if "PHVAL" not in ts:
            errors[7] += 1  # ERRMSG7: timeseries not available
            ts["PHVAL_GQ"] = zeros(simlen)
        else:
            ts["PHVAL_GQ"] = ts["PHVAL"]
    if roxfg == 1:
        if "ROC" not in ts:
            errors[8] += 1  # ERRMSG8: timeseries not available
            ts["ROC_GQ"] = zeros(simlen)
        else:
            ts["ROC_GQ"] = ts["ROC"]
    if cldfg == 1:
        if "CLOUD" not in ts:
            errors[9] += 1  # ERRMSG9: timeseries not available
            ts["CLOUD_GQ"] = zeros(simlen)
        else:
            ts["CLOUD_GQ"] = ts["CLOUD"]
    if sdfg == 1:
        if "SSED4" not in ts:
            errors[10] += 1  # ERRMSG10: timeseries not available
            ts["SDCNC_GQ"] = zeros(simlen)
        else:
            ts["SDCNC_GQ"] = ts["SSED4"]
    if phytfg == 1:
        if "PHYTO" not in ts:
            errors[11] += 1  # ERRMSG11: timeseries not available
            ts["PHYTO_GQ"] = zeros(simlen)
        else:
            ts["PHYTO_GQ"] = ts["PHYTO"]

    # get input timeseries
    TW = ts["TW_GQ"]
    PHVAL = ts["PHVAL_GQ"]
    ROC = ts["ROC_GQ"]
    CLD = ts["CLOUD_GQ"]
    SDCNC = ts["SDCNC_GQ"]
    PHYTO = ts["PHYTO_GQ"]

    AVDEP = ts["AVDEP"]
    WIND = ts["WIND"] * 1609.0  # miles to meters
    AVVEL = ts["AVVEL"]
    PREC = ts["PREC"]
    SAREA = ts["SAREA"]
    GQADFX = ts["GQADFX"]
    GQADCN = ts["GQADCN"]
    if "BIO" not in ts:
        ts["BIO"] = zeros(simlen)
    BIO = ts["BIO"]

    VOL = ts["VOL"]
    SROVOL = ts["SROVOL"]
    EROVOL = ts["EROVOL"]
    SOVOL = zeros((simlen, nexits))
    EOVOL = zeros((simlen, nexits))
    for i in range(nexits):
        SOVOL[:, i] = ts["SOVOL" + str(i + 1)]
        EOVOL[:, i] = ts["EOVOL" + str(i + 1)]

    # get incoming flow of constituent or zeros;
    if ("GQUAL" + str(index) + "_IDQAL") not in ts:
        ts["GQUAL" + str(index) + "_IDQAL"] = zeros(simlen)
    IDQAL = ts["GQUAL" + str(index) + "_IDQAL"]
    if ("GQUAL" + str(index) + "_ISQAL1") not in ts:
        ts["GQUAL" + str(index) + "_ISQAL1"] = zeros(simlen)
    ISQAL1 = ts["GQUAL" + str(index) + "_ISQAL1"]
    if ("GQUAL" + str(index) + "_ISQAL2") not in ts:
        ts["GQUAL" + str(index) + "_ISQAL2"] = zeros(simlen)
    ISQAL2 = ts["GQUAL" + str(index) + "_ISQAL2"]
    if ("GQUAL" + str(index) + "_ISQAL3") not in ts:
        ts["GQUAL" + str(index) + "_ISQAL3"] = zeros(simlen)
    ISQAL3 = ts["GQUAL" + str(index) + "_ISQAL3"]

    if qalfg[7] == 1:  # this constituent is associated with sediment
        DEPSCR1 = ts["DEPSCR1"]
        DEPSCR2 = ts["DEPSCR2"]
        DEPSCR3 = ts["DEPSCR3"]
        ROSED1 = ts["ROSED1"]
        ROSED2 = ts["ROSED2"]
        ROSED3 = ts["ROSED3"]

        OSED1 = zeros((simlen, nexits))
        OSED2 = zeros((simlen, nexits))
        OSED3 = zeros((simlen, nexits))

        for timeindex in range(simlen):
            if nexits > 1:
                for xindex in range(nexits):
                    OSED1[timeindex, xindex] = ts["OSED1" + str(xindex + 1)][timeindex]
                    OSED2[timeindex, xindex] = ts["OSED2" + str(xindex + 1)][timeindex]
                    OSED3[timeindex, xindex] = ts["OSED3" + str(xindex + 1)][timeindex]
            else:
                OSED1[timeindex, 0] = ts["ROSED1"][timeindex]
                OSED2[timeindex, 0] = ts["ROSED2"][timeindex]
                OSED3[timeindex, 0] = ts["ROSED3"][timeindex]

    # this number is used to adjust reaction rates for temperature
    # TW20 = TW - 20.0

    name = "GQUAL" + str(index)  # arbitrary identification
    # preallocate output arrays (always needed)
    ADQAL1 = ts[name + "_ADQAL1"] = zeros(simlen)
    ADQAL2 = ts[name + "_ADQAL2"] = zeros(simlen)
    ADQAL3 = ts[name + "_ADQAL3"] = zeros(simlen)
    ADQAL4 = ts[name + "_ADQAL4"] = zeros(simlen)
    ADQAL5 = ts[name + "_ADQAL5"] = zeros(simlen)
    ADQAL6 = ts[name + "_ADQAL6"] = zeros(simlen)
    ADQAL7 = ts[name + "_ADQAL7"] = zeros(simlen)
    DDQAL1 = ts[name + "_DDQAL1"] = zeros(simlen)
    DDQAL2 = ts[name + "_DDQAL2"] = zeros(simlen)
    DDQAL3 = ts[name + "_DDQAL3"] = zeros(simlen)
    DDQAL4 = ts[name + "_DDQAL4"] = zeros(simlen)
    DDQAL5 = ts[name + "_DDQAL5"] = zeros(simlen)
    DDQAL6 = ts[name + "_DDQAL6"] = zeros(simlen)
    DDQAL7 = ts[name + "_DDQAL7"] = zeros(simlen)
    DQAL = ts[name + "_DQAL"] = zeros(simlen)
    DSQAL1 = ts[name + "_DSQAL1"] = zeros(simlen)
    DSQAL2 = ts[name + "_DSQAL2"] = zeros(simlen)
    DSQAL3 = ts[name + "_DSQAL3"] = zeros(simlen)
    DSQAL4 = ts[name + "_DSQAL4"] = zeros(simlen)
    GQADDR = ts[name + "_GQADDR"] = zeros(simlen)
    GQADEP = ts[name + "_GQADEP"] = zeros(simlen)
    GQADWT = ts[name + "_GQADWT"] = zeros(simlen)
    ISQAL4 = ts[name + "_ISQAL4"] = zeros(simlen)
    PDQAL = ts[name + "_PDQAL"] = zeros(simlen)
    RDQAL = ts[name + "_RDQAL"] = zeros(simlen)
    RODQAL = ts[name + "_RODQAL"] = zeros(simlen)
    ROSQAL1 = ts[name + "_ROSQAL1"] = zeros(simlen)
    ROSQAL2 = ts[name + "_ROSQAL2"] = zeros(simlen)
    ROSQAL3 = ts[name + "_ROSQAL3"] = zeros(simlen)
    ROSQAL4 = ts[name + "_ROSQAL4"] = zeros(simlen)
    RRQAL = ts[name + "_RRQAL"] = zeros(simlen)
    RSQAL1 = ts[name + "_RSQAL1"] = zeros(simlen)
    RSQAL2 = ts[name + "_RSQAL2"] = zeros(simlen)
    RSQAL3 = ts[name + "_RSQAL3"] = zeros(simlen)
    RSQAL4 = ts[name + "_RSQAL4"] = zeros(simlen)
    RSQAL5 = ts[name + "_RSQAL5"] = zeros(simlen)
    RSQAL6 = ts[name + "_RSQAL6"] = zeros(simlen)
    RSQAL7 = ts[name + "_RSQAL7"] = zeros(simlen)
    RSQAL8 = ts[name + "_RSQAL8"] = zeros(simlen)
    RSQAL9 = ts[name + "_RSQAL9"] = zeros(simlen)
    RSQAL10 = ts[name + "_RSQAL10"] = zeros(simlen)
    RSQAL11 = ts[name + "_RSQAL11"] = zeros(simlen)
    RSQAL12 = ts[name + "_RSQAL12"] = zeros(simlen)
    SQAL1 = ts[name + "_SQAL1"] = zeros(simlen)
    SQAL2 = ts[name + "_SQAL2"] = zeros(simlen)
    SQAL3 = ts[name + "_SQAL3"] = zeros(simlen)
    SQAL4 = ts[name + "_SQAL4"] = zeros(simlen)
    SQAL5 = ts[name + "_SQAL5"] = zeros(simlen)
    SQAL6 = ts[name + "_SQAL6"] = zeros(simlen)
    SQDEC1 = ts[name + "_SQDEC1"] = zeros(simlen)
    SQDEC2 = ts[name + "_SQDEC2"] = zeros(simlen)
    SQDEC3 = ts[name + "_SQDEC3"] = zeros(simlen)
    SQDEC4 = ts[name + "_SQDEC4"] = zeros(simlen)
    SQDEC5 = ts[name + "_SQDEC5"] = zeros(simlen)
    SQDEC6 = ts[name + "_SQDEC6"] = zeros(simlen)
    SQDEC7 = ts[name + "_SQDEC7"] = zeros(simlen)
    TIQAL = ts[name + "_TIQAL"] = zeros(simlen)
    TROQAL = ts[name + "_TROQAL"] = zeros(simlen)
    TOQAL = zeros((simlen, nexits))
    ODQAL = zeros((simlen, nexits))
    OSQAL1 = zeros((simlen, nexits))
    OSQAL2 = zeros((simlen, nexits))
    OSQAL3 = zeros((simlen, nexits))
    TOSQAL = zeros((simlen, nexits))

    for loop in range(simlen):
        # within time loop

        # tw20 may be required for bed decay of qual even if tw is undefined (due to vol=0.0)
        tw = TW[loop]
        if uunits == 1:
            tw = (tw - 32.0) * 0.5555  # 5.0 / 9.0
        tw20 = tw - 20.0  # TW20[loop]
        if tw <= -10.0:
            tw20 = 0.0
        # correct unrealistically high values of tw calculated in htrch
        if tw >= 50.0:
            tw20 = 30.0

        phval = PHVAL[loop]
        roc = ROC[loop]
        cld = CLD[loop]
        sdcnc = SDCNC[loop]
        phy = PHYTO[loop]

        prec = PREC[loop]
        sarea = SAREA[loop]
        vol = VOL[loop] * AFACT
        toqal = TOQAL[loop]
        tosqal = TOSQAL[loop]

        # initialize sediment-related variables:
        if qalfg[7] == 1:  # constituent is sediment-associated
            osed1 = zeros(nexits)
            osed2 = zeros(nexits)
            osed3 = zeros(nexits)

            # define conversion factor:
            cf = 1.0
            if uunits == 1:
                cf = 3.121e-8
            else:
                cf = 1.0e-6

            depscr1 = DEPSCR1[loop] / cf
            depscr2 = DEPSCR2[loop] / cf
            depscr3 = DEPSCR3[loop] / cf
            rosed1 = ROSED1[loop] / cf
            rosed2 = ROSED2[loop] / cf
            rosed3 = ROSED3[loop] / cf

            for i in range(nexits):
                osed1[i] = OSED1[loop, i] / cf
                osed2[i] = OSED2[loop, i] / cf
                osed3[i] = OSED3[loop, i] / cf

            rsed = zeros(7)
            rsed[1] = RSED1[loop] / cf
            rsed[2] = RSED2[loop] / cf
            rsed[3] = RSED3[loop] / cf
            rsed[4] = RSED4[loop] / cf
            rsed[5] = RSED5[loop] / cf
            rsed[6] = RSED6[loop] / cf

        isqal1 = ISQAL1[loop]
        isqal2 = ISQAL2[loop]
        isqal3 = ISQAL3[loop]

        if uunits == 2:  # uci is in metric units
            avdepm = AVDEP[loop]
            avdepe = AVDEP[loop] * 3.28
            avvele = AVVEL[loop] * 3.28
        else:  # uci is in english units
            avdepm = AVDEP[loop] * 0.3048
            avdepe = AVDEP[loop]
            avvele = AVVEL[loop]

        fact2 = zeros(19)
        if qalfg[3] > 0:
            # one or more constituents undergoes photolysis decay
            if avdepe > 0.17:
                # depth of water in rchres is greater than two inches -
                # consider photolysis; this criteria will also be applied to other decay processes

                lset = lset_month[loop]
                # southern hemisphere is 2 seasons out of phase
                if lat < 0:
                    lset += 2
                    if lset > 4:
                        lset -= 4

                for l in range(1, 19):
                    # evaluate the light extinction exponent- 2.76*klamda*d
                    kl = alph[l] + gamm[l] * sdcnc + delta[l] * phy
                    expnt = 2.76 * kl * avdepm * 100.0
                    # evaluate the cloud factor
                    cldl = (10.0 - cld * kcld[l]) / 10.0
                    if expnt <= -20.0:
                        expnt = -20.0
                    if expnt >= 20.0:
                        expnt = 20.0
                    # evaluate the precalculated factors fact2
                    # lit is data from the seq file
                    # fact2[l] = cldl * lit[l,lset] * (1.0 - exp(-expnt)) / expnt
                    fact2[l] = (
                        cldl
                        * light_factor(l, lset, light)
                        * (1.0 - exp(-expnt))
                        / expnt
                    )
            else:
                # depth of water in rchres is less than two inches -photolysis is not considered
                pass

        korea = 0.0
        if qalfg[4] > 0:
            # prepare to simulate volatilization by finding the oxygen reaeration coefficient
            wind = 0.0
            if lkfg == 1:
                wind = WIND[loop]
            if avdepe > 0.17:  # rchres depth is sufficient to consider volatilization
                # compute oxygen reaeration rate-korea
                korea = oxrea(
                    lkfg,
                    wind,
                    cforea,
                    avvele,
                    avdepe,
                    tcginv,
                    reamfg,
                    reak,
                    reakt,
                    expred,
                    exprev,
                    len_,
                    delth,
                    tw,
                    delts,
                    delt60,
                    uunits,
                )
                # KOREA = OXREA(LKFG,WIND,CFOREA,AVVELE,AVDEPE,TCGINV,REAMFG,REAK,REAKT,EXPRED,EXPREV,LEN, DELTH,TWAT,DELTS,DELT60,UUNITS,KOREA)
            else:
                # rchres depth is not sufficient to consider volatilization
                pass

        # get data on inflow of dissolved material
        gqadfx = GQADFX[loop]
        gqadcn = GQADCN[loop]
        gqaddr = sarea * conv * gqadfx  # dry deposition;
        gqadwt = prec * sarea * gqadcn  # wet deposition;

        gqadep = gqaddr + gqadwt  # total atmospheric deposition
        idqal = IDQAL[loop] * conv
        indqal = idqal + gqaddr + gqadwt

        # simulate advection of dissolved material
        srovol = SROVOL[loop]
        erovol = EROVOL[loop]
        sovol = SOVOL[loop, :]
        eovol = EOVOL[loop, :]
        dqal, rodqal, odqal = advect(
            indqal, dqal, nexits, svol, vol, srovol, erovol, sovol, eovol
        )

        bio = biop
        if qalfg[5] > 0:
            # get biomass input, if required (for degradation)
            bio = BIO[loop]

        if avdepe > 0.17:  #  simulate decay of dissolved material
            hr = HRFG[loop]
            ddqal[:, index] = ddecay(
                qalfg,
                tw20,
                ka,
                kb,
                kn,
                thhyd,
                phval,
                kox,
                thox,
                roc,
                fact2,
                fact1,
                photpm,
                korea,
                cfgas,
                biocon,
                thbio,
                bio,
                fstdec,
                thfst,
                vol,
                dqal,
                hr,
                delt60,
            )
            # ddqal[1,index] = DDECAY(QALFG(1,I),TW20,HYDPM(1,I),PHVAL,ROXPM(1,I),ROC,FACT2(1),FACT1,PHOTPM(1,I),KOREA,CFGAS(I),
            # 						BIOPM(1,I),BIO(I),GENPM(1,I),VOLSP,DQAL(I),HR,DELT60,DDQAL(1,I))

            pdqal = 0.0
            for k in range(1, 7):
                if (
                    gqpm2[k] == 1
                ):  # this compound is a "daughter"-compute the contribution to it from its "parent(s)"
                    itobe = index - 1
                    for j in range(1, itobe):
                        pdqal = pdqal + ddqal[k, j] * c[j, k]

            # update the concentration to account for decay and for input
            # from decay of "parents"- units are conc/l
            if vol > 0:
                dqal = dqal + (pdqal - ddqal[7, index]) / vol
        else:
            # rchres depth is less than two inches - dissolved decay is not considered
            for l in range(1, 8):
                ddqal[l, index] = 0.0
            # 320      CONTINUE
            pdqal = 0.0

        adqal = zeros(8)
        dsqal1 = 0.0
        dsqal2 = 0.0
        dsqal3 = 0.0
        dsqal4 = 0.0
        osqal1 = zeros(nexits)
        osqal2 = zeros(nexits)
        osqal3 = zeros(nexits)
        osqal4 = zeros(nexits)
        rosqal1 = 0.0
        rosqal2 = 0.0
        rosqal3 = 0.0
        sqdec1 = 0.0
        sqdec2 = 0.0
        sqdec3 = 0.0
        sqdec4 = 0.0
        sqdec5 = 0.0
        sqdec6 = 0.0
        sqdec7 = 0.0
        # zero the accumulators
        isqal4 = 0.0
        dsqal4 = 0.0
        rosqal4 = 0.0

        if qalfg[7] == 1:  # this constituent is associated with sediment
            if nexits > 1:
                for n in range(1, nexits):
                    tosqal[n] = 0.0

            # repeat for each sediment size fraction
            # get data on inflow of sediment-associated material

            # sand
            # advect this material, including calculation of deposition and scour
            errors, sqal[1], sqal[4], dsqal1, rosqal1, osqal1 = advqal(
                isqal1 * conv,
                rsed[1],
                rsed[4],
                depscr1,
                rosed1,
                osed1,
                nexits,
                rsqal1,
                rsqal5,
                errors,
            )
            rosqal1 = rosqal1 / conv
            osqal1 = osqal1 / conv
            # GQECNT(1),SQAL(J,I),SQAL(J + 3,I),DSQAL(J,I), ROSQAL(J,I),OSQAL(1,J,I)) = ADVQAL (ISQAL(J,I),RSED(J),RSED(J + 3),\
            # DEPSCR(J),ROSED(J),OSED(1,J),NEXITS,RCHNO, MESSU,MSGFL,DATIM, GQID(1,I),J,RSQAL(J,I),RSQAL(J + 4,I),GQECNT(1),
            # SQAL(J,I),SQAL(J + 3,I),DSQAL(J,I),ROSQAL(J,I),OSQAL(1,J,I))

            isqal4 = isqal4 + isqal1
            dsqal4 = dsqal4 + dsqal1
            rosqal4 = rosqal4 + rosqal1
            if nexits > 1:
                for n in range(1, nexits):
                    tosqal[n] = tosqal[n] + osqal1[n]

            # silt
            # advect this material, including calculation of deposition and scour
            errors, sqal[2], sqal[5], dsqal2, rosqal2, osqal2 = advqal(
                isqal2 * conv,
                rsed[2],
                rsed[5],
                depscr2,
                rosed2,
                osed2,
                nexits,
                rsqal2,
                rsqal6,
                errors,
            )
            rosqal2 = rosqal2 / conv
            osqal2 = osqal2 / conv
            # GQECNT(1), SQAL(J, I), SQAL(J + 3, I), DSQAL(J, I), ROSQAL(J, I), OSQAL(1, J, I)) = ADVQAL(
            # 	ISQAL(J, I), RSED(J), RSED(J + 3), \
            # 	DEPSCR(J), ROSED(J), OSED(1, J), NEXITS, RCHNO, MESSU, MSGFL, DATIM, GQID(1, I), J, RSQAL(J, I),
            # 	RSQAL(J + 4, I), GQECNT(1),
            # 	SQAL(J, I), SQAL(J + 3, I), DSQAL(J, I), ROSQAL(J, I), OSQAL(1, J, I))

            isqal4 = isqal4 + isqal2
            dsqal4 = dsqal4 + dsqal2
            rosqal4 = rosqal4 + rosqal2
            if nexits > 1:
                for n in range(1, nexits):
                    tosqal[n] = tosqal[n] + osqal2[n]

            # clay
            # advect this material, including calculation of deposition and scour
            errors, sqal[3], sqal[6], dsqal3, rosqal3, osqal3 = advqal(
                isqal3 * conv,
                rsed[3],
                rsed[6],
                depscr3,
                rosed3,
                osed3,
                nexits,
                rsqal3,
                rsqal7,
                errors,
            )
            rosqal3 = rosqal3 / conv
            osqal3 = osqal3 / conv
            # GQECNT(1), SQAL(J, I), SQAL(J + 3, I), DSQAL(J, I), ROSQAL(J, I), OSQAL(1, J, I)) = ADVQAL(
            # 	ISQAL(J, I), RSED(J), RSED(J + 3), \
            # 	DEPSCR(J), ROSED(J), OSED(1, J), NEXITS, RCHNO, MESSU, MSGFL, DATIM, GQID(1, I), J, RSQAL(J, I),
            # 	RSQAL(J + 4, I), GQECNT(1),
            # 	SQAL(J, I), SQAL(J + 3, I), DSQAL(J, I), ROSQAL(J, I), OSQAL(1, J, I))

            isqal4 = isqal4 + isqal3
            dsqal4 = dsqal4 + dsqal3
            rosqal4 = rosqal4 + rosqal3
            if nexits > 1:
                for n in range(1, nexits):
                    tosqal[n] = tosqal[n] + osqal3[n]

            tiqal = idqal + isqal4
            troqal = (rodqal / conv) + rosqal4
            if nexits > 1:
                for n in range(0, nexits - 1):
                    toqal[n] = odqal[n] + tosqal[n]

            if avdepe > 0.17:  # simulate decay on suspended sediment
                sqal[1], sqal[2], sqal[3], sqdec1, sqdec2, sqdec3 = adecay(
                    addcpm1,
                    addcpm2,
                    tw20,
                    rsed[1],
                    rsed[2],
                    rsed[3],
                    sqal[1],
                    sqal[2],
                    sqal[3],
                )
                # SQAL((1),I), SQDEC((1),I)) =  ADECAY(ADDCPM(1,I),TW20,RSED(1),SQAL((1),I),SQDEC((1),I))
            else:
                # rchres depth is less than two inches - decay of qual
                # associated with suspended sediment is not considered
                sqdec1 = 0.0
                sqdec2 = 0.0
                sqdec3 = 0.0

            # simulate decay on bed sediment
            sqal[4], sqal[5], sqal[6], sqdec4, sqdec5, sqdec6 = adecay(
                addcpm3,
                addcpm4,
                tw20,
                rsed[4],
                rsed[5],
                rsed[6],
                sqal[4],
                sqal[5],
                sqal[6],
            )
            # SQAL((4),I), SQDEC((4),I)) = ADECAY(ADDCPM(3,I),TW20,RSED(4),SQAL((4),I),SQDEC((4),I))

            # get total decay
            sqdec7 = sqdec1 + sqdec2 + sqdec3 + sqdec4 + sqdec5 + sqdec6

            if avdepe > 0.17:  # simulate exchange due to adsorption and desorption
                dqal, sqal, adqal = adsdes(
                    vol, rsed, adpm1, adpm2, adpm3, tw20, dqal, sqal
                )
                # DQAL(I), SQAL(1,I), ADQAL(1,I) = ADSDES(VOLSP,RSED(1),ADPM(1,1,I),TW20,DQAL(I),SQAL(1,I),ADQAL(1,I))
            else:
                # rchres depth is less than two inches - adsorption and
                # desorption of qual is not considered
                adqal[1] = 0.0
                adqal[2] = 0.0
                adqal[3] = 0.0
                adqal[4] = 0.0
                adqal[5] = 0.0
                adqal[6] = 0.0
                adqal[7] = 0.0

            # find total quantity of material on various forms of sediment
            rsqal4 = 0.0
            rsqal8 = 0.0
            rsqal12 = 0.0
            rsqal1 = sqal[1] * rsed[1]
            rsqal2 = sqal[2] * rsed[2]
            rsqal3 = sqal[3] * rsed[3]
            rsqal4 = rsqal1 + rsqal2 + rsqal3
            rsqal5 = sqal[4] * rsed[4]
            rsqal6 = sqal[5] * rsed[5]
            rsqal7 = sqal[6] * rsed[6]
            rsqal8 = rsqal5 + rsqal6 + rsqal7
            rsqal9 = rsqal1 + rsqal5
            rsqal10 = rsqal2 + rsqal6
            rsqal11 = rsqal3 + rsqal7
            rsqal12 = rsqal9 + rsqal10 + rsqal11
        else:
            # qual constituent not associated with sediment-total just
            # above should have been set to zero by run interpreter
            tiqal = idqal
            troqal = rodqal / conv
            if nexits > 1:
                for n in range(1, nexits):
                    toqal[n] = odqal[n]

        # find total quantity of qual in rchres
        rdqal = dqal * vol
        if qalfg[7] == 1:
            rrqal = rdqal + rsqal12
        else:
            rrqal = rdqal

        svol = vol  # svol is volume at start of time step, update for next time thru

        ADQAL1[loop] = adqal[1] / conv  # put values for this time step back into TS
        ADQAL2[loop] = adqal[2] / conv
        ADQAL3[loop] = adqal[3] / conv
        ADQAL4[loop] = adqal[4] / conv
        ADQAL5[loop] = adqal[5] / conv
        ADQAL6[loop] = adqal[6] / conv
        ADQAL7[loop] = adqal[7] / conv
        DDQAL1[loop] = ddqal[1, index] / conv
        DDQAL2[loop] = ddqal[2, index] / conv
        DDQAL3[loop] = ddqal[3, index] / conv
        DDQAL4[loop] = ddqal[4, index] / conv
        DDQAL5[loop] = ddqal[5, index] / conv
        DDQAL6[loop] = ddqal[6, index] / conv
        DDQAL7[loop] = ddqal[7, index] / conv
        DQAL[loop] = dqal
        DSQAL1[loop] = dsqal1 / conv
        DSQAL2[loop] = dsqal2 / conv
        DSQAL3[loop] = dsqal3 / conv
        DSQAL4[loop] = dsqal4 / conv
        GQADDR[loop] = gqaddr
        GQADEP[loop] = gqadep
        GQADWT[loop] = gqadwt
        ISQAL4[loop] = isqal4
        ODQAL[loop] = odqal / conv
        OSQAL1[loop] = osqal1
        OSQAL2[loop] = osqal2
        OSQAL3[loop] = osqal3
        PDQAL[loop] = pdqal
        RDQAL[loop] = rdqal / conv
        RODQAL[loop] = rodqal / conv
        ROSQAL1[loop] = rosqal1
        ROSQAL2[loop] = rosqal2
        ROSQAL3[loop] = rosqal3
        ROSQAL4[loop] = rosqal4
        RRQAL[loop] = rrqal / conv
        RSQAL1[loop] = rsqal1 / conv
        RSQAL2[loop] = rsqal2 / conv
        RSQAL3[loop] = rsqal3 / conv
        RSQAL4[loop] = rsqal4 / conv
        RSQAL5[loop] = rsqal5 / conv
        RSQAL6[loop] = rsqal6 / conv
        RSQAL7[loop] = rsqal7 / conv
        RSQAL8[loop] = rsqal8 / conv
        RSQAL9[loop] = rsqal9 / conv
        RSQAL10[loop] = rsqal10 / conv
        RSQAL11[loop] = rsqal11 / conv
        RSQAL12[loop] = rsqal12 / conv
        SQAL1[loop] = sqal[1]
        SQAL2[loop] = sqal[2]
        SQAL3[loop] = sqal[3]
        SQAL4[loop] = sqal[4]
        SQAL5[loop] = sqal[5]
        SQAL6[loop] = sqal[6]
        SQDEC1[loop] = sqdec1 / conv
        SQDEC2[loop] = sqdec2 / conv
        SQDEC3[loop] = sqdec3 / conv
        SQDEC4[loop] = sqdec4 / conv
        SQDEC5[loop] = sqdec5 / conv
        SQDEC6[loop] = sqdec6 / conv
        SQDEC7[loop] = sqdec7 / conv
        TIQAL[loop] = tiqal / conv
        TOSQAL[loop] = tosqal
        TROQAL[loop] = troqal

    if nexits > 1:
        for i in range(nexits):
            ts[name + "_ODQAL" + str(i + 1)] = ODQAL[:, i]
            ts[name + "_OSQAL1" + str(i + 1)] = OSQAL1[:, i]
            ts[name + "_OSQAL2" + str(i + 1)] = OSQAL2[:, i]
            ts[name + "_OSQAL3" + str(i + 1)] = OSQAL3[:, i]
            ts[name + "_TOSQAL" + str(i + 1)] = TOSQAL[:, i]

    return errors


@njit(cache=True)
def adecay(
    addcpm1,
    addcpm2,
    tw20,
    rsed_sand,
    rsed_silt,
    rsed_clay,
    sqal_sand,
    sqal_silt,
    sqal_clay,
):
    # real  addcpm(2),rsed(3),sqal(3),sqdec(3),tw20
    """simulate decay of material in adsorbed state"""

    sqdec_sand = 0.0
    sqdec_silt = 0.0
    sqdec_clay = 0.0
    if addcpm1 > 0.0:  # calculate temp-adjusted decay rate
        dk = addcpm1 * addcpm2**tw20
        fact = 1.0 - exp(-dk)

        if sqal_sand > 1.0e-30:
            dconc = sqal_sand * fact
            sqal_sand = sqal_sand - dconc
            sqdec_sand = dconc * rsed_sand
        if sqal_silt > 1.0e-30:
            dconc = sqal_silt * fact
            sqal_silt = sqal_silt - dconc
            sqdec_silt = dconc * rsed_silt
        if sqal_clay > 1.0e-30:
            dconc = sqal_clay * fact
            sqal_clay = sqal_clay - dconc
            sqdec_clay = dconc * rsed_clay

    return sqal_sand, sqal_silt, sqal_clay, sqdec_sand, sqdec_silt, sqdec_clay


@njit(cache=True)
def adsdes(vol, rsed, adpm1, adpm2, adpm3, tw20, dqal, sqal):
    #  adpm(6,3),adqal(7),dqal,rsed(6),sqal(6),tw20,vol

    """simulate exchange of a constituent between the dissolved
    state and adsorbed state-note that 6 adsorption site classes are
    considered: 1- suspended sand  2- susp. silt  3- susp. clay
    4- bed sand  5- bed silt  6- bed clay"""

    ainv = zeros(7)
    cainv = zeros(7)
    adqal = zeros(8)
    if vol > 0.0:  # adsorption/desorption can take place
        # first find the new dissolved conc.
        num = vol * dqal
        denom = vol
        for j in range(1, 7):
            if rsed[j] > 0.0:  # this sediment class is present-evaluate terms due to it
                # transfer rate, corrected for water temp
                akj = adpm2[j] * adpm3[j] ** tw20
                temp = 1.0 / (1.0 + akj)

                # calculate 1/a and c/a
                ainv[j] = akj * adpm1[j] * temp
                cainv[j] = sqal[j] * temp

                # accumulate terms for numerator and denominator in dqal equation
                num = num + (sqal[j] - cainv[j]) * rsed[j]
                denom = denom + rsed[j] * ainv[j]

        # calculate new dissolved concentration-units are conc/l
        dqal = num / denom

        # calculate new conc on each sed class and the corresponding adsorption/desorption flux
        adqal[7] = 0.0
        for j in range(1, 7):
            if (
                rsed[j] > 0.0
            ):  # this sediment class is present-calculate data pertaining to it
                # new concentration
                temp = cainv[j] + dqal * ainv[j]

                # quantity of material transferred
                adqal[j] = (temp - sqal[j]) * rsed[j]
                sqal[j] = temp

                # accumulate total adsorption/desorption flux
                adqal[7] = adqal[7] + adqal[j]
            else:  # this sediment class is absent
                adqal[j] = 0.0
                # sqal(j) is unchanged-"undefined"
    else:  # no water, no adsorption/desorption
        for j in range(1, 7):
            adqal[j] = 0.0
            # sqal(1 thru 3) and dqal should already have been set to undefined values

    return dqal, sqal, adqal


@njit(cache=True)
def advqal(isqal, rsed, bsed, depscr, rosed, osed, nexits, rsqals, rbqals, errors):
    """simulate the advective processes, including deposition and
    scour for the quality constituent attached to one sediment size fraction"""

    if depscr < 0.0:  # there was scour during the interval
        if bsed <= 0.0:  #  bed was scoured "clean"
            bqal = -1.0e30
            dsqal = (
                -1.0 * rbqals
            )  # cbrb changed sign of dsqal; it should be negative for scour; fixed 4/2007
        else:  # there is still bed material left
            bqal = rbqals / (bsed - depscr)
            dsqal = bqal * depscr

        # calculate concentration in suspension-under these conditions,
        # denominator should never be zero
        if rsed + rosed > 0.0:
            sqal = (isqal + rsqals - dsqal) / (rsed + rosed)
        else:
            sqal = 0.0
        rosqal = rosed * sqal
    else:  # there was deposition or no scour/deposition during the interval
        denom = rsed + depscr + rosed
        if denom <= 0.0:  # there was no sediment in suspension during the interval
            sqal = -1.0e30
            rosqal = 0.0
            dsqal = 0.0
            if abs(isqal) > 0.0 or abs(rsqals) > 0.0:
                errors[4] += (
                    1  # ERRMSG4: error-under these conditions these values should be zero
                )
        else:  # there was some suspended sediment during the interval
            # calculate conc on suspended sed
            sqal = (isqal + rsqals) / denom
            rosqal = rosed * sqal
            dsqal = depscr * sqal
            if rsed <= 0.0:
                # rchres ended up without any suspended sediment-revise
                # value for sqal, but values obtained for rsqal,
                # rosqal, and dsqal are still ok
                sqal = -1.0e30

        # calculate conditions on the bed
        if bsed <= 0.0:  # no bed sediments at end of interval
            bqal = -1.0e30
            if abs(dsqal) > 0.0 or abs(rbqals > 0.0):
                errors[5] += (
                    1  # ERRMSG4: error-under these conditions these values should be zero
                )
        else:  # there is bed sediment at the end of the interval
            rbqal = dsqal + rbqals
            bqal = rbqal / bsed

    osqal = zeros(nexits)
    # osqal = array([0.0, 0.0, 0.0, 0.0, 0.0])
    if nexits > 1:  # we need to compute outflow through each individual exit
        if rosed <= 0.0:  # all zero
            for i in range(nexits):
                osqal[i] = 0.0
        else:
            for i in range(nexits):
                osqal[i] = rosqal * osed[i] / rosed

    return errors, sqal, bqal, dsqal, rosqal, osqal


@njit(cache=True)
def ddecay(
    qalfg,
    tw20,
    ka,
    kb,
    kn,
    thhyd,
    phval,
    kox,
    thox,
    roc,
    fact2,
    fact1,
    photpm,
    korea,
    cfgas,
    biocon,
    thbio,
    bio,
    fstdec,
    thfst,
    volsp,
    dqal,
    hr,
    delt60,
):
    """estimate decay of dissolved constituent"""

    # bio,biopm(2),cfgas,ddqal(7),delt60,dqal,fact1,fact2(18),genpm(2),hydpm(4),korea,photpm(20),phval, roc,roxpm(2),tw20,volsp

    ddqal = array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    if dqal > 1.0e-25:  # simulate decay
        k = array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        k[1] = 0.0
        if qalfg[1] == 1:  # simulate hydrolysis
            khyd = ka * 10.0 ** (-phval) + kb * 10.0 ** (phval - 14.0) + kn
            k[1] = khyd * thhyd**tw20  # adjust for temperature

        k[2] = 0.0
        if qalfg[2] == 1:  # simulate oxidation by free radical processes
            krox = kox * roc
            k[2] = krox * thox**tw20  # adjust for temperature

        k[3] = 0.0
        if qalfg[3] == 1:  # simulate photolysis
            # go through summation over 18 wave-length intervals
            fact3 = 0.0
            for l in range(1, 19):
                fact3 = fact3 + fact2[l] * photpm[l]
            k[3] = fact1 * photpm[19] * fact3 * photpm[20] ** tw20
        if delt60 < 24.0:
            if (
                17 > hr >= 5
            ):  # it is a daylight hour; photolysis rate is doubled for this interval
                k[3] = 2.0 * k[3]
            else:  # it is not a daylight hour; photolysis does not occur
                k[3] = 0.0
        # else:
        # simulation interval is greater than 24 hours;
        # no correction is made to photolysis rate to
        # represent diurnal fluctuation

        # simulate volatilization
        k[4] = korea * cfgas if qalfg[4] == 1 else 0.0

        # simulate biodegradation
        k[5] = biocon * bio * thbio**tw20 if qalfg[5] == 1 else 0.0

        # simulate simple first-order decay
        k[6] = fstdec * thfst**tw20 if qalfg[6] == 1 else 0.0

        # get total decay rate
        k7 = k[1] + k[2] + k[3] + k[4] + k[5] + k[6]

        # calculate the total change in material due to decay-units are conc*vol/l.ivl
        ddqal[7] = dqal * (1.0 - exp(-k7)) * volsp

        # prorate among the individual decay processes- the method used
        # for proration is linear, which is not strictly correct, but
        # should be a good approximation under most conditions
        for i in range(1, 7):
            if k7 > 0.0:
                ddqal[i] = k[i] / k7 * ddqal[7]
            else:
                ddqal[i] = 0.0

    return ddqal


@njit(cache=True)
def light_factor(l, lset, light):
    # light factors for photolysis, in hspf read from seq file
    vals = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    if light == 1:
        if lset == 1:
            vals = [
                0.0102,
                0.0178,
                0.0285,
                0.0327,
                0.0418,
                0.0370,
                0.339,
                0.433,
                0.840,
                1.16,
                1.47,
                1.50,
                2.74,
                2.90,
                2.90,
                2.80,
                2.70,
                3.00,
            ]
        elif lset == 2:
            vals = [
                0.000466,
                0.00316,
                0.00937,
                0.0190,
                0.0291,
                0.0265,
                0.329,
                0.438,
                0.837,
                1.17,
                1.47,
                1.50,
                2.69,
                2.79,
                2.80,
                2.80,
                2.70,
                2.50,
            ]
        elif lset == 3:
            vals = [
                0.000419,
                0.00287,
                0.00851,
                0.00173,
                0.0266,
                0.0291,
                0.299,
                0.385,
                0.764,
                1.07,
                1.36,
                1.37,
                2.46,
                2.52,
                2.60,
                2.60,
                2.50,
                2.30,
            ]
        else:
            vals = [
                0.000320,
                0.00239,
                0.00726,
                0.0151,
                0.0238,
                0.0236,
                0.0292,
                0.344,
                0.696,
                0.980,
                1.23,
                1.27,
                2.26,
                2.35,
                2.43,
                2.30,
                2.40,
                2.10,
            ]
    elif light == 2:
        if lset == 1:
            vals = [
                0.000351,
                0.00251,
                0.00809,
                0.0181,
                0.0282,
                0.0283,
                0.329,
                0.424,
                0.841,
                1.17,
                1.47,
                1.50,
                2.68,
                2.80,
                2.80,
                2.80,
                2.76,
                2.50,
            ]
        elif lset == 2:
            vals = [
                0.000444,
                0.00315,
                0.00961,
                0.0197,
                0.0302,
                0.0303,
                0.347,
                0.447,
                0.883,
                1.23,
                1.55,
                1.58,
                2.81,
                2.96,
                2.90,
                3.00,
                2.80,
                2.70,
            ]
        elif lset == 3:
            vals = [
                0.000274,
                0.00220,
                0.00689,
                0.0148,
                0.0233,
                0.0233,
                0.268,
                0.345,
                0.696,
                0.980,
                1.24,
                1.26,
                2.30,
                2.35,
                2.42,
                2.40,
                2.20,
                2.26,
            ]
        else:
            vals = [
                0.000147,
                0.00147,
                0.00534,
                0.0115,
                0.0188,
                0.0188,
                0.221,
                0.286,
                0.597,
                0.840,
                1.06,
                1.09,
                1.95,
                2.03,
                2.07,
                2.10,
                2.36,
                1.60,
            ]
    elif light == 3:
        if lset == 1:
            vals = [
                0.000230,
                0.00213,
                0.00726,
                0.0165,
                0.0264,
                0.0269,
                0.320,
                0.414,
                0.827,
                1.15,
                1.45,
                1.48,
                2.64,
                2.74,
                2.76,
                2.80,
                2.70,
                2.50,
            ]
        elif lset == 2:
            vals = [
                0.000365,
                0.00232,
                0.00902,
                0.0192,
                0.0302,
                0.0304,
                0.374,
                0.437,
                0.907,
                1.34,
                1.59,
                1.62,
                2.89,
                3.03,
                3.00,
                3.00,
                2.90,
                2.80,
            ]
        elif lset == 3:
            vals = [
                0.000135,
                0.00144,
                0.00484,
                0.0116,
                0.0189,
                0.0230,
                0.223,
                0.284,
                0.623,
                0.850,
                1.09,
                1.11,
                2.00,
                2.07,
                2.09,
                2.10,
                2.10,
                1.90,
            ]
        else:
            vals = [
                0.0000410,
                0.000650,
                0.00276,
                0.00755,
                0.0131,
                0.0134,
                0.170,
                0.219,
                0.475,
                0.669,
                0.850,
                0.880,
                1.57,
                1.63,
                1.67,
                1.73,
                1.63,
                1.60,
            ]
    elif light == 4:
        if lset == 1:
            vals = [
                0.000109,
                0.00137,
                0.00296,
                0.00799,
                0.0138,
                0.0142,
                0.178,
                0.230,
                0.526,
                0.676,
                0.890,
                0.923,
                1.69,
                1.73,
                1.78,
                1.50,
                1.70,
                1.60,
            ]
        elif lset == 2:
            vals = [
                0.000249,
                0.00232,
                0.00793,
                0.0181,
                0.0291,
                0.0297,
                0.354,
                0.458,
                0.971,
                1.28,
                1.43,
                1.63,
                2.92,
                3.05,
                3.00,
                3.10,
                2.90,
                2.90,
            ]
        elif lset == 3:
            vals = [
                0.000109,
                0.00137,
                0.00535,
                0.0138,
                0.02319,
                0.0239,
                0.108,
                0.384,
                0.791,
                1.11,
                1.39,
                1.42,
                2.52,
                2.62,
                2.60,
                4.70,
                2.60,
                2.50,
            ]
        else:
            vals = [
                0.0000054,
                0.000156,
                0.00102,
                0.00379,
                0.00753,
                0.00810,
                0.0752,
                0.147,
                0.338,
                0.480,
                0.610,
                0.620,
                1.12,
                1.16,
                1.19,
                1.39,
                1.20,
                1.16,
            ]
    elif light == 5:
        if lset == 1:
            vals = [
                0.0000371,
                0.000710,
                0.00355,
                0.00730,
                0.00184,
                0.0196,
                0.266,
                0.348,
                0.724,
                1.02,
                1.29,
                1.32,
                2.34,
                2.40,
                2.44,
                2.50,
                2.50,
                2.30,
            ]
        elif lset == 2:
            vals = [
                0.0000079,
                0.00175,
                0.00653,
                0.0163,
                0.0267,
                0.0277,
                0.343,
                0.444,
                0.904,
                1.26,
                1.60,
                1.63,
                2.90,
                3.04,
                3.00,
                3.10,
                2.90,
                2.90,
            ]
        elif lset == 3:
            vals = [
                0.000152,
                0.000225,
                0.00129,
                0.00439,
                0.00864,
                0.00920,
                0.124,
                0.166,
                0.365,
                0.517,
                0.660,
                0.680,
                1.22,
                1.25,
                1.31,
                1.34,
                1.31,
                1.24,
            ]
        else:
            vals = [
                0.0000004,
                0.0000157,
                0.000178,
                0.00120,
                0.00293,
                0.00368,
                0.0629,
                0.0821,
                0.196,
                0.275,
                0.351,
                0.355,
                0.630,
                0.640,
                0.690,
                0.710,
                0.710,
                0.690,
            ]
    return vals[l - 1]


def expand_GQUAL_masslinks(flags, uci, dat, recs):
    if flags["GQUAL"]:
        ngqual = 1
        if "PARAMETERS" in uci:
            ui = uci["PARAMETERS"]
            if "NGQUAL" in ui:
                ngqual = ui["NGQUAL"]
        for i in range(1, ngqual + 1):
            # IDQAL                            # loop for each gqual
            rec = {}
            rec["MFACTOR"] = dat.MFACTOR
            rec["SGRPN"] = "GQUAL"
            if dat.SGRPN == "ROFLOW":
                rec["SMEMN"] = "RODQAL"
                rec["SMEMSB1"] = str(i)  # first sub is qual index
                rec["SMEMSB2"] = ""
            else:
                rec["SMEMN"] = "ODQAL"
                rec["SMEMSB1"] = str(i)  # qual index
                rec["SMEMSB2"] = dat.SMEMSB1  # exit number
            rec["TMEMN"] = "IDQAL"
            rec["TMEMSB1"] = dat.TMEMSB1
            rec["TMEMSB2"] = dat.TMEMSB2
            rec["SVOL"] = dat.SVOL
            recs.append(rec)
            # ISQAL1
            rec = {}
            rec["MFACTOR"] = dat.MFACTOR
            rec["SGRPN"] = "GQUAL"
            if dat.SGRPN == "ROFLOW":
                rec["SMEMN"] = "ROSQAL"
                rec["SMEMSB1"] = "1"  # for sand
                rec["SMEMSB2"] = str(i)  # second sub is qual index
            else:
                rec["SMEMN"] = "OSQAL"
                rec["SMEMSB1"] = str(i)  # qual i
                rec["SMEMSB2"] = "1" + dat.SMEMSB1  # for clay for exit number
            rec["TMEMN"] = "ISQAL1"
            rec["TMEMSB1"] = dat.TMEMSB1
            rec["TMEMSB2"] = dat.TMEMSB2
            rec["SVOL"] = dat.SVOL
            recs.append(rec)
            # ISQAL2
            rec = {}
            rec["MFACTOR"] = dat.MFACTOR
            rec["SGRPN"] = "GQUAL"
            if dat.SGRPN == "ROFLOW":
                rec["SMEMN"] = "ROSQAL"
                rec["SMEMSB1"] = "2"  # for silt
                rec["SMEMSB2"] = str(i)  # second sub is qual index
            else:
                rec["SMEMN"] = "OSQAL"
                rec["SMEMSB1"] = str(i)  # qual i
                rec["SMEMSB2"] = "2" + dat.SMEMSB1  # for clay for exit number
            rec["TMEMN"] = "ISQAL2"
            rec["TMEMSB1"] = dat.TMEMSB1
            rec["TMEMSB2"] = dat.TMEMSB2
            rec["SVOL"] = dat.SVOL
            recs.append(rec)
            # ISQAL3
            rec = {}
            rec["MFACTOR"] = dat.MFACTOR
            rec["SGRPN"] = "GQUAL"
            if dat.SGRPN == "ROFLOW":
                rec["SMEMN"] = "ROSQAL"
                rec["SMEMSB1"] = "3"  # for clay
                rec["SMEMSB2"] = str(i)  # second sub is qual index
            else:
                rec["SMEMN"] = "OSQAL"
                rec["SMEMSB1"] = str(i)  # qual i
                rec["SMEMSB2"] = "3" + dat.SMEMSB1  # for clay for exit number
            rec["TMEMN"] = "ISQAL3"
            rec["TMEMSB1"] = dat.TMEMSB1
            rec["TMEMSB2"] = dat.TMEMSB2
            rec["SVOL"] = dat.SVOL
            rec["INDEX"] = str(i)
            recs.append(rec)
    return recs


def hour24Flag(siminfo, dofirst=False):
    """timeseries with hour values"""
    hours24 = zeros(24)
    for i in range(0, 24):
        hours24[i] = i
    return hoursval(siminfo, hours24, dofirst)
