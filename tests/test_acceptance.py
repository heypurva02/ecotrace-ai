"""End-to-end journey through Python APIs (no browser)."""

from src.database import Database
from src.demo import load_demonstration_dataset
from src.report_generator import export_summary_csv, generate_pdf_report
from src.services import compute_unsaved_scenario, persist_scenario
from src.utils import result_from_run_row


def test_demo_journey(tmp_path):
    db = Database(tmp_path / "ecotrace.db")
    created = load_demonstration_dataset(db)
    assessment_id = created["aluminium"]
    row = db.get_assessment(assessment_id)
    assert row["is_demo"] == 1
    activities = db.get_activities(assessment_id)
    assert len(activities) >= 8
    assert any(a.factor_id is None or a.factor_id == "" for a in activities)
    run = db.get_latest_run(assessment_id, "baseline")
    assert run is not None
    full = db.get_run(run["id"])
    result = result_from_run_row(full, full["contributions"])
    assert result.total_kg_co2e > 0
    assert result.by_category
    payload = compute_unsaved_scenario(db, assessment_id, {"electricity_multiplier": 0.8})
    assert payload["scenario"].total_kg_co2e != payload["baseline"].total_kg_co2e
    persist_scenario(db, assessment_id, "acceptance", "test", payload)
    pdf = generate_pdf_report(db, assessment_id, tmp_path / "a.pdf")
    assert len(pdf) > 1000
    csv = export_summary_csv(db, assessment_id)
    assert str(run["total_kg_co2e"]).encode() in csv or b"total_kg_co2e" in csv
    # reopen a new Database object on the same file (simulates restart)
    db2 = Database(tmp_path / "ecotrace.db")
    assert db2.get_assessment(assessment_id)
    assert db2.list_scenarios(assessment_id)
