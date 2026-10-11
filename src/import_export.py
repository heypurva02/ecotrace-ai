"""CSV/XLSX import and export helpers."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from src.config import MAX_UPLOAD_BYTES, TEMPLATE_CSV
from src.models import ActivityInput, AssessmentInput, EmissionFactor, ProductInput
from src.unit_conversion import units_compatible
from src.validation import ValidationIssue, validate_activity

REQUIRED_COLUMNS = [
    "product_name",
    "activity_name",
    "activity_category",
    "life_cycle_stage",
    "quantity",
    "quantity_unit",
    "factor_id",
    "source_note",
    "data_origin",
    "reporting_period",
]
OPTIONAL_COLUMNS = ["supplier", "assessment_name", "material_type", "functional_unit", "location"]


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_upload(filename: str, data: bytes) -> pd.DataFrame:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Only .csv and .xlsx files are accepted.")
    buffer = io.BytesIO(data)
    try:
        if suffix == ".csv":
            frame = pd.read_csv(buffer)
        else:
            frame = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"The file could not be parsed: {exc}") from None
    if frame.empty and list(frame.columns) == []:
        raise ValueError("The spreadsheet is empty or has no header row.")
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


def template_dataframe() -> pd.DataFrame:
    if TEMPLATE_CSV.exists():
        return pd.read_csv(TEMPLATE_CSV)
    return pd.DataFrame(columns=REQUIRED_COLUMNS + ["supplier"])


def validate_import_frame(
    frame: pd.DataFrame,
    factors: dict[str, EmissionFactor],
) -> dict[str, Any]:
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    detected = list(frame.columns)
    if missing_cols:
        return {
            "ok": False,
            "detected_columns": detected,
            "missing_columns": missing_cols,
            "rows": [],
            "errors": [
                ValidationIssue(
                    "error",
                    "columns",
                    f"Missing required columns: {', '.join(missing_cols)}.",
                ).as_dict()
            ],
            "warnings": [],
            "valid_activities": [],
            "preview": frame.head(8),
        }

    rows_out: list[dict[str, Any]] = []
    valid_activities: list[ActivityInput] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    signatures: dict[tuple, list[int]] = {}

    working = frame.copy()
    working["factor_id"] = working["factor_id"].fillna("").astype(str).str.strip()
    working["factor_id"] = working["factor_id"].replace({"nan": ""})

    for index, row in working.iterrows():
        excel_row = int(index) + 2
        quantity_raw = row.get("quantity")
        try:
            quantity = float(quantity_raw)
        except (TypeError, ValueError):
            quantity = None
        factor_id = str(row.get("factor_id") or "").strip()
        if factor_id.lower() in {"", "nan", "none"}:
            factor_id = ""
        activity = ActivityInput(
            category=str(row.get("activity_category") or "").strip(),
            description=str(row.get("activity_name") or "").strip(),
            life_cycle_stage=str(row.get("life_cycle_stage") or "").strip(),
            quantity=quantity if quantity is not None else 0,
            quantity_unit=str(row.get("quantity_unit") or "").strip(),
            factor_id=factor_id or None,
            supplier_note=str(row.get("supplier") or row.get("source_note") or ""),
            data_origin=str(row.get("data_origin") or "secondary"),
            evidence_reference=str(row.get("source_note") or ""),
        )
        issues = []
        if quantity is None:
            issues.append(
                ValidationIssue("error", "quantity", "Quantity is not numeric.", excel_row)
            )
        else:
            issues.extend(validate_activity(activity, factors, row=excel_row))
            if factor_id and factor_id in factors:
                factor = factors[factor_id]
                if not units_compatible(activity.quantity_unit, factor.reference_activity_unit):
                    # already added by validate_activity
                    pass
        row_errors = [i for i in issues if i.level == "error"]
        row_warnings = [i for i in issues if i.level == "warning"]
        status = "error" if row_errors else "warning" if row_warnings else "ok"
        record = {
            "row": excel_row,
            "product_name": str(row.get("product_name") or ""),
            "activity": activity.model_dump(),
            "status": status,
            "errors": [i.message for i in row_errors],
            "warnings": [i.message for i in row_warnings],
            "material_type": str(row.get("material_type") or "Aluminium"),
            "assessment_name": str(row.get("assessment_name") or ""),
            "functional_unit": str(row.get("functional_unit") or "1 unit"),
            "location": str(row.get("location") or "India"),
            "reporting_period": str(row.get("reporting_period") or ""),
        }
        rows_out.append(record)
        for issue in row_errors:
            errors.append(issue.as_dict())
        for issue in row_warnings:
            warnings.append(issue.as_dict())
        if not row_errors and quantity is not None:
            valid_activities.append(activity)
            sig = (
                activity.description,
                activity.category,
                activity.quantity,
                activity.quantity_unit,
                activity.factor_id,
            )
            signatures.setdefault(sig, []).append(excel_row)

    for _sig, row_numbers in signatures.items():
        if len(row_numbers) > 1:
            warnings.append(
                ValidationIssue(
                    "warning",
                    "duplicate",
                    f"Rows {row_numbers} appear identical.",
                    row_numbers[0],
                ).as_dict()
            )

    return {
        "ok": len(errors) == 0,
        "detected_columns": detected,
        "missing_columns": [],
        "rows": rows_out,
        "errors": errors,
        "warnings": warnings,
        "valid_activities": valid_activities,
        "preview": working.head(8),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "valid_count": len(valid_activities),
        "row_count": len(working),
    }


def activities_from_valid_rows(report: dict[str, Any]) -> list[ActivityInput]:
    return list(report.get("valid_activities") or [])


def default_assessment_from_import(frame: pd.DataFrame) -> tuple[ProductInput, AssessmentInput]:
    first = frame.iloc[0]
    product = ProductInput(
        name=str(first.get("product_name") or "Imported product"),
        category=str(first.get("product_category") or "Imported"),
        material_type=str(first.get("material_type") or "Aluminium"),
        notes="Created from spreadsheet import.",
    )
    assessment = AssessmentInput(
        name=str(first.get("assessment_name") or f"Import {first.get('product_name')}"),
        production_quantity=float(first.get("production_quantity") or 1),
        production_quantity_unit=str(first.get("production_quantity_unit") or "units"),
        functional_unit=str(first.get("functional_unit") or "1 unit"),
        functional_unit_quantity=float(first.get("functional_unit_quantity") or first.get("production_quantity") or 1),
        reporting_period=str(first.get("reporting_period") or "unspecified"),
        location=str(first.get("location") or "unspecified"),
        boundary="cradle_to_gate",
        notes="Imported spreadsheet data. Review boundary and production quantity before relying on totals.",
        data_origin="import",
    )
    return product, assessment


def error_report_csv(rows: list[dict[str, Any]]) -> str:
    failed = [r for r in rows if r.get("status") == "error"]
    frame = pd.DataFrame(
        [
            {
                "row": r["row"],
                "product_name": r.get("product_name"),
                "activity_name": (r.get("activity") or {}).get("description"),
                "errors": "; ".join(r.get("errors") or []),
            }
            for r in failed
        ]
    )
    return frame.to_csv(index=False)


def dataframe_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def write_excel_workbook(sheets: dict[str, pd.DataFrame], path: Union[str, Path, None] = None) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    data = buffer.getvalue()
    if path:
        Path(path).write_bytes(data)
    return data
