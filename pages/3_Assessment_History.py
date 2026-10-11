"""Persistent assessment history."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.ui import bootstrap, empty_state, selected_id
from src.utils import assessment_code, format_kg

db = bootstrap("Assessment History")
st.title("Assessments History")
st.caption("Records persist in SQLite and remain after restarting Streamlit.")

search = st.text_input("Search by assessment, product, or material")
rows = db.list_assessments(search)
if not rows:
    empty_state("No assessments match the current filter.")
    st.stop()

table = pd.DataFrame(
    [
        {
            "ID": assessment_code(r["id"]),
            "Assessment": r["name"],
            "Product": r["product_name"],
            "Material": r["material_type"],
            "Quantity": f"{r['production_quantity']} {r['production_quantity_unit']}",
            "Functional unit": r["functional_unit"],
            "kg CO₂e": r["latest_total_kg"],
            "Calculated": r["latest_calc_at"],
            "Quality": r["data_quality_status"] or "Not calculated",
            "Demo": "Yes" if r["is_demo"] else "No",
        }
        for r in rows
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)

ids = [r["id"] for r in rows]
chosen = st.selectbox("Open details", ids, format_func=lambda i: f"{assessment_code(i)}")
if st.button("Use as selected assessment"):
    st.session_state.selected_assessment_id = int(chosen)
    st.rerun()

assessment_id = selected_id() or chosen
row = db.get_assessment(assessment_id)
st.subheader(f"{assessment_code(assessment_id)} · {row['product_name']}")
st.write(
    f"Boundary `{row['boundary']}` · {row['location']} · {row['reporting_period']} · "
    f"origin `{row['data_origin']}`"
)

runs = db.list_runs(assessment_id)
st.markdown("**Calculation runs (immutable)**")
if runs:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Run": r["id"],
                    "Type": r["run_type"],
                    "kg CO₂e": r["total_kg_co2e"],
                    "Fingerprint": (r["input_fingerprint"] or "")[:16],
                    "When": r["created_at"],
                    "Method": r["methodology_version"],
                }
                for r in runs
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    if len(runs) >= 2:
        a, b = st.columns(2)
        run_a = a.selectbox("Compare run A", [r["id"] for r in runs], key="run_a")
        run_b = b.selectbox("Compare run B", [r["id"] for r in runs], index=min(1, len(runs) - 1), key="run_b")
        ra, rb = db.get_run(run_a), db.get_run(run_b)
        st.write(
            f"Run {run_a}: {format_kg(ra['total_kg_co2e'])} vs run {run_b}: {format_kg(rb['total_kg_co2e'])}"
        )
        st.caption("Fingerprints match if activity data, factors, boundary, and methodology were identical.")
        st.code(f"A {ra['input_fingerprint']}\nB {rb['input_fingerprint']}")
else:
    empty_state("This assessment has no saved calculation runs.")

st.markdown("**Factor snapshots from the latest baseline**")
latest = db.get_latest_run(assessment_id, "baseline")
if latest:
    full = db.get_run(latest["id"])
    snaps = []
    for item in full["contributions"]:
        if not item.get("factor_snapshot_json"):
            continue
        snap = json.loads(item["factor_snapshot_json"])
        snaps.append(
            {
                "Activity": item["description"],
                "Factor": item["factor_id"],
                "Value stored": item["factor_value"],
                "Provenance": snap.get("provenance"),
                "Source": snap.get("source_title"),
            }
        )
    if snaps:
        st.dataframe(pd.DataFrame(snaps), use_container_width=True, hide_index=True)

st.markdown("**Saved scenarios**")
scenarios = db.list_scenarios(assessment_id)
if scenarios:
    st.dataframe(pd.DataFrame(scenarios)[["id", "name", "description", "created_at"]], hide_index=True, use_container_width=True)
else:
    st.caption("No saved scenarios.")

st.markdown("**Delete**")
st.caption("Deletes the assessment and dependent records. The rest of the database is kept.")
if st.checkbox("I understand this cannot be undone"):
    if st.button("Delete this assessment", type="primary"):
        db.delete_assessment(assessment_id)
        st.session_state.selected_assessment_id = None
        st.success("Assessment deleted.")
        st.rerun()
