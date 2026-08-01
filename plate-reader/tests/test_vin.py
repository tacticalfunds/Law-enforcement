"""Tests for VIN decoding.

Check-digit validation and field selection run fully offline. The decode tests
monkeypatch the HTTP helpers so no network (or the NHTSA host) is required.
"""

import json

import pytest

from plate_reader import vin as vinmod
from plate_reader.vin import (
    decode_vin, decode_vins, is_valid_vin, vin_model_year,
)
from plate_reader.vin_cli import run as vin_run


# -- offline validation -----------------------------------------------------

def test_valid_vin_check_digit():
    # Canonical valid examples (correct check digit at position 9).
    assert is_valid_vin("11111111111111111")   # all ones -> check digit 1
    assert is_valid_vin("1M8GDM9AXKP042788")   # NHTSA/Wikipedia example, 'X'


def test_invalid_vin_check_digit_and_shape():
    assert not is_valid_vin("1M8GDM9A0KP042788")  # wrong check digit
    assert not is_valid_vin("SHORTVIN")           # too short
    assert not is_valid_vin("1M8GDM9AXKP04278I")  # illegal letter I


def test_vin_model_year_hint():
    # Position 10 = 'K' -> 1989 in the 1980+ cycle.
    assert vin_model_year("1M8GDM9AXKP042788") == 1989
    assert vin_model_year("short") is None


# -- decode with mocked HTTP ------------------------------------------------

def test_decode_vin_selects_core_fields(monkeypatch):
    fake = {"Results": [{
        "VIN": "1HGCM82633A004352", "Make": "HONDA", "Model": "Accord",
        "ModelYear": "2003", "BodyClass": "Sedan/Saloon",
        "DisplacementL": "2.4", "PlantCity": "MARYSVILLE",
        "SomeOtherField": "ignored-when-not-full", "ErrorCode": "0",
    }]}
    monkeypatch.setattr(vinmod, "_get_json", lambda url, *, timeout: fake)

    out = decode_vin("1hgcm82633a004352")
    assert out["Make"] == "HONDA"
    assert out["Model"] == "Accord"
    assert out["ModelYear"] == "2003"
    assert "SomeOtherField" not in out           # core subset only
    assert out["Trim"] is None                   # missing -> None


def test_decode_vin_full_keeps_all(monkeypatch):
    fake = {"Results": [{"VIN": "X", "Make": "A", "Extra": "keep"}]}
    monkeypatch.setattr(vinmod, "_get_json", lambda url, *, timeout: fake)
    out = decode_vin("X", full=True)
    assert out["Extra"] == "keep"


def test_decode_vins_batches(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, data, *, timeout):
        calls["n"] += 1
        body = data.decode()
        assert "data=" in body
        return {"Results": [{"VIN": "A", "Make": "X"},
                            {"VIN": "B", "Make": "Y"}]}

    monkeypatch.setattr(vinmod, "_post_json", fake_post)
    rows = decode_vins(["a", "b"], chunk=50)
    assert calls["n"] == 1
    assert [r["Make"] for r in rows] == ["X", "Y"]


# -- CLI --------------------------------------------------------------------

def test_cli_validate_only_no_network(tmp_path, capsys):
    out = tmp_path / "v.json"
    rc = vin_run(["1M8GDM9AXKP042788", "BADVIN",
                  "--validate-only", "--format", "json",
                  "-o", str(out), "--quiet"])
    assert rc == 0
    rows = json.loads(out.read_text())
    by_vin = {r["VIN"]: r for r in rows}
    assert by_vin["1M8GDM9AXKP042788"]["valid"] is True
    assert by_vin["BADVIN"]["valid"] is False


def test_cli_decode_csv_with_mock(tmp_path, monkeypatch):
    monkeypatch.setattr(
        vinmod, "_post_json",
        lambda url, data, *, timeout: {"Results": [
            {"VIN": "1HGCM82633A004352", "Make": "HONDA", "Model": "Accord",
             "ModelYear": "2003"}]},
    )
    out = tmp_path / "cars.csv"
    rc = vin_run(["1HGCM82633A004352", "--format", "csv",
                  "-o", str(out), "--quiet"])
    assert rc == 0
    text = out.read_text()
    assert "Make" in text.splitlines()[0]     # header
    assert "HONDA" in text


def test_cli_requires_a_vin(capsys):
    rc = vin_run([])
    assert rc == 2
