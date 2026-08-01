"""Pluggable provider interface for RESTRICTED vehicle data.

This is the boundary between what this tool ships (free, public data) and what
it deliberately does not: title/history and owner/registration records.

Why it's a plug-in and not a built-in:

  * Plate -> owner (name/address) lookups are governed in the U.S. by the
    Driver's Privacy Protection Act (18 U.S.C. Sec. 2721 et seq.). Records may
    only be obtained for an enumerated "permissible purpose" and only from a
    source you are authorized to query.
  * Title/brand/odometer history via NMVTIS is only available through an
    NMVTIS-approved data provider account.

To use these features, implement a subclass backed by a provider you are
legally authorized to use, and register it on the CLI with --provider. No
concrete provider is shipped in this repository on purpose.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class TitleRecord:
    """A single title/brand history event (e.g. from NMVTIS)."""

    state: str = ""
    title_number: str = ""
    issue_date: str = ""
    odometer: str = ""
    brand: str = ""  # e.g. "salvage", "flood", "junk", "clean"


@dataclass
class RegistrationRecord:
    """Owner / registration info. DPPA-protected; permissible purpose required."""

    plate: str = ""
    state: str = ""
    vin: str = ""
    # Owner PII intentionally left as free-form so an authorized provider can
    # populate only what the caller's permissible purpose entitles them to.
    details: dict[str, str] = field(default_factory=dict)


class RecordsProvider(abc.ABC):
    """Implement this against a data source you are authorized to query."""

    #: Human-readable name shown in reports and audit logs.
    name: str = "unnamed-provider"

    @abc.abstractmethod
    def title_history(self, vin: str) -> list[TitleRecord]:
        """Return title/brand history for a VIN (e.g. via NMVTIS)."""

    @abc.abstractmethod
    def registration_by_plate(self, plate: str, state: str, *, permissible_purpose: str) -> RegistrationRecord:
        """Return registration/owner info for a plate.

        Implementations MUST record `permissible_purpose` for audit and MUST
        refuse the lookup if the configured account is not entitled to it.
        """
