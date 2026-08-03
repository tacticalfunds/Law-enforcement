# plate-records

A command-line tool for looking up vehicle records, built to mirror **how the
legitimate parts of commercial plate-lookup sites actually work** — the
"VIN & title databases" and "public records" layers — while keeping the
legally-restricted parts behind an explicit, authorized plug-in.

## What it does (and what it deliberately doesn't)

| Layer | Source | Status here |
|-------|--------|-------------|
| VIN decode (make/model/specs) | NHTSA vPIC API | ✅ Built-in, public, no key |
| Recalls | NHTSA recalls API | ✅ Built-in, public, no key |
| Title / brand / odometer history | NMVTIS (approved provider) | 🔌 Plug-in slot only |
| Registration / owner (plate → person) | State DMV / DPPA-gated provider | 🔌 Plug-in slot only, purpose-gated |

The public layers are fully implemented and work today. The restricted layers
are intentionally **not** shipped with a real backend — see *Legal boundary*.

## Install

No third-party dependencies. Requires Python 3.10+.

```bash
git clone <this repo>
cd law-enforcement
python3 -m plate_records --help
```

## Usage

Decode a VIN (public):

```bash
python3 -m plate_records vin 1HGCM82633A004352
```

Full public report (VIN decode + recalls):

```bash
python3 -m plate_records --json report 1HGCM82633A004352
```

Recalls by make/model/year (public):

```bash
python3 -m plate_records recalls Honda Accord 2003
```

Title history / plate lookup (restricted — require `--provider`):

```bash
# Only the demo 'mock' provider ships in this repo:
python3 -m plate_records title 1HGCM82633A004352 --provider mock
python3 -m plate_records plate ABC123 CA --provider mock --purpose "insurance claim investigation"
```

The `plate` command **refuses** to run without a `--purpose`, mirroring how a
DPPA-compliant provider must gate every owner lookup.

## Web search & page review

A general research utility: search the web via a real search API, and fetch a
page to extract its readable text for review.

```bash
# Web search (only the demo 'mock' provider ships; add your own API key):
python3 -m plate_records search "1967 mustang restoration" --provider mock --count 5

# Fetch a URL and extract its readable text:
python3 -m plate_records review https://example.com --limit 3000
```

`search` is a scriptable wrapper over a search API (Brave / Bing / Google
Programmable Search / SerpAPI). Register a real provider in
`plate_records/search.py` (`SEARCH_PROVIDERS`) with your own key. `review` uses
only the standard library to pull a page's title and text.

This is a general query-in / public-results-out tool. It intentionally does
**not** aggregate or profile personal information about individuals, scrape
people-search / data-broker sites, or link a plate or vehicle to a person's
identity.

## Legal boundary (read this)

Consumer "look up any plate" sites do **not** have a magic pipe into the DMV.
Plate-to-owner data in the U.S. is protected by the **Driver's Privacy
Protection Act (18 U.S.C. § 2721 et seq.)**. Owner/registration records may
only be obtained:

1. for an enumerated *permissible purpose* (law enforcement, insurance,
   licensed investigation, etc.), and
2. from a source you are actually authorized to query.

Likewise, **NMVTIS** title data is only available through an approved data
provider account.

This tool therefore ships only the freely-public layers. To enable title or
owner lookups, implement a `RecordsProvider`
(`plate_records/providers/base.py`) backed by an account you are legally
authorized to use, register it in `plate_records/providers/__init__.py`, and
select it with `--provider`. **No scraping of terms-of-service-protected sites
and no harvesting of personal data is included, by design.**

## Adding an image (OCR) front end

To go from a *photo* of a plate to a lookup, run the image through a plate
detector/OCR (e.g. OpenALPR or a cloud vision API) to get the plate string,
then feed that into the `plate`/provider path above. That step is left out of
this repo because it depends on which OCR engine you license.

## Layout

```
plate_records/
  cli.py            # argparse CLI
  http.py           # stdlib HTTP helper (honors HTTPS_PROXY)
  vin.py            # NHTSA vPIC VIN decode (public)
  recalls.py        # NHTSA recalls (public)
  providers/
    base.py         # RecordsProvider interface (the restricted-data boundary)
    mock.py         # demo provider — fake data, purpose-gated
    __init__.py     # provider registry
```
