import hilbertcurve
import hilbertcurve.hilbertcurve

import csv
import pathlib
import logging

import typing

logger = logging.getLogger(f"EDMCBoxelSurveyor.boxel_surveyor")

def parse_id64(id64: int):
    L = id64 & ((1 << 3) - 1)
    id64 = id64 >> 3

    Lz = id64 & ((1 << (7 - L)) - 1)
    id64 = id64 >> (7 - L)
    Hz = id64 & ((1 << 7) - 1)
    id64 = id64 >> 7

    Ly = id64 & ((1 << (7 - L)) - 1)
    id64 = id64 >> (7 - L)
    Hy = id64 & ((1 << 6) - 1)
    id64 = id64 >> 6

    Lx = id64 & ((1 << (7 - L)) - 1)
    id64 = id64 >> (7 - L)
    Hx = id64 & ((1 << 7) - 1)
    id64 = id64 >> 7

    N = id64 & ((1 << (32 - (3 * (7 - L)))) - 1)

    return {
        "MassCode": L,
        "BoxelZ": Lz,
        "SectorZ": Hz,
        "BoxelY": Ly,
        "SectorY": Hy,
        "BoxelX": Lx,
        "SectorX": Hx,
        "Index": N
    }

def suffix(parsed_id64: dict[str, int]):
    massCode = chr(97 + parsed_id64["MassCode"])
    boxelIndex = parsed_id64["BoxelX"] + (parsed_id64["BoxelY"] << 7) + (parsed_id64["BoxelZ"] << 14)

    A = chr(65 + (boxelIndex % 26))
    boxelIndex = boxelIndex // 26
    B = chr(65 + (boxelIndex % 26))
    boxelIndex = boxelIndex // 26
    C = chr(65 + (boxelIndex % 26))
    boxelIndex = boxelIndex // 26
    D = boxelIndex

    if D == 0:
        return f"{A}{B}-{C} {massCode}{parsed_id64['Index']}"
    else:
        return f"{A}{B}-{C} {massCode}{D}-{parsed_id64['Index']}"

sectorsByCoord = {}
with (pathlib.Path(__file__).parent / 'sector-list.csv').open() as f:
    r = csv.DictReader(f)
    for row in r:
        if row["id64 X"]:
            sectorsByCoord[(int(row["id64 X"]), int(row["id64 Y"]), int(row["id64 Z"]))] = row["Sector"]

def id64ToName(id64: int):
    parsed_id64 = parse_id64(id64)
    return parsedToName(parsed_id64)

def parsedToName(parsed_id64):
    sectorName = sectorsByCoord.get((parsed_id64["SectorX"], parsed_id64["SectorY"], parsed_id64["SectorZ"]), "Unknown Sector")

    return f"{sectorName} {suffix(parsed_id64)}"

def nextInBoxel(id64: int, knownIdxs: typing.Set[int] = set()):
    parsed_id64 = parse_id64(id64)

    parsed_id64['Index'] = parsed_id64['Index'] + 1
    if knownIdxs and len(knownIdxs):
        parsed_id64["Index"] = 0
        while parsed_id64["Index"] in knownIdxs:
            parsed_id64["Index"] = parsed_id64["Index"] + 1
    return parsedToName(parsed_id64)

def currentBoxelInLayer(parsed_id64: dict):
    hc = hilbertcurve.hilbertcurve.HilbertCurve(n = 3, p = 7 - parsed_id64["MassCode"])
    boxelCoord = (parsed_id64["BoxelX"], parsed_id64["BoxelY"], parsed_id64["BoxelZ"])

    h = hc.distance_from_point(boxelCoord)
    return h, hc.max_h

def nextBoxelInLayer(id64: int, offset: int = 1):
    parsed_id64 = parse_id64(id64)

    if parsed_id64["MassCode"] == 7:
        return None

    hc = hilbertcurve.hilbertcurve.HilbertCurve(n = 3, p = 7 - parsed_id64["MassCode"])
    boxelCoord = (parsed_id64["BoxelX"], parsed_id64["BoxelY"], parsed_id64["BoxelZ"])

    h = hc.distance_from_point(boxelCoord)
    if h == hc.max_h:
        return None

    nextBoxelCoord = hc.point_from_distance(max(0, min(h + offset, hc.max_h - 1)))
    parsed_id64["BoxelX"], parsed_id64["BoxelY"], parsed_id64["BoxelZ"] = nextBoxelCoord
    parsed_id64["Index"] = 0

    return parsedToName(parsed_id64)