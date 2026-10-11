"""Local rule-based advisor with optional LLM rephrasing."""

from __future__ import annotations

import streamlit as st

from src.ai_provider import explain_with_llm, llm_enabled
from src.services import advisor_payload
from src.ui import bootstrap, empty_state, require_assessment
from src.utils import format_kg

db = bootstrap("AI Sustainability Advisor")
st.title("AI Sustainability Advisor")
st.caption(
    "Primary engine: deterministic Python rules using this assessment's calculated results. "
    "Optional LLM explanation is off by default and cannot change the footprint."
)

row = require_assessment(db)
if not row:
    st.stop()

try:
    payload = advisor_payload(db, row["id"])
except ValueError as exc:
    empty_state(str(exc))
    st.stop()

result = payload["result"]
st.write(
    f"Using calculated total **{format_kg(result.total_kg_co2e)}** for **{row['product_name']}**. "
    "Numerical values below come from the calculation engine."
)

for rec in payload["recommendations"]:
    with st.container(border=True):
        st.markdown(f"**{rec.title}** · `{rec.recommendation_id}`")
        st.write(rec.supporting_observation)
        st.write(f"Suggested action: {rec.suggested_action}")
        cols = st.columns(3)
        cols[0].caption(f"Category: {rec.relevant_activity_or_category}")
        cols[1].caption(f"Evidence: {rec.confidence_status}")
        cols[2].caption(f"Direction: {rec.expected_direction}")
        st.caption(f"Required next data: {rec.required_next_data}")
        st.caption(f"Limitations: {rec.limitations}")

st.subheader("Optional language-model explanation")
st.write(
    "Status: " + ("configured" if llm_enabled() else "disabled (no key / ECOTRACE_LLM_ENABLED is not true)")
)
if st.button("Request LLM rephrasing of the calculated summary"):
    summary = {
        "total_kg_co2e": result.total_kg_co2e,
        "warnings": result.warnings,
        "by_category": result.by_category,
        "missing_factor_count": result.missing_factor_count,
        "boundary": row["boundary"],
        "data_quality": result.data_quality,
    }
    text, status = explain_with_llm(summary, payload["recommendations"])
    st.info(status)
    if text:
        st.write(text)
    else:
        st.caption("Local recommendations remain the source of advice.")
