"""Tests for batch processing and result export.

The export writers are pure data-in/data-out and always run. The batch
integration test drives the real pipeline over a few synthetic images; it does
not require Tesseract because unreadable/failed OCR simply yields an error
record — every image still produces exactly one record either way.
"""

import csv
import json

import cv2
import pytest

from plate_reader.batch import collect_images, process
from plate_reader.export import build_writer, processed_images
from examples.make_sample import make_sample


# -- sample dicts for writer tests ------------------------------------------

def _plate(text="ABC1234", conf=0.82):
    return {
        "text": text, "raw_text": text, "confidence": conf,
        "ocr_confidence": 0.9, "detect_score": 0.7,
        "detector": "contour", "ocr_engine": "tesseract",
        "bbox": {"x": 10, "y": 20, "w": 100, "h": 30},
    }


def test_jsonl_writer_one_object_per_line(tmp_path):
    out = tmp_path / "r.jsonl"
    with build_writer("jsonl", out) as w:
        w.write("a.jpg", [_plate("ABC1234")])
        w.write("b.jpg", [], error="unreadable")
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 2
    r0 = json.loads(lines[0])
    assert r0["image"] == "a.jpg" and r0["count"] == 1
    assert r0["plates"][0]["text"] == "ABC1234"
    r1 = json.loads(lines[1])
    assert r1["image"] == "b.jpg" and r1["error"] == "unreadable"


def test_csv_writer_row_per_plate(tmp_path):
    out = tmp_path / "r.csv"
    with build_writer("csv", out) as w:
        w.write("a.jpg", [_plate("ABC1234"), _plate("XYZ789")])
        w.write("b.jpg", [])  # no plates -> single row
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 3
    assert rows[0]["image"] == "a.jpg" and rows[0]["text"] == "ABC1234"
    assert rows[1]["text"] == "XYZ789"
    assert rows[2]["image"] == "b.jpg" and rows[2]["text"] == ""


def test_json_writer_is_valid_object(tmp_path):
    out = tmp_path / "r.json"
    with build_writer("json", out) as w:
        w.write("a.jpg", [_plate("ABC1234")])
        w.write("b.jpg", [])
    data = json.loads(out.read_text())
    assert set(data) == {"a.jpg", "b.jpg"}
    assert data["a.jpg"][0]["text"] == "ABC1234"
    assert data["b.jpg"] == []


def test_build_writer_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        build_writer("xml", tmp_path / "x")


def test_processed_images_reads_back(tmp_path):
    out = tmp_path / "r.jsonl"
    with build_writer("jsonl", out) as w:
        w.write("a.jpg", [_plate()])
        w.write("b.jpg", [])
    assert processed_images(out, "jsonl") == {"a.jpg", "b.jpg"}
    assert processed_images(tmp_path / "missing.jsonl", "jsonl") == set()


# -- batch pipeline ---------------------------------------------------------

def _make_images(tmp_path, n):
    paths = []
    for i in range(n):
        p = tmp_path / f"img_{i}.jpg"
        cv2.imwrite(str(p), make_sample(f"CAR{i:04d}"))
        paths.append(p)
    return paths


def test_collect_images_finds_and_filters(tmp_path):
    _make_images(tmp_path, 2)
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / "sub").mkdir()
    cv2.imwrite(str(tmp_path / "sub" / "deep.png"), make_sample("SUB1"))

    found = collect_images(tmp_path, recursive=True)
    assert len(found) == 3  # 2 jpg + 1 nested png, txt excluded
    shallow = collect_images(tmp_path, recursive=False)
    assert len(shallow) == 2  # nested png not included


def _collect_records(images, workers):
    records = {}
    cfg = dict(detector="contour", ocr="tesseract")
    stats = process(
        images, cfg,
        lambda path, plates, error: records.__setitem__(path, (plates, error)),
        workers=workers, progress=False,
    )
    return records, stats


def test_process_serial_covers_every_image(tmp_path):
    images = _make_images(tmp_path, 4)
    records, stats = _collect_records(images, workers=1)
    assert stats["images"] == 4
    assert set(records) == {str(p) for p in images}


def test_process_parallel_covers_every_image(tmp_path):
    images = _make_images(tmp_path, 5)
    records, stats = _collect_records(images, workers=2)
    assert stats["images"] == 5
    assert set(records) == {str(p) for p in images}


def test_process_records_unreadable_image(tmp_path):
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not an image")
    records, stats = _collect_records([bad], workers=1)
    plates, error = records[str(bad)]
    assert plates == [] and error == "unreadable"
