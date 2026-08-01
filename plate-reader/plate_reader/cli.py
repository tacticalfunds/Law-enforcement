"""Command-line interface for plate_reader.

Examples
--------
    # Read a single image, print JSON, save an annotated copy
    python -m plate_reader car.jpg --annotate out.jpg

    # Process a whole folder, write results to results.json
    python -m plate_reader ./images --json results.json

    # Use YOLO for detection and EasyOCR for reading
    python -m plate_reader car.jpg --detector yolo \
        --detector-model plate_yolo.pt --ocr easyocr
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from .draw import annotate as draw_annotate
from .pipeline import PlateReader

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _collect_images(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    return [path]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plate_reader",
        description="Detect and read license plates in images.",
    )
    p.add_argument("input", help="Image file or a directory of images")
    p.add_argument("--detector", default="contour",
                   choices=["contour", "yolo"], help="Detection backend")
    p.add_argument("--detector-model", default=None,
                   help="Path to YOLO .pt weights (required for --detector yolo)")
    p.add_argument("--ocr", default="tesseract",
                   choices=["tesseract", "easyocr"], help="OCR backend")
    p.add_argument("--min-confidence", type=float, default=0.10,
                   help="Drop readings below this combined confidence (0..1)")
    p.add_argument("--fix-confusions", action="store_true",
                   help="Normalize common OCR confusions (O->0, I->1, ...)")
    p.add_argument("--annotate", metavar="PATH", default=None,
                   help="Save an annotated image (single input) or directory "
                        "(folder input)")
    p.add_argument("--json", metavar="PATH", default=None,
                   help="Write all results as JSON to this path")
    p.add_argument("--quiet", action="store_true", help="Suppress per-image stdout")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input not found: {in_path}", file=sys.stderr)
        return 2

    try:
        reader = PlateReader(
            detector=args.detector,
            ocr=args.ocr,
            detector_model=args.detector_model,
            min_confidence=args.min_confidence,
            fix_confusions=args.fix_confusions,
        )
    except (ImportError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    images = _collect_images(in_path)
    if not images:
        print(f"error: no images found in {in_path}", file=sys.stderr)
        return 2

    annotate_dir = None
    if args.annotate and in_path.is_dir():
        annotate_dir = Path(args.annotate)
        annotate_dir.mkdir(parents=True, exist_ok=True)

    all_results: dict[str, list[dict]] = {}
    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"warn: could not read {img_path}", file=sys.stderr)
            continue
        results = reader.read(img)
        all_results[str(img_path)] = [r.to_dict() for r in results]

        if not args.quiet:
            plates = ", ".join(f"{r.text} ({r.confidence:.0%})" for r in results)
            print(f"{img_path}: {plates or '(no plates found)'}")

        if args.annotate:
            annotated = draw_annotate(img, results)
            if annotate_dir is not None:
                out = annotate_dir / f"{img_path.stem}_annotated{img_path.suffix}"
            else:
                out = Path(args.annotate)
            cv2.imwrite(str(out), annotated)

    if args.json:
        Path(args.json).write_text(json.dumps(all_results, indent=2))
        if not args.quiet:
            print(f"wrote {args.json}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
