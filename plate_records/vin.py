"""VIN decoding via the NHTSA vPIC API.

vPIC is a free, public U.S. government API. No API key and no permissible
purpose is required, because a VIN describes the *vehicle* (make/model/specs),
not the owner. Docs: https://vpic.nhtsa.dot.gov/api/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .http import HTTPError, get_json

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"

# The subset of vPIC fields most people actually care about, mapped to friendly
# names. vPIC returns ~130 fields; we keep the report readable.
_FIELDS = {
    "Make": "make",
    "Model": "model",
    "ModelYear": "year",
    "Trim": "trim",
    "BodyClass": "body_class",
    "VehicleType": "vehicle_type",
    "FuelTypePrimary": "fuel_type",
    "EngineCylinders": "engine_cylinders",
    "DisplacementL": "displacement_l",
    "DriveType": "drive_type",
    "TransmissionStyle": "transmission",
    "Doors": "doors",
    "PlantCountry": "plant_country",
    "Manufacturer": "manufacturer",
    "Series": "series",
}


@dataclass
class VinReport:
    vin: str
    fields: dict[str, str] = field(default_factory=dict)
    error_text: str | None = None

    @property
    def summary(self) -> str:
        parts = [self.fields.get(k) for k in ("year", "make", "model", "trim")]
        return " ".join(p for p in parts if p) or "(no vehicle description returned)"


def decode_vin(vin: str, timeout: float = 20.0) -> VinReport:
    """Decode a 17-character VIN into vehicle attributes.

    Raises HTTPError on network failure. Returns a VinReport even if vPIC
    reports the VIN is invalid (see report.error_text).
    """
    vin = vin.strip().upper()
    if not vin:
        raise ValueError("VIN is empty")

    url = f"{VPIC_BASE}/DecodeVinValues/{urllib_quote(vin)}"
    data: Any = get_json(url, params={"format": "json"}, timeout=timeout)

    results = data.get("Results") or []
    if not results:
        raise HTTPError("vPIC returned no results")
    raw = results[0]

    report = VinReport(vin=vin)
    for src, dst in _FIELDS.items():
        val = (raw.get(src) or "").strip()
        if val:
            report.fields[dst] = val

    # vPIC reports validity via ErrorCode ("0" == no errors).
    error_code = (raw.get("ErrorCode") or "").strip()
    if error_code and error_code != "0":
        report.error_text = (raw.get("ErrorText") or "").strip() or f"ErrorCode {error_code}"

    return report


def urllib_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
