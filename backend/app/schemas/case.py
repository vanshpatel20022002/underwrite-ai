from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Recommendation(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    REJECT = "reject"


class UnderwritingCaseCreate(BaseModel):
    model_config = {"extra": "ignore"}

    address: str
    property_type: str = "single_family"
    bedrooms: int = Field(ge=0)
    bathrooms: float = Field(ge=0)
    square_footage: int = Field(ge=0)
    lot_size: float | None = None
    year_built: int | None = None
    listing_description: str = ""
    borrower_notes: str = ""
    latitude: float | None = None
    longitude: float | None = None


class ConfidenceInterval(BaseModel):
    low: float
    high: float
    level: float = 0.8


class ComparableSale(BaseModel):
    id: str
    address: str
    sale_price: float
    sale_date: date
    bedrooms: int
    bathrooms: float
    square_footage: int
    lot_size: float | None = None
    year_built: int | None = None
    property_type: str
    distance_miles: float
    similarity_score: float
    adjusted_price: float | None = None
    latitude: float | None = None
    longitude: float | None = None


class AdjustmentRow(BaseModel):
    comp_id: str
    factor: str
    subject_value: str
    comp_value: str
    adjustment_amount: float
    notes: str = ""


class ShapFeature(BaseModel):
    feature: str
    contribution: float


class RiskFlag(BaseModel):
    code: str
    severity: str
    message: str
    evidence: str = ""


class ImageConditionNote(BaseModel):
    image_path: str
    condition: str
    risk_level: str
    confidence: float


class Citation(BaseModel):
    doc_type: str
    page: int | None = None
    section: str | None = None
    snippet: str
    source_file: str = ""


class UnderwritingReport(BaseModel):
    estimated_value: float | None = None
    confidence_interval: ConfidenceInterval | None = None
    confidence_score: float | None = None
    top_5_comps: list[ComparableSale] = Field(default_factory=list)
    adjustment_table: list[AdjustmentRow] = Field(default_factory=list)
    risk_score: float | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    image_condition_notes: list[ImageConditionNote] = Field(default_factory=list)
    shap_features: list[ShapFeature] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    memo_markdown: str = ""
    recommendation: Recommendation = Recommendation.REVIEW
    raw_json: dict[str, Any] = Field(default_factory=dict)


class UnderwritingCaseResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    input: UnderwritingCaseCreate
    report: UnderwritingReport | None = None
    ingestion_status: str = "pending"
    workflow_status: str = "pending"

    model_config = {"from_attributes": True}
