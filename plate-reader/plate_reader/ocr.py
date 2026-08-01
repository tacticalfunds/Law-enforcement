"""Read plate characters from a cropped plate image.

Backends:

* ``tesseract`` — uses the Tesseract engine via ``pytesseract``. Lightweight,
                  no large model download (just the ``tesseract-ocr`` system
                  package). This is the default.
* ``easyocr``   — deep-learning OCR, more robust on angled/low-quality crops.
                  Requires the ``easyocr`` package (downloads a model on first
                  run).

Both return a ``(text, confidence)`` pair where confidence is 0..1.
"""

from __future__ import annotations

import re
import string
from typing import Optional

import cv2
import numpy as np

# Characters we allow in a plate reading. Tune per jurisdiction if needed.
PLATE_ALPHABET = string.ascii_uppercase + string.digits
_ALLOWED_RE = re.compile(f"[^{PLATE_ALPHABET}]")

# Common OCR confusions, only applied when normalising toward plate format.
_CONFUSIONS = str.maketrans({"O": "0", "I": "1", "Q": "0", "Z": "2"})


def normalize_plate_text(raw: str, *, fix_confusions: bool = False) -> str:
    """Uppercase, strip anything outside the plate alphabet, collapse spaces."""
    text = raw.upper()
    text = _ALLOWED_RE.sub("", text)
    if fix_confusions:
        text = text.translate(_CONFUSIONS)
    return text


def preprocess_plate(crop: np.ndarray, target_height: int = 96) -> np.ndarray:
    """Upscale + binarize a plate crop to make characters OCR-friendly."""
    if crop.ndim == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop

    h = gray.shape[0]
    if h and h < target_height:
        scale = target_height / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)

    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    # Otsu handles both dark-on-light and light-on-dark once we check polarity.
    _, binary = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # Tesseract expects dark text on light background; flip if inverted.
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)
    return binary


class TesseractOCR:
    name = "tesseract"

    def __init__(self, psm: int = 7):
        try:
            import pytesseract  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The 'tesseract' OCR backend needs 'pytesseract' and the "
                "tesseract-ocr system package.\n"
                "  pip install pytesseract\n"
                "  apt-get install tesseract-ocr   (or: brew install tesseract)"
            ) from exc
        self._pt = pytesseract
        # psm 7 = treat the image as a single text line.
        self._config = (
            f"--psm {psm} --oem 3 "
            f"-c tessedit_char_whitelist={PLATE_ALPHABET}"
        )

    def read(self, crop: np.ndarray) -> tuple[str, float]:
        prepared = preprocess_plate(crop)
        data = self._pt.image_to_data(
            prepared, config=self._config,
            output_type=self._pt.Output.DICT,
        )
        words, confs = [], []
        for text, conf in zip(data["text"], data["conf"]):
            text = text.strip()
            if not text:
                continue
            words.append(text)
            try:
                c = float(conf)
            except (TypeError, ValueError):
                c = -1.0
            if c >= 0:
                confs.append(c)
        raw = "".join(words)
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return raw, float(confidence)


class EasyOCR:
    name = "easyocr"

    def __init__(self, languages: Optional[list[str]] = None, gpu: bool = False):
        try:
            import easyocr  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The 'easyocr' OCR backend needs the 'easyocr' package.\n"
                "  pip install easyocr"
            ) from exc
        self._reader = easyocr.Reader(languages or ["en"], gpu=gpu)

    def read(self, crop: np.ndarray) -> tuple[str, float]:
        prepared = preprocess_plate(crop)
        results = self._reader.readtext(prepared, allowlist=PLATE_ALPHABET)
        if not results:
            return "", 0.0
        # Concatenate text boxes left-to-right; average their confidences.
        results.sort(key=lambda r: r[0][0][0])  # by left x of bbox
        raw = "".join(r[1] for r in results)
        confidence = sum(float(r[2]) for r in results) / len(results)
        return raw, float(confidence)


def build_ocr(backend: str = "tesseract", **kwargs):
    """Factory for OCR engines. ``backend`` is 'tesseract' (default) or 'easyocr'."""
    backend = backend.lower()
    if backend == "tesseract":
        return TesseractOCR(**kwargs)
    if backend == "easyocr":
        return EasyOCR(**kwargs)
    raise ValueError(f"Unknown OCR backend: {backend!r}")
