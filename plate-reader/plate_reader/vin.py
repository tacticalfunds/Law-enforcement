"""Decode vehicle details from a VIN via the NHTSA vPIC API.

vPIC (https://vpic.nhtsa.dot.gov/api/) is a free, public, key-less US
government service that returns *vehicle* facts for a VIN — make, model, year,
body style, engine, plant, and ~130 other fields. It exposes only vehicle
data; it does not return owners or any personal information.

This module offers:

* :func:`is_valid_vin` / :func:`vin_model_year` — offline checks (ISO 3779
  check-digit validation, model-year hint) so you can screen a large list
  before hitting the network.
* :func:`decode_vin`  — decode a single VIN.
* :func:`decode_vins` — decode many VINs using vPIC's batch endpoint (one
  request per ~50 VINs), so large lists stay fast.

Network access is only needed for the two ``decode_*`` calls.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from typing import Iterable, Optional

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"

# The subset of vPIC's ~130 fields we surface by default, in a friendly order.
CORE_FIELDS = [
    "VIN", "Make", "Model", "ModelYear", "Trim", "Series", "BodyClass",
    "VehicleType", "Manufacturer", "PlantCity", "PlantState", "PlantCountry",
    "EngineCylinders", "DisplacementL", "FuelTypePrimary", "DriveType",
    "TransmissionStyle", "Doors", "GVWR", "ErrorCode", "ErrorText",
]

# VIN characters exclude I, O and Q (to avoid confusion with 1 and 0).
VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"

# Transliteration + weights for the ISO 3779 / NHTSA check digit (position 9).
_TRANSLIT = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9, "S": 2, "T": 3,
    "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# Model-year code -> year, for VIN position 10 (1980-2039 cycle).
_YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"


def normalize_vin(vin: str) -> str:
    """Uppercase and strip whitespace (does not alter characters)."""
    return vin.strip().upper()


def is_valid_vin(vin: str) -> bool:
    """True if ``vin`` is a well-formed 17-char VIN with a valid check digit.

    Note: the check digit is mandatory for North American VINs but not for all
    world markets, so a ``False`` here means "not a standard NA VIN", not
    necessarily "undecodable" — vPIC can still decode many partial/foreign VINs.
    """
    vin = normalize_vin(vin)
    if len(vin) != 17 or any(c not in VIN_ALPHABET for c in vin):
        return False
    total = sum(_TRANSLIT[c] * w for c, w in zip(vin, _WEIGHTS))
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    return vin[8] == expected


def vin_model_year(vin: str) -> Optional[int]:
    """Best-effort model year from VIN position 10 (None if not decodable).

    The single-character code repeats every 30 years; this assumes the modern
    (1980+) cycle, biased toward recent years, which is right for the vast
    majority of vehicles on the road.
    """
    vin = normalize_vin(vin)
    if len(vin) < 10:
        return None
    code = vin[9]
    if code not in _YEAR_CODES:
        return None
    idx = _YEAR_CODES.index(code)
    return 1980 + idx


# -- network helpers --------------------------------------------------------

def _default_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Honour a custom CA bundle if the environment sets one (e.g. behind a
    # TLS-terminating proxy). Harmless when unset.
    ca = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca and os.path.exists(ca):
        ctx.load_verify_locations(ca)
    return ctx


def _get_json(url: str, *, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout,
                                context=_default_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, data: bytes, *, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=data,
        headers={"Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout,
                                context=_default_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _select(row: dict, *, full: bool) -> dict:
    """Keep the friendly core fields (or everything, if ``full``)."""
    if full:
        return {k: (v if v not in ("", None) else None) for k, v in row.items()}
    out = {}
    for key in CORE_FIELDS:
        val = row.get(key)
        out[key] = val if val not in ("", None) else None
    return out


# -- public decoding --------------------------------------------------------

def decode_vin(vin: str, *, model_year: Optional[int] = None,
               timeout: float = 20.0, full: bool = False) -> dict:
    """Decode a single VIN into a dict of vehicle facts.

    ``model_year`` optionally disambiguates VINs whose year code is ambiguous.
    Set ``full=True`` to return all vPIC fields instead of the core subset.
    """
    vin = normalize_vin(vin)
    params = {"format": "json"}
    if model_year:
        params["modelyear"] = str(model_year)
    url = (f"{VPIC_BASE}/DecodeVinValues/{urllib.parse.quote(vin)}"
           f"?{urllib.parse.urlencode(params)}")
    data = _get_json(url, timeout=timeout)
    results = data.get("Results") or [{}]
    return _select(results[0], full=full)


def decode_vins(vins: Iterable[str], *, timeout: float = 30.0,
                chunk: int = 50, full: bool = False) -> list[dict]:
    """Decode many VINs using vPIC's batch endpoint.

    VINs are sent in groups of ``chunk`` (vPIC's practical per-request limit),
    so a list of thousands becomes a handful of requests. Returns one dict per
    VIN, in input order.
    """
    vins = [normalize_vin(v) for v in vins if normalize_vin(v)]
    out: list[dict] = []
    url = f"{VPIC_BASE}/DecodeVINValuesBatch/"
    for i in range(0, len(vins), chunk):
        part = vins[i:i + chunk]
        payload = urllib.parse.urlencode(
            {"format": "json", "data": ";".join(part)}
        ).encode("utf-8")
        data = _post_json(url, payload, timeout=timeout)
        for row in data.get("Results", []):
            out.append(_select(row, full=full))
    return out
