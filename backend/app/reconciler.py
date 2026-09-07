import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models import ExtractedFact, FactRelationship, RelationshipType
from app.schemas import FactComparisonResult
from app.extractor import _get_instructor_gemini_client

logger = logging.getLogger(__name__)


def _compare_facts_heuristic(
    fact_a: ExtractedFact,
    fact_b: ExtractedFact
) -> FactComparisonResult:
    """Deterministic comparison logic used when LLM API is unavailable or for fallback."""
    val_a = (fact_a.value or "").strip().lower()
    val_b = (fact_b.value or "").strip().lower()

    time_a = (fact_a.time_period or "").strip().lower()
    time_b = (fact_b.time_period or "").strip().lower()

    # If either fact is a fallback anomaly or unknown
    if fact_a.entity == "System" or fact_b.entity == "System":
        return FactComparisonResult(
            relationship_type=RelationshipType.FAILURE_ANALYSIS,
            explanation_reasoning="One or both facts were flagged as system extraction anomalies."
        )

    # Identical values and identical time periods
    if val_a == val_b and (time_a == time_b or not time_a or not time_b):
        return FactComparisonResult(
            relationship_type=RelationshipType.CORROBORATES,
            explanation_reasoning=(
                f"Both documents agree on metric '{fact_a.metric}' for '{fact_a.entity}': "
                f"Value '{fact_a.value}' verified across sources."
            )
        )

    # Different time periods explains different values -> RECONCILED
    if time_a and time_b and time_a != time_b:
        return FactComparisonResult(
            relationship_type=RelationshipType.RECONCILED,
            explanation_reasoning=(
                f"Discrepancy explained by temporal context: Doc A reports for {fact_a.time_period} "
                f"({fact_a.value}), whereas Doc B reports for {fact_b.time_period} ({fact_b.value})."
            )
        )

    # Same time period (or both unstated) with differing values -> CONTRADICTS
    if val_a != val_b:
        return FactComparisonResult(
            relationship_type=RelationshipType.CONTRADICTS,
            explanation_reasoning=(
                f"Direct contradiction: Both documents report on '{fact_a.entity}' {fact_a.metric} "
                f"for the same period ({fact_a.time_period or 'unstated'}), but assert conflicting values "
                f"('{fact_a.value}' vs '{fact_b.value}')."
            )
        )

    return FactComparisonResult(
        relationship_type=RelationshipType.FAILURE_ANALYSIS,
        explanation_reasoning="Unable to conclusively resolve relationship between the fact pair."
    )


def reconcile_document_facts(db: Session, new_doc_id: int) -> List[FactRelationship]:
    """
    Compares facts from new_doc_id against existing facts from other documents in SQLite.
    Classifies relationships into CORROBORATES, CONTRADICTS, RECONCILED, or FAILURE_ANALYSIS.
    """
    new_facts = db.query(ExtractedFact).filter(ExtractedFact.document_id == new_doc_id).all()
    other_facts = db.query(ExtractedFact).filter(ExtractedFact.document_id != new_doc_id).all()

    if not new_facts or not other_facts:
        return []

    created_relationships: List[FactRelationship] = []
    client = _get_instructor_gemini_client()

    for n_fact in new_facts:
        for o_fact in other_facts:
            # Check for candidate entity/metric match
            same_entity = (
                n_fact.entity.lower() in o_fact.entity.lower() or
                o_fact.entity.lower() in n_fact.entity.lower()
            )
            same_metric = (
                n_fact.metric.lower() in o_fact.metric.lower() or
                o_fact.metric.lower() in n_fact.metric.lower()
            )

            # Only compare related pairs
            if not (same_entity or same_metric):
                continue

            comparison_result: Optional[FactComparisonResult] = None

            if client is not None:
                try:
                    prompt = (
                        "Analyze the following two atomic facts extracted from different documents and classify their relationship.\n"
                        "Classification categories:\n"
                        "- CORROBORATES: Both facts state the same factual conclusion or consistent values.\n"
                        "- CONTRADICTS: Direct irreconcilable disagreement on the same entity and time period.\n"
                        "- RECONCILED: Discrepancy is explainable by metadata (e.g. differing time periods, units, scopes).\n"
                        "- FAILURE_ANALYSIS: Inconclusive, ambiguous, or potential hallucination/extraction defect.\n\n"
                        f"Fact A (Doc ID {n_fact.document_id}, Page {n_fact.page_number}):\n"
                        f"Entity: {n_fact.entity} | Metric: {n_fact.metric} | Value: {n_fact.value} | "
                        f"Unit: {n_fact.unit} | Period: {n_fact.time_period}\n"
                        f"Evidence: {n_fact.raw_text_evidence}\n\n"
                        f"Fact B (Doc ID {o_fact.document_id}, Page {o_fact.page_number}):\n"
                        f"Entity: {o_fact.entity} | Metric: {o_fact.metric} | Value: {o_fact.value} | "
                        f"Unit: {o_fact.unit} | Period: {o_fact.time_period}\n"
                        f"Evidence: {o_fact.raw_text_evidence}\n"
                    )

                    comparison_result = client.chat.completions.create(
                        model="gemini-2.5-flash",
                        response_model=FactComparisonResult,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a senior auditor comparing claims across documents to identify consensus, conflicts, and contextual reconciliations."
                            },
                            {"role": "user", "content": prompt}
                        ]
                    )
                except Exception as e:
                    logger.warning(
                        f"LLM reconciliation failed between fact {n_fact.id} and {o_fact.id}: {e}. "
                        "Falling back to heuristic classifier."
                    )

            if comparison_result is None:
                comparison_result = _compare_facts_heuristic(n_fact, o_fact)

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

