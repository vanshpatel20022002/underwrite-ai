from datetime import date

from app.agents.risk import evaluate_risk
from app.schemas.case import ComparableSale, ImageConditionNote


def test_risk_flags_missing_zoning():
    comps = [
        ComparableSale(
            id="1",
            address="1 Test",
            sale_price=400000,
            sale_date=date(2024, 6, 1),
            bedrooms=3,
            bathrooms=2,
            square_footage=1800,
            property_type="single_family",
            distance_miles=0.5,
            similarity_score=0.9,
            adjusted_price=410000,
        )
    ]
    score, flags = evaluate_risk(
        {"square_footage": 1800, "bedrooms": 3, "borrower_notes": ""},
        comps,
        400000,
        [],
        has_zoning=False,
    )
    assert score > 0
    assert any(f.code == "MISSING_ZONING" for f in flags)
