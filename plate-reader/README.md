# plate-reader

Detect, read, and locate **license plates in images** — a small, self-contained
ALPR/ANPR toolkit (Automatic License Plate Recognition).

Given an image it returns, for each plate it finds:

- **location** — the plate's bounding box within the image (pixel coordinates),
- **text** — the plate characters via OCR,
- **confidence** — combined detection + OCR confidence (0–1).

Detection and OCR are **pluggable backends**, so it runs out of the box with no
model downloads (classical OpenCV detector + Tesseract OCR) and upgrades to
deep-learning backends (YOLO + EasyOCR) when you want more accuracy on
real-world photos.

> This project is standalone — it has no dependency on anything else in this
> repository.

---

## Install

```bash
cd plate-reader
pip install -r requirements.txt

# Tesseract is a system package (not pip):
#   Ubuntu/Debian:  sudo apt-get install tesseract-ocr
#   macOS:          brew install tesseract
#   Windows:        https://github.com/UB-Mannheim/tesseract/wiki
```

Optional, higher-accuracy backends:

```bash
pip install ultralytics        # YOLO detector (needs a .pt weights file)
pip install easyocr            # deep-learning OCR
pip install "fastapi[standard]"  # HTTP API service
```

## Quick start

Generate a synthetic test image and run the reader:

```bash
python examples/make_sample.py --text "ABC1234"
python -m plate_reader examples/sample_plate.jpg --annotate out.jpg --json out.json
# examples/sample_plate.jpg: ABC1234 (82%)
```

### Command line

```bash
# Single image
python -m plate_reader car.jpg

# A whole folder, annotated copies + JSON results
python -m plate_reader ./images --annotate ./annotated --json results.json

# Higher-accuracy backends
python -m plate_reader car.jpg \
    --detector yolo --detector-model plate_yolo.pt \
    --ocr easyocr --fix-confusions
```

Useful flags: `--min-confidence`, `--fix-confusions` (normalize O→0, I→1, …),
`--quiet`.

### Bulk processing & export

Point it at a directory to process large image sets in parallel and stream the
results straight to disk in a portable format — CSV, JSON Lines, or JSON. The
run is **memory-bounded**: results are flushed per image, so a folder of ten
images and a folder of ten million use the same (small) amount of RAM.

```bash
# All CPU cores, stream to CSV (one row per detected plate)
python -m plate_reader ./images --format csv --output plates.csv

# JSON Lines with 8 workers; --quiet shows a live progress bar instead of
# one line per image (ideal for very large runs)
python -m plate_reader ./images --format jsonl -o plates.jsonl -j 8 --quiet

# Interrupted a huge run? Re-run with --resume to skip what's already done
python -m plate_reader ./images --format jsonl -o plates.jsonl --resume
```

Scaling flags:

| Flag | Meaning |
|---|---|
| `--format {json,jsonl,csv}` | Export format for `--output` (default `json`). `jsonl`/`csv` stream and support resume. |
| `--output, -o PATH` | Where to write results. |
| `--workers, -j N` | Worker processes (`0` = all CPUs). |
| `--resume` | Skip images already present in `--output` (`jsonl`/`csv`). |
| `--no-recursive` | Don't descend into subdirectories. |

CSV columns: `image, text, confidence, ocr_confidence, detect_score, detector,
ocr_engine, x, y, w, h, error`. `--json PATH` remains as an alias for
`--output PATH --format json`.

### Python API

```python
from plate_reader import PlateReader, process, collect_images, build_writer

# Single image
reader = PlateReader(detector="contour", ocr="tesseract")
for r in reader.read("car.jpg"):
    print(r.text, f"{r.confidence:.0%}", r.bbox.as_xyxy())

reader.read_to_dict("car.jpg")          # JSON-ready dicts

# Bulk: parallel, streaming export over a folder you control
images = collect_images("./images")
with build_writer("csv", "plates.csv") as w:
    stats = process(images, dict(detector="contour", ocr="tesseract"),
                    on_result=w.write, workers=0)      # 0 = all CPUs
print(stats)   # {"images": ..., "plates": ..., "seconds": ...}
```

### Packaging / export as a library

The project is a standard installable package (`pyproject.toml`):

```bash
pip install .                 # or:  pip install -e .   for editable installs
python -m build               # build a wheel + sdist in dist/  (pip install build)
```

Installing it puts a `plate-reader` command on your PATH and makes
`import plate_reader` available to other projects.

### HTTP service (the "bot")

```bash
uvicorn plate_reader.api:app --host 0.0.0.0 --port 8000
curl -F "file=@car.jpg" http://localhost:8000/read
```

```json
{
  "filename": "car.jpg",
  "count": 1,
  "plates": [
    {"text": "ABC1234", "confidence": 0.82,
     "bbox": {"x": 309, "y": 285, "w": 288, "h": 44}, ...}
  ]
}
```

Backends for the service are set via env vars: `PLATE_DETECTOR`, `PLATE_OCR`,
`PLATE_DETECTOR_MODEL`, `PLATE_MIN_CONFIDENCE`. The endpoint is stateless — it
does not store uploaded images or results.

## How it works

```
image ──▶ detector ──▶ candidate boxes ──▶ crop ──▶ OCR ──▶ normalize ──▶ ranked results
          (contour|yolo)                            (tesseract|easyocr)
```

1. **Detect** — the default `contour` backend uses a morphological pipeline
   (black-hat → x-gradient → wide horizontal close) to isolate the plate's
   character band, filtered by plate-like aspect ratio and area. The `yolo`
   backend uses a trained detector for real-world robustness.
2. **Read** — each candidate crop is upscaled, binarized (Otsu, polarity-aware),
   and passed to OCR restricted to `A–Z0–9`.
3. **Filter & rank** — readings are validated by length/variety and combined
   confidence, deduplicated, and returned best-first.

### Choosing backends

| Use case | Detector | OCR |
|---|---|---|
| Quick start, no downloads, clean/frontal images | `contour` | `tesseract` |
| Real-world photos, angles, motion, glare | `yolo` (trained weights) | `easyocr` |

The `contour`+`tesseract` default is a capable baseline for clean, roughly
frontal shots. For production accuracy on street scenes, plug in a YOLO plate
model and EasyOCR — the interfaces are identical.

## Tests

```bash
pip install pytest
pytest            # OCR test auto-skips if Tesseract isn't installed
```

## Responsible use

License plate recognition is a form of personal-data processing and, in many
places, is regulated (e.g. GDPR and sector-specific rules; in the US, state
ALPR and data-retention laws). This tool is intended for **lawful, authorized
uses** — for example parking and access control, tolling, fleet management,
consented research, or authorized official use with the appropriate legal basis.

Before deploying:

- confirm you have a **lawful basis and authorization** for the images and the
  purpose;
- apply **data minimization and retention limits** — don't keep readings longer
  than needed;
- remember OCR is **imperfect**: always treat a reading as a candidate to be
  verified, never as ground truth for any consequential decision.

You are responsible for using this software in compliance with applicable law.

## License

MIT
