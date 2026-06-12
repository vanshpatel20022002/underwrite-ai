from app.schemas.case import Recommendation, UnderwritingCaseCreate, UnderwritingReport


def test_case_create_schema():
    case = UnderwritingCaseCreate(
        address="123 Main St",
        bedrooms=3,
        bathrooms=2.0,
        square_footage=1800,
    )
    assert case.property_type == "single_family"


def test_report_guardrail_recommendation():
    report = UnderwritingReport(recommendation=Recommendation.REVIEW)
    assert report.recommendation == Recommendation.REVIEW
