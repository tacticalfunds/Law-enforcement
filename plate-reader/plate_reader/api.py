"""Optional HTTP service exposing the plate reader as a JSON API.

Run with:
    pip install "fastapi[standard]"
    uvicorn plate_reader.api:app --host 0.0.0.0 --port 8000

Then POST an image:
    curl -F "file=@car.jpg" http://localhost:8000/read

The service is intentionally minimal: one stateless endpoint that takes an
image and returns plate readings. It does not store images or results.
"""

from __future__ import annotations

import io
import os

import cv2
import numpy as np

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The HTTP API needs FastAPI. Install with:\n"
        '  pip install "fastapi[standard]"'
    ) from exc

from .pipeline import PlateReader

# Backends are configurable via environment variables so the same image can
# run with contour+tesseract locally and yolo+easyocr in production.
_DETECTOR = os.getenv("PLATE_DETECTOR", "contour")
_OCR = os.getenv("PLATE_OCR", "tesseract")
_DETECTOR_MODEL = os.getenv("PLATE_DETECTOR_MODEL") or None
_MIN_CONF = float(os.getenv("PLATE_MIN_CONFIDENCE", "0.10"))

app = FastAPI(title="plate_reader", version="0.1.0")
_reader: PlateReader | None = None


def _get_reader() -> PlateReader:
    global _reader
    if _reader is None:
        _reader = PlateReader(
            detector=_DETECTOR, ocr=_OCR,
            detector_model=_DETECTOR_MODEL, min_confidence=_MIN_CONF,
        )
    return _reader


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "detector": _DETECTOR, "ocr": _OCR}


@app.post("/read")
async def read_plate(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")
    buf = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    results = _get_reader().read(img)
    return {
        "filename": file.filename,
        "count": len(results),
        "plates": [r.to_dict() for r in results],
    }
