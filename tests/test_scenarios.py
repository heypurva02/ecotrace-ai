import pytest

from src.calculations import calculate_assessment
from src.models import ActivityInput, EmissionFactor
from src.scenario_engine import run_scenario

ELEC = EmissionFactor(
    factor_id="EF-ELEC-IN-GRID-ILLUS",
    name="grid",
    activity_category="Electricity",
    material_or_activity_type="electricity",
    factor_value=1.0,
    reference_activity_unit="kWh",
    provenance="illustrative",
)
ELEC2 = EmissionFactor(
    factor_id="EF-ELEC-RE-MIX-ILLUS",
    name="re",
    activity_category="Electricity",
    material_or_activity_type="electricity",
    factor_value=0.5,
    reference_activity_unit="kWh",
    provenance="illustrative",
)
PRIM = EmissionFactor(
    factor_id="EF-AL-PRIM-ILLUS",
    name="p",
    activity_category="Raw materials",
    material_or_activity_type="Primary aluminium",
    factor_value=10,
    reference_activity_unit="kg",
    provenance="illustrative",
)
REC = EmissionFactor(
    factor_id="EF-AL-REC-ILLUS",
    name="r",
    activity_category="Raw materials",
    material_or_activity_type="Recycled aluminium",
    factor_value=1,
    reference_activity_unit="kg",
    provenance="illustrative",
)
TRUCK = EmissionFactor(
    factor_id="EF-TRUCK-TKM-ILLUS",
    name="t",
    activity_category="Inbound transport",
    material_or_activity_type="freight",
    factor_value=1,
    reference_activity_unit="tkm",
    provenance="illustrative",
)
FACTORS = {f.factor_id: f for f in (ELEC, ELEC2, PRIM, REC, TRUCK)}


def activities():
    return [
        ActivityInput(
            category="Electricity",
            description="e",
            life_cycle_stage="Manufacturing",
            quantity=100,
            quantity_unit="kWh",
            factor_id="EF-ELEC-IN-GRID-ILLUS",
        ),
        ActivityInput(
            category="Raw materials",
            description="primary",
            life_cycle_stage="Raw material supply",
            quantity=80,
            quantity_unit="kg",
            factor_id="EF-AL-PRIM-ILLUS",
        ),
        ActivityInput(
            category="Raw materials",
            description="recycled",
            life_cycle_stage="Raw material supply",
            quantity=20,
            quantity_unit="kg",
            factor_id="EF-AL-REC-ILLUS",
        ),
        ActivityInput(
            category="Inbound transport",
            description="freight",
            life_cycle_stage="Inbound logistics",
            quantity=10,
            quantity_unit="tkm",
            factor_id="EF-TRUCK-TKM-ILLUS",
        ),
    ]


def test_scenario_reduces_emissions():
    payload = run_scenario(activities(), FACTORS, {"electricity_multiplier": 0.5})
    assert payload["scenario"].total_kg_co2e < payload["baseline"].total_kg_co2e
    assert payload["percent_difference"] == pytest.approx(50 / payload["baseline"].total_kg_co2e * 100)
    assert payload["label"] == "modelled improvement"


def test_scenario_increases_emissions():
    payload = run_scenario(activities(), FACTORS, {"electricity_multiplier": 2.0})
    assert payload["scenario"].total_kg_co2e > payload["baseline"].total_kg_co2e
    assert payload["percent_difference"] < 0
    assert payload["label"] == "modelled increase"


def test_scenario_zero_baseline():
    empty_like = [
        ActivityInput(
            category="Electricity",
            description="e",
            life_cycle_stage="Manufacturing",
            quantity=0,
            quantity_unit="kWh",
            factor_id="EF-ELEC-IN-GRID-ILLUS",
        )
    ]
    payload = run_scenario(empty_like, FACTORS, {"electricity_multiplier": 0.5})
    assert payload["baseline"].total_kg_co2e == 0
    assert payload["percent_difference"] is None
    assert payload["label"] == "undefined percentage"


def test_original_activities_not_mutated():
    original = activities()
    qty = original[0].quantity
    run_scenario(original, FACTORS, {"electricity_multiplier": 0.2})
    assert original[0].quantity == qty


def test_recycled_share_rebalance():
    payload = run_scenario(activities(), FACTORS, {"recycled_share": 1.0})
    rec = next(c for c in payload["scenario"].contributions if c.description == "recycled")
    prim = next(c for c in payload["scenario"].contributions if c.description == "primary")
    assert rec.quantity == pytest.approx(100)
    assert prim.quantity == pytest.approx(0)
