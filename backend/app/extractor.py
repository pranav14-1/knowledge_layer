import os
import re
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.models import ExtractedFact
from app.schemas import ExtractedFactList, AtomicFactSchema

load_dotenv()
logger = logging.getLogger(__name__)


def _get_instructor_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        return None
    try:
        from google import genai
        import instructor
        client = instructor.from_genai(
            client=genai.Client(api_key=api_key, http_options={"timeout": 10000}),
            mode=instructor.Mode.TOOLS,
        )
        return client
    except Exception as e:
        logger.warning(f"Failed to initialize Instructor GenAI client: {e}")
        return None


def _heuristic_fact_extraction(page_number: int, text: str) -> List[AtomicFactSchema]:
    """Fallback rule-based heuristic extractor when LLM API is unavailable."""
    facts: List[AtomicFactSchema] = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Pattern detecting numbers, currency, or percentages
    pattern = re.compile(
        r"([A-Z][A-Za-z0-9\s&]+?)\s+(?:reported|achieved|was|is|stood at|reached|of)\s+([A-Za-z\s]+?)\s+(?:of\s+)?([₹$€£]?\s*[\d,]+(?:\.\d+)?\s*(?:[A-Za-z%]+)?)",
        re.IGNORECASE
    )

    for line in lines:
        match = pattern.search(line)
        if match:
            entity = match.group(1).strip()
            metric = match.group(2).strip()
            value = match.group(3).strip()
            
            # Extract time period if found (e.g. Q1, Q2, FY24, 2024)
            time_match = re.search(r"\b(Q[1-4]|FY\d{2,4}|\d{4}(?:-\d{2,4})?)\b", line)
            time_period = time_match.group(1) if time_match else None
            
            facts.append(
                AtomicFactSchema(
                    entity=entity,
                    metric=metric,
                    value=value,
                    unit=None,
                    time_period=time_period,
                    raw_text_evidence=line,
                    page_number=page_number
                )
            )

    # If pattern didn't match but text has content, extract simple metric-value pairs
    if not facts and lines:
        for line in lines:
            num_match = re.search(r"([₹$€£]?\s*[\d,]+(?:\.\d+)?\s*(?:%|[A-Za-z]+)?)", line)
            if num_match and len(line) > 10:
                words = line.split()
                entity = words[0] if words else "Unknown Entity"
                facts.append(
                    AtomicFactSchema(
                        entity=entity,
                        metric="Reported Metric",
                        value=num_match.group(1),
                        unit=None,
                        time_period=None,
                        raw_text_evidence=line,
                        page_number=page_number
                    )
                )
                break

    return facts


def extract_facts_from_document(
    db: Session,
    doc_id: int,
    parsed_content: dict
) -> List[ExtractedFact]:
    """
    Extracts atomic facts from parsed document content and persists them in SQLite.
    Uses Instructor + Gemini (gemini-2.5-flash) with structured output, falling back
    to heuristic extraction if API key is missing or model call fails.
    """
    extracted_db_facts: List[ExtractedFact] = []
    pages = parsed_content.get("pages", [])
    client = _get_instructor_gemini_client()

    for page in pages:
        page_no = page.get("page_number", 1)
        text_content = page.get("text", "")
        tables = page.get("tables", [])

        if not text_content and not tables:
            continue

        page_evidence = text_content
        if tables:
            table_str = "\n".join([str(t) for t in tables])
            page_evidence = f"{page_evidence}\n\nTables:\n{table_str}"

        page_facts: List[AtomicFactSchema] = []

        if client is not None:
            try:
                prompt = (
                    f"Extract all verifiable atomic facts from the following document page (Page {page_no}).\n"
                    "For each fact, identify the specific entity, metric name, exact value, unit, "
                    "time period/vintage, and cite the exact verbatim sentence from the text.\n\n"
                    f"--- PAGE {page_no} CONTENT ---\n{page_evidence}"
                )

                response: ExtractedFactList = client.chat.completions.create(
                    model="gemini-2.5-flash",
                    response_model=ExtractedFactList,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a high-precision fact extraction engine. Extract granular atomic facts with exact citations."
                        },
                        {"role": "user", "content": prompt}
                    ]
                )
                if response and response.facts:
                    for f in response.facts:
                        f.page_number = page_no
                    page_facts.extend(response.facts)
            except Exception as e:
                logger.warning(
                    f"Gemini Instructor extraction failed on doc {doc_id} page {page_no}: {e}. "
                    "Falling back to heuristic extraction."
                )

        # If LLM wasn't available or produced no facts, run heuristic fallback
        if not page_facts:
            page_facts = _heuristic_fact_extraction(page_no, page_evidence)

        # If still no facts found, record a fallback record for Failure Analysis
        if not page_facts:
            page_facts.append(
                AtomicFactSchema(
                    entity="System",
                    metric="Fact Extraction",
                    value="No grounded facts detected",
                    unit=None,
                    time_period=None,
                    raw_text_evidence=page_evidence[:200] if page_evidence else "Empty page",
                    page_number=page_no
                )
            )

        for fact_schema in page_facts:
            db_fact = ExtractedFact(
                document_id=doc_id,
                page_number=fact_schema.page_number,
                entity=fact_schema.entity,
                metric=fact_schema.metric,
                value=fact_schema.value,
                unit=fact_schema.unit,
                time_period=fact_schema.time_period,
                raw_text_evidence=fact_schema.raw_text_evidence
            )
            db.add(db_fact)
            extracted_db_facts.append(db_fact)

    db.commit()
    for f in extracted_db_facts:
        db.refresh(f)

    return extracted_db_facts

