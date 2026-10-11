"""Transparent heuristic data-quality scoring for the academic prototype.

This is an internal EcoTrace indicator, not a certified Pedigree-matrix result
and not a substitute for ISO data-quality assessment.
"""

from __future__ import annotations

from typing import Any

from src.config import ACTIVITY_CATEGORIES
from src.models import ActivityInput, AssessmentInput, CalculationResult, EmissionFactor

WEIGHTS = {
    "completeness": 0.25,
    "data_origin": 0.15,
    "geographic_relevance": 0.10,
    "temporal_relevance": 0.10,
    "technology_relevance": 0.10,
    "factor_documentation": 0.20,
    "unit_compatibility": 0.10,
}


def score_data_quality(
    assessment: AssessmentInput,
    activities: list[ActivityInput],
    result: CalculationResult,
    factors: dict[str, EmissionFactor],
) -> dict[str, Any]:
    deductions: list[str] = []
    missing_evidence: list[str] = []
    improvements: list[str] = []

    represented_categories = {a.category for a in activities}
    completeness_ratio = len(represented_categories) / max(len(ACTIVITY_CATEGORIES), 1)
    completeness = round(100 * completeness_ratio, 1)
    if completeness < 100:
        missing = [c for c in ACTIVITY_CATEGORIES if c not in represented_categories]
        deductions.append(f"Activity categories not represented: {', '.join(missing)}.")
        improvements.append("Add activity data for missing life-cycle categories before making broader claims.")

    if result.missing_factor_count:
        completeness = max(0.0, completeness - 15 * result.missing_factor_count)
        deductions.append(
            f"{result.missing_factor_count} activit"
            f"{'y is' if result.missing_factor_count == 1 else 'ies are'} missing a usable factor."
        )
        missing_evidence.append("Documented emission factors for rows currently excluded from the total.")

    origins = [a.data_origin for a in activities]
    primary_share = origins.count("primary") / max(len(origins), 1)
    data_origin = round(40 + 60 * primary_share, 1)
    if primary_share == 0:
        deductions.append("No primary (measured) activity data was identified.")
        improvements.append("Replace demonstration or secondary estimates with metered or supplier data.")

    location = (assessment.location or "").lower()
    geo_scores = []
    temporal_scores = []
    tech_scores = []
    doc_scores = []
    unit_score = 100.0
    illustrative_count = 0

    for item in result.contributions:
        if not item.included:
            if item.warning and "compatible" in (item.warning or "").lower():
                unit_score = min(unit_score, 40.0)
            continue
        snapshot = item.factor_snapshot or {}
        provenance = snapshot.get("provenance", "")
        geo = (snapshot.get("geographic_scope") or "").lower()
        if "global" in geo or not geo:
            geo_scores.append(55)
        elif any(token in location for token in geo.replace(",", " ").split() if len(token) > 3):
            geo_scores.append(90)
        elif "india" in geo and "india" in location:
            geo_scores.append(90)
        else:
            geo_scores.append(60)
            deductions.append(
                f"Factor {item.factor_id} geographic scope ({snapshot.get('geographic_scope')}) "
                f"may not match manufacturing location ({assessment.location})."
            )

        year = str(snapshot.get("reference_year") or "")
        if year.isdigit() and int(year) >= 2020:
            temporal_scores.append(85)
        elif year.isdigit() and int(year) >= 2015:
            temporal_scores.append(70)
        else:
            temporal_scores.append(50)
            deductions.append(f"Factor {item.factor_id} has limited temporal documentation.")

        if snapshot.get("technology_description"):
            tech_scores.append(80)
        else:
            tech_scores.append(55)

        documented = all(
            snapshot.get(field)
            for field in ("source_organisation", "source_title", "provenance")
        )
        if provenance == "verified" and documented:
            doc_scores.append(90)
        elif provenance == "illustrative":
            illustrative_count += 1
            doc_scores.append(35)
        elif documented:
            doc_scores.append(70)
        else:
            doc_scores.append(40)
            missing_evidence.append(f"Bibliographic details for factor {item.factor_id}.")

    geographic = _avg(geo_scores, default=50)
    temporal = _avg(temporal_scores, default=50)
    technology = _avg(tech_scores, default=50)
    documentation = _avg(doc_scores, default=40)

    if illustrative_count:
        deductions.append(
            f"{illustrative_count} included factor"
            f"{'' if illustrative_count == 1 else 's'} are illustrative demonstration values."
        )
        improvements.append(
            "Replace illustrative factors with documented, geographically applicable sources before any external use."
        )

    if result.excluded_activity_count:
        deductions.append(
            f"{result.excluded_activity_count} activity row(s) were excluded from the numerical total."
        )

    dimensions = {
        "completeness": max(0.0, min(100.0, completeness)),
        "data_origin": max(0.0, min(100.0, data_origin)),
        "geographic_relevance": max(0.0, min(100.0, geographic)),
        "temporal_relevance": max(0.0, min(100.0, temporal)),
        "technology_relevance": max(0.0, min(100.0, technology)),
        "factor_documentation": max(0.0, min(100.0, documentation)),
        "unit_compatibility": max(0.0, min(100.0, unit_score)),
    }
    overall = sum(dimensions[key] * WEIGHTS[key] for key in WEIGHTS)
    rating = _rating(overall)

    unique_deductions = list(dict.fromkeys(deductions))
    unique_missing = list(dict.fromkeys(missing_evidence))
    unique_improvements = list(dict.fromkeys(improvements))

    return {
        "overall_score": round(overall, 1),
        "rating": rating,
        "label": "Internal EcoTrace prototype indicator (not a certified data-quality score)",
        "dimensions": {k: round(v, 1) for k, v in dimensions.items()},
        "weights": WEIGHTS,
        "deductions": unique_deductions,
        "missing_evidence": unique_missing,
        "improvements": unique_improvements,
        "illustrative_factor_count": illustrative_count,
    }


def _avg(values: list[float], default: float) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def _rating(score: float) -> str:
    if score >= 80:
        return "Higher internal completeness"
    if score >= 60:
        return "Moderate internal completeness"
    if score >= 40:
        return "Limited evidence"
    return "Low evidence — demonstration only"
