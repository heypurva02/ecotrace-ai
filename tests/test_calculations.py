import math

import pytest

from src.calculations import CalculationError, calculate_assessment, fingerprint_inputs, percentage_difference
from src.models import ActivityInput, EmissionFactor

FACTOR = EmissionFactor(
    factor_id="EF-TEST",
    name="Test electricity",
    activity_category="Electricity",
    material_or_activity_type="Electricity",
    factor_value=0.5,
    factor_unit="kg CO2e",
    reference_activity_unit="kWh",
    provenance="illustrative",
)
MASS = EmissionFactor(
    factor_id="EF-MASS",
    name="Test mass",
    activity_category="Raw materials",
    material_or_activity_type="Aluminium",
    factor_value=2.0,
    factor_unit="kg CO2e",
    reference_activity_unit="kg",
    provenance="illustrative",
)
FACTORS = {FACTOR.factor_id: FACTOR, MASS.factor_id: MASS}


def _act(**kwargs):
    base = dict(
        category="Electricity",
        description="Power",
        life_cycle_stage="Manufacturing",
        quantity=10,
        quantity_unit="kWh",
        factor_id="EF-TEST",
    )
    base.update(kwargs)
    return ActivityInput(**base)


def test_simple_multiplication():
    result = calculate_assessment([_act(quantity=10)], FACTORS)
    assert result.total_kg_co2e == pytest.approx(5.0)
    assert result.total_tonnes_co2e == pytest.approx(0.005)


def test_sum_of_multiple_activities():
    activities = [
        _act(quantity=10),
        _act(
            category="Raw materials",
            description="Metal",
            life_cycle_stage="Raw material supply",
            quantity=3,
            quantity_unit="kg",
            factor_id="EF-MASS",
        ),
    ]
    result = calculate_assessment(activities, FACTORS)
    assert result.total_kg_co2e == pytest.approx(5.0 + 6.0)


def test_wh_to_kwh_in_engine():
    result = calculate_assessment([_act(quantity=2000, quantity_unit="Wh")], FACTORS)
    assert result.total_kg_co2e == pytest.approx(1.0)


def test_grams_to_kg_in_engine():
    result = calculate_assessment(
        [
            _act(
                category="Raw materials",
                description="Metal",
                life_cycle_stage="Raw material supply",
                quantity=1500,
                quantity_unit="g",
                factor_id="EF-MASS",
            )
        ],
        FACTORS,
    )
    assert result.total_kg_co2e == pytest.approx(3.0)


def test_per_functional_unit():
    result = calculate_assessment([_act(quantity=10)], FACTORS, functional_unit_quantity=5, functional_unit="1 item")
    assert result.footprint_per_functional_unit == pytest.approx(1.0)


def test_zero_production_quantity_safe_denominator():
    result = calculate_assessment([_act()], FACTORS, functional_unit_quantity=0)
    assert result.total_kg_co2e == pytest.approx(5.0)
    assert result.footprint_per_functional_unit is None
    assert any("denominator" in w.lower() or "functional-unit" in w.lower() for w in result.warnings)


def test_negative_activity_quantity():
    with pytest.raises(CalculationError):
        calculate_assessment([_act(quantity=-1)], FACTORS)


def test_negative_emission_factor():
    bad = FACTOR.model_copy(update={"factor_value": -1})
    with pytest.raises(CalculationError):
        calculate_assessment([_act()], {"EF-TEST": bad})


def test_nan_and_inf():
    with pytest.raises(CalculationError):
        calculate_assessment([_act(quantity=math.nan)], FACTORS)
    with pytest.raises(CalculationError):
        calculate_assessment([_act(quantity=math.inf)], FACTORS)
    bad = FACTOR.model_copy(update={"factor_value": math.nan})
    with pytest.raises(CalculationError):
        calculate_assessment([_act()], {"EF-TEST": bad})


def test_missing_factor_excluded():
    result = calculate_assessment([_act(factor_id=None)], FACTORS)
    assert result.total_kg_co2e == pytest.approx(0)
    assert result.missing_factor_count == 1
    assert result.excluded_activity_count == 1


def test_incompatible_units_excluded():
    result = calculate_assessment([_act(quantity_unit="kg")], FACTORS)
    assert result.total_kg_co2e == pytest.approx(0)
    assert result.included_activity_count == 0
    assert any("Incompatible" in w for w in result.warnings)


def test_empty_activities():
    result = calculate_assessment([], FACTORS)
    assert result.total_kg_co2e == 0
    assert result.included_activity_count == 0


def test_zero_total_percentages():
    result = calculate_assessment([_act(factor_id=None)], FACTORS)
    assert all(c.percentage == 0 for c in result.contributions)


def test_stage_aggregation_and_percentages():
    activities = [
        _act(quantity=10),
        _act(
            category="Raw materials",
            description="Metal",
            life_cycle_stage="Raw material supply",
            quantity=5,
            quantity_unit="kg",
            factor_id="EF-MASS",
        ),
    ]
    result = calculate_assessment(activities, FACTORS)
    assert result.by_stage["Manufacturing"] == pytest.approx(5)
    assert result.by_stage["Raw material supply"] == pytest.approx(10)
    assert result.contributions[0].percentage + result.contributions[1].percentage == pytest.approx(100)


def test_reproducibility_fingerprint():
    a = calculate_assessment([_act(quantity=4)], FACTORS)
    b = calculate_assessment([_act(quantity=4)], FACTORS)
    assert a.total_kg_co2e == b.total_kg_co2e
    assert a.input_fingerprint == b.input_fingerprint
    assert len(a.input_fingerprint) == 64


def test_factor_snapshot_preserved():
    result = calculate_assessment([_act()], FACTORS)
    snap = result.contributions[0].factor_snapshot
    assert snap["factor_id"] == "EF-TEST"
    assert snap["factor_value"] == 0.5
    mutated = FACTOR.model_copy(update={"factor_value": 9})
    later = calculate_assessment([_act()], {mutated.factor_id: mutated})
    assert result.contributions[0].factor_value == 0.5
    assert later.contributions[0].factor_value == 9


def test_gate_to_gate_excludes_upstream():
    activities = [
        _act(),
        _act(
            category="Raw materials",
            description="Metal",
            life_cycle_stage="Raw material supply",
            quantity=5,
            quantity_unit="kg",
            factor_id="EF-MASS",
        ),
    ]
    result = calculate_assessment(activities, FACTORS, boundary="gate_to_gate")
    assert result.total_kg_co2e == pytest.approx(5)
    assert result.excluded_activity_count == 1


def test_percentage_difference_zero_baseline():
    assert percentage_difference(0, 5) is None
    assert percentage_difference(100, 80) == pytest.approx(20)
