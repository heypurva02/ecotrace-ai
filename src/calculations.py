"""Deterministic screening LCA calculation engine.

This module must not import Streamlit or call an AI model.
Emissions are always: converted activity quantity × documented factor.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable, Optional

from src.config import BOUNDARIES, METHODOLOGY_VERSION
from src.models import (
    ActivityInput,
    CalculationResult,
    ContributionResult,
    EmissionFactor,
    utc_now_iso,
)
from src.unit_conversion import UnitConversionError, convert_quantity


class CalculationError(ValueError):
    """Invalid calculation input."""


def _finite(value: float, name: str) -> float:
    if value is None or not math.isfinite(float(value)):
        raise CalculationError(f"{name} must be a finite number.")
    return float(value)


def resolve_included_stages(boundary: str, selected_stages: Optional[Iterable[str]] = None) -> list[str]:
    spec = BOUNDARIES.get(boundary)
    if spec is None:
        raise CalculationError(f"Unknown boundary '{boundary}'.")
    if boundary == "selected":
        stages = list(selected_stages or [])
        if not stages:
            raise CalculationError("Selected-stage boundary requires at least one stage.")
        return stages
    return list(spec["stages"])


def _canonical_payload(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def fingerprint_inputs(
    activities: list[ActivityInput],
    factors: dict[str, EmissionFactor],
    functional_unit_quantity: float,
    functional_unit: str,
    boundary: str,
    included_stages: list[str],
    methodology_version: str,
) -> str:
    payload = {
        "activities": [a.model_dump() for a in activities],
        "factors": {
            fid: factors[fid].model_dump()
            for fid in sorted({(a.factor_id or "") for a in activities if a.factor_id})
            if fid in factors
        },
        "functional_unit_quantity": functional_unit_quantity,
        "functional_unit": functional_unit,
        "boundary": boundary,
        "included_stages": included_stages,
        "methodology_version": methodology_version,
    }
    return hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()


def calculate_assessment(
    activities: list[ActivityInput],
    factors: dict[str, EmissionFactor],
    *,
    assessment_id: Optional[int] = None,
    functional_unit: str = "1 unit",
    functional_unit_quantity: float = 1.0,
    boundary: str = "cradle_to_gate",
    selected_stages: Optional[list[str]] = None,
    methodology_version: str = METHODOLOGY_VERSION,
) -> CalculationResult:
    """Calculate screening GHG emissions from activity data and a factor registry."""
    included_stages = resolve_included_stages(boundary, selected_stages)
    fu_qty = _finite(functional_unit_quantity, "functional_unit_quantity")
    warnings: list[str] = []
    contributions: list[ContributionResult] = []
    missing_factor_count = 0
    included_count = 0
    excluded_count = 0

    for activity in activities:
        quantity = _finite(activity.quantity, f"quantity for '{activity.description}'")
        if quantity < 0:
            raise CalculationError(
                f"Activity '{activity.description}' has a negative quantity."
            )

        outside_boundary = activity.life_cycle_stage not in included_stages
        factor_id = (activity.factor_id or "").strip() or None
        factor = factors.get(factor_id) if factor_id else None

        contribution = ContributionResult(
            activity_id=activity.activity_id,
            category=activity.category,
            description=activity.description,
            life_cycle_stage=activity.life_cycle_stage,
            quantity=quantity,
            quantity_unit=activity.quantity_unit,
            factor_id=factor_id,
        )

        if outside_boundary:
            contribution.included = False
            contribution.warning = "Outside selected system boundary."
            excluded_count += 1
            warnings.append(
                f"'{activity.description}' is outside the {boundary} boundary and was excluded."
            )
            contributions.append(contribution)
            continue

        if not factor_id:
            contribution.included = False
            contribution.warning = "Missing emission factor."
            missing_factor_count += 1
            excluded_count += 1
            warnings.append(
                f"'{activity.description}' has no factor and was excluded from the total."
            )
            contributions.append(contribution)
            continue

        if factor is None:
            contribution.included = False
            contribution.warning = f"Unknown factor ID '{factor_id}'."
            missing_factor_count += 1
            excluded_count += 1
            warnings.append(
                f"'{activity.description}' references unknown factor '{factor_id}' "
                "and was excluded. No substitute factor was applied."
            )
            contributions.append(contribution)
            continue

        factor_value = _finite(factor.factor_value, f"factor {factor.factor_id}")
        if factor_value < 0:
            raise CalculationError(
                f"Emission factor {factor.factor_id} is negative."
            )

        try:
            converted = convert_quantity(
                quantity, activity.quantity_unit, factor.reference_activity_unit
            )
        except UnitConversionError as exc:
            contribution.included = False
            contribution.warning = str(exc)
            excluded_count += 1
            warnings.append(f"'{activity.description}': {exc}")
            contributions.append(contribution)
            continue

        emissions = converted.quantity * factor_value
        if not math.isfinite(emissions):
            raise CalculationError(
                f"Non-finite emissions result for '{activity.description}'."
            )

        snapshot = factor.model_dump()
        source_reference = "; ".join(
            part
            for part in [
                factor.source_organisation,
                factor.source_title,
                factor.reference_year,
                f"provenance={factor.provenance}",
            ]
            if part
        )
        contribution.converted_quantity = converted.quantity
        contribution.converted_unit = converted.to_unit
        contribution.factor_value = factor_value
        contribution.factor_unit = factor.factor_unit
        contribution.source_reference = source_reference
        contribution.conversion_applied = converted.conversion_applied
        contribution.contribution_kg_co2e = emissions
        contribution.included = True
        contribution.factor_snapshot = snapshot
        if factor.provenance == "illustrative":
            contribution.warning = "Illustrative factor."
            warnings.append(
                f"'{activity.description}' used illustrative factor {factor.factor_id}."
            )
        included_count += 1
        contributions.append(contribution)

    total = sum(c.contribution_kg_co2e for c in contributions if c.included)
    if not math.isfinite(total):
        raise CalculationError("Total emissions are not finite.")

    for item in contributions:
        if item.included and total > 0:
            item.percentage = (item.contribution_kg_co2e / total) * 100.0
        else:
            item.percentage = 0.0

    by_stage: dict[str, float] = {}
    by_category: dict[str, float] = {}
    by_material: dict[str, float] = {}
    for item in contributions:
        if not item.included:
            continue
        by_stage[item.life_cycle_stage] = by_stage.get(item.life_cycle_stage, 0.0) + item.contribution_kg_co2e
        by_category[item.category] = by_category.get(item.category, 0.0) + item.contribution_kg_co2e
        material_key = (item.factor_snapshot or {}).get("material_or_activity_type") or item.category
        by_material[str(material_key)] = by_material.get(str(material_key), 0.0) + item.contribution_kg_co2e

    footprint = total / fu_qty if fu_qty > 0 else None
    if fu_qty <= 0:
        warnings.append("Per-functional-unit footprint was not calculated because the denominator is not positive.")

    if not activities:
        warnings.append("No activity data was provided. Total emissions are 0 kg CO2e.")

    boundary_label = BOUNDARIES[boundary]["label"]
    fp = fingerprint_inputs(
        activities,
        factors,
        fu_qty,
        functional_unit,
        boundary,
        included_stages,
        methodology_version,
    )

    return CalculationResult(
        assessment_id=assessment_id,
        total_kg_co2e=total,
        total_tonnes_co2e=total / 1000.0,
        functional_unit=functional_unit,
        functional_unit_quantity=fu_qty,
        footprint_per_functional_unit=footprint,
        contributions=contributions,
        by_stage=by_stage,
        by_category=by_category,
        by_material=by_material,
        included_activity_count=included_count,
        excluded_activity_count=excluded_count,
        missing_factor_count=missing_factor_count,
        warnings=sorted(set(warnings)),
        factor_snapshots=[c.factor_snapshot for c in contributions if c.factor_snapshot],
        calculated_at=utc_now_iso(),
        methodology_version=methodology_version,
        input_fingerprint=fp,
        boundary_label=boundary_label,
        included_stages=included_stages,
    )


def percentage_difference(baseline: float, scenario: float) -> Optional[float]:
    """Return (baseline - scenario) / baseline * 100, or None if baseline is 0."""
    baseline = _finite(baseline, "baseline")
    scenario = _finite(scenario, "scenario")
    if baseline == 0:
        return None
    return (baseline - scenario) / baseline * 100.0
