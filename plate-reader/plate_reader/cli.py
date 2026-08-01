"""Command-line interface for plate_reader.

Examples
--------
    # Read a single image, print JSON, save an annotated copy
    python -m plate_reader car.jpg --annotate out.jpg

    # Process a whole folder, stream results to CSV using all CPU cores
    python -m plate_reader ./images --format csv --output results.csv

    # A very large run: quiet (progress bar only), resumable
    python -m plate_reader ./millions --format jsonl -o out.jsonl --quiet --resume

    # Use YOLO for detection and EasyOCR for reading
    python -m plate_reader car.jpg --detector yolo \
        --detector-model plate_yolo.pt --ocr easyocr
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from .batch import collect_images, process
from .draw import annotate as draw_annotate
from .export import build_writer, processed_images
from .pipeline import PlateReader


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plate_reader",
        description="Detect and read license plates in images (single file or "
                    "bulk folders).",
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

    out = p.add_argument_group("output / export")
    out.add_argument("--output", "-o", metavar="PATH", default=None,
                     help="Write results to this file (format from --format)")
    out.add_argument("--format", default="json",
                     choices=["json", "jsonl", "csv"],
                     help="Export format for --output (default: json). jsonl and "
                          "csv stream to disk and support --resume")
    out.add_argument("--json", metavar="PATH", default=None,
                     help="Deprecated alias for --output PATH --format json")

    perf = p.add_argument_group("scaling (folder input)")
    perf.add_argument("--workers", "-j", type=int, default=0,
                      help="Worker processes for folder input (0 = all CPUs)")
    perf.add_argument("--no-recursive", action="store_true",
                      help="Do not descend into subdirectories")
    perf.add_argument("--resume", action="store_true",
                      help="Skip images already present in --output "
                           "(jsonl/csv only)")

    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-image stdout; show a progress bar instead")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input not found: {in_path}", file=sys.stderr)
        return 2

    cfg = dict(
        detector=args.detector,
        ocr=args.ocr,
        detector_model=args.detector_model,
        min_confidence=args.min_confidence,
        fix_confusions=args.fix_confusions,
    )
    # Build one reader up front to surface backend errors (missing ultralytics,
    # bad model path, ...) before we spawn a worker pool. Reused for single files.
    try:
        probe = PlateReader(**cfg)
    except (ImportError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    images = collect_images(in_path, recursive=not args.no_recursive)
    if not images:
        print(f"error: no images found in {in_path}", file=sys.stderr)
        return 2

    # Resolve export target: --output/--format, or the legacy --json alias.
    fmt = args.format
    output = args.output
    if output is None and args.json:
        output, fmt = args.json, "json"

    # Resume: drop images already recorded in the output file.
    if output and args.resume:
        if fmt == "json":
            print("warn: --resume is not supported with --format json; ignoring",
                  file=sys.stderr)
        else:
            already = processed_images(output, fmt)
            if already:
                before = len(images)
                images = [p for p in images if str(p) not in already]
                if not args.quiet:
                    print(f"resuming: skipping {before - len(images)} "
                          f"already-processed images", file=sys.stderr)
    if not images:
        if not args.quiet:
            print("nothing to do (all images already processed)", file=sys.stderr)
        return 0

    writer = build_writer(fmt, output) if output else None

    def on_result(path: str, plates: list[dict], error: str | None) -> None:
        if writer is not None:
            writer.write(path, plates, error)
        if not args.quiet:
            if error:
                print(f"{path}: [{error}]")
            else:
                summary = ", ".join(
                    f"{pl['text']} ({pl['confidence']:.0%})" for pl in plates
                )
                print(f"{path}: {summary or '(no plates found)'}")

    try:
        if in_path.is_dir():
            annotate_dir = None
            if args.annotate:
                annotate_dir = Path(args.annotate)
                annotate_dir.mkdir(parents=True, exist_ok=True)
            stats = process(
                images, cfg, on_result,
                workers=args.workers,
                annotate_dir=str(annotate_dir) if annotate_dir else None,
                progress=args.quiet,   # progress bar stands in for per-image lines
                log=sys.stderr,
            )
        else:
            # Single file: keep the simple, exact-path annotate behaviour.
            src = images[0]
            img = cv2.imread(str(src))
            if img is None:
                on_result(str(src), [], "unreadable")
                stats = {"images": 1, "plates": 0}
            else:
                results = probe.read(img)
                on_result(str(src), [r.to_dict() for r in results], None)
                if args.annotate:
                    cv2.imwrite(args.annotate, draw_annotate(img, results))
                stats = {"images": 1, "plates": len(results)}
    finally:
        if writer is not None:
            writer.close()

    if output:
        print(f"wrote {output}  "
              f"({stats['images']} images, {stats['plates']} plates)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
