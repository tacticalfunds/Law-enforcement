"""Command-line interface for plate_records.

Subcommands:
  vin      Decode a VIN via NHTSA vPIC (public).
  recalls  Look up recalls by make/model/year via NHTSA (public).
  report   Full public report for a VIN: decode + recalls.
  title    Title/brand history for a VIN via a provider (restricted).
  plate    Registration/owner lookup by plate via a provider (DPPA-restricted).

The `title` and `plate` subcommands require --provider. Only `mock` ships in
this repository; supply your own authorized provider for real data.
"""

from __future__ import annotations

import argparse
import json
import sys

from .http import HTTPError
from .providers import get_provider
from .recalls import lookup_recalls
from .vin import decode_vin


def _print(obj, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, default=lambda o: o.__dict__))
    else:
        print(obj)


def cmd_vin(args) -> int:
    report = decode_vin(args.vin)
    if args.json:
        _print({"vin": report.vin, "summary": report.summary, **report.fields,
                "error": report.error_text}, True)
    else:
        print(f"VIN {report.vin}: {report.summary}")
        for k, v in report.fields.items():
            print(f"  {k:16} {v}")
        if report.error_text:
            print(f"  ! vPIC note: {report.error_text}")
    return 0


def cmd_recalls(args) -> int:
    report = lookup_recalls(args.make, args.model, args.year)
    if args.json:
        _print(report, True)
    else:
        print(f"{report.year} {report.make} {report.model}: {report.count} recall(s)")
        for r in report.recalls:
            print(f"  [{r.campaign}] {r.component}")
            if r.summary:
                print(f"      {r.summary}")
    return 0


def cmd_report(args) -> int:
    vin_report = decode_vin(args.vin)
    out = {"vin": vin_report.vin, "summary": vin_report.summary, **vin_report.fields}
    make = vin_report.fields.get("make")
    model = vin_report.fields.get("model")
    year = vin_report.fields.get("year")
    if make and model and year:
        try:
            rec = lookup_recalls(make, model, year)
            out["recalls"] = [r.__dict__ for r in rec.recalls]
        except HTTPError as exc:
            out["recalls_error"] = str(exc)
    else:
        out["recalls"] = "skipped (incomplete vehicle description)"
    _print(out, True)
    return 0


def cmd_title(args) -> int:
    provider = get_provider(args.provider)
    records = provider.title_history(args.vin.strip().upper())
    _print([r.__dict__ for r in records], True)
    return 0


def cmd_plate(args) -> int:
    provider = get_provider(args.provider)
    try:
        record = provider.registration_by_plate(
            args.plate, args.state, permissible_purpose=args.purpose or ""
        )
    except PermissionError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    _print(record, True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="plate-records", description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="emit JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("vin", help="decode a VIN (public)")
    sp.add_argument("vin")
    sp.set_defaults(func=cmd_vin)

    sp = sub.add_parser("recalls", help="recalls by make/model/year (public)")
    sp.add_argument("make")
    sp.add_argument("model")
    sp.add_argument("year")
    sp.set_defaults(func=cmd_recalls)

    sp = sub.add_parser("report", help="full public report for a VIN")
    sp.add_argument("vin")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("title", help="title/brand history for a VIN (restricted, needs --provider)")
    sp.add_argument("vin")
    sp.add_argument("--provider", required=True)
    sp.set_defaults(func=cmd_title)

    sp = sub.add_parser("plate", help="registration/owner by plate (DPPA-restricted, needs --provider)")
    sp.add_argument("plate")
    sp.add_argument("state")
    sp.add_argument("--provider", required=True)
    sp.add_argument("--purpose", help="DPPA permissible purpose (required by real providers)")
    sp.set_defaults(func=cmd_plate)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HTTPError as exc:
        print(f"Network/API error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
