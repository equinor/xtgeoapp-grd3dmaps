import logging

import numpy as np
import xtgeo

logger = logging.getLogger(__name__)


def zonation(config, grd):
    """Get the zonations, by either a file or a config spec.

    It must be zranges OR zproperty.

    The super zonation is a collection of zones, whcih do not need to be
    in sequence.

    Args:
        config (dict): The config dict,
        grd (Grid): the grid property object

    Returns:
        zonation (np): zonation, 3D numpy
        zoned (dict): Zonation dictionary (name: zone number)
        superzoned (dict): Super zonation dictionary (name: [zone range])
    """

    if "zproperty" in config["zonation"] and "zranges" in config["zonation"]:
        raise ValueError('Cannot have both "zproperty" and "zranges" in "zonation"')

    usezonation = np.zeros(grd.dimensions, dtype=np.int32)
    zoned = {}
    superzoned = {}

    eclroot = None
    if "eclroot" in config["input"] and config["input"]["eclroot"] is not None:
        eclroot = config["input"]["eclroot"]

    if "zproperty" in config["zonation"]:
        zcfg = config["zonation"]["zproperty"]

        mysource = zcfg["source"]
        if "$eclroot" in mysource:
            mysource = mysource.replace("$eclroot", eclroot)

        zon = xtgeo.gridproperty_from_file(
            mysource, fformat="guess", name=zcfg["name"], grid=grd
        )
        myzonation = zon.values.astype(np.int32)
        # myzonation = np.ma.filled(zonation, fill_value=0)
        for izn, zns in enumerate(zcfg["zones"]):
            zname = list(zns.keys())[0]  # zz.keys()[0]
            iranges = list(zns.values())[0]
            for ira in iranges:
                usezonation[myzonation == ira] = izn + 1
            zoned[zname] = izn + 1

    elif "zranges" in config["zonation"]:
        zclist = config["zonation"]["zranges"]
        logger.debug(type(zclist))
        for i, zz in enumerate(config["zonation"]["zranges"]):
            zname = list(zz.keys())[0]  # zz.keys()[0]
            intv = list(zz.values())[0]
            k01 = intv[0] - 1
            k02 = intv[1]

            logger.debug("K01 K02: %s - %s", k01, k02)

            usezonation[:, :, k01:k02] = i + 1
            zoned[zname] = i + 1

    if "superranges" in config["zonation"]:
        logger.debug("Found superranges keyword...")
        for i, zz in enumerate(config["zonation"]["superranges"]):
            zname = list(zz.keys())[0]
            superzoned[zname] = []
            intv = list(zz.values())[0]
            logger.debug("Superzone spec no %s: %s  %s", i + 1, zname, intv)
            for zn in intv:
                superzoned[zname].append(zoned[zn])
    else:
        logger.debug("Did not find any superranges...")

    for myz, val in zoned.items():
        logger.debug("Zonation list: %s: %s", myz, val)

    for key, vals in superzoned.items():
        logger.debug("Superzoned %s  %s", key, vals)

    logger.debug("The zoned dict: %s", zoned)
    logger.debug("The superzoned dict: %s", superzoned)

    zmerged = zoned.copy()
    zmerged.update(superzoned)

    zmerged["all"] = None

    return usezonation, zmerged
