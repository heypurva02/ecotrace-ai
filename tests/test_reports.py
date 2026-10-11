from src.database import Database
from src.demo import load_demonstration_dataset
from src.report_generator import export_activity_csv, export_excel, export_summary_csv, generate_pdf_report


def test_pdf_and_csv_from_demo(tmp_path):
    db = Database(tmp_path / "t.db")
    created = load_demonstration_dataset(db)
    assessment_id = created["aluminium"]
    pdf_path = tmp_path / "report.pdf"
    pdf = generate_pdf_report(db, assessment_id, pdf_path)
    assert pdf_path.exists()
    assert len(pdf) > 1000
    assert b"EcoTrace AI" in pdf
    assert b"AST-" in pdf or b"Assessment" in pdf
    csv_bytes = export_summary_csv(db, assessment_id)
    assert b"total_kg_co2e" in csv_bytes
    activity_csv = export_activity_csv(db, assessment_id)
    assert b"contribution_kg_co2e" in activity_csv
    xlsx = export_excel(db, assessment_id, tmp_path / "w.xlsx")
    assert len(xlsx) > 100


def test_demo_loader_is_idempotent(tmp_path):
    db = Database(tmp_path / "t.db")
    first = load_demonstration_dataset(db)
    second = load_demonstration_dataset(db)
    assert first["aluminium"] == second["aluminium"]
    assert len(db.list_assessments()) == 2
