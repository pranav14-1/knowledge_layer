import os
import re
import json
import logging
import shutil
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import engine, Base, SessionLocal, get_db, init_db
from app.models import Document, ExtractedFact, FactRelationship, RelationshipType, DocumentStatus, ChatSession, ChatMessage
from app.schemas import (
    DocumentResponse,
    DocumentStatusItem,
    DocumentStatusResponse,
    MultiUploadResponse,
    ExtractedFactResponse,
    FactRelationshipDetailResponse
)
from app.parser import parse_pdf_document
from app.extractor import extract_facts_from_document, _get_instructor_gemini_client
from app.reconciler import reconcile_document_facts

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads")))


def process_documents_pipeline(doc_ids: List[int]):
    """Background task with granular progress tracking (Parsing 35%, Extracting 70%, Completed 100%)."""
    db = SessionLocal()
    try:
        for doc_id in doc_ids:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                continue
            try:
                # Phase 1: Parsing (35%)
                doc.status = DocumentStatus.PARSING.value
                doc.progress = 35
                db.commit()

                parsed_data = parse_pdf_document(doc.filepath)
                doc.page_count = parsed_data.get("page_count", 1)
                db.commit()

                # Phase 2: Extraction & Reconciliation (70%)
                doc.status = DocumentStatus.EXTRACTING.value
                doc.progress = 70
                db.commit()

                extract_facts_from_document(
                    db=db,
                    doc_id=doc.id,
                    parsed_content=parsed_data
                )

                reconcile_document_facts(
                    db=db,
                    new_doc_id=doc.id
                )

                # Phase 3: Completed (100%)
                doc.status = DocumentStatus.COMPLETED.value
                doc.progress = 100
                doc.error_message = None
                db.commit()
            except Exception as e:
                logger.error(f"Error processing doc {doc_id}: {e}", exc_info=True)
                doc.status = DocumentStatus.FAILED.value
                doc.progress = 100
                doc.error_message = str(e)
                db.commit()

                # Record failure fact for auditable failure analysis
                failure_fact = ExtractedFact(
                    document_id=doc.id,
                    page_number=1,
                    entity="System",
                    metric="Ingestion Pipeline",
                    value="Failed",
                    raw_text_evidence=f"Processing exception: {str(e)[:400]}"
                )
                db.add(failure_fact)
                db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()
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


@app.get("/api/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy", "service": "fact-knowledge-layer-api"}


@app.post("/api/upload", response_model=MultiUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    chat_id: Optional[int] = Query(None, description="Chat session ID to associate documents with"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    from datetime import datetime

    # Resolve or create target chat workspace
    target_chat_id = chat_id
    if target_chat_id is not None:
        chat = db.query(ChatSession).filter(ChatSession.id == target_chat_id).first()
        if not chat:
            target_chat_id = None

    if target_chat_id is None:
        chat = db.query(ChatSession).order_by(ChatSession.id.desc()).first()
        if not chat:
            now = datetime.utcnow()
            chat = ChatSession(title="Default Workspace", created_at=now, updated_at=now)
            db.add(chat)
            db.commit()
            db.refresh(chat)
        target_chat_id = chat.id

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_documents = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")

        # Sanitize filename to prevent directory traversal and special character issues
        raw_basename = os.path.basename(file.filename)
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', raw_basename)
        if not safe_filename.lower().endswith(".pdf"):
            safe_filename += ".pdf"

        dest_path = os.path.join(UPLOAD_DIR, safe_filename)

        # Reset file pointer to beginning and synchronously write bytes
        file.file.seek(0)
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create initial Document record in QUEUED state with 10% progress
        db_document = Document(
            filename=safe_filename,
            filepath=dest_path,
            page_count=1,
            status=DocumentStatus.QUEUED.value,
            progress=10,
            error_message=None,
            chat_session_id=target_chat_id
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)

        saved_documents.append(db_document)

    # Trigger async background pipeline
    background_tasks.add_task(
        process_documents_pipeline,
        [doc.id for doc in saved_documents]
    )

    return MultiUploadResponse(
        total_uploaded=len(saved_documents),
        documents=saved_documents,
        status="processing"
    )


@app.get("/api/documents/status", response_model=DocumentStatusResponse)
def get_documents_status(
    chat_id: Optional[int] = Query(None, description="Filter by chat session ID"),
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    if chat_id is not None:
        query = query.filter(Document.chat_session_id == chat_id)
    docs = query.order_by(Document.id.desc()).all()
    items = [
        DocumentStatusItem(
            id=d.id,
            filename=d.filename,
            status=d.status,
            progress=d.progress,
            error_message=d.error_message,
            page_count=d.page_count
        )
        for d in docs
    ]
    all_completed = len(docs) > 0 and all(d.status in ("COMPLETED", "FAILED") for d in docs)
    return DocumentStatusResponse(documents=items, all_completed=all_completed)


@app.get("/api/documents", response_model=List[DocumentResponse])
def get_documents(
    chat_id: Optional[int] = Query(None, description="Filter by chat session ID"),
    db: Session = Depends(get_db)
):
    query = db.query(Document)
    if chat_id is not None:
        query = query.filter(Document.chat_session_id == chat_id)
    return query.order_by(Document.upload_timestamp.desc()).all()


@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.get("/api/facts", response_model=List[ExtractedFactResponse])
def get_facts(
    document_id: Optional[int] = Query(None, description="Filter facts by source document ID"),
    chat_id: Optional[int] = Query(None, description="Filter facts by chat session ID"),
    db: Session = Depends(get_db)
):
    query = db.query(ExtractedFact)
    if document_id is not None:
        query = query.filter(ExtractedFact.document_id == document_id)
    elif chat_id is not None:
        query = query.join(ExtractedFact.document).filter(Document.chat_session_id == chat_id)
    return query.order_by(ExtractedFact.page_number.asc()).all()


@app.get("/api/relationships", response_model=List[FactRelationshipDetailResponse])
def get_relationships(
    type: Optional[RelationshipType] = Query(None, description="Filter by relationship classification"),
    chat_id: Optional[int] = Query(None, description="Filter by chat session ID"),
    db: Session = Depends(get_db)
):
    query = db.query(FactRelationship).options(
        joinedload(FactRelationship.fact_a).joinedload(ExtractedFact.document),
        joinedload(FactRelationship.fact_b).joinedload(ExtractedFact.document)
    )
    if chat_id is not None:
        subquery = (
            db.query(ExtractedFact.id)
            .join(Document, ExtractedFact.document_id == Document.id)
            .filter(Document.chat_session_id == chat_id)
        )
        query = query.filter(
            FactRelationship.fact_a_id.in_(subquery),
            FactRelationship.fact_b_id.in_(subquery)
        )
    if type is not None:
        query = query.filter(FactRelationship.relationship_type == type)
    return query.order_by(FactRelationship.id.desc()).all()


@app.get("/api/pdf/{filename}")
def get_pdf(filename: str, db: Session = Depends(get_db)):
    # 1. First check if document exists in database
    doc = db.query(Document).filter(Document.filename == filename).order_by(Document.id.desc()).first()
    if doc and os.path.exists(doc.filepath):
        return FileResponse(doc.filepath, media_type="application/pdf", filename=doc.filename)

    # 2. Check sanitized and raw filenames on disk
    raw_basename = os.path.basename(filename)
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', raw_basename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    if not os.path.exists(file_path):
        direct_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(direct_path):
            file_path = direct_path
        else:
            raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(file_path, media_type="application/pdf", filename=safe_filename)


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fact_ids = [f.id for f in doc.facts]
    if fact_ids:
        db.query(FactRelationship).filter(
            (FactRelationship.fact_a_id.in_(fact_ids)) |
            (FactRelationship.fact_b_id.in_(fact_ids))
        ).delete(synchronize_session=False)

    file_path = doc.filepath
    db.delete(doc)
    db.commit()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete disk file {file_path}: {e}")

    return {"status": "success", "deleted_id": doc_id}


class ChatSessionCreate(BaseModel):
    title: str


class ChatMessageCreate(BaseModel):
    content: str


@app.get("/api/chats")
def get_chats(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]


class ChatSessionUpdate(BaseModel):
    title: str


@app.post("/api/chats", status_code=status.HTTP_201_CREATED)
def create_chat_session(payload: ChatSessionCreate, db: Session = Depends(get_db)):
    from datetime import datetime
    now = datetime.utcnow()
    session = ChatSession(title=payload.title, created_at=now, updated_at=now)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": []
    }


@app.get("/api/chats/{chat_id}")
def get_chat_session(chat_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": json.loads(m.citations) if m.citations else [],
            "created_at": m.created_at
        }
        for m in session.messages
    ]
    return {"id": session.id, "title": session.title, "created_at": session.created_at, "messages": messages}


@app.patch("/api/chats/{chat_id}")
@app.put("/api/chats/{chat_id}")
def update_chat_session(chat_id: int, payload: ChatSessionUpdate, db: Session = Depends(get_db)):
    from datetime import datetime
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    new_title = payload.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Workspace title cannot be empty")
    session.title = new_title
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }


@app.delete("/api/chats/{chat_id}")
def delete_chat_session(chat_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Clean up associated physical PDF files from disk
    for doc in session.documents:
        if doc.filepath and os.path.exists(doc.filepath):
            try:
                os.remove(doc.filepath)
            except Exception as e:
                logger.warning(f"Failed to remove physical document {doc.filepath}: {e}")

    db.delete(session)
    db.commit()
    return {"status": "success", "deleted_id": chat_id}


@app.post("/api/chats/{chat_id}/messages")
def send_chat_message(chat_id: int, payload: ChatMessageCreate, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # 1. Add user message
    user_msg = ChatMessage(session_id=session.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()

    # 2. Retrieve grounded citations from ExtractedFacts with eager loaded document
    query_text = payload.content.lower()
    all_facts = (
        db.query(ExtractedFact)
        .options(joinedload(ExtractedFact.document))
        .join(Document)
        .filter(Document.chat_session_id == chat_id)
        .all()
    )
    matching_facts = []
    for f in all_facts:
        ent = (f.entity or "").lower()
        met = (f.metric or "").lower()
        if (ent and ent in query_text) or (met and met in query_text) or any(w in query_text for w in ent.split() if len(w) > 3):
            matching_facts.append(f)

    if not matching_facts and all_facts:
        matching_facts = all_facts[:5]

    citations = [
        {
            "fact_id": f.id,
            "document_id": f.document_id,
            "filename": f.document.filename if f.document else "Document",
            "entity": f.entity,
            "metric": f.metric,
            "value": f.value,
            "page_number": f.page_number,
            "evidence": f.raw_text_evidence
        }
        for f in matching_facts[:8]
    ]

    # 3. Grounded Synthesis via Gemini with graceful bullet-point fallback
    content_resp = None
    client = _get_instructor_gemini_client()
    if client and matching_facts:
        try:
            facts_context = "\n".join([
                f"- [{f.document.filename if f.document else 'Doc'}, Page {f.page_number}] {f.entity} | {f.metric}: {f.value} ({f.unit or ''}, {f.time_period or ''}) -- Evidence: \"{f.raw_text_evidence}\""
                for f in matching_facts[:8]
            ])
            prompt = (
                f"User Question: {payload.content}\n\n"
                f"Verified Grounded Facts from Workspace Documents:\n{facts_context}\n\n"
                "Instructions:\n"
                "1. Answer the user's question directly, accurately, and concisely using the verified facts above.\n"
                "2. Explicitly cite the document name and page number when stating metrics.\n"
                "3. If the facts do not contain the answer, state what is available instead."
            )
            chat_completion = client.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if chat_completion and chat_completion.text:
                content_resp = chat_completion.text.strip()
        except Exception as e:
            logger.warning(f"Gemini chat completion failed or rate limited: {e}. Falling back to structured response.")

    if not content_resp:
        if matching_facts:
            bullet_points = [
                f"- {f.entity} -- {f.metric}: {f.value} (from {f.document.filename if f.document else 'Doc'}, Page {f.page_number})"
                for f in matching_facts[:8]
            ]
            content_resp = "Based on the verified documents in this workspace:\n" + "\n".join(bullet_points)
        else:
            content_resp = "I searched the documents in this workspace but did not locate verified metrics matching your request."

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content_resp,
        citations=json.dumps(citations)
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return {
        "id": assistant_msg.id,
        "role": assistant_msg.role,
        "content": assistant_msg.content,
        "citations": citations,
        "created_at": assistant_msg.created_at
    }

