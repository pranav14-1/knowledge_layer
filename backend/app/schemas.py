from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.models import RelationshipType


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


class MultiUploadResponse(BaseModel):
    total_uploaded: int
    documents: List[DocumentResponse]
    status: str = "success"
