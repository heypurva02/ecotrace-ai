"""Formatting helpers and shared utilities."""

from __future__ import annotations

import json
from typing import Any, Optional

from src.config import BOUNDARIES
from src.models import CalculationResult, ContributionResult


def format_kg(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.1f} kg CO₂e"
    return f"{value:,.{digits}f} kg CO₂e"


def format_tonnes(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.4f} t CO₂e"


def format_number(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


def format_percent(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.1f}%"


def assessment_code(assessment_id: int) -> str:
    return f"AST-{int(assessment_id):04d}"


def boundary_explanation(boundary: str) -> str:
    spec = BOUNDARIES.get(boundary) or {}
    return spec.get("explanation", "")


def result_from_run_row(run: dict[str, Any], contributions: Optional[list[dict[str, Any]]] = None) -> CalculationResult:
    contrib_rows = contributions if contributions is not None else run.get("contributions") or []
    items = []
    for row in contrib_rows:
        snapshot = row.get("factor_snapshot_json") or row.get("factor_snapshot") or {}
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot) if snapshot else {}
        items.append(
            ContributionResult(
                activity_id=row.get("activity_id"),
                category=row.get("category") or "",
                description=row.get("description") or "",
                life_cycle_stage=row.get("life_cycle_stage") or "",
                quantity=row.get("quantity") or 0,
                quantity_unit=row.get("quantity_unit") or "",
                converted_quantity=row.get("converted_quantity"),
                converted_unit=row.get("converted_unit"),
                factor_id=row.get("factor_id"),
                factor_value=row.get("factor_value"),
                factor_unit=row.get("factor_unit"),
                source_reference=row.get("source_reference") or "",
                conversion_applied=row.get("conversion_applied") or "none",
                contribution_kg_co2e=row.get("contribution_kg_co2e") or 0,
                included=bool(row.get("included")),
                percentage=row.get("percentage") or 0,
                factor_snapshot=snapshot,
            )
        )
    warnings = run.get("warnings_json") or run.get("warnings") or []
    if isinstance(warnings, str):
        warnings = json.loads(warnings)
    quality = run.get("data_quality_json") or run.get("data_quality") or {}
    if isinstance(quality, str):
        quality = json.loads(quality) if quality else {}
    by_stage = run.get("by_stage_json") or run.get("by_stage") or {}
    if isinstance(by_stage, str):
        by_stage = json.loads(by_stage) if by_stage else {}
    by_category = run.get("by_category_json") or run.get("by_category") or {}
    if isinstance(by_category, str):
        by_category = json.loads(by_category) if by_category else {}
    return CalculationResult(
        assessment_id=run.get("assessment_id"),
        calculation_run_id=run.get("id") or run.get("calculation_run_id"),
        total_kg_co2e=run.get("total_kg_co2e") or 0,
        total_tonnes_co2e=run.get("total_tonnes_co2e") or 0,
        functional_unit=run.get("functional_unit") or "",
        functional_unit_quantity=run.get("functional_unit_quantity") or 1,
        footprint_per_functional_unit=run.get("footprint_per_fu") or run.get("footprint_per_functional_unit"),
        contributions=items,
        by_stage=by_stage,
        by_category=by_category,
        by_material={},
        included_activity_count=run.get("included_count") or 0,
        excluded_activity_count=run.get("excluded_count") or 0,
        missing_factor_count=run.get("missing_factor_count") or 0,
        warnings=warnings,
        factor_snapshots=[c.factor_snapshot for c in items if c.factor_snapshot],
        calculated_at=run.get("created_at") or "",
        methodology_version=run.get("methodology_version") or "",
        data_quality=quality,
        input_fingerprint=run.get("input_fingerprint") or "",
    )


def selected_stages_from_assessment(row: dict[str, Any]) -> list[str]:
    raw = row.get("selected_stages_json") or "[]"
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []
