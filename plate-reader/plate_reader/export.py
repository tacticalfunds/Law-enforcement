"""Streaming exporters for batch plate-reading results.

Writers accept one image's results at a time and flush them to disk as they
arrive, so a run over hundreds of thousands of images never holds more than a
single image's worth of results in memory. Three portable formats are
supported:

* ``jsonl`` — one JSON object per line: ``{"image", "count", "plates", ...}``.
              Ideal for very large runs and for streaming into other tools.
* ``csv``   — one row per detected plate (flat columns), easy to open in a
              spreadsheet or load into a database.
* ``json``  — a single ``{image: [plates]}`` object (the original format),
              written incrementally. Convenient but not resumable.

Each reading is a dict as produced by :meth:`PlateResult.to_dict`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

# Flat column layout for the CSV export (one row per plate).
CSV_FIELDS = [
    "image", "text", "confidence", "ocr_confidence", "detect_score",
    "detector", "ocr_engine", "x", "y", "w", "h", "error",
]


class ResultWriter:
    """Base class: a sink that records one image's plates at a time."""

    def write(self, image: str, plates: list[dict], error: Optional[str] = None) -> None:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - trivial
        pass

    def __enter__(self) -> "ResultWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class JSONLWriter(ResultWriter):
    """One JSON object per line. Appends, so it is resume-friendly."""

    def __init__(self, path: str | Path):
        self._f = open(path, "a", encoding="utf-8")

    def write(self, image: str, plates: list[dict], error: Optional[str] = None) -> None:
        rec: dict = {"image": image, "count": len(plates), "plates": plates}
        if error:
            rec["error"] = error
        self._f.write(json.dumps(rec) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


class CSVWriter(ResultWriter):
    """One row per detected plate; images with no plates get a single row."""

    def __init__(self, path: str | Path):
        p = Path(path)
        had_content = p.exists() and p.stat().st_size > 0
        self._f = open(path, "a", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=CSV_FIELDS, restval="")
        if not had_content:  # only write the header for a fresh file
            self._w.writeheader()

    def write(self, image: str, plates: list[dict], error: Optional[str] = None) -> None:
        if not plates:
            self._w.writerow({"image": image, "error": error or ""})
        else:
            for pl in plates:
                b = pl["bbox"]
                self._w.writerow({
                    "image": image,
                    "text": pl["text"],
                    "confidence": pl["confidence"],
                    "ocr_confidence": pl["ocr_confidence"],
                    "detect_score": pl["detect_score"],
                    "detector": pl["detector"],
                    "ocr_engine": pl["ocr_engine"],
                    "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"],
                    "error": error or "",
                })
        self._f.flush()

    def close(self) -> None:
        self._f.close()


class JSONWriter(ResultWriter):
    """A single ``{image: [plates]}`` object, written incrementally.

    Not resumable (the file is truncated on open); use ``jsonl`` or ``csv``
    for resumable large runs.
    """

    def __init__(self, path: str | Path):
        self._f = open(path, "w", encoding="utf-8")
        self._f.write("{\n")
        self._first = True

    def write(self, image: str, plates: list[dict], error: Optional[str] = None) -> None:
        prefix = "" if self._first else ",\n"
        self._first = False
        self._f.write(f"{prefix}  {json.dumps(image)}: {json.dumps(plates)}")

    def close(self) -> None:
        self._f.write("\n}\n")
        self._f.close()


_WRITERS = {"jsonl": JSONLWriter, "csv": CSVWriter, "json": JSONWriter}


def build_writer(fmt: str, path: str | Path) -> ResultWriter:
    """Factory: ``fmt`` is one of ``json`` | ``jsonl`` | ``csv``."""
    try:
        return _WRITERS[fmt.lower()](path)
    except KeyError:
        raise ValueError(
            f"Unknown export format: {fmt!r} (choose json, jsonl or csv)"
        ) from None


def processed_images(path: str | Path, fmt: str) -> set[str]:
    """Return image paths already recorded in ``path`` (for ``--resume``).

    Supported for ``jsonl`` and ``csv``. ``json`` is not resumable and always
    returns an empty set.
    """
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return set()

    fmt = fmt.lower()
    done: set[str] = set()
    if fmt == "jsonl":
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["image"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
    elif fmt == "csv":
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                img = row.get("image")
                if img:
                    done.add(img)
    return done
