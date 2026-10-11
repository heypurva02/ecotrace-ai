"""Application services that connect validation, calculation, and storage."""

from __future__ import annotations

import json
from typing import Any, Optional

from src.calculations import calculate_assessment
from src.data_quality import score_data_quality
from src.database import Database
from src.models import ActivityInput, AssessmentInput, CalculationResult, ProductInput
from src.recommendations import build_recommendations
from src.scenario_engine import run_scenario
from src.utils import selected_stages_from_assessment
from src.validation import split_issues, validate_activities, validate_assessment, validate_product


def assessment_input_from_row(row: dict[str, Any]) -> AssessmentInput:
    return AssessmentInput(
        name=row["name"],
        production_quantity=row["production_quantity"],
        production_quantity_unit=row["production_quantity_unit"],
        functional_unit=row["functional_unit"],
        functional_unit_quantity=row["functional_unit_quantity"],
        reporting_period=row["reporting_period"],
        location=row["location"],
        boundary=row["boundary"],
        selected_stages=selected_stages_from_assessment(row),
        notes=row.get("notes") or "",
        is_demo=bool(row.get("is_demo")),
        data_origin=row.get("data_origin") or "user",
    )


def preview_calculation(
    product: ProductInput,
    assessment: AssessmentInput,
    activities: list[ActivityInput],
    db: Database,
) -> dict[str, Any]:
    factors = db.factor_map()
    issues = validate_product(product) + validate_assessment(assessment) + validate_activities(
        activities, factors, included_stages=_stages(assessment)
    )
    errors, warnings = split_issues(issues)
    mapped = sum(1 for a in activities if (a.factor_id or "").strip() in factors)
    missing = sum(1 for a in activities if not (a.factor_id or "").strip() or (a.factor_id or "") not in factors)
    return {
        "issues": [i.as_dict() for i in issues],
        "errors": [i.as_dict() for i in errors],
        "warnings": [i.as_dict() for i in warnings],
        "activity_count": len(activities),
        "mapped_count": mapped,
        "missing_factor_count": missing,
        "warning_count": len(warnings),
        "functional_unit": assessment.functional_unit,
        "boundary": assessment.boundary,
        "can_calculate": len(errors) == 0,
    }


def create_and_calculate(
    db: Database,
    product: ProductInput,
    assessment: AssessmentInput,
    activities: list[ActivityInput],
    demo_key: Optional[str] = None,
) -> dict[str, Any]:
    preview = preview_calculation(product, assessment, activities, db)
    if not preview["can_calculate"]:
        raise ValueError("Calculation blocked by validation errors.")
    product_id = db.create_product(product)
    assessment_id = db.create_assessment(product_id, assessment, demo_key=demo_key)
    stored_ids = db.replace_activities(assessment_id, activities)
    for activity, stored_id in zip(activities, stored_ids):
        activity.activity_id = stored_id
    result = run_baseline(db, assessment_id)
    return {"assessment_id": assessment_id, "product_id": product_id, "result": result, "preview": preview}


def run_baseline(db: Database, assessment_id: int) -> CalculationResult:
    row = db.get_assessment(assessment_id)
    if not row:
        raise ValueError(f"Assessment {assessment_id} was not found.")
    assessment = assessment_input_from_row(row)
    activities = db.get_activities(assessment_id)
    factors = db.factor_map()
    result = calculate_assessment(
        activities,
        factors,
        assessment_id=assessment_id,
        functional_unit=assessment.functional_unit,
        functional_unit_quantity=assessment.functional_unit_quantity,
        boundary=assessment.boundary,
        selected_stages=assessment.selected_stages,
    )
    result.data_quality = score_data_quality(assessment, activities, result, factors)
    db.save_calculation_run(assessment_id, result, run_type="baseline")
    return result


def compute_unsaved_scenario(db: Database, assessment_id: int, modifications: dict[str, Any]) -> dict[str, Any]:
    row = db.get_assessment(assessment_id)
    if not row:
        raise ValueError(f"Assessment {assessment_id} was not found.")
    assessment = assessment_input_from_row(row)
    activities = db.get_activities(assessment_id)
    factors = db.factor_map()
    payload = run_scenario(
        activities,
        factors,
        modifications,
        assessment_id=assessment_id,
        functional_unit=assessment.functional_unit,
        functional_unit_quantity=assessment.functional_unit_quantity,
        boundary=assessment.boundary,
        selected_stages=assessment.selected_stages,
    )
    payload["scenario"].data_quality = score_data_quality(
        assessment, payload["modified_activities"], payload["scenario"], factors
    )
    return payload


def persist_scenario(
    db: Database,
    assessment_id: int,
    name: str,
    description: str,
    payload: dict[str, Any],
) -> int:
    latest = db.get_latest_run(assessment_id, "baseline")
    if not latest:
        raise ValueError("Save a baseline calculation before saving a scenario.")
    scenario_result: CalculationResult = payload["scenario"]
    scenario_run_id = db.save_calculation_run(assessment_id, scenario_result, run_type="scenario")
    contribs = [c.model_dump() for c in scenario_result.contributions]
    return db.save_scenario(
        assessment_id=assessment_id,
        name=name,
        description=description,
        modifications=payload["modifications"],
        baseline_run_id=latest["id"],
        scenario_run_id=scenario_run_id,
        scenario_contributions=contribs,
    )


def advisor_payload(db: Database, assessment_id: int) -> dict[str, Any]:
    row = db.get_assessment(assessment_id)
    run = db.get_run(db.get_latest_run(assessment_id, "baseline")["id"]) if db.get_latest_run(assessment_id, "baseline") else None
    if not row or not run:
        raise ValueError("Calculate the assessment before requesting advice.")
    from src.utils import result_from_run_row

    result = result_from_run_row(run, run.get("contributions"))
    scenario = db.get_latest_saved_scenario(assessment_id)
    scenario_summary = None
    if scenario:
        baseline_run = db.get_run(scenario["baseline_run_id"])
        scenario_run = db.get_run(scenario["scenario_run_id"])
        if baseline_run and scenario_run:
            from src.calculations import percentage_difference

            scenario_summary = {
                "baseline_kg": baseline_run["total_kg_co2e"],
                "scenario_kg": scenario_run["total_kg_co2e"],
                "percent_difference": percentage_difference(
                    baseline_run["total_kg_co2e"], scenario_run["total_kg_co2e"]
                ),
                "affected_categories": json.loads(scenario["modifications_json"]).keys(),
            }
    recs = build_recommendations(result, scenario_summary=scenario_summary)
    return {"result": result, "recommendations": recs, "assessment": row}


def _stages(assessment: AssessmentInput) -> list[str]:
    from src.calculations import resolve_included_stages

    return resolve_included_stages(assessment.boundary, assessment.selected_stages)
