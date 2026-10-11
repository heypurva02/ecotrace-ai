"""Interactive what-if simulator using the same calculation engine."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.scenario_engine import ScenarioError
from src.services import compute_unsaved_scenario, persist_scenario
from src.ui import bootstrap, chart_baseline_scenario, delta_caption, empty_state, kpi_row, require_assessment
from src.utils import format_kg, format_number

db = bootstrap("Scenario Optimiser")
st.title("Scenario Optimiser")
st.caption("The original assessment is not modified until you explicitly save a scenario.")

row = require_assessment(db)
if not row:
    st.stop()
if not db.get_latest_run(row["id"], "baseline"):
    empty_state("Calculate a baseline before modelling scenarios.")
    st.stop()

factors = db.factor_map()
electricity_factors = [f.factor_id for f in factors.values() if f.activity_category == "Electricity"]

st.subheader("Supported modifications")
electricity_pct = st.slider("Electricity consumption relative to baseline", 50, 150, 100, 1, help="100% keeps current electricity quantities.")
alt_factor = st.selectbox(
    "Electricity factor",
    options=["(keep current)"] + electricity_factors,
    help="Only documented registry alternatives can be selected. No invented factors.",
)
transport_pct = st.slider("Transport activity (tkm) relative to baseline", 50, 150, 100, 1)
recycled = st.slider(
    "Recycled-material share (aluminium or steel pairs only)",
    0.0,
    1.0,
    0.25,
    0.05,
    help="Reallocates existing primary/recycled material mass. Disabled in effect if those rows are absent.",
)
apply_recycled = st.checkbox("Apply recycled-share rebalance", value=False)
yield_value = st.slider("Manufacturing yield", 0.70, 1.00, 1.00, 0.01)
apply_yield = st.checkbox("Apply yield scaling to material, electricity, and fuel inputs", value=False)

modifications = {"electricity_multiplier": electricity_pct / 100.0}
if alt_factor != "(keep current)":
    modifications["electricity_factor_id"] = alt_factor
modifications["transport_distance_multiplier"] = transport_pct / 100.0
if apply_recycled:
    modifications["recycled_share"] = recycled
if apply_yield:
    modifications["manufacturing_yield"] = yield_value

try:
    payload = compute_unsaved_scenario(db, row["id"], modifications)
except (ScenarioError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

baseline = payload["baseline"]
scenario = payload["scenario"]
kpi_row(
    [
        ("Baseline", format_kg(baseline.total_kg_co2e), "Unmodified saved model"),
        ("Scenario", format_kg(scenario.total_kg_co2e), payload["label"]),
        ("Absolute difference", format_kg(payload["absolute_difference_kg"]), "Baseline minus scenario"),
        (
            "Per FU (scenario)",
            format_number(scenario.footprint_per_functional_unit, 4),
            scenario.functional_unit,
        ),
    ]
)
delta_caption(payload["percent_difference"], payload["absolute_difference_kg"])
chart_baseline_scenario(baseline.total_kg_co2e, scenario.total_kg_co2e)

st.markdown("**Modified assumptions**")
st.json(payload["modifications"])
st.write("Categories affected:", ", ".join(payload["affected_categories"]) or "None")
if payload["warnings"]:
    st.warning("Scenario warnings")
    for warning in payload["warnings"]:
        st.write(f"- {warning}")

compare = pd.DataFrame(
    {
        "Category": sorted(set(list(baseline.by_category) + list(scenario.by_category))),
    }
)
compare["Baseline kg"] = compare["Category"].map(lambda c: baseline.by_category.get(c, 0))
compare["Scenario kg"] = compare["Category"].map(lambda c: scenario.by_category.get(c, 0))
st.dataframe(compare, hide_index=True, use_container_width=True)

st.subheader("Save scenario")
name = st.text_input("Scenario name", value="Modelled alternative")
description = st.text_area(
    "Assumptions to retain",
    value="Hypothetical modelled change. Not a measured real-world improvement.",
)
if st.button("Save scenario to assessment history", type="primary"):
    scenario_id = persist_scenario(db, row["id"], name, description, payload)
    st.success(f"Saved scenario {scenario_id}. Baseline calculation {db.get_latest_run(row['id'], 'baseline')['id']} is unchanged.")
