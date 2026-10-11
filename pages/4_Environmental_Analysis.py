"""Results, charts, hotspots, and limitations for a selected assessment."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui import (
    bootstrap,
    chart_baseline_scenario,
    chart_by_category,
    chart_by_stage,
    chart_percentages,
    chart_sources,
    empty_state,
    kpi_row,
    require_assessment,
)
from src.utils import assessment_code, format_kg, format_number, result_from_run_row

db = bootstrap("Environmental Analysis")
st.title("Environmental Analysis")
row = require_assessment(db)
if not row:
    st.stop()

run_row = db.get_latest_run(row["id"], "baseline")
if not run_row:
    empty_state("This assessment has no saved calculation. Open New Assessment and run the calculation.")
    st.stop()

run = db.get_run(run_row["id"])
result = result_from_run_row(run, run["contributions"])
included = [c for c in result.contributions if c.included]
largest = max(included, key=lambda c: c.contribution_kg_co2e, default=None)
quality = result.data_quality or {}

kpi_row(
    [
        ("Total assessed footprint", format_kg(result.total_kg_co2e), assessment_code(row["id"])),
        (
            "Per functional unit",
            format_number(result.footprint_per_functional_unit, 4),
            result.functional_unit,
        ),
        ("Included activities", str(result.included_activity_count), f"{result.excluded_activity_count} excluded"),
        (
            "Largest source",
            largest.description if largest else "None",
            f"{largest.percentage:.1f}%" if largest else "No included contributions",
        ),
        ("Data-quality rating", str(quality.get("rating") or "—"), quality.get("label") or "Internal indicator"),
        ("Boundary", row["boundary"], result.boundary_label or ""),
    ]
)

t1, t2, t3, t4, t5 = st.tabs(
    ["By category", "Ranked sources", "By stage", "Percentages", "Scenario"]
)
with t1:
    chart_by_category(result.by_category)
with t2:
    chart_sources(result.contributions)
with t3:
    chart_by_stage(result.by_stage)
with t4:
    chart_percentages(result.contributions)
with t5:
    scenario = db.get_latest_saved_scenario(row["id"])
    if scenario:
        base = db.get_run(scenario["baseline_run_id"])
        alt = db.get_run(scenario["scenario_run_id"])
        if base and alt:
            chart_baseline_scenario(base["total_kg_co2e"], alt["total_kg_co2e"])
            st.caption(scenario["description"])
        else:
            empty_state("Scenario runs are missing.")
    else:
        empty_state("No saved scenario. Use Scenario Optimiser to model an alternative.")

st.subheader("Hotspot analysis")
if largest and result.total_kg_co2e > 0:
    st.info(
        f"{largest.description} accounts for {largest.percentage:.1f}% of the assessed footprint "
        f"({largest.contribution_kg_co2e:,.2f} kg CO₂e). Investigate the activity quantity and "
        "the applicability of the selected factor before prioritising changes. "
        "This is an observation from the calculation, not a verified improvement opportunity."
    )
else:
    st.warning("No included contribution is available, so a largest source cannot be identified.")

st.subheader("Activity contributions")
st.dataframe(
    pd.DataFrame(
        [
            {
                "Activity": c.description,
                "Category": c.category,
                "Stage": c.life_cycle_stage,
                "Quantity": c.quantity,
                "Unit": c.quantity_unit,
                "Factor": c.factor_id,
                "kg CO₂e": c.contribution_kg_co2e,
                "%": c.percentage if c.included else None,
                "Included": c.included,
                "Note": c.warning,
            }
            for c in result.contributions
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Data-quality breakdown")
if quality:
    st.caption(quality.get("label"))
    st.metric("Overall internal score", quality.get("overall_score"))
    st.dataframe(
        pd.DataFrame(
            [{"Dimension": k, "Score": v, "Weight": quality.get("weights", {}).get(k)} for k, v in (quality.get("dimensions") or {}).items()]
        ),
        hide_index=True,
        use_container_width=True,
    )
    if quality.get("deductions"):
        st.write("Reasons for deductions")
        for item in quality["deductions"]:
            st.write(f"- {item}")
    if quality.get("improvements"):
        st.write("Steps that would improve the indicator")
        for item in quality["improvements"]:
            st.write(f"- {item}")

st.subheader("Limitations")
st.markdown(
    f"""
- **System boundary:** `{row['boundary']}`. Product use and end-of-life are not calculated unless included as activity data, which this prototype does not model by default.
- **Missing activity data:** {result.missing_factor_count} row(s) lacked a usable factor.
- **Excluded rows:** {result.excluded_activity_count} row(s) were omitted from the total.
- **Factor limitations:** stored snapshots show provenance. Illustrative factors are demonstration values.
- **Uncertainty:** this run does not quantify statistical uncertainty.
- **Verification:** this assessment has not undergone independent verification and is not ISO-certified.
"""
)
if result.warnings:
    st.write("Calculation warnings")
    for warning in result.warnings:
        st.write(f"- {warning}")
