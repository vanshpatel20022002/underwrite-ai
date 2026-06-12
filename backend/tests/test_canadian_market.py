from pathlib import Path

import pandas as pd

from app.ingestion.canadian_market import (
    build_alberta_market_summary,
    load_calgary_assessments,
    parse_assessed_value,
    parse_cmhc_rental_export,
    polygon_centroid,
)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def test_parse_assessed_value():
    assert parse_assessed_value("729,000") == 729000.0
    assert parse_assessed_value(500000) == 500000.0


def test_polygon_centroid():
    wkt = "MULTIPOLYGON (((-114.0039681 50.9218733, -114.0041999 50.9221048)))"
    lat, lon = polygon_centroid(wkt)
    assert lat is not None and lon is not None
    assert 50.9 < lat < 51.0
    assert -114.1 < lon < -114.0


def test_load_calgary_assessments():
    path = DATA_DIR / "calgary.csv"
    if not path.exists():
        return
    df = load_calgary_assessments(path, limit=100)
    assert len(df) > 0
    assert "sale_price" in df.columns
    assert df["latitude"].notna().all()
    assert (df["sale_price"] > 0).all()


def test_parse_cmhc_rental():
    path = DATA_DIR / "TableExport.csv"
    if not path.exists():
        return
    df = parse_cmhc_rental_export(path)
    assert len(df) > 20
    assert "median_rent_cad" in df.columns
    assert df["year"].max() >= 2024


def test_build_alberta_market_summary():
    if not (DATA_DIR / "calgary.csv").exists():
        return
    summary = build_alberta_market_summary(DATA_DIR)
    assert not summary.empty
    assert "median_price" in summary.columns or "median_rent_cad" in summary.columns
