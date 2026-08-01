"""Recall lookups via the NHTSA public recalls API.

Public, no key required. You query by make/model/year (which you can get from a
VIN via vin.decode_vin). Docs: https://www.nhtsa.gov/nhtsa-datasets-and-apis
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .http import get_json

RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


@dataclass
class Recall:
    campaign: str
    component: str
    summary: str
    remedy: str
    report_date: str


@dataclass
class RecallReport:
    make: str
    model: str
    year: str
    recalls: list[Recall] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.recalls)


def lookup_recalls(make: str, model: str, year: str, timeout: float = 20.0) -> RecallReport:
    """Return open recalls for a make/model/year."""
    data = get_json(
        RECALLS_URL,
        params={"make": make, "model": model, "modelYear": year},
        timeout=timeout,
    )
    report = RecallReport(make=make, model=model, year=str(year))
    for item in data.get("results") or []:
        report.recalls.append(
            Recall(
                campaign=item.get("NHTSACampaignNumber", "").strip(),
                component=item.get("Component", "").strip(),
                summary=item.get("Summary", "").strip(),
                remedy=item.get("Remedy", "").strip(),
                report_date=item.get("ReportReceivedDate", "").strip(),
            )
        )
    return report
