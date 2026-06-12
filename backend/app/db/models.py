import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UnderwritingCaseDB(Base):
    __tablename__ = "underwriting_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(50), default="created")
    ingestion_status: Mapped[str] = mapped_column(String(50), default="pending")
    workflow_status: Mapped[str] = mapped_column(String(50), default="pending")
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    report_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PropertySaleDB(Base):
    __tablename__ = "property_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(500))
    sale_price: Mapped[float] = mapped_column(Float)
    sale_date: Mapped[datetime] = mapped_column(DateTime)
    bedrooms: Mapped[int] = mapped_column(Integer)
    bathrooms: Mapped[float] = mapped_column(Float)
    square_footage: Mapped[int] = mapped_column(Integer)
    lot_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_type: Mapped[str] = mapped_column(String(100), default="single_family")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    listing_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentChunkDB(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    source_file: Mapped[str] = mapped_column(String(500))
    qdrant_point_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
