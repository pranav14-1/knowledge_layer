import os
import re
import logging
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models import ExtractedFact, FactRelationship, RelationshipType, Document
from app.schemas import FactComparisonResult
from app.extractor import _get_instructor_gemini_client

logger = logging.getLogger(__name__)

RECONCILER_SYSTEM_PROMPT = """You are an Executive Financial & Data Auditor. Your job is to provide a SHORT, DIRECT 1-SENTENCE REASONING explaining the relationship between Fact A and Fact B.

RULES FOR REASONING OUTPUT:
1. MAX 25 WORDS: Keep the explanation strictly under 25 words.
2. NO FLUFF: Do NOT use filler phrases like "Both documents report...", "According to the extracted text...", or "It can be observed that...".
3. HIGHLIGHT THE DELTA: Immediately state the exact difference in metric, value, date, or context.
4. USE DIRECT FORMULA FORMATS BASED ON TYPE:

- CORROBORATES:
  "Exact match: Both documents confirm [Metric] at [Value] for [Time Period]."
  
- CONTRADICTS:
  "Direct conflict: [Doc A] states [Value A] while [Doc B] states [Value B] for [Metric] in [Time Period]."
  
- RECONCILED:
  "Contextual difference: [Value A] ([Time Period A]) vs [Value B] ([Time Period B]) due to [Reason: vintage/scope/unit]."
  
- FAILURE_ANALYSIS:
  "Extraction gap: [Brief reason why comparison failed or data was ambiguous]."
"""


def _clean_doc_label(filename: Optional[str], default_id: int) -> str:
    """Produces clean, compact document name (e.g. 'IMF Report 2025' or 'Delhivery FY24')."""
    if not filename:
        return f"Doc {default_id}"
    base = os.path.basename(filename)
    name = re.sub(r"\.pdf$", "", base, flags=re.IGNORECASE)
    name = re.sub(r"^[0-9]+[-_]", "", name)
    name = name.replace("-", " ").replace("_", " ").strip()
    return name.title() if len(name) < 32 else name[:29].strip() + "..."


def _extract_number(val: str) -> Optional[float]:
    """Extracts first valid floating number from value string."""
    if not val:
        return None
    m = re.search(r"[-+]?[\d,]+(?:\.\d+)?", val)
    if m:
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None
    return None


def _is_comparable_pair(fact_a: ExtractedFact, fact_b: ExtractedFact) -> bool:
    """
    Pre-Filter Matching: ONLY compare two facts if they share a similar entity AND metric.
    Prevents comparing unrelated nouns (e.g. 'Skill' vs 'Tariffs') or cross-company figures.
    """
    banned = {"reported metric", "system", "unknown", "figure", "fact extraction"}
    if fact_a.metric.lower() in banned or fact_b.metric.lower() in banned:
        return False
    if fact_a.entity.lower() in banned or fact_b.entity.lower() in banned:
        return False

    ent_a = fact_a.entity.lower().strip()
    ent_b = fact_b.entity.lower().strip()
    met_a = fact_a.metric.lower().strip()
    met_b = fact_b.metric.lower().strip()

    clean_m_a = re.sub(r"\(.*?\)", "", met_a).strip()
    clean_m_b = re.sub(r"\(.*?\)", "", met_b).strip()

    # 1. Metric alignment check
    metric_matches = (
        clean_m_a in clean_m_b or clean_m_b in clean_m_a or
        (any(k in met_a for k in ["revenue", "sales", "turnover"]) and any(k in met_b for k in ["revenue", "sales", "turnover"])) or
        (any(k in met_a for k in ["deficit"]) and any(k in met_b for k in ["deficit"])) or
        (any(k in met_a for k in ["gdp"]) and any(k in met_b for k in ["gdp"])) or
        (any(k in met_a for k in ["inflation"]) and any(k in met_b for k in ["inflation"])) or
        (any(k in met_a for k in ["margin"]) and any(k in met_b for k in ["margin"])) or
        (any(k in met_a for k in ["capex", "capital expenditure"]) and any(k in met_b for k in ["capex", "capital expenditure"])) or
        (any(k in met_a for k in ["profit", "income"]) and any(k in met_b for k in ["profit", "income"])) or
        (any(k in met_a for k in ["receipts", "expenditure"]) and any(k in met_b for k in ["receipts", "expenditure"]))
    )
    if not metric_matches:
        return False

    # 2. Entity alignment check
    macro_entities = {"general economy", "central government", "government", "general government", "india", "union", "public sector"}
    is_macro_a = any(me in ent_a for me in macro_entities)
    is_macro_b = any(me in ent_b for me in macro_entities)
    if is_macro_a and is_macro_b:
        return True

    entity_matches = (
        ent_a in ent_b or ent_b in ent_a or
        any(w in ent_b for w in ent_a.split() if len(w) > 3)
    )
    return entity_matches


def _compare_facts_heuristic(
    fact_a: ExtractedFact,
    fact_b: ExtractedFact,
    doc_a_label: str = "Doc A",
    doc_b_label: str = "Doc B"
) -> FactComparisonResult:
    """Strict quantitative comparison logic following the 4 core cases with short, direct reasoning under 25 words."""
    val_a = (fact_a.value or "").strip()
    val_b = (fact_b.value or "").strip()

    time_a = (fact_a.time_period or "").strip()
    time_b = (fact_b.time_period or "").strip()
    norm_time_a = re.sub(r"[^a-z0-9]", "", time_a.lower())
    norm_time_b = re.sub(r"[^a-z0-9]", "", time_b.lower())

    unit_a = (fact_a.unit or "").strip()
    unit_b = (fact_b.unit or "").strip()

    num_a = _extract_number(val_a)
    num_b = _extract_number(val_b)

    metric_name = fact_a.metric or fact_b.metric or "metric"
    time_label = time_a or time_b or "the period"

    # If either fact is a fallback anomaly
    if fact_a.entity == "System" or fact_b.entity == "System":
        return FactComparisonResult(
            relationship_type=RelationshipType.FAILURE_ANALYSIS,
            explanation_reasoning="Extraction gap: Ingestion anomaly flagged in document fact extraction."
        )

    # 1. DIFFERENT TIME PERIODS -> RECONCILED (Vintage/temporal difference)
    if norm_time_a and norm_time_b and norm_time_a != norm_time_b:
        return FactComparisonResult(
            relationship_type=RelationshipType.RECONCILED,
            explanation_reasoning=(
                f"Contextual difference: {val_a} ({time_a}) vs {val_b} ({time_b}) due to periodic reporting vintage."
            )
        )

    # 2. DIFFERENT UNITS -> RECONCILED (e.g. % of GDP vs Absolute Currency)
    if unit_a and unit_b and unit_a.lower() != unit_b.lower():
        return FactComparisonResult(
            relationship_type=RelationshipType.RECONCILED,
            explanation_reasoning=(
                f"Contextual difference: {val_a} ({unit_a}) vs {val_b} ({unit_b}) due to differing measurement units."
            )
        )

    # 3. NUMERICAL EQUIVALENCE -> CORROBORATES
    if (num_a is not None and num_b is not None and abs(num_a - num_b) < 0.001) or val_a.lower() == val_b.lower():
        return FactComparisonResult(
            relationship_type=RelationshipType.CORROBORATES,
            explanation_reasoning=(
                f"Exact match: Both documents confirm {metric_name} at {val_a} for {time_label}."
            )
        )

    # 4. SAME TIME PERIOD & UNIT, BUT CONFLICTING NUMBERS -> CONTRADICTS
    if (norm_time_a == norm_time_b or not norm_time_a or not norm_time_b) and (val_a.lower() != val_b.lower()):
        return FactComparisonResult(
            relationship_type=RelationshipType.CONTRADICTS,
            explanation_reasoning=(
                f"Direct conflict: {doc_a_label} states {val_a} while {doc_b_label} states {val_b} for {metric_name} in {time_label}."
            )
        )

    return FactComparisonResult(
        relationship_type=RelationshipType.FAILURE_ANALYSIS,
        explanation_reasoning="Extraction gap: Unresolved ambiguity between extracted data claims."
    )


def reconcile_document_facts(db: Session, new_doc_id: int) -> List[FactRelationship]:
    """
    Compares facts from new_doc_id against existing facts from other documents in SQLite.
    Pre-filters candidate pairs and classifies relationships into:
    CORROBORATES, CONTRADICTS, RECONCILED, or FAILURE_ANALYSIS.
    Generates short, direct reasoning (< 25 words) highlighting the exact delta.
    """
    new_doc = db.query(Document).filter(Document.id == new_doc_id).first()
    chat_session_id = new_doc.chat_session_id if new_doc else None

    new_facts = (
        db.query(ExtractedFact)
        .options(joinedload(ExtractedFact.document))
        .filter(ExtractedFact.document_id == new_doc_id)
        .all()
    )
    other_facts_query = (
        db.query(ExtractedFact)
        .options(joinedload(ExtractedFact.document))
        .filter(ExtractedFact.document_id != new_doc_id)
    )
    if chat_session_id is not None:
        other_facts_query = other_facts_query.join(ExtractedFact.document).filter(Document.chat_session_id == chat_session_id)
    other_facts = other_facts_query.all()

    if not new_facts or not other_facts:
        return []

    created_relationships: List[FactRelationship] = []
    client = _get_instructor_gemini_client()
    use_llm = client is not None and os.getenv("RECONCILER_USE_LLM", "false").lower() == "true"
    llm_comparisons_count = 0
    max_comparisons = 50

    for n_fact in new_facts:
        if len(created_relationships) >= max_comparisons:
            break
        for o_fact in other_facts:
            if len(created_relationships) >= max_comparisons:
                break

            # STRICT PRE-FILTER MATCHING: only compare if entity AND metric align
            if not _is_comparable_pair(n_fact, o_fact):
                continue

            doc_a_label = _clean_doc_label(n_fact.document.filename if n_fact.document else None, n_fact.document_id)
            doc_b_label = _clean_doc_label(o_fact.document.filename if o_fact.document else None, o_fact.document_id)

            comparison_result: Optional[FactComparisonResult] = None

            # 1. Deterministic heuristic comparison (exact formulas, 0-cost, <1ms)
            heuristic_result = _compare_facts_heuristic(n_fact, o_fact, doc_a_label, doc_b_label)

            # 2. If heuristic is clear (CORROBORATES, CONTRADICTS, or RECONCILED), use directly without burning LLM quota
            if heuristic_result and heuristic_result.relationship_type != RelationshipType.FAILURE_ANALYSIS:
                comparison_result = heuristic_result
            elif use_llm and llm_comparisons_count < 3:
                try:
                    prompt = (
                        f"Compare Fact A from '{doc_a_label}' with Fact B from '{doc_b_label}'.\n\n"
                        f"Fact A [{doc_a_label}, Page {n_fact.page_number}]:\n"
                        f"- Entity: {n_fact.entity}\n"
                        f"- Metric: {n_fact.metric}\n"
                        f"- Value: {n_fact.value} (Unit: {n_fact.unit or 'N/A'}, Period: {n_fact.time_period or 'N/A'})\n"
                        f"- Evidence: {n_fact.raw_text_evidence}\n\n"
                        f"Fact B [{doc_b_label}, Page {o_fact.page_number}]:\n"
                        f"- Entity: {o_fact.entity}\n"
                        f"- Metric: {o_fact.metric}\n"
                        f"- Value: {o_fact.value} (Unit: {o_fact.unit or 'N/A'}, Period: {o_fact.time_period or 'N/A'})\n"
                        f"- Evidence: {o_fact.raw_text_evidence}\n\n"
                        f"Classify relationship and output a 1-sentence reasoning STRICTLY UNDER 25 WORDS following the required formula."
                    )

                    comparison_result = client.chat.completions.create(
                        model="gemini-2.5-flash",
                        response_model=FactComparisonResult,
                        messages=[
                            {
                                "role": "system",
                                "content": RECONCILER_SYSTEM_PROMPT
                            },
                            {"role": "user", "content": prompt}
                        ]
                    )
                    llm_comparisons_count += 1
                except Exception as e:
                    logger.warning(f"LLM reconciliation failed: {e}. Falling back to heuristic classifier.")
                    use_llm = False

            if comparison_result is None:
                comparison_result = heuristic_result

            relationship = FactRelationship(
                fact_a_id=n_fact.id,
                fact_b_id=o_fact.id,
                relationship_type=comparison_result.relationship_type,
                explanation_reasoning=comparison_result.explanation_reasoning
            )
            db.add(relationship)
            created_relationships.append(relationship)

    db.commit()
    for rel in created_relationships:
        db.refresh(rel)

    return created_relationships

