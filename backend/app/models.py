import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class RelationshipType(str, enum.Enum):
    CORROBORATES = "CORROBORATES"
    CONTRADICTS = "CONTRADICTS"
    RECONCILED = "RECONCILED"
    FAILURE_ANALYSIS = "FAILURE_ANALYSIS"


class DocumentStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    PARSING = "PARSING"
    EXTRACTING = "EXTRACTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(1024), nullable=False)
    page_count = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default=DocumentStatus.QUEUED.value)
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True, index=True)

    facts = relationship("ExtractedFact", back_populates="document", cascade="all, delete-orphan")
    session = relationship("ChatSession", back_populates="documents")


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    entity = Column(String(255), nullable=False, index=True)
    metric = Column(String(255), nullable=False)
    value = Column(String(255), nullable=False)
    unit = Column(String(100), nullable=True)
    time_period = Column(String(100), nullable=True)
    raw_text_evidence = Column(Text, nullable=False)

    document = relationship("Document", back_populates="facts")

    @property
    def document_filename(self) -> Optional[str]:
        return self.document.filename if self.document else None


class FactRelationship(Base):
    __tablename__ = "fact_relationships"

    id = Column(Integer, primary_key=True, index=True)
    fact_a_id = Column(Integer, ForeignKey("extracted_facts.id"), nullable=False, index=True)
    fact_b_id = Column(Integer, ForeignKey("extracted_facts.id"), nullable=False, index=True)
    relationship_type = Column(SQLEnum(RelationshipType), nullable=False)
    explanation_reasoning = Column(Text, nullable=False)

    fact_a = relationship("ExtractedFact", foreign_keys=[fact_a_id])
    fact_b = relationship("ExtractedFact", foreign_keys=[fact_b_id])


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("ChatSession", back_populates="messages")

