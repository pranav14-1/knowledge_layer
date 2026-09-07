import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.database import engine, Base, get_db
from app.models import Document, ExtractedFact, FactRelationship, RelationshipType
from app.schemas import (
    DocumentResponse,
    MultiUploadResponse,
    ExtractedFactResponse,
    FactRelationshipDetailResponse
)
from app.parser import parse_pdf_document
from app.extractor import extract_facts_from_document
from app.reconciler import reconcile_document_facts

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Fact Knowledge Layer API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload", response_model=MultiUploadResponse)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    saved_documents = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")

        safe_filename = os.path.basename(file.filename)
        dest_path = os.path.join(UPLOAD_DIR, safe_filename)

        with open(dest_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        parsed_data = parse_pdf_document(dest_path)
        page_count = parsed_data.get("page_count", 1)

        db_document = Document(
            filename=safe_filename,
            filepath=dest_path,
            page_count=page_count
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)

        # Extract atomic facts from parsed content
        extract_facts_from_document(
            db=db,
            doc_id=db_document.id,
            parsed_content=parsed_data
        )

        # Cross-reference facts against existing corpus documents
        reconcile_document_facts(
            db=db,
            new_doc_id=db_document.id
        )

        saved_documents.append(db_document)

    return MultiUploadResponse(
        total_uploaded=len(saved_documents),
        documents=saved_documents
    )


@app.get("/api/documents", response_model=List[DocumentResponse])
def get_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.upload_timestamp.desc()).all()


@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/api/facts", response_model=List[ExtractedFactResponse])
def get_facts(
    document_id: Optional[int] = Query(None, description="Filter facts by source document ID"),
    db: Session = Depends(get_db)
):
    query = db.query(ExtractedFact)
    if document_id is not None:
        query = query.filter(ExtractedFact.document_id == document_id)
    return query.order_by(ExtractedFact.page_number.asc()).all()


@app.get("/api/relationships", response_model=List[FactRelationshipDetailResponse])
def get_relationships(
    type: Optional[RelationshipType] = Query(None, description="Filter by relationship classification"),
    db: Session = Depends(get_db)
):
    query = db.query(FactRelationship).options(
        joinedload(FactRelationship.fact_a),
        joinedload(FactRelationship.fact_b)
    )
    if type is not None:
        query = query.filter(FactRelationship.relationship_type == type)
    return query.order_by(FactRelationship.id.desc()).all()


@app.get("/api/pdf/{filename}")
def get_pdf(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(file_path, media_type="application/pdf", filename=safe_filename)
