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
from app.schemas import (
    AtomicFactSchema,
    ExtractedFactList,
    FactComparisonResult
)
from app.extractor import extract_facts_from_document
from app.reconciler import reconcile_document_facts, _compare_facts_heuristic
from app.main import app


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


@pytest.fixture(scope="session")
def sample_reconciliation_pdfs():
    temp_dir = tempfile.mkdtemp()

    # Document 1: Delhivery FY24 revenue
    doc1_path = os.path.join(temp_dir, "delhivery_fy24.pdf")
    d1 = fitz.open()
    p1 = d1.new_page()
    p1.insert_text((72, 72), "Delhivery reported Revenue of ₹8,839 Cr in FY24.")
    d1.save(doc1_path)
    d1.close()

    # Document 2: Annual Report corroborating FY24 revenue and stating FY23 revenue
    doc2_path = os.path.join(temp_dir, "delhivery_annual.pdf")
    d2 = fitz.open()
    p2 = d2.new_page()
    p2.insert_text((72, 72), "Delhivery achieved Revenue of ₹8,839 Cr in FY24.")
    p2.insert_text((72, 100), "Delhivery reported Revenue of ₹7,225 Cr in FY23.")
    d2.save(doc2_path)
    d2.close()

    yield {
        "doc1": doc1_path,
        "doc2": doc2_path,
        "dir": temp_dir
    }


def test_pydantic_schemas_validation():
    """Verifies that AtomicFactSchema and FactComparisonResult enforce valid structures."""
    fact = AtomicFactSchema(
        entity="Delhivery",
        metric="Revenue",
        value="₹8,839 Cr",
        unit="INR Cr",
        time_period="FY24",
        raw_text_evidence="Delhivery reported Revenue of ₹8,839 Cr in FY24.",
        page_number=1
    )
    assert fact.entity == "Delhivery"
    assert fact.metric == "Revenue"
    assert fact.page_number == 1

    fact_list = ExtractedFactList(facts=[fact])
    assert len(fact_list.facts) == 1
    assert fact_list.facts[0].value == "₹8,839 Cr"

    comp_result = FactComparisonResult(
        relationship_type=RelationshipType.CORROBORATES,
        explanation_reasoning="Consensus verified across both financial statements."
    )
    assert comp_result.relationship_type == RelationshipType.CORROBORATES


def test_extractor_creates_db_facts(test_db_session):
    """Verifies that extractor converts parsed content into persisted ExtractedFact records."""
    doc = Document(filename="doc1.pdf", filepath="/tmp/doc1.pdf", page_count=1)
    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)

    parsed_content = {
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "text": "Delhivery reported Revenue of ₹8,839 Cr in FY24.",
                "tables": []
            }
        ]
    }

    facts = extract_facts_from_document(test_db_session, doc.id, parsed_content)
    assert len(facts) >= 1
    stored_fact = facts[0]
    assert stored_fact.document_id == doc.id
    assert stored_fact.entity != ""
    assert stored_fact.page_number == 1
    assert "Delhivery" in stored_fact.raw_text_evidence


def test_reconciler_classifies_the_four_cases(test_db_session):
    """Verifies that reconciliation correctly classifies CORROBORATES, CONTRADICTS, RECONCILED, and FAILURE_ANALYSIS."""
    doc1 = Document(filename="doc1.pdf", filepath="/tmp/doc1.pdf", page_count=1)
    doc2 = Document(filename="doc2.pdf", filepath="/tmp/doc2.pdf", page_count=1)
    test_db_session.add_all([doc1, doc2])
    test_db_session.commit()

    # Fact Base (Doc 1)
    base_fact = ExtractedFact(
        document_id=doc1.id,
        page_number=1,
        entity="Delhivery",
        metric="Revenue",
        value="₹8,839 Cr",
        unit="INR Cr",
        time_period="FY24",
        raw_text_evidence="Delhivery reported Revenue of ₹8,839 Cr in FY24."
    )

    # 1. Corroborating Fact (Doc 2)
    corrob_fact = ExtractedFact(
        document_id=doc2.id,
        page_number=1,
        entity="Delhivery",
        metric="Revenue",
        value="₹8,839 Cr",
        unit="INR Cr",
        time_period="FY24",
        raw_text_evidence="Delhivery achieved Revenue of ₹8,839 Cr in FY24."
    )

    # 2. Contradicting Fact (Doc 2)
    contradict_fact = ExtractedFact(
        document_id=doc2.id,
        page_number=1,
        entity="Delhivery",
        metric="Revenue",
        value="₹7,500 Cr",
        unit="INR Cr",
        time_period="FY24",
        raw_text_evidence="Delhivery achieved Revenue of ₹7,500 Cr in FY24."
    )

    # 3. Contextually Reconciled Fact (Doc 2)
    reconciled_fact = ExtractedFact(
        document_id=doc2.id,
        page_number=1,
        entity="Delhivery",
        metric="Revenue",
        value="₹7,225 Cr",
        unit="INR Cr",
        time_period="FY23",
        raw_text_evidence="Delhivery achieved Revenue of ₹7,225 Cr in FY23."
    )

    # 4. Anomaly / Failure Analysis Fact
    failure_fact = ExtractedFact(
        document_id=doc2.id,
        page_number=1,
        entity="System",
        metric="Fact Extraction",
        value="No grounded facts detected",
        unit=None,
        time_period=None,
        raw_text_evidence="Corrupted section text"
    )

    test_db_session.add_all([base_fact, corrob_fact, contradict_fact, reconciled_fact, failure_fact])
    test_db_session.commit()

    # Test heuristic classification logic directly
    res_corrob = _compare_facts_heuristic(base_fact, corrob_fact)
    assert res_corrob.relationship_type == RelationshipType.CORROBORATES

    res_contradict = _compare_facts_heuristic(base_fact, contradict_fact)
    assert res_contradict.relationship_type == RelationshipType.CONTRADICTS

    res_reconciled = _compare_facts_heuristic(base_fact, reconciled_fact)
    assert res_reconciled.relationship_type == RelationshipType.RECONCILED

    res_failure = _compare_facts_heuristic(base_fact, failure_fact)
    assert res_failure.relationship_type == RelationshipType.FAILURE_ANALYSIS


def test_api_facts_and_relationships_endpoints(client, sample_reconciliation_pdfs):
    """Verifies that uploading PDFs extracts facts, reconciles them, and exposes GET endpoints."""
    with open(sample_reconciliation_pdfs["doc1"], "rb") as f1, open(sample_reconciliation_pdfs["doc2"], "rb") as f2:
        upload_res = client.post(
            "/api/upload",
            files=[
                ("files", ("delhivery_fy24.pdf", f1, "application/pdf")),
                ("files", ("delhivery_annual.pdf", f2, "application/pdf"))
            ]
        )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["total_uploaded"] == 2
    doc1_id = upload_data["documents"][0]["id"]
    doc2_id = upload_data["documents"][1]["id"]

    # 1. Query /api/facts without filter
    facts_res = client.get("/api/facts")
    assert facts_res.status_code == 200
    all_facts = facts_res.json()
    assert len(all_facts) >= 2

    # 2. Query /api/facts with document_id filter
    facts_doc1_res = client.get(f"/api/facts?document_id={doc1_id}")
    assert facts_doc1_res.status_code == 200
    doc1_facts = facts_doc1_res.json()
    assert all(f["document_id"] == doc1_id for f in doc1_facts)

    # 3. Query /api/relationships
    rel_res = client.get("/api/relationships")
    assert rel_res.status_code == 200
    relationships = rel_res.json()
    assert len(relationships) >= 1
    first_rel = relationships[0]
    assert "relationship_type" in first_rel
    assert "explanation_reasoning" in first_rel
    assert "fact_a" in first_rel
    assert "fact_b" in first_rel
    assert first_rel["fact_a"]["document_id"] != first_rel["fact_b"]["document_id"]

    # 4. Query /api/relationships with type filter
    filtered_rel_res = client.get(f"/api/relationships?type={first_rel['relationship_type']}")
    assert filtered_rel_res.status_code == 200
    filtered_list = filtered_rel_res.json()
    assert all(r["relationship_type"] == first_rel["relationship_type"] for r in filtered_list)

