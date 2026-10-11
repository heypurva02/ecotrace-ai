"""Input validation for assessments and activity data."""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional

from src.config import ACTIVITY_CATEGORIES, BOUNDARIES, LIFE_CYCLE_STAGES, MATERIAL_TYPES
from src.models import ActivityInput, AssessmentInput, EmissionFactor, ProductInput
from src.unit_conversion import UnitConversionError, units_compatible


class ValidationIssue:
    def __init__(self, level: str, field: str, message: str, row: Optional[int] = None):
        self.level = level  # error | warning
        self.field = field
        self.message = message
        self.row = row

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "field": self.field,
            "message": self.message,
            "row": self.row,
        }


def _is_finite_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def validate_product(product: ProductInput) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not product.name.strip():
        issues.append(ValidationIssue("error", "product_name", "Product name cannot be blank."))
    if product.material_type not in MATERIAL_TYPES:
        issues.append(
            ValidationIssue(
                "error",
                "material_type",
                f"Material type must be one of: {', '.join(MATERIAL_TYPES)}.",
            )
        )
    elif product.material_type == "Other":
        issues.append(
            ValidationIssue(
                "warning",
                "material_type",
                "Factor coverage for 'Other' materials is limited in this prototype.",
            )
        )
    return issues


def validate_assessment(assessment: AssessmentInput) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not assessment.name.strip():
        issues.append(ValidationIssue("error", "assessment_name", "Assessment name cannot be blank."))
    if not _is_finite_number(assessment.production_quantity) or assessment.production_quantity <= 0:
        issues.append(
            ValidationIssue(
                "error",
                "production_quantity",
                "Production quantity must be a positive finite number.",
            )
        )
    if not assessment.functional_unit.strip():
        issues.append(ValidationIssue("error", "functional_unit", "Functional unit cannot be blank."))
    if (
        not _is_finite_number(assessment.functional_unit_quantity)
        or assessment.functional_unit_quantity <= 0
    ):
        issues.append(
            ValidationIssue(
                "error",
                "functional_unit_quantity",
                "Functional unit quantity must be a positive finite number.",
            )
        )
    if not assessment.reporting_period.strip():
        issues.append(ValidationIssue("error", "reporting_period", "Reporting period cannot be blank."))
    if not assessment.location.strip():
        issues.append(ValidationIssue("error", "location", "Manufacturing location cannot be blank."))
    if assessment.boundary not in BOUNDARIES:
        issues.append(ValidationIssue("error", "boundary", "Unknown assessment boundary."))
    if assessment.boundary == "selected" and not assessment.selected_stages:
        issues.append(
            ValidationIssue(
                "error",
                "selected_stages",
                "Select at least one life-cycle stage for a selected-stage boundary.",
            )
        )
    for stage in assessment.selected_stages:
        if stage not in LIFE_CYCLE_STAGES:
            issues.append(ValidationIssue("error", "selected_stages", f"Unknown stage: {stage}."))
    if assessment.production_quantity > 1e9:
        issues.append(
            ValidationIssue(
                "warning",
                "production_quantity",
                "Production quantity is unusually large. Confirm the unit before calculating.",
            )
        )
    return issues


def validate_activity(
    activity: ActivityInput,
    factors: dict[str, EmissionFactor],
    row: Optional[int] = None,
    included_stages: Optional[Iterable[str]] = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not activity.description.strip():
        issues.append(ValidationIssue("error", "description", "Activity description cannot be blank.", row))
    if activity.category not in ACTIVITY_CATEGORIES:
        issues.append(
            ValidationIssue(
                "error",
                "category",
                f"Unknown activity category '{activity.category}'.",
                row,
            )
        )
    if activity.life_cycle_stage not in LIFE_CYCLE_STAGES:
        issues.append(
            ValidationIssue(
                "error",
                "life_cycle_stage",
                f"Unknown life-cycle stage '{activity.life_cycle_stage}'.",
                row,
            )
        )
    if not _is_finite_number(activity.quantity):
        issues.append(
            ValidationIssue("error", "quantity", "Activity quantity must be a finite number.", row)
        )
    elif activity.quantity < 0:
        issues.append(
            ValidationIssue("error", "quantity", "Activity quantities cannot be negative.", row)
        )
    if not str(activity.quantity_unit).strip():
        issues.append(ValidationIssue("error", "quantity_unit", "Quantity unit cannot be blank.", row))

    factor_id = (activity.factor_id or "").strip()
    if not factor_id:
        issues.append(
            ValidationIssue(
                "warning",
                "factor_id",
                "No emission factor selected. This row will be excluded from the numerical total.",
                row,
            )
        )
    elif factor_id not in factors:
        issues.append(
            ValidationIssue(
                "error",
                "factor_id",
                f"Unknown factor ID '{factor_id}'. The application will not substitute another factor.",
                row,
            )
        )
    else:
        factor = factors[factor_id]
        if not _is_finite_number(factor.factor_value) or factor.factor_value < 0:
            issues.append(
                ValidationIssue(
                    "error",
                    "factor_value",
                    f"Factor {factor_id} is invalid (must be finite and non-negative).",
                    row,
                )
            )
        try:
            compatible = units_compatible(activity.quantity_unit, factor.reference_activity_unit)
        except UnitConversionError:
            compatible = False
        if not compatible:
            issues.append(
                ValidationIssue(
                    "error",
                    "quantity_unit",
                    (
                        f"Unit '{activity.quantity_unit}' is not compatible with factor "
                        f"{factor_id} reference unit '{factor.reference_activity_unit}'."
                    ),
                    row,
                )
            )
        if factor.provenance == "illustrative":
            issues.append(
                ValidationIssue(
                    "warning",
                    "factor_id",
                    f"Factor {factor_id} is illustrative and not suitable for external reporting.",
                    row,
                )
            )
        if activity.quantity > 1e8:
            issues.append(
                ValidationIssue(
                    "warning",
                    "quantity",
                    "Quantity is unusually large. Confirm the unit before calculating.",
                    row,
                )
            )

    if included_stages is not None and activity.life_cycle_stage not in set(included_stages):
        issues.append(
            ValidationIssue(
                "warning",
                "life_cycle_stage",
                "This activity is outside the selected boundary and will be excluded from the total.",
                row,
            )
        )
    return issues


def validate_activities(
    activities: list[ActivityInput],
    factors: dict[str, EmissionFactor],
    included_stages: Optional[Iterable[str]] = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not activities:
        issues.append(ValidationIssue("error", "activities", "Enter at least one activity row."))
        return issues
    signatures: dict[tuple, list[int]] = {}
    for index, activity in enumerate(activities, start=1):
        issues.extend(validate_activity(activity, factors, row=index, included_stages=included_stages))
        signature = (
            activity.category,
            activity.description.strip().lower(),
            activity.life_cycle_stage,
            round(float(activity.quantity), 6) if _is_finite_number(activity.quantity) else activity.quantity,
            str(activity.quantity_unit).strip().lower(),
            (activity.factor_id or "").strip(),
        )
        signatures.setdefault(signature, []).append(index)
    for _signature, rows in signatures.items():
        if len(rows) > 1:
            issues.append(
                ValidationIssue(
                    "warning",
                    "duplicate",
                    f"Rows {rows} look identical. Confirm they are not accidental duplicates.",
                    rows[0],
                )
            )
    return issues


def split_issues(issues: Iterable[ValidationIssue]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    return errors, warnings
