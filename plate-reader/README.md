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

### Python API

```python
from plate_reader import PlateReader

reader = PlateReader(detector="contour", ocr="tesseract")
for r in reader.read("car.jpg"):
    print(r.text, f"{r.confidence:.0%}", r.bbox.as_xyxy())

# Or JSON-ready dicts:
reader.read_to_dict("car.jpg")
```

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
