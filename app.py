"""EcoTrace AI — Streamlit entry point (Dashboard)."""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from src.demo import load_demonstration_dataset
from src.ui import (
    PLOTLY_LAYOUT,
    bootstrap,
    chart_baseline_scenario,
    chart_by_category,
    chart_by_stage,
    empty_state,
    kpi_row,
    selected_id,
)
from src.utils import assessment_code, format_kg, format_number, result_from_run_row

db = bootstrap("Dashboard")

st.title("Dashboard")
st.caption("Screening indicators from saved assessments only. Empty values are shown as empty, not invented.")

load_col, _ = st.columns([1, 3])
with load_col:
    if st.button("Load demonstration dataset", use_container_width=True):
        created = load_demonstration_dataset(db)
        st.session_state.selected_assessment_id = created["aluminium"]
        st.success(
            f"Demonstration assessments ready (aluminium #{created['aluminium']}, steel #{created['steel']}). "
            "Existing demo records were reused if already present. User assessments were not overwritten."
        )
        st.rerun()

metrics = db.dashboard_metrics()
if metrics["total_assessments"] == 0:
    empty_state(
        "No assessments are stored yet. Create a new assessment or load the labelled demonstration dataset."
    )
    st.page_link("pages/2_New_Assessment.py", label="Go to New Assessment")
    st.stop()

latest = metrics["latest"]
kpi_row(
    [
        ("Assessments", str(metrics["total_assessments"]), "Saved in the local SQLite database"),
        ("Distinct products", str(metrics["distinct_products"]), "Unique product records assessed"),
        (
            "Latest footprint",
            format_kg(latest["total_kg_co2e"]) if latest else "—",
            latest["product_name"] if latest else "No calculation yet",
        ),
        (
            "Average per FU",
            format_number(metrics["average_footprint_per_fu"], 4)
            if metrics["average_footprint_per_fu"] is not None
            else "Not comparable",
            metrics["average_fu_label"] or "Mixed functional units are not averaged",
        ),
        (
            "Saved scenario delta",
            format_kg(metrics["potential_reduction_kg"]) if metrics["potential_reduction_kg"] is not None else "None saved",
            "Hypothetical modelled difference only",
        ),
        (
            "Incomplete / low evidence",
            str(metrics["low_quality_or_incomplete"]),
            "Missing factors or internal score below 60",
        ),
    ]
)

left, right = st.columns(2)
with left:
    recent = metrics["recent"]
    if recent:
        frame = pd.DataFrame(recent)
        frame["label"] = frame["id"].map(lambda i: assessment_code(int(i)))
        fig = px.bar(
            frame.sort_values("id"),
            x="label",
            y="total_kg_co2e",
            title="Recent assessment activity (saved totals)",
            hover_data=["product_name"],
        )
        fig.update_layout(**PLOTLY_LAYOUT, yaxis_title="kg CO₂e")
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No recent assessments to chart.")

assessment_id = selected_id()
with right:
    if assessment_id:
        run_row = db.get_latest_run(assessment_id, "baseline")
        if run_row:
            run = db.get_run(run_row["id"])
            result = result_from_run_row(run, run["contributions"])
            chart_by_stage(result.by_stage)
        else:
            empty_state("The selected assessment has not been calculated yet.")
    else:
        empty_state("Select an assessment to view stage-level emissions.")

c1, c2 = st.columns(2)
with c1:
    if assessment_id and db.get_latest_run(assessment_id, "baseline"):
        run = db.get_run(db.get_latest_run(assessment_id, "baseline")["id"])
        result = result_from_run_row(run, run["contributions"])
        chart_by_category(result.by_category)
    else:
        empty_state("Category chart needs a calculated assessment.")
with c2:
    scenario = db.get_latest_saved_scenario(assessment_id) if assessment_id else None
    if scenario:
        base = db.get_run(scenario["baseline_run_id"])
        alt = db.get_run(scenario["scenario_run_id"])
        if base and alt:
            chart_baseline_scenario(base["total_kg_co2e"], alt["total_kg_co2e"])
        else:
            empty_state("Saved scenario is missing a calculation run.")
    else:
        empty_state("No saved alternative scenario for the selected assessment.")

st.subheader("Recent assessments")
rows = db.list_assessments()
table = pd.DataFrame(
    [
        {
            "Assessment ID": assessment_code(r["id"]),
            "Product": r["product_name"],
            "Material": r["material_type"],
            "Production quantity": f"{r['production_quantity']} {r['production_quantity_unit']}",
            "Functional unit": r["functional_unit"],
            "Total kg CO₂e": r["latest_total_kg"],
            "Date": r["created_at"],
            "Data quality": r["data_quality_status"] or "Not calculated",
            "Demo": "Yes" if r["is_demo"] else "No",
            "_id": r["id"],
        }
        for r in rows
    ]
)
st.dataframe(table.drop(columns=["_id"]), use_container_width=True, hide_index=True)
choice = st.selectbox(
    "Open an assessment",
    options=[r["id"] for r in rows],
    format_func=lambda i: f"{assessment_code(i)} · {next(r['product_name'] for r in rows if r['id']==i)}",
)
if st.button("Open selected assessment"):
    st.session_state.selected_assessment_id = int(choice)
    st.switch_page("pages/4_Environmental_Analysis.py")
