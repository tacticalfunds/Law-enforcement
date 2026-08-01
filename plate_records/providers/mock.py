"""A mock provider so the CLI runs end-to-end without a real data account.

It returns clearly-fake, deterministic data and refuses any registration
lookup unless a permissible purpose string is supplied -- mirroring how a real
DPPA-compliant provider must gate access. Never use this for real decisions.
"""

from __future__ import annotations

from .base import RecordsProvider, RegistrationRecord, TitleRecord


class MockProvider(RecordsProvider):
    name = "mock"

    def title_history(self, vin: str) -> list[TitleRecord]:
        return [
            TitleRecord(
                state="XX",
                title_number="MOCK-" + vin[-6:],
                issue_date="2020-01-01",
                odometer="42000",
                brand="clean",
            )
        ]

    def registration_by_plate(self, plate: str, state: str, *, permissible_purpose: str) -> RegistrationRecord:
        if not permissible_purpose:
            raise PermissionError(
                "A permissible purpose is required for a registration/owner lookup (DPPA). "
                "A real provider would refuse this request."
            )
        return RegistrationRecord(
            plate=plate.upper(),
            state=state.upper(),
            vin="MOCKVIN0000000000",
            details={
                "note": "SAMPLE DATA ONLY - not a real record",
                "purpose_logged": permissible_purpose,
            },
        )
