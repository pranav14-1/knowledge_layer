from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models import RelationshipType


class AtomicFactSchema(BaseModel):
    entity: str = Field(description="Business or economic subject, e.g. 'Delhivery', 'India GDP'")
    metric: str = Field(description="Metric name, e.g. 'Revenue', 'Inflation Rate'")
    value: str = Field(description="Extracted numerical or categorical value, e.g. '8,839 Cr', '6.5%'")
    unit: Optional[str] = Field(None, description="Unit of measurement if applicable, e.g. 'INR Cr', '%'")
    time_period: Optional[str] = Field(None, description="Reporting period, e.g. 'FY24', 'Q4 FY24'")
    raw_text_evidence: str = Field(description="Verbatim sentence or table segment from source PDF")
    page_number: int = Field(description="Source PDF page index (1-based)")


class ExtractedFactList(BaseModel):
    facts: List[AtomicFactSchema] = Field(default_factory=list, description="List of extracted atomic facts")


class FactComparisonResult(BaseModel):
    relationship_type: RelationshipType = Field(description="Classification of relationship between the two facts")
    explanation_reasoning: str = Field(description="Detailed context explanation describing the classification")


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    filepath: str
    page_count: int
    upload_timestamp: datetime


class ExtractedFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
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
