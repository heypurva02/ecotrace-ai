"""Pydantic models for EcoTrace AI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class EmissionFactor(BaseModel):
    factor_id: str
    name: str
    activity_category: str
    material_or_activity_type: str
    factor_value: float
    factor_unit: str = "kg CO2e"
    reference_activity_unit: str
    geographic_scope: str = ""
    reference_year: str = ""
    technology_description: str = ""
    source_organisation: str = ""
    source_title: str = ""
    source_url: str = ""
    data_classification: str = ""
    source_publication: str = ""
    licence_note: str = ""
    uncertainty_note: str = ""
    provenance: str
    date_added: str = Field(default_factory=utc_now_iso)

    @field_validator("factor_id", "name", "reference_activity_unit", "provenance")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("This field cannot be blank.")
        return str(value).strip()


class ActivityInput(BaseModel):
    category: str
    description: str
    life_cycle_stage: str
    quantity: float
    quantity_unit: str
    factor_id: Optional[str] = None
    supplier_note: str = ""
    data_origin: str = "secondary"
    evidence_reference: str = ""
    include_in_total: bool = True
    activity_id: Optional[int] = None


class ProductInput(BaseModel):
    name: str
    category: str
    material_type: str
    notes: str = ""
    is_demo: bool = False


class AssessmentInput(BaseModel):
    name: str
    production_quantity: float
    production_quantity_unit: str
    functional_unit: str
    functional_unit_quantity: float
    reporting_period: str
    location: str
    boundary: str
    selected_stages: list[str] = Field(default_factory=list)
    notes: str = ""
    is_demo: bool = False
    data_origin: str = "user"


class ContributionResult(BaseModel):
    activity_id: Optional[int] = None
    category: str
    description: str
    life_cycle_stage: str
    quantity: float
    quantity_unit: str
    converted_quantity: Optional[float] = None
    converted_unit: Optional[str] = None
    factor_id: Optional[str] = None
    factor_value: Optional[float] = None
    factor_unit: Optional[str] = None
    source_reference: str = ""
    conversion_applied: str = "none"
    contribution_kg_co2e: float = 0.0
    included: bool = False
    percentage: float = 0.0
    factor_snapshot: dict[str, Any] = Field(default_factory=dict)
    warning: Optional[str] = None


class CalculationResult(BaseModel):
    assessment_id: Optional[int] = None
    calculation_run_id: Optional[int] = None
    total_kg_co2e: float
    total_tonnes_co2e: float
    functional_unit: str
    functional_unit_quantity: float
    footprint_per_functional_unit: Optional[float]
    contributions: list[ContributionResult]
    by_stage: dict[str, float]
    by_category: dict[str, float]
    by_material: dict[str, float]
    included_activity_count: int
    excluded_activity_count: int
    missing_factor_count: int
    warnings: list[str]
    factor_snapshots: list[dict[str, Any]]
    calculated_at: str
    methodology_version: str
    data_quality: dict[str, Any] = Field(default_factory=dict)
    input_fingerprint: str = ""
    boundary_label: str = ""
    included_stages: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    recommendation_id: str
    title: str
    explanation: str
    supporting_observation: str
    relevant_activity_or_category: str
    suggested_action: str
    expected_direction: str
    confidence_status: str
    required_next_data: str
    limitations: str
