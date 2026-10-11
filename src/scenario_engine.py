"""What-if modifications applied to a copy of activity data.

The original assessment is never mutated. Recycled-content and yield changes
are applied only when the activity set contains the required material rows.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from src.calculations import CalculationError, calculate_assessment, percentage_difference
from src.models import ActivityInput, CalculationResult, EmissionFactor

ELECTRICITY_CATEGORIES = {"Electricity"}
TRANSPORT_CATEGORIES = {"Inbound transport", "Outbound transport"}
PRIMARY_AL_FACTORS = {"EF-AL-PRIM-ILLUS"}
RECYCLED_AL_FACTORS = {"EF-AL-REC-ILLUS"}
PRIMARY_STEEL_FACTORS = {"EF-STEEL-BOF-ILLUS"}
RECYCLED_STEEL_FACTORS = {"EF-STEEL-EAF-ILLUS"}


class ScenarioError(ValueError):
    """Unsupported or invalid scenario modification."""


def apply_modifications(
    activities: list[ActivityInput],
    modifications: dict[str, Any],
    factors: dict[str, EmissionFactor],
) -> tuple[list[ActivityInput], list[str], list[str]]:
    """Return copied activities, warnings, and affected categories."""
    copied = [ActivityInput.model_validate(a.model_dump()) for a in activities]
    warnings: list[str] = []
    affected: set[str] = set()

    elec_mult = modifications.get("electricity_multiplier")
    if elec_mult is not None:
        _require_positive(elec_mult, "electricity_multiplier")
        count = 0
        for row in copied:
            if row.category in ELECTRICITY_CATEGORIES:
                row.quantity = row.quantity * float(elec_mult)
                affected.add(row.category)
                count += 1
        if count == 0:
            warnings.append("No electricity activity rows were found, so electricity consumption was not changed.")

    new_elec_factor = (modifications.get("electricity_factor_id") or "").strip()
    if new_elec_factor:
        if new_elec_factor not in factors:
            raise ScenarioError(f"Unknown electricity factor '{new_elec_factor}'.")
        count = 0
        for row in copied:
            if row.category in ELECTRICITY_CATEGORIES:
                row.factor_id = new_elec_factor
                affected.add(row.category)
                count += 1
        if count == 0:
            warnings.append("No electricity activity rows were found, so the electricity factor was not changed.")

    trans_mult = modifications.get("transport_distance_multiplier")
    if trans_mult is not None:
        _require_positive(trans_mult, "transport_distance_multiplier")
        count = 0
        for row in copied:
            if row.category in TRANSPORT_CATEGORIES:
                row.quantity = row.quantity * float(trans_mult)
                affected.add(row.category)
                count += 1
        if count == 0:
            warnings.append("No transport activity rows were found, so transport distance was not changed.")

    recycled_share = modifications.get("recycled_share")
    if recycled_share is not None:
        share = float(recycled_share)
        if share < 0 or share > 1:
            raise ScenarioError("Recycled-material share must be between 0 and 1.")
        applied = _apply_recycled_share(copied, share, factors)
        if applied:
            affected.add("Raw materials")
        else:
            warnings.append(
                "Recycled-content change was not applied: the assessment does not contain "
                "paired primary and recycled material factors supported by this prototype."
            )

    yield_value = modifications.get("manufacturing_yield")
    if yield_value is not None:
        y = float(yield_value)
        if y <= 0 or y > 1.5:
            raise ScenarioError("Manufacturing yield must be greater than 0 and at most 1.5.")
        if y > 1:
            warnings.append("Yield above 1.0 is unusual; inputs were still scaled as 1/yield.")
        scale = 1.0 / y
        for row in copied:
            if row.category in {"Raw materials", "Electricity", "Fuel and direct energy use"}:
                row.quantity = row.quantity * scale
                affected.add(row.category)
        warnings.append(
            f"Manufacturing yield of {y:.2f} scaled selected input categories by {scale:.4f} "
            "(inputs required per unit output)."
        )

    return copied, warnings, sorted(affected)


def run_scenario(
    activities: list[ActivityInput],
    factors: dict[str, EmissionFactor],
    modifications: dict[str, Any],
    *,
    assessment_id: Optional[int] = None,
    functional_unit: str = "1 unit",
    functional_unit_quantity: float = 1.0,
    boundary: str = "cradle_to_gate",
    selected_stages: Optional[list[str]] = None,
    baseline: Optional[CalculationResult] = None,
) -> dict[str, Any]:
    if baseline is None:
        baseline = calculate_assessment(
            activities,
            factors,
            assessment_id=assessment_id,
            functional_unit=functional_unit,
            functional_unit_quantity=functional_unit_quantity,
            boundary=boundary,
            selected_stages=selected_stages,
        )
    modified, warnings, affected = apply_modifications(activities, modifications, factors)
    scenario = calculate_assessment(
        modified,
        factors,
        assessment_id=assessment_id,
        functional_unit=functional_unit,
        functional_unit_quantity=functional_unit_quantity,
        boundary=boundary,
        selected_stages=selected_stages,
    )
    pct = percentage_difference(baseline.total_kg_co2e, scenario.total_kg_co2e)
    if baseline.total_kg_co2e == 0:
        warnings.append("Baseline emissions are zero, so a percentage difference is not defined.")
        label = "undefined percentage"
    elif pct is not None and pct > 0.0001:
        label = "modelled improvement"
    elif pct is not None and pct < -0.0001:
        label = "modelled increase"
    else:
        label = "no modelled change"

    abs_diff = baseline.total_kg_co2e - scenario.total_kg_co2e
    return {
        "baseline": baseline,
        "scenario": scenario,
        "modified_activities": modified,
        "modifications": deepcopy(modifications),
        "warnings": warnings + scenario.warnings,
        "affected_categories": affected,
        "absolute_difference_kg": abs_diff,
        "percent_difference": pct,
        "label": label,
        "baseline_kg": baseline.total_kg_co2e,
        "scenario_kg": scenario.total_kg_co2e,
    }


def _apply_recycled_share(
    activities: list[ActivityInput],
    recycled_share: float,
    factors: dict[str, EmissionFactor],
) -> bool:
    al_rows = [
        a
        for a in activities
        if a.category == "Raw materials"
        and (a.factor_id in PRIMARY_AL_FACTORS or a.factor_id in RECYCLED_AL_FACTORS)
    ]
    st_rows = [
        a
        for a in activities
        if a.category == "Raw materials"
        and (a.factor_id in PRIMARY_STEEL_FACTORS or a.factor_id in RECYCLED_STEEL_FACTORS)
    ]
    if al_rows:
        return _rebalance(al_rows, recycled_share, PRIMARY_AL_FACTORS, RECYCLED_AL_FACTORS)
    if st_rows:
        return _rebalance(st_rows, recycled_share, PRIMARY_STEEL_FACTORS, RECYCLED_STEEL_FACTORS)
    return False


def _rebalance(
    rows: list[ActivityInput],
    recycled_share: float,
    primary_ids: set[str],
    recycled_ids: set[str],
) -> bool:
    total_mass = sum(r.quantity for r in rows)
    if total_mass <= 0:
        return False
    primary_rows = [r for r in rows if r.factor_id in primary_ids]
    recycled_rows = [r for r in rows if r.factor_id in recycled_ids]
    if not primary_rows or not recycled_rows:
        return False
    recycled_mass = total_mass * recycled_share
    primary_mass = total_mass - recycled_mass
    _set_mass(primary_rows, primary_mass)
    _set_mass(recycled_rows, recycled_mass)
    return True


def _set_mass(rows: list[ActivityInput], mass: float) -> None:
    current = sum(r.quantity for r in rows) or 1.0
    for row in rows:
        row.quantity = mass * (row.quantity / current) if current else mass / len(rows)


def _require_positive(value: Any, name: str) -> None:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ScenarioError(f"{name} must be numeric.") from exc
    if number <= 0:
        raise ScenarioError(f"{name} must be greater than zero.")
    if number > 5:
        raise ScenarioError(f"{name} is outside the supported modelling range (0–5).")


# Keep CalculationError imported for callers that catch engine errors.
__all__ = [
    "ScenarioError",
    "apply_modifications",
    "run_scenario",
    "CalculationError",
]
