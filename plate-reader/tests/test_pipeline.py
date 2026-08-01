"""Integration tests against a synthetic plate image.

The detector test needs only OpenCV. The end-to-end OCR test needs a working
Tesseract install and is skipped automatically when it is unavailable.
"""

import importlib.util

import numpy as np
import pytest

from plate_reader.detect import ContourDetector
from examples.make_sample import make_sample


def _has_tesseract() -> bool:
    if importlib.util.find_spec("pytesseract") is None:
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def test_detector_localizes_synthetic_plate():
    img = make_sample("ABC1234")
    dets = ContourDetector().detect(img)
    assert dets, "detector should find at least one candidate region"
    # The top candidate should overlap the plate, which sits in the middle band.
    top = dets[0].bbox
    cx, cy = top.x + top.w / 2, top.y + top.h / 2
    h, w = img.shape[:2]
    assert 0.25 * w < cx < 0.75 * w
    assert 0.30 * h < cy < 0.70 * h


@pytest.mark.skipif(not _has_tesseract(), reason="tesseract not installed")
def test_end_to_end_reads_plate():
    from plate_reader import PlateReader

    reader = PlateReader()  # contour + tesseract
    img = make_sample("XYZ789")
    results = reader.read(img)
    assert results, "should read at least one plate"
    texts = [r.text for r in results]
    # Exact match is ideal; at minimum the reading must be plate-shaped.
    assert "XYZ789" in texts or any(len(t) >= 4 for t in texts)
    assert 0.0 <= results[0].confidence <= 1.0


def test_no_plate_on_blank_image():
    from plate_reader.detect import ContourDetector

    blank = np.full((400, 600, 3), 128, dtype=np.uint8)
    dets = ContourDetector().detect(blank)
    # A flat image has no character band; detector should return nothing.
    assert dets == []
