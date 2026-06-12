from pathlib import Path

import duckdb
import pandas as pd

from app.ingestion.canadian_market import (
    build_alberta_market_summary,
    parse_cmhc_rental_export,
    parse_statcan_residential_sales,
)


def _detect_and_normalize(path: Path) -> pd.DataFrame:
    name = path.name.lower()

    if name in {"tableexport.csv", "cmhc-alberta-rental-market.csv"}:
        return parse_cmhc_rental_export(path)

    if "46100057" in name or "statcan" in name:
        return parse_statcan_residential_sales(path, geo_filter=None)

    if name == "sample_market.csv":
        summary_path = path.parent / "alberta_market_summary.csv"
        if summary_path.exists():
            return pd.read_csv(summary_path)

    # CMHC export heuristic: title line mentions Rental Market
    try:
        head = path.read_text(encoding="utf-8-sig", errors="replace")[:500]
        if "Rental Market Statistics" in head or "CMHC Rental Market" in head:
            return parse_cmhc_rental_export(path)
    except OSError:
        pass

    return pd.read_csv(path)


def load_market_file(path: str) -> dict:
    p = Path(path)
    df = _detect_and_normalize(p)

    conn = duckdb.connect(":memory:")
    conn.register("market_df", df)
    conn.execute("CREATE TABLE market AS SELECT * FROM market_df")

    count = conn.execute("SELECT COUNT(*) FROM market").fetchone()[0]
    columns = [row[0] for row in conn.execute("DESCRIBE market").fetchall()]
    sample = conn.execute("SELECT * FROM market LIMIT 5").fetchdf()

    stats: dict = {"row_count": count, "columns": columns, "geo": "Canada"}

    for price_col in ("median_price", "median_sale_price_cad", "value_cad", "median_rent_cad"):
        if price_col in columns:
            val = conn.execute(
                f"SELECT AVG(CAST({price_col} AS DOUBLE)) FROM market WHERE {price_col} IS NOT NULL"
            ).fetchone()[0]
            if val:
                stats[f"avg_{price_col}"] = float(val)

    if "vacancy_rate_pct" in columns:
        vac = conn.execute(
            "SELECT AVG(vacancy_rate_pct) FROM market WHERE vacancy_rate_pct IS NOT NULL"
        ).fetchone()[0]
        if vac is not None:
            stats["avg_vacancy_rate_pct"] = float(vac)

    conn.close()
    return {"stats": stats, "sample": sample.to_dict(orient="records")}


def ensure_alberta_market_files(data_dir: str | Path) -> Path:
    """Build alberta_market_summary.csv and sample_market.csv from Canadian sources."""
    data_dir = Path(data_dir)
    summary = build_alberta_market_summary(data_dir)
    if summary.empty:
        return data_dir / "sample_market.csv"

    summary_path = data_dir / "alberta_market_summary.csv"
    sample_path = data_dir / "sample_market.csv"
    summary.to_csv(summary_path, index=False)
    summary.to_csv(sample_path, index=False)
    return sample_path
