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


QUANTITATIVE_SYSTEM_PROMPT = (
    "You are a Quantitative Financial & Data Analyst. Your job is to extract grounded ATOMIC NUMERICAL & DATA FACTS from the provided document.\n\n"
    "EXTRACTION PRIORITY:\n"
    "1. PRIORITIZE DATA TABLES, FINANCIAL METRICS, PERCENTAGES, CURRENCIES, FISCAL FIGURES, DATES, AND QUANTITATIVE STATEMENTS.\n"
    "2. DO NOT extract generic words, headlines, or non-data phrases as metrics (e.g., DO NOT extract 'tariffs', 'warrants', 'reskilling', or 'international' as standalone metrics).\n"
    "3. Every metric MUST be a clear, specific quantitative metric (e.g., 'Fiscal Deficit (% of GDP)', 'Total Revenue', 'Inflation Rate', 'Capital Expenditure').\n"
    "4. Every extracted value MUST contain a concrete number, figure, percentage, or specific status statement (e.g., '5.6%', '₹8,839 Cr', '3.1').\n"
    "5. Always extract the precise `time_period` (e.g., 'FY 2025/26', 'Q4 2024', '2023 Actual') associated with the table column or row."
)


def _heuristic_fact_extraction(
    page_number: int,
    text: str,
    tables: Optional[List[str]] = None
) -> List[AtomicFactSchema]:
    """
    Quantitative heuristic extractor that extracts facts strictly from:
    1. Markdown data tables (matching column vintages with row metrics).
    2. Quantitative prose statements with concrete numerical metrics.
    Rejects generic words or non-numeric fragments.
    """
    facts: List[AtomicFactSchema] = []

    # 1. Parse Markdown Tables
    all_tables = list(tables or [])
    table_matches = re.findall(r'(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)', text)
    for tm in table_matches:
        if tm not in all_tables:
            all_tables.append(tm)

    for tbl in all_tables:
        lines = [l.strip() for l in tbl.split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        rows = []
        for l in lines:
            if l.startswith("|") and not re.match(r"^\|\s*[-:\s|]+\|$", l):
                cells = [c.strip() for c in l.split("|")[1:-1]]
                rows.append(cells)
        if len(rows) < 2:
            continue
        header = rows[0]
        for row in rows[1:]:
            if not row or not any(row):
                continue
            row_label = row[0]
            if not row_label or len(row_label) < 2 or row_label.lower() in {"source", "note", "chart", "figure"}:
                continue
            for col_idx in range(1, min(len(header), len(row))):
                col_label = header[col_idx]
                cell_val = row[col_idx]
                if not cell_val or not re.search(r"\d", cell_val):
                    continue
                unit_match = re.search(r"(%|Cr|Crore|Lakh|Billion|Million|USD|INR|₹|\$|per cent)", cell_val)
                unit = unit_match.group(1) if unit_match else None
                time_match = re.search(r"\b(FY\s*\d{2,4}|Q[1-4]\s*(?:FY\s*\d{2,4}|\d{4})?|\d{4})\b", col_label, re.I)
                time_p = time_match.group(0) if time_match else col_label

                try:
                    is_macro = any(k in row_label.lower() for k in ["deficit", "gdp", "inflation", "receipts", "debt"])
                    facts.append(AtomicFactSchema(
                        entity="General Economy" if is_macro else row_label,
                        metric=row_label,
                        value=cell_val,
                        unit=unit,
                        time_period=time_p if time_p and len(time_p) > 2 else None,
                        raw_text_evidence=f"{row_label} | {col_label}: {cell_val}",
                        page_number=page_number
                    ))
                except Exception:
                    pass

    # 2. Parse Quantitative Financial Statements from Prose
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Pattern A: Entity [reported/achieved] [Time] Metric [was/of] Value [Time]
    p_corp = re.compile(
        r"^(?:(?:the|in)\s+)?([A-Z][A-Za-z0-9\s&.,-]+?)(?:\s+(?:reported|achieved|recorded|posted|announced|had|registered))?\s+(?:(Q[1-4]\s*(?:FY\s*\d{2,4}|\d{4})?|H[1-2]\s*(?:FY\s*\d{2,4}|\d{4})?|FY\s*\d{2,4}|\d{4})\s+)?(Revenue|Total Revenue|Gross Margin|Net Profit|Net Income|EBITDA|Capital Expenditure|Capex|Operating Profit)\s+(?:was|is|reached|stood at|of)\s+([₹$€£·Rs\.]*\s*[\d,]+(?:\.\d+)?\s*(?:%|Cr|Crore|Lakh|Billion|Million|USD|INR|percent|per cent)?)(?:\s+(?:in|for)\s+(Q[1-4]\s*(?:FY\s*\d{2,4}|\d{4})?|H[1-2]\s*(?:FY\s*\d{2,4}|\d{4})?|FY\s*\d{2,4}|\d{4}))?",
        re.IGNORECASE
    )

    # Pattern B: Macroeconomic metrics (Fiscal Deficit, Real GDP, Inflation)
    p_macro = re.compile(
        r"\b(Fiscal Deficit|Total Revenue|Revenue|Real GDP|GDP growth|Inflation Rate|Inflation|Headline Inflation|Gross Margin|Operating Margin|Capex|Capital Expenditure)\s+(?:for\s+(Q[1-4]\s*(?:FY\s*\d{2,4}|\d{4})?|FY\s*\d{2,4}|\d{4})\s+)?(?:was|is|stood at|reached|projected at|at|of)\s+([₹$€£·Rs\.]*\s*[\d,]+(?:\.\d+)?\s*(?:%|Cr|Crore|Lakh|Billion|Million|USD|INR|percent|per cent)?(?:\s+of\s+GDP)?)(?:\s+(?:in|for)\s+(Q[1-4]\s*(?:FY\s*\d{2,4}|\d{4})?|FY\s*\d{2,4}|\d{4}))?",
        re.IGNORECASE
    )

    for line in lines:
        if line.startswith("|") or line.startswith("["):
            continue

        m_corp = p_corp.search(line)
        if m_corp:
            ent = m_corp.group(1).strip()
            time_p = m_corp.group(5) or m_corp.group(2)
            met = m_corp.group(3).strip()
            val = m_corp.group(4).strip()
            unit_m = re.search(r"(%|Cr|Crore|Billion|Million|USD|INR|percent|per cent)", val)
            try:
                facts.append(AtomicFactSchema(
                    entity=ent,
                    metric=met,
                    value=val,
                    unit=unit_m.group(1) if unit_m else None,
                    time_period=time_p,
                    raw_text_evidence=line,
                    page_number=page_number
                ))
            except Exception:
                pass
            continue

        m_macro = p_macro.search(line)
        if m_macro:
            met = m_macro.group(1).strip()
            time_p = m_macro.group(2) or m_macro.group(4)
            val = m_macro.group(3).strip()
            unit_m = re.search(r"(%|Cr|Crore|Billion|Million|USD|INR|percent|per cent)", val)
            try:
                facts.append(AtomicFactSchema(
                    entity="General Economy",
                    metric=met,
                    value=val,
                    unit=unit_m.group(1) if unit_m else None,
                    time_period=time_p,
                    raw_text_evidence=line,
                    page_number=page_number
                ))
            except Exception:
                pass

    return facts


def extract_facts_from_document(
    db: Session,
    doc_id: int,
    parsed_content: dict
) -> List[ExtractedFact]:
    """
    Extracts atomic facts from parsed document content and persists them in SQLite.
    Uses Instructor + Gemini (gemini-2.5-flash) with strict quantitative instructions,
    falling back to table-first heuristic extraction if API key is missing or model call fails.
    """
    extracted_db_facts: List[ExtractedFact] = []
    all_pages = parsed_content.get("pages", [])
    pages = all_pages[:25]
    client = _get_instructor_gemini_client()
    
    # Environment control: 'fast' (100% offline heuristic, 0 API quota), 'smart' (budgeted 3 LLM calls), 'full'
    extraction_mode = os.getenv("EXTRACTION_MODE", "fast").lower()
    max_llm_pages = 0 if extraction_mode == "fast" else int(os.getenv("MAX_LLM_PAGES_PER_DOC", "3"))
    use_llm = client is not None and max_llm_pages > 0
    llm_calls_count = 0

    for page in pages:
        page_no = page.get("page_number", 1)
        text_content = page.get("text", "")
        tables = page.get("tables", [])

        if not text_content and not tables:
            continue

        page_evidence = text_content
        if tables:
            table_str = "\n\n".join([str(t) for t in tables])
            page_evidence = f"{page_evidence}\n\n### DATA TABLES:\n{table_str}"

        page_facts: List[AtomicFactSchema] = []

        # Use fast offline heuristic extraction first
        heuristic_facts = _heuristic_fact_extraction(page_no, page_evidence, tables=tables)

        # Only invoke LLM if heuristic detected ambiguous/dense content and LLM budget remains
        should_use_llm_for_page = (
            use_llm
            and llm_calls_count < max_llm_pages
            and (tables or len(heuristic_facts) < 2)
        )

        if should_use_llm_for_page:
            try:
                prompt = (
                    f"Extract all verifiable atomic quantitative facts from the following document page (Page {page_no}).\n"
                    "PRIORITIZE TABLES, FINANCIAL METRICS, FIGURES, AND CONCRETE VALUES.\n\n"
                    f"--- PAGE {page_no} CONTENT ---\n{page_evidence}"
                )

                response: ExtractedFactList = client.chat.completions.create(
                    model="gemini-2.5-flash",
                    response_model=ExtractedFactList,
                    messages=[
                        {
                            "role": "system",
                            "content": QUANTITATIVE_SYSTEM_PROMPT
                        },
                        {"role": "user", "content": prompt}
                    ]
                )
                llm_calls_count += 1
                if response and response.facts:
                    for f in response.facts:
                        f.page_number = page_no
                    page_facts.extend(response.facts)
            except Exception as e:
                err_str = str(e).lower()
                is_quota_error = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
                if is_quota_error:
                    logger.warning(
                        f"Gemini API rate limit / quota exhausted on page {page_no}. "
                        "Seamlessly switching to 100% local table-first extraction."
                    )
                    use_llm = False
                else:
                    logger.warning(f"LLM extraction encountered an error on page {page_no}: {e}. Using local heuristic.")

        # Fallback to heuristic facts if LLM wasn't called or produced no facts
        if not page_facts and heuristic_facts:
            page_facts = heuristic_facts
        elif not page_facts:
            page_facts = _heuristic_fact_extraction(page_no, page_evidence, tables=tables)

        # If still no facts found, record a fallback record for Failure Analysis
        if not page_facts:
            page_facts.append(
                AtomicFactSchema(
                    entity="System",
                    metric="Fact Extraction",
                    value="0 grounded facts detected",
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

