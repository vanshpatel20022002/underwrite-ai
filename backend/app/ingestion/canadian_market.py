"""Loaders for Canadian open-data market and property files."""

import csv
import re
from pathlib import Path

import pandas as pd

# Calgary demo center — kept only as a named constant, not used as a fallback.
CALGARY_CENTER_LAT, CALGARY_CENTER_LON = 51.0447, -114.0719

# Kept for backwards-compatibility; load_calgary_assessments now uses SUB_PROPERTY_USE_MAP.
PROPERTY_TYPE_MAP_CALGARY = {
    "LI": "single_family",
    "LO": "single_family",
    "IO": "multi_family",
}

ASSESSMENT_CLASS_MAP = {
    "RE": "single_family",
    "NR": "multi_family",
    "FL": "condo",
}

# Maps Calgary SUB_PROPERTY_USE codes to internal property_type values.
# R1xx = single/semi-detached, R2xx = apartment/condo, R3xx = row/townhouse,
# R4xx/R5xx = multi-residential. Unmapped codes default to "single_family".
_SUB_USE_MAP: dict[str, str] = {
    "R110": "single_family",   # Single Detached
    "R120": "single_family",   # Semi-Detached
    "R121": "single_family",   # Semi-Detached (corner lot)
    "R201": "condo",           # Low-Rise Apartment
    "R202": "condo",           # High-Rise Apartment
    "R301": "townhouse",       # Row House
    "R302": "townhouse",       # Townhouse
    "R401": "multi_family",    # Duplex
    "R402": "multi_family",    # Multi-Residential (3-6 units)
    "R510": "multi_family",    # Multi-Residential (7+ units)
}


def parse_assessed_value(value: str | float | int) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("$", "").strip() or 0)


def polygon_centroid(wkt: str) -> tuple[float | None, float | None]:
    if not wkt or not isinstance(wkt, str):
        return None, None
    coords = re.findall(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)", wkt)
    if not coords:
        return None, None
    lons = [float(c[0]) for c in coords]
    lats = [float(c[1]) for c in coords]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def _estimate_dwelling_features(assessed_value: float, lot_size_sf: float) -> tuple[int, float, int]:
    """Heuristic beds/baths/sqft when not in source data (assessment rolls)."""
    bedrooms = min(6, max(1, int(assessed_value / 250_000) + 1))
    bathrooms = round(bedrooms * 0.5 + 0.5, 1)
    if lot_size_sf and lot_size_sf > 0:
        sqft = int(min(5000, max(700, lot_size_sf * 0.28)))
    else:
        sqft = int(min(4500, max(900, assessed_value / 220)))
    return bedrooms, bathrooms, sqft


def load_calgary_assessments(
    path: str | Path,
    limit: int | None = None,
    residential_only: bool = True,
) -> pd.DataFrame:
    """Transform Calgary open-data assessments into the property_sales schema.

    NOTE: 'sale_price' in the output stores the Calgary ASSESSED VALUE, not an
    actual transaction sale price. Calgary open data does not publish individual
    sale transactions. This proxy is used for demo valuation modelling only and
    must be disclosed in any generated report.

    Quality filters applied:
    - ASSESSMENT_CLASS == 'RE' (residential only)
    - assessed value between $100,000 and $3,000,000
    - valid MULTIPOLYGON geometry (rows without a parseable centroid are dropped)

    The limit parameter, if set, is applied AFTER all quality filters (useful
    for fast testing; set to None for the full dataset).
    """
    df = pd.read_csv(path, low_memory=False)
    raw_total = len(df)

    # --- Step 1: residential class filter ---
    if residential_only:
        df = df[df["ASSESSMENT_CLASS"] == "RE"].copy()
    after_class = len(df)

    # --- Step 2: vectorized value parsing and outlier removal ---
    # ASSESSED_VALUE arrives as a comma-formatted string e.g. "729,000"
    df["_val"] = df["ASSESSED_VALUE"].map(parse_assessed_value)
    df = df[(df["_val"] >= 100_000) & (df["_val"] <= 3_000_000)].copy()
    after_value = len(df)

    # --- Step 3: optional row cap (applied after quality filters) ---
    if limit:
        df = df.head(limit)

    # --- Step 4: median year_built for null-filling ---
    year_series = pd.to_numeric(df["YEAR_OF_CONSTRUCTION"], errors="coerce")
    year_median = int(year_series.median()) if year_series.notna().any() else 1985

    print(
        f"  Calgary: {raw_total:,} raw -> {after_class:,} residential -> "
        f"{after_value:,} in value range -> {len(df):,} to process"
    )

    rows = []
    skipped_geo = 0
    for _, row in df.iterrows():
        assessed = float(row["_val"])

        # Centroid from MULTIPOLYGON — drop rows where geometry is missing/unparseable
        # rather than falling back to city centre (which would create fake nearby comps).
        lat, lon = polygon_centroid(str(row.get("MULTIPOLYGON", "")))
        if lat is None or lon is None:
            skipped_geo += 1
            continue

        lot_size = parse_assessed_value(row.get("LAND_SIZE_SF", 0)) or None

        raw_year = row.get("YEAR_OF_CONSTRUCTION")
        try:
            year_built = int(raw_year) if pd.notna(raw_year) and int(raw_year) > 1800 else year_median
        except (ValueError, TypeError):
            year_built = year_median

        # Use SUB_PROPERTY_USE for property type — finer-grained than PROPERTY_TYPE (LI/LO/IO)
        sub_use = str(row.get("SUB_PROPERTY_USE", "")).strip()
        prop_type = _SUB_USE_MAP.get(sub_use, "single_family")

        beds, baths, sqft = _estimate_dwelling_features(assessed, lot_size or 5_000)

        mod_date = str(row.get("MOD_DATE", "2026/01/01")).replace("/", "-")
        sale_date = mod_date if len(mod_date) >= 10 else "2026-01-01"

        address = str(row.get("ADDRESS", "")).strip()
        comm = str(row.get("COMM_NAME", "Calgary")).strip()
        lot_str = f"{int(lot_size):,} sqft" if lot_size else "N/A"

        rows.append(
            {
                "address": f"{address}, {comm}, AB, Canada",
                # sale_price stores the assessed value as a valuation proxy.
                "sale_price": assessed,
                "sale_date": sale_date,
                "bedrooms": beds,
                "bathrooms": baths,
                "square_footage": sqft,
                "lot_size": lot_size,
                "year_built": year_built,
                "property_type": prop_type,
                "latitude": lat,
                "longitude": lon,
                "listing_text": (
                    f"Calgary, Alberta property assessment. "
                    f"{prop_type.replace('_', ' ').title()} at {address}, "
                    f"neighbourhood {comm}. Built {year_built}. "
                    f"~{sqft:,} sqft, {beds} bed, {baths} bath. "
                    f"Lot size: {lot_str}. "
                    f"Assessed value (proxy, not sale price): ${assessed:,.0f} CAD."
                ),
                # Metadata: not inserted into DB but preserved in the training CSV.
                "value_type": "assessed",
                "data_source": "Calgary Open Data — Current Year Property Assessments",
            }
        )

    if skipped_geo:
        print(f"  Skipped {skipped_geo} rows with unparseable polygon geometry.")

    return pd.DataFrame(rows)


def parse_cmhc_rental_export(path: str | Path) -> pd.DataFrame:
    """Parse CMHC HMIP TableExport.csv (rental market summary)."""
    raw_lines = Path(path).read_text(encoding="cp1252", errors="replace").splitlines()

    records = []
    for line in raw_lines:
        if not line.strip() or line.startswith("Notes") or line.startswith("Source,"):
            continue
        if line.startswith("Alberta") or "Vacancy Rate" in line:
            continue
        if "October" not in line:
            continue

        parts = next(csv.reader([line]))
        if len(parts) < 8:
            continue
        period = parts[0].strip()
        try:
            year = int(period.split()[0])
        except (ValueError, IndexError):
            continue

        def _num(idx: int) -> float | None:
            if idx >= len(parts):
                return None
            val = parts[idx].replace(",", "").strip()
            if not val or val in {"a", "b", "c", "d", "**", "++"}:
                return None
            try:
                return float(val)
            except ValueError:
                return None

        records.append(
            {
                "year": year,
                "month": "October",
                "geo": "Alberta",
                "source": "CMHC Rental Market Survey",
                "vacancy_rate_pct": _num(1),
                "availability_rate_pct": _num(3),
                "avg_rent_cad": _num(5),
                "median_rent_cad": _num(7),
                "rent_pct_change": _num(9),
                "rental_units": _num(11),
            }
        )

    return pd.DataFrame(records)


def parse_statcan_residential_sales(path: str | Path, geo_filter: str | None = "Alberta") -> pd.DataFrame:
    """Parse StatCan table 46-10-0057 residential sale statistics."""
    df = pd.read_csv(path, low_memory=False)
    if geo_filter:
        df = df[df["GEO"].str.contains(geo_filter, case=False, na=False)]

    estimates = df["Estimates"].astype(str)
    price_rows = df[
        estimates.str.contains("Median sale price|Average sale price", case=False, na=False)
    ].copy()

    records = []
    for _, row in price_rows.iterrows():
        val = row.get("VALUE")
        try:
            price = float(val)
        except (TypeError, ValueError):
            continue
        records.append(
            {
                "ref_year": row.get("REF_DATE"),
                "geo": row.get("GEO"),
                "sale_type": row.get("Sale type"),
                "property_type": row.get("Property characteristics"),
                "metric": row.get("Estimates"),
                "value_cad": price,
                "source": "Statistics Canada 46-10-0057",
            }
        )
    return pd.DataFrame(records)


def calgary_assessed_value_median(data_dir: str | Path, sample: int = 20_000) -> float | None:
    """Median assessed value from Calgary open data (Alberta price proxy)."""
    path = Path(data_dir) / "calgary.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, usecols=["ASSESSED_VALUE", "ASSESSMENT_CLASS"], nrows=sample, low_memory=False)
    df = df[df["ASSESSMENT_CLASS"] == "RE"]
    values = df["ASSESSED_VALUE"].map(parse_assessed_value)
    values = values[values > 0]
    if values.empty:
        return None
    return float(values.median())


def build_alberta_market_summary(data_dir: str | Path) -> pd.DataFrame:
    """Combine CMHC rental + StatCan/Calgary sale proxies into one market trend table."""
    data_dir = Path(data_dir)
    frames: list[dict] = []

    cmhc_path = data_dir / "TableExport.csv"
    if cmhc_path.exists():
        rental = parse_cmhc_rental_export(cmhc_path)
        if not rental.empty:
            latest = rental.sort_values("year").tail(1).iloc[0]
            frames.append(
                {
                    "year": int(latest["year"]),
                    "geo": "Alberta",
                    "median_rent_cad": latest.get("median_rent_cad"),
                    "vacancy_rate_pct": latest.get("vacancy_rate_pct"),
                    "rental_units": latest.get("rental_units"),
                    "source": "CMHC",
                }
            )

    statcan_path = data_dir / "46100057-eng" / "46100057.csv"
    if statcan_path.exists():
        for geo in ("Alberta", "British Columbia", "Canada"):
            sales = parse_statcan_residential_sales(statcan_path, geo_filter=geo)
            if sales.empty:
                continue
            med = sales[sales["metric"].str.contains("Median sale price", na=False)]
            med = med[med["property_type"].astype(str).str.contains("Total, all property", na=False)]
            if not med.empty:
                latest_sale = med.sort_values("ref_year").tail(1).iloc[0]
                if frames:
                    frames[0]["median_sale_price_cad"] = latest_sale["value_cad"]
                    frames[0]["sale_ref_year"] = latest_sale["ref_year"]
                    frames[0]["sale_geo"] = geo
                else:
                    frames.append(
                        {
                            "year": latest_sale["ref_year"],
                            "geo": "Alberta",
                            "median_sale_price_cad": latest_sale["value_cad"],
                            "sale_geo": geo,
                            "source": "StatCan",
                        }
                    )
                break

    assessed_median = calgary_assessed_value_median(data_dir)
    if assessed_median:
        if frames:
            frames[0]["median_assessed_value_calgary_cad"] = assessed_median
            frames[0]["median_price"] = assessed_median
            frames[0]["price_note"] = "Calgary assessed value median (proxy)"
        else:
            frames.append(
                {
                    "year": 2026,
                    "geo": "Alberta",
                    "median_price": assessed_median,
                    "price_note": "Calgary assessed value median (proxy)",
                    "source": "Calgary Open Data",
                }
            )

    if not frames:
        return pd.DataFrame()

    summary = pd.DataFrame(frames)
    row = summary.iloc[0]
    median_price = row.get("median_sale_price_cad") or row.get("median_assessed_value_calgary_cad")

    # Expand to monthly rows for DuckDB market_loader compatibility
    monthly_rows = []
    for _, row in summary.iterrows():
        year = int(row.get("year", 2024))
        mp = row.get("median_price") or row.get("median_assessed_value_calgary_cad")
        for month in range(1, 13):
            monthly_rows.append(
                {
                    "month": f"{year}-{month:02d}",
                    "geo": row.get("geo", "Alberta"),
                    "median_price": mp,
                    "median_rent_cad": row.get("median_rent_cad"),
                    "vacancy_rate_pct": row.get("vacancy_rate_pct"),
                    "inventory_count": row.get("rental_units"),
                    "source": row.get("source"),
                    "price_note": row.get("price_note") or row.get("sale_geo"),
                }
            )
    return pd.DataFrame(monthly_rows)
