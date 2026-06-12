"""Seed PostGIS and train LightGBM from Calgary open-data property assessments.

Data source: Calgary Open Data — Current Year Property Assessments
  https://data.calgary.ca/Government/Current-Year-Property-Assessments-Parcel-/4bsw-nn7w

IMPORTANT: The 'sale_price' column in property_sales stores the Calgary ASSESSED
VALUE, not an actual transaction sale price. Calgary open data does not include
individual real-estate transactions. This proxy is used only for demo valuation
modelling and must be disclosed in any generated underwriting report.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db.init_db import init_db
from app.db.session import async_session_factory
from app.ingestion.canadian_market import load_calgary_assessments
from app.ingestion.market_loader import ensure_alberta_market_files
from app.ml.train import train_price_model

settings = get_settings()
DATA_DIR = Path(settings.data_dir)
DATA_DIR.mkdir(parents=True, exist_ok=True)


async def seed_postgres(df: pd.DataFrame) -> None:
    await init_db()
    async with async_session_factory() as session:
        await session.execute(text("TRUNCATE property_sales RESTART IDENTITY CASCADE"))
        await session.commit()

        insert_sql = text("""
            INSERT INTO property_sales
            (address, sale_price, sale_date, bedrooms, bathrooms, square_footage,
             lot_size, year_built, property_type, latitude, longitude, geom, listing_text)
            VALUES
            (:address, :sale_price, :sale_date, :bedrooms, :bathrooms,
             :square_footage, :lot_size, :year_built, :property_type, :latitude, :longitude,
             ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326), :listing_text)
        """)

        batch_size = 500
        records = df.to_dict(orient="records")
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            for row in batch:
                await session.execute(
                    insert_sql,
                    {
                        "address": row["address"],
                        "sale_price": float(row["sale_price"]),
                        "sale_date": date.fromisoformat(str(row["sale_date"])[:10]),
                        "bedrooms": int(row["bedrooms"]),
                        "bathrooms": float(row["bathrooms"]),
                        "square_footage": int(row["square_footage"]),
                        "lot_size": row.get("lot_size"),
                        "year_built": row.get("year_built"),
                        "property_type": row["property_type"],
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "listing_text": row["listing_text"],
                    },
                )
            await session.commit()
            print(f"Inserted {min(start + batch_size, len(records))}/{len(records)} rows")


def main():
    calgary_path = DATA_DIR / "calgary.csv"
    if not calgary_path.exists():
        raise FileNotFoundError(
            f"Missing {calgary_path}. Download Calgary assessments from data.calgary.ca"
        )

    print("Building Alberta market summary from CMHC + StatCan...")
    market_path = ensure_alberta_market_files(DATA_DIR)
    print(f"Market file ready: {market_path}")

    print("\n[1/4] Loading Calgary residential assessments (all rows, no limit)...")
    df = load_calgary_assessments(calgary_path, limit=None, residential_only=True)
    print(f"  => {len(df):,} clean records ready for seeding and training.")

    # Drop metadata-only columns before writing the training CSV and inserting into DB.
    training_df = df.drop(columns=["value_type", "data_source"], errors="ignore")

    csv_path = DATA_DIR / "property_sales.csv"
    training_df.to_csv(csv_path, index=False)
    print(f"\n[2/4] Saved training CSV: {csv_path}  ({len(training_df):,} rows)")

    model_dir = Path(__file__).parent.parent / "models"
    print(f"\n[3/4] Training LightGBM model...")
    metrics = train_price_model(str(csv_path))
    print(f"  MAE:  ${metrics['mae']:,.0f}")
    print(f"  RMSE: ${metrics['rmse']:,.0f}")
    print(f"  MAPE: {metrics['mape']:.2f}%")
    print(f"  Train size: {metrics['train_size']:,} rows")
    print(f"  Model saved: {model_dir / 'price_model.txt'}")
    print(f"  Residuals:   {model_dir / 'residual_stats.json'}")
    print(f"  Metrics:     {model_dir / 'metrics.json'}")

    print(f"\n[4/4] Seeding PostGIS ({len(training_df):,} rows)...")
    asyncio.run(seed_postgres(training_df))
    print("Done! Use Calgary, AB addresses for demo cases.")


if __name__ == "__main__":
    main()
