from src.import_export import error_report_csv, read_upload, validate_import_frame
from src.factor_registry import load_factors_from_csv
from src.models import EmissionFactor
import pytest


def _factors():
    loaded = load_factors_from_csv()
    return {f.factor_id: f for f in loaded}


def test_valid_csv_import():
    csv = (
        "product_name,activity_name,activity_category,life_cycle_stage,quantity,quantity_unit,factor_id,source_note,data_origin,reporting_period\n"
        "Part,Grid,Electricity,Manufacturing,10,kWh,EF-ELEC-IN-GRID-ILLUS,note,primary,2024\n"
    ).encode()
    frame = read_upload("ok.csv", csv)
    report = validate_import_frame(frame, _factors())
    assert report["valid_count"] == 1
    assert report["error_count"] == 0


def test_valid_xlsx_import(tmp_path):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "product_name": "Part",
                "activity_name": "Grid",
                "activity_category": "Electricity",
                "life_cycle_stage": "Manufacturing",
                "quantity": 10,
                "quantity_unit": "kWh",
                "factor_id": "EF-ELEC-IN-GRID-ILLUS",
                "source_note": "n",
                "data_origin": "primary",
                "reporting_period": "2024",
            }
        ]
    )
    path = tmp_path / "ok.xlsx"
    frame.to_excel(path, index=False)
    loaded = read_upload("ok.xlsx", path.read_bytes())
    report = validate_import_frame(loaded, _factors())
    assert report["valid_count"] == 1


def test_missing_columns():
    data = b"hello,world\n1,2\n"
    frame = read_upload("x.csv", data)
    report = validate_import_frame(frame, _factors())
    assert report["missing_columns"]


def test_malformed_file():
    with pytest.raises(ValueError):
        read_upload("x.csv", b"")


def test_invalid_quantity():
    csv = (
        "product_name,activity_name,activity_category,life_cycle_stage,quantity,quantity_unit,factor_id,source_note,data_origin,reporting_period\n"
        "Part,Grid,Electricity,Manufacturing,abc,kWh,EF-ELEC-IN-GRID-ILLUS,n,primary,2024\n"
    ).encode()
    report = validate_import_frame(read_upload("x.csv", csv), _factors())
    assert report["error_count"] >= 1


def test_unknown_factor_id():
    csv = (
        "product_name,activity_name,activity_category,life_cycle_stage,quantity,quantity_unit,factor_id,source_note,data_origin,reporting_period\n"
        "Part,Grid,Electricity,Manufacturing,10,kWh,EF-DOES-NOT-EXIST,n,primary,2024\n"
    ).encode()
    report = validate_import_frame(read_upload("x.csv", csv), _factors())
    assert any("Unknown factor" in e["message"] for e in report["errors"])


def test_duplicate_rows_warning():
    csv = (
        "product_name,activity_name,activity_category,life_cycle_stage,quantity,quantity_unit,factor_id,source_note,data_origin,reporting_period\n"
        "Part,Grid,Electricity,Manufacturing,10,kWh,EF-ELEC-IN-GRID-ILLUS,n,primary,2024\n"
        "Part,Grid,Electricity,Manufacturing,10,kWh,EF-ELEC-IN-GRID-ILLUS,n,primary,2024\n"
    ).encode()
    report = validate_import_frame(read_upload("x.csv", csv), _factors())
    assert any(w["field"] == "duplicate" for w in report["warnings"])


def test_error_report_non_empty():
    csv = (
        "product_name,activity_name,activity_category,life_cycle_stage,quantity,quantity_unit,factor_id,source_note,data_origin,reporting_period\n"
        "Part,Grid,Electricity,Manufacturing,abc,kWh,EF-ELEC-IN-GRID-ILLUS,n,primary,2024\n"
    ).encode()
    report = validate_import_frame(read_upload("x.csv", csv), _factors())
    text = error_report_csv(report["rows"])
    assert "errors" in text
    assert "Part" in text
