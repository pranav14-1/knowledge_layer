import os
import tempfile
import pytest
import pymupdf as fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Document, ExtractedFact, FactRelationship, RelationshipType
from app.parser import parse_pdf_document, _parse_with_pymupdf
from app.main import app, UPLOAD_DIR


@pytest.fixture(scope="session")
def sample_pdf_files():
    temp_dir = tempfile.mkdtemp()
    
    # 1-page sample PDF
    single_page_path = os.path.join(temp_dir, "sample_single.pdf")
    doc1 = fitz.open()
    page1 = doc1.new_page()
    page1.insert_text((72, 72), "Alphabet Inc. Q3 2024 Revenue was 88.27 USD Billion.")
    doc1.save(single_page_path)
    doc1.close()

    # 2-page sample PDF
    multi_page_path = os.path.join(temp_dir, "sample_multi.pdf")
    doc2 = fitz.open()
    p1 = doc2.new_page()
    p1.insert_text((72, 72), "Apple Inc. Q3 2024 Revenue was 85.78 USD Billion.")
    p2 = doc2.new_page()
    p2.insert_text((72, 72), "Gross Margin was 46.3 percent.")
    doc2.save(multi_page_path)
    doc2.close()

    yield {
        "single": single_page_path,
        "multi": multi_page_path,
        "dir": temp_dir
    }


@pytest.fixture
def test_db_session():
    test_db_url = "sqlite:///:memory:"
    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_database_models_and_tables(test_db_session):
    """Verifies that all tables are created and relationships operate cleanly."""
    doc = Document(filename="test.pdf", filepath="/tmp/test.pdf", page_count=2)
    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)
    assert doc.id is not None

    fact1 = ExtractedFact(
        document_id=doc.id,
        page_number=1,
        entity="Alphabet",
        metric="Revenue",
        value="88.27",
        unit="USD Billion",
        time_period="Q3 2024",
        raw_text_evidence="Q3 2024 Revenue was 88.27 USD Billion."
    )
    fact2 = ExtractedFact(
        document_id=doc.id,
        page_number=2,
        entity="Alphabet",
        metric="Revenue",
        value="88.27",
        unit="USD Billion",
        time_period="Q3 2024",
        raw_text_evidence="Reported revenue of 88.27B USD."
    )
    test_db_session.add_all([fact1, fact2])
    test_db_session.commit()
    test_db_session.refresh(fact1)
    test_db_session.refresh(fact2)
    assert fact1.id is not None
    assert fact2.id is not None

    rel = FactRelationship(
        fact_a_id=fact1.id,
        fact_b_id=fact2.id,
        relationship_type=RelationshipType.CORROBORATES,
        explanation_reasoning="Both facts assert identical revenue for Q3 2024."
    )
    test_db_session.add(rel)
    test_db_session.commit()
    test_db_session.refresh(rel)
    assert rel.id is not None
    assert rel.relationship_type == RelationshipType.CORROBORATES


def test_parser_extracts_text_and_pages(sample_pdf_files):
    """Verifies that parser extracts page count and text from sample PDFs."""
    # Test single page
    res_single = parse_pdf_document(sample_pdf_files["single"])
    assert res_single["page_count"] == 1
    assert len(res_single["pages"]) == 1
    assert "Alphabet" in res_single["pages"][0]["text"] or "88.27" in res_single["pages"][0]["text"]

    # Test multi page
    res_multi = parse_pdf_document(sample_pdf_files["multi"])
    assert res_multi["page_count"] == 2
    assert len(res_multi["pages"]) == 2

    # Test pymupdf direct fallback
    res_fallback = _parse_with_pymupdf(sample_pdf_files["single"])
    assert res_fallback["page_count"] == 1
    assert "Alphabet" in res_fallback["pages"][0]["text"]


def test_single_and_multi_upload_endpoints(client, sample_pdf_files):
    """Verifies single and multi PDF uploads, listing, and retrieving documents."""
    # 1. Single PDF upload
    with open(sample_pdf_files["single"], "rb") as f:
        response = client.post(
            "/api/upload",
            files=[("files", ("sample_single.pdf", f, "application/pdf"))]
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total_uploaded"] == 1
    assert len(data["documents"]) == 1
    doc_id = data["documents"][0]["id"]
    assert data["documents"][0]["filename"] == "sample_single.pdf"
    assert data["documents"][0]["page_count"] == 1

    # 2. Multi PDF upload
    with open(sample_pdf_files["single"], "rb") as f1, open(sample_pdf_files["multi"], "rb") as f2:
        response_multi = client.post(
            "/api/upload",
            files=[
                ("files", ("doc_a.pdf", f1, "application/pdf")),
                ("files", ("doc_b.pdf", f2, "application/pdf"))
            ]
        )
    assert response_multi.status_code == 200
    multi_data = response_multi.json()
    assert multi_data["total_uploaded"] == 2
    assert len(multi_data["documents"]) == 2

    # 3. List documents
    list_response = client.get("/api/documents")
    assert list_response.status_code == 200
    docs = list_response.json()
    assert len(docs) >= 3

    # 4. Get specific document
    single_doc_response = client.get(f"/api/documents/{doc_id}")
    assert single_doc_response.status_code == 200
    assert single_doc_response.json()["id"] == doc_id

    # 5. Fetch PDF file binary
    pdf_file_response = client.get("/api/pdf/sample_single.pdf")
    assert pdf_file_response.status_code == 200
    assert pdf_file_response.headers["content-type"] == "application/pdf"
    assert len(pdf_file_response.content) > 0

    # 6. Reject non-PDF file
    fake_file = ("bad.txt", b"not a pdf", "text/plain")
    bad_upload_response = client.post("/api/upload", files=[("files", fake_file)])
    assert bad_upload_response.status_code == 400

