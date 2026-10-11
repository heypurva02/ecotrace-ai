"""Create a validated assessment and run the deterministic calculation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import (
    ACTIVITY_CATEGORIES,
    BOUNDARIES,
    DATA_ORIGINS,
    LIFE_CYCLE_STAGES,
    MATERIAL_TYPES,
    TEMPLATE_CSV,
)
from src.import_export import (
    default_assessment_from_import,
    error_report_csv,
    file_sha256,
    read_upload,
    validate_import_frame,
)
from src.models import ActivityInput, AssessmentInput, ProductInput
from src.services import create_and_calculate, preview_calculation
from src.ui import bootstrap, issue_table
from src.utils import format_kg

db = bootstrap("New Assessment")
st.title("New Assessment")
st.caption("Enter activity data, review the boundary, then run the deterministic calculation.")

factors = db.factor_map()
factor_options = [""] + sorted(factors.keys())

tab_manual, tab_import = st.tabs(["Manual entry", "CSV / Excel import"])

with tab_manual:
    st.subheader("Product information")
    c1, c2, c3 = st.columns(3)
    product_name = c1.text_input("Product name")
    product_category = c2.text_input("Product category", value="Manufactured component")
    material = c3.selectbox("Material type", MATERIAL_TYPES)
    c4, c5, c6 = st.columns(3)
    assessment_name = c4.text_input("Assessment name / reference")
    production_quantity = c5.number_input("Production quantity", min_value=0.0, value=1000.0, step=1.0)
    production_unit = c6.text_input("Production quantity unit", value="units")
    c7, c8, c9 = st.columns(3)
    functional_unit = c7.text_input("Functional unit", value="1 unit")
    fu_quantity = c8.number_input(
        "Number of functional units in this production quantity",
        min_value=0.0,
        value=1000.0,
        help="Per-unit footprint = total kg CO₂e ÷ this number. Use a positive value with a clear meaning.",
    )
    reporting_period = c9.text_input("Reporting period", value="2024")
    location = st.text_input("Manufacturing location / country", value="India")
    notes = st.text_area("Assessment notes")

    st.subheader("Life-cycle boundary")
    boundary_key = st.selectbox(
        "Assessment boundary",
        list(BOUNDARIES.keys()),
        format_func=lambda k: BOUNDARIES[k]["label"],
    )
    st.info(BOUNDARIES[boundary_key]["explanation"])
    selected_stages = LIFE_CYCLE_STAGES
    if boundary_key == "selected":
        selected_stages = st.multiselect("Included stages", LIFE_CYCLE_STAGES, default=["Manufacturing"])
    elif boundary_key == "gate_to_gate":
        selected_stages = BOUNDARIES["gate_to_gate"]["stages"]
    st.markdown(
        f"**Boundary summary:** {BOUNDARIES[boundary_key]['label']} — included stages: "
        + ", ".join(selected_stages)
        + ". Only processes represented by activity data inside those stages are calculated."
    )

    st.subheader("Activity data")
    st.caption("Add or remove rows. A missing factor excludes the row from the numerical total.")
    default_rows = pd.DataFrame(
        [
            {
                "category": "Raw materials",
                "description": "",
                "life_cycle_stage": "Raw material supply",
                "quantity": 0.0,
                "quantity_unit": "kg",
                "factor_id": "",
                "supplier_note": "",
                "data_origin": "secondary",
                "evidence_reference": "",
            }
        ]
    )
    edited = st.data_editor(
        default_rows,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=ACTIVITY_CATEGORIES),
            "life_cycle_stage": st.column_config.SelectboxColumn("Stage", options=LIFE_CYCLE_STAGES),
            "factor_id": st.column_config.SelectboxColumn("Factor ID", options=factor_options),
            "data_origin": st.column_config.SelectboxColumn("Data origin", options=DATA_ORIGINS),
            "quantity": st.column_config.NumberColumn("Quantity", format="%.4f"),
        },
    )

    activities: list[ActivityInput] = []
    parse_errors = []
    for idx, row in edited.iterrows():
        if not str(row.get("description") or "").strip() and float(row.get("quantity") or 0) == 0:
            continue
        try:
            activities.append(
                ActivityInput(
                    category=str(row["category"]),
                    description=str(row["description"]),
                    life_cycle_stage=str(row["life_cycle_stage"]),
                    quantity=float(row["quantity"]),
                    quantity_unit=str(row["quantity_unit"]),
                    factor_id=str(row["factor_id"] or "") or None,
                    supplier_note=str(row.get("supplier_note") or ""),
                    data_origin=str(row.get("data_origin") or "secondary"),
                    evidence_reference=str(row.get("evidence_reference") or ""),
                )
            )
        except Exception as exc:
            parse_errors.append({"level": "error", "field": "row", "message": str(exc), "row": int(idx) + 1})

    product = ProductInput(
        name=product_name,
        category=product_category,
        material_type=material,
        notes=notes,
    )
    assessment = AssessmentInput(
        name=assessment_name,
        production_quantity=production_quantity,
        production_quantity_unit=production_unit,
        functional_unit=functional_unit,
        functional_unit_quantity=fu_quantity,
        reporting_period=reporting_period,
        location=location,
        boundary=boundary_key,
        selected_stages=list(selected_stages),
        notes=notes,
    )

    st.subheader("Calculation preview")
    preview = preview_calculation(product, assessment, activities, db)
    preview["errors"].extend(parse_errors)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Activity rows", preview["activity_count"])
    k2.metric("Mapped factors", preview["mapped_count"])
    k3.metric("Missing factors", preview["missing_factor_count"])
    k4.metric("Warnings", preview["warning_count"])
    k5.metric("Functional unit", preview["functional_unit"])
    if preview["errors"]:
        st.error("Validation errors must be corrected before calculation.")
        issue_table(preview["errors"])
    if preview["warnings"]:
        st.warning("Warnings will not block calculation, but they affect interpretation.")
        issue_table(preview["warnings"])

    if st.button("Run deterministic calculation and save", type="primary", disabled=not preview["can_calculate"] or bool(parse_errors)):
        try:
            payload = create_and_calculate(db, product, assessment, activities)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.session_state.selected_assessment_id = payload["assessment_id"]
            result = payload["result"]
            st.success(
                f"Assessment {payload['assessment_id']} saved. Total {format_kg(result.total_kg_co2e)}."
            )
            st.page_link("pages/4_Environmental_Analysis.py", label="Open environmental analysis")

with tab_import:
    st.subheader("Spreadsheet import")
    st.download_button(
        "Download blank template",
        data=TEMPLATE_CSV.read_bytes(),
        file_name="assessment_template.csv",
        mime="text/csv",
    )
    uploaded = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])
    if uploaded:
        raw = uploaded.getvalue()
        digest = file_sha256(raw)
        prior = db.find_import_hash(digest)
        if prior:
            st.warning(
                f"This file was imported before at {prior['imported_at']} "
                f"(log #{prior['id']}). Importing again may duplicate activity records."
            )
        try:
            frame = read_upload(uploaded.name, raw)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.write("Detected columns:", list(frame.columns))
            st.dataframe(frame.head(8), use_container_width=True)
            report = validate_import_frame(frame, factors)
            if report["missing_columns"]:
                st.error("Required columns are missing: " + ", ".join(report["missing_columns"]))
            st.write(
                f"Rows: {report.get('row_count', len(frame))} · valid: {report.get('valid_count', 0)} · "
                f"errors: {report.get('error_count', 0)} · warnings: {report.get('warning_count', 0)}"
            )
            if report["errors"]:
                issue_table(report["errors"])
                st.download_button(
                    "Download error report",
                    data=error_report_csv(report["rows"]),
                    file_name="import_errors.csv",
                    mime="text/csv",
                )
            if report["warnings"]:
                issue_table(report["warnings"])
            valid = report.get("valid_activities") or []
            if valid:
                st.info(f"{len(valid)} valid rows can be imported. Invalid rows are not discarded silently; they remain in the error report.")
                if st.button("Import valid rows and calculate"):
                    product, assessment = default_assessment_from_import(frame)
                    try:
                        payload = create_and_calculate(db, product, assessment, valid)
                    except Exception as exc:
                        st.error(str(exc))
                    else:
                        db.log_import(
                            filename=uploaded.name,
                            file_hash=digest,
                            row_count=report.get("row_count"),
                            valid_count=len(valid),
                            error_count=report.get("error_count"),
                            warning_count=report.get("warning_count"),
                            summary="Imported valid rows after confirmation",
                            assessment_id=payload["assessment_id"],
                        )
                        st.session_state.selected_assessment_id = payload["assessment_id"]
                        st.success(f"Imported assessment {payload['assessment_id']}.")
            elif not report["missing_columns"]:
                st.error("No valid rows are available to import. Correct the file and upload again.")
