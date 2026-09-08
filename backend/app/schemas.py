import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import RelationshipType


class AtomicFactSchema(BaseModel):
    entity: str = Field(description="Entity or department, e.g. 'Central Government of India', 'Delhivery', 'Apple Inc.'")
    metric: str = Field(description="Specific numerical or fiscal metric, e.g. 'Fiscal Deficit', 'Total Revenue', 'Inflation Rate'. Must NOT be generic words.")
    value: str = Field(description="Number, percentage, or currency figure, e.g. '5.6%', '8,839 Cr', '14.1'. Require a value to contain numbers or explicit data unless explicitly categorized.")
    unit: Optional[str] = Field(None, description="Unit of measurement, e.g. '% of GDP', 'INR Billion', 'USD', 'Crores'")
    time_period: Optional[str] = Field(None, description="Year/Quarter/Period, e.g. 'FY 2024/25 Budget', 'FY24', 'Q3 2024'")
    raw_text_evidence: str = Field(description="Verbatim sentence or table row from source PDF")
    page_number: int = Field(description="Source PDF page index (1-based)")

    @field_validator("value")
    @classmethod
    def validate_numeric_value(cls, v: str) -> str:
        val = str(v).strip()
        # Value must contain at least one digit or explicit numerical/status token
        if not re.search(r"\d", val) and val.lower() not in {"failed", "n/a", "none"}:
            raise ValueError(f"Extracted value '{val}' must contain a concrete numerical figure.")
        return val

    @field_validator("metric")
    @classmethod
    def validate_metric_name(cls, v: str) -> str:
        met = str(v).strip()
        banned = {
            "reported metric", "tariffs", "warrants", "reskilling", "international",
            "following", "executive", "discussions", "table", "staff", "assessment"
        }
        if met.lower() in banned:
            raise ValueError(f"Generic word '{met}' cannot be used as a standalone metric.")
        if len(met) < 2:
            raise ValueError("Metric name too short.")
        return met


class ExtractedFactList(BaseModel):
    facts: List[AtomicFactSchema] = Field(default_factory=list, description="List of extracted atomic facts")


class FactComparisonResult(BaseModel):
    relationship_type: RelationshipType = Field(description="Classification of relationship between the two facts")
    explanation_reasoning: str = Field(
        description="A short, direct 1-sentence explanation strictly under 25 words following the formula format"
    )

    @field_validator("explanation_reasoning")
    @classmethod
    def validate_reasoning(cls, v: str) -> str:
        s = str(v).strip().strip('"').strip("'")
        sentences = [sent.strip() for sent in re.split(r"(?<=[.!?])\s+", s) if sent.strip()]
        if sentences:
            s = sentences[0]
        words = s.split()
        if len(words) > 25:
            s = " ".join(words[:25]) + "."
        return s


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    filepath: str
    page_count: int
    status: str = "COMPLETED"
    progress: int = 100
    error_message: Optional[str] = None
    upload_timestamp: datetime


class DocumentStatusItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    page_count: int


class DocumentStatusResponse(BaseModel):
    documents: List[DocumentStatusItem]
    all_completed: bool


class ExtractedFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    document_filename: Optional[str] = None
    page_number: int
    entity: str
    metric: str
    value: str
    unit: Optional[str] = None
    time_period: Optional[str] = None
    raw_text_evidence: str


class FactRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fact_a_id: int
    fact_b_id: int
    relationship_type: RelationshipType
    explanation_reasoning: str


class FactRelationshipDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fact_a_id: int
    fact_b_id: int
    relationship_type: RelationshipType
    explanation_reasoning: str
    fact_a: Optional[ExtractedFactResponse] = None
    fact_b: Optional[ExtractedFactResponse] = None


class MultiUploadResponse(BaseModel):
    total_uploaded: int
    documents: List[DocumentResponse]
    status: str = "success"
