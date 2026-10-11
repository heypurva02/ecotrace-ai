import json

import pytest

from src.database import Database
from src.factor_registry import seed_registry
from src.models import ActivityInput, AssessmentInput, ProductInput
from src.services import create_and_calculate, persist_scenario, compute_unsaved_scenario


def test_initialise(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "assessments" in tables
    assert "calculation_runs" in tables


def test_create_assessment_and_activities(tmp_path):
    db = Database(tmp_path / "t.db")
    seed_registry(db)
    product_id = db.create_product(ProductInput(name="P", category="c", material_type="Aluminium"))
    assessment_id = db.create_assessment(
        product_id,
        AssessmentInput(
            name="A",
            production_quantity=10,
            production_quantity_unit="units",
            functional_unit="1 unit",
            functional_unit_quantity=10,
            reporting_period="2024",
            location="India",
            boundary="cradle_to_gate",
        ),
    )
    db.replace_activities(
        assessment_id,
        [
            ActivityInput(
                category="Electricity",
                description="e",
                life_cycle_stage="Manufacturing",
                quantity=10,
                quantity_unit="kWh",
                factor_id="EF-ELEC-IN-GRID-ILLUS",
            )
        ],
    )
    assert len(db.get_activities(assessment_id)) == 1
    assert db.get_assessment(assessment_id)["name"] == "A"


def test_save_runs_and_history(tmp_path):
    db = Database(tmp_path / "t.db")
    seed_registry(db)
    payload = create_and_calculate(
        db,
        ProductInput(name="Can", category="pack", material_type="Aluminium"),
        AssessmentInput(
            name="A",
            production_quantity=100,
            production_quantity_unit="units",
            functional_unit="1 unit",
            functional_unit_quantity=100,
            reporting_period="2024",
            location="India",
            boundary="cradle_to_gate",
        ),
        [
            ActivityInput(
                category="Electricity",
                description="e",
                life_cycle_stage="Manufacturing",
                quantity=10,
                quantity_unit="kWh",
                factor_id="EF-ELEC-IN-GRID-ILLUS",
            )
        ],
    )
    first_run = payload["result"].calculation_run_id
    again = compute_unsaved_scenario(db, payload["assessment_id"], {"electricity_multiplier": 0.5})
    persist_scenario(db, payload["assessment_id"], "cut", "demo", again)
    runs = db.list_runs(payload["assessment_id"])
    assert len(runs) >= 2
    assert db.get_run(first_run)["total_kg_co2e"] == pytest.approx(payload["result"].total_kg_co2e)
    assert db.list_scenarios(payload["assessment_id"])


def test_foreign_keys(tmp_path):
    db = Database(tmp_path / "t.db")
    with pytest.raises(Exception):
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO assessments (
                    product_id, name, production_quantity, production_quantity_unit,
                    functional_unit, functional_unit_quantity, reporting_period, location,
                    boundary, created_at
                ) VALUES (999, 'x', 1, 'u', 'fu', 1, '2024', 'IN', 'cradle_to_gate', 'now')
                """
            )


def test_factor_snapshot_not_rewritten(tmp_path):
    db = Database(tmp_path / "t.db")
    seed_registry(db)
    payload = create_and_calculate(
        db,
        ProductInput(name="Can", category="pack", material_type="Aluminium"),
        AssessmentInput(
            name="A",
            production_quantity=1,
            production_quantity_unit="units",
            functional_unit="1",
            functional_unit_quantity=1,
            reporting_period="2024",
            location="India",
            boundary="cradle_to_gate",
        ),
        [
            ActivityInput(
                category="Electricity",
                description="e",
                life_cycle_stage="Manufacturing",
                quantity=1,
                quantity_unit="kWh",
                factor_id="EF-ELEC-IN-GRID-ILLUS",
            )
        ],
    )
    run_id = payload["result"].calculation_run_id
    original = db.get_factor("EF-ELEC-IN-GRID-ILLUS")
    updated = original.model_copy(update={"factor_value": 99.0, "provenance": "user_supplied"})
    db.upsert_factor(updated, overwrite_illustrative=True)
    stored = db.get_run(run_id)["contributions"][0]
    snap = json.loads(stored["factor_snapshot_json"])
    assert snap["factor_value"] == pytest.approx(original.factor_value)
    assert stored["factor_value"] == pytest.approx(original.factor_value)
