"""Command-line VIN lookup: decode vehicle details for one or many VINs.

Uses NHTSA vPIC (public, no key). Vehicle data only — no owner/personal info.

Examples
--------
    # One VIN, pretty JSON to stdout
    python -m plate_reader.vin_cli 1HGCM82633A004352

    # Many VINs from a file, streamed to CSV (batched requests)
    python -m plate_reader.vin_cli --input-file vins.txt --format csv -o cars.csv

    # Just validate check digits offline, no network
    python -m plate_reader.vin_cli 1HGCM82633A004352 --validate-only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .vin import (
    CORE_FIELDS, decode_vins, is_valid_vin, normalize_vin, vin_model_year,
)


def _read_vins(args) -> list[str]:
    vins: list[str] = list(args.vins)
    if args.input_file:
        text = Path(args.input_file).read_text()
        vins.extend(line.strip() for line in text.splitlines() if line.strip())
    # De-dupe while preserving order.
    seen, ordered = set(), []
    for v in (normalize_vin(v) for v in vins):
        if v and v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def _write(rows: list[dict], fmt: str, output) -> None:
    fmt = fmt.lower()
    if fmt == "json":
        text = json.dumps(rows, indent=2)
        _emit(text + "\n", output)
    elif fmt == "jsonl":
        _emit("".join(json.dumps(r) + "\n" for r in rows), output)
    elif fmt == "csv":
        # Union of keys keeps --full output intact; core order otherwise.
        fields = list(CORE_FIELDS)
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
        _emit(buf.getvalue(), output)
    else:  # pragma: no cover - argparse restricts choices
        raise ValueError(f"unknown format {fmt!r}")


def _emit(text: str, output) -> None:
    if output:
        Path(output).write_text(text)
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plate_reader.vin",
        description="Decode vehicle details from VIN(s) via NHTSA vPIC "
                    "(vehicle data only; no owner/personal info).",
    )
    p.add_argument("vins", nargs="*", help="One or more VINs")
    p.add_argument("--input-file", metavar="PATH",
                   help="Text file with one VIN per line")
    p.add_argument("--format", default="json",
                   choices=["json", "jsonl", "csv"], help="Output format")
    p.add_argument("--output", "-o", metavar="PATH",
                   help="Write to this file instead of stdout")
    p.add_argument("--full", action="store_true",
                   help="Return all vPIC fields, not just the core subset")
    p.add_argument("--validate-only", action="store_true",
                   help="Only check VIN format/check digit offline; no network")
    p.add_argument("--timeout", type=float, default=30.0,
                   help="Per-request network timeout in seconds")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress warnings about invalid VINs")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vins = _read_vins(args)
    if not vins:
        print("error: provide at least one VIN (arg or --input-file)",
              file=sys.stderr)
        return 2

    if not args.quiet:
        for v in vins:
            if not is_valid_vin(v):
                yr = vin_model_year(v)
                hint = f" (year hint: {yr})" if yr else ""
                print(f"warn: {v} is not a standard 17-char VIN / check digit "
                      f"failed{hint}; decoding anyway", file=sys.stderr)

    if args.validate_only:
        rows = [{"VIN": v, "valid": is_valid_vin(v),
                 "model_year_hint": vin_model_year(v)} for v in vins]
        _write(rows, args.format, args.output)
        return 0

    try:
        rows = decode_vins(vins, timeout=args.timeout, full=args.full)
    except Exception as exc:  # network / HTTP errors
        print(f"error: VIN decode request failed: {exc}", file=sys.stderr)
        return 1

    _write(rows, args.format, args.output)
    if args.output and not args.quiet:
        print(f"wrote {args.output} ({len(rows)} VINs)", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
