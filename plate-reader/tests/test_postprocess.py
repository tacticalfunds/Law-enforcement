"""Unit tests for text normalization and geometry — no OCR engine required."""

from plate_reader.ocr import normalize_plate_text
from plate_reader.types import BBox, PlateResult


def test_normalize_uppercases_and_strips():
    assert normalize_plate_text("abc 123") == "ABC123"
    assert normalize_plate_text("  a-b.c/1 ") == "ABC1"
    assert normalize_plate_text("plate: XY-Z 99") == "PLATEXYZ99"


def test_normalize_confusions_optional():
    assert normalize_plate_text("O0I1", fix_confusions=False) == "O0I1"
    assert normalize_plate_text("OIZQ", fix_confusions=True) == "0120"


def test_bbox_geometry():
    b = BBox(10, 20, 100, 40)
    assert b.x2 == 110
    assert b.y2 == 60
    assert b.area == 4000
    assert b.aspect_ratio == 2.5
    assert b.as_xyxy() == (10, 20, 110, 60)


def test_plate_result_confidence_is_mean_of_signals():
    r = PlateResult(bbox=BBox(0, 0, 10, 5), text="ABC123",
                    ocr_confidence=0.8, detect_score=0.6)
    assert abs(r.confidence - 0.7) < 1e-9


def test_plate_result_confidence_ignores_zero_signals():
    r = PlateResult(bbox=BBox(0, 0, 10, 5), text="ABC123",
                    ocr_confidence=0.9, detect_score=0.0)
    assert abs(r.confidence - 0.9) < 1e-9
