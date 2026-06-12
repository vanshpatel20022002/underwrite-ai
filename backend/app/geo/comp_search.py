from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.case import AdjustmentRow, ComparableSale


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def compute_adjustments(
    subject: dict, comp: ComparableSale
) -> tuple[float, list[AdjustmentRow]]:
    rows: list[AdjustmentRow] = []
    adjusted = comp.sale_price

    sqft_delta = subject["square_footage"] - comp.square_footage
    sqft_adj = sqft_delta * 100
    rows.append(
        AdjustmentRow(
            comp_id=comp.id,
            factor="square_footage",
            subject_value=str(subject["square_footage"]),
            comp_value=str(comp.square_footage),
            adjustment_amount=sqft_adj,
            notes="$100 per sqft delta",
        )
    )
    adjusted += sqft_adj

    bed_delta = subject["bedrooms"] - comp.bedrooms
    bed_adj = bed_delta * 15000
    rows.append(
        AdjustmentRow(
            comp_id=comp.id,
            factor="bedrooms",
            subject_value=str(subject["bedrooms"]),
            comp_value=str(comp.bedrooms),
            adjustment_amount=bed_adj,
            notes="$15k per bedroom delta",
        )
    )
    adjusted += bed_adj

    if subject.get("year_built") and comp.year_built:
        age_delta = comp.year_built - subject["year_built"]
        age_adj = age_delta * 2000
        rows.append(
            AdjustmentRow(
                comp_id=comp.id,
                factor="age",
                subject_value=str(subject["year_built"]),
                comp_value=str(comp.year_built),
                adjustment_amount=age_adj,
                notes="$2k per year age delta",
            )
        )
        adjusted += age_adj

    return adjusted, rows


async def search_comparables(
    session: AsyncSession,
    subject: dict,
    radius_miles: float = 5.0,
    limit: int = 20,
) -> list[ComparableSale]:
    lat = subject.get("latitude")
    lon = subject.get("longitude")
    if not lat or not lon:
        return []

    cutoff = date.today() - timedelta(days=365 * 2)
    property_type = subject.get("property_type", "single_family")

    query = text("""
        SELECT id, address, sale_price, sale_date, bedrooms, bathrooms,
               square_footage, lot_size, year_built, property_type,
               latitude, longitude,
               ST_Distance(
                   geom::geography,
                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
               ) / 1609.34 AS distance_miles
        FROM property_sales
        WHERE property_type = :property_type
          AND sale_date >= :cutoff
          AND ST_DWithin(
              geom::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :radius_meters
          )
        ORDER BY distance_miles ASC, sale_date DESC
        LIMIT :limit
    """)

    result = await session.execute(
        query,
        {
            "lat": lat,
            "lon": lon,
            "property_type": property_type,
            "cutoff": cutoff,
            "radius_meters": radius_miles * 1609.34,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    comps: list[ComparableSale] = []
    for row in rows:
        similarity = max(0.0, 1.0 - (row.distance_miles / radius_miles) * 0.5)
        sqft_ratio = min(subject["square_footage"], row.square_footage) / max(
            subject["square_footage"], row.square_footage
        )
        similarity = (similarity + sqft_ratio) / 2

        comp = ComparableSale(
            id=str(row.id),
            address=row.address,
            sale_price=float(row.sale_price),
            sale_date=row.sale_date.date() if hasattr(row.sale_date, "date") else row.sale_date,
            bedrooms=row.bedrooms,
            bathrooms=float(row.bathrooms),
            square_footage=row.square_footage,
            lot_size=row.lot_size,
            year_built=row.year_built,
            property_type=row.property_type,
            distance_miles=round(float(row.distance_miles), 2),
            similarity_score=round(similarity, 3),
            latitude=row.latitude,
            longitude=row.longitude,
        )
        adjusted, _ = compute_adjustments(subject, comp)
        comp.adjusted_price = round(adjusted, 2)
        comps.append(comp)

    comps.sort(key=lambda c: c.similarity_score, reverse=True)
    return comps[:5]
