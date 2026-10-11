"""Methodology, calculation rules, and the factor registry."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import ACTIVITY_CATEGORIES, BOUNDARIES, METHODOLOGY_VERSION
from src.data_quality import WEIGHTS
from src.ui import bootstrap

db = bootstrap("Methodology")
st.title("Methodology & Data Sources")
st.caption(f"Methodology version {METHODOLOGY_VERSION}")

st.header("What life-cycle assessment means here")
st.write(
    "Life-cycle assessment (LCA) estimates environmental impacts associated with a product "
    "across defined stages. This prototype performs **screening greenhouse-gas accounting** "
    "from user-supplied activity data and a documented factor registry. It is a decision-support "
    "teaching tool, not a certified LCA."
)

st.header("Activity data versus emission factors")
st.write(
    "**Activity data** are the quantities you enter (kWh, kg, tkm, litres). "
    "**Emission factors** convert a compatible activity quantity into kg CO₂e. "
    "The application never invents a factor when one is missing; that row is excluded and flagged."
)

st.header("Calculation formula")
st.latex(r"E_i = q_i^{\mathrm{converted}} \times EF_i")
st.latex(r"E_{\mathrm{total}} = \sum_{i \in \mathrm{included}} E_i")
st.latex(r"e_{\mathrm{FU}} = E_{\mathrm{total}} / Q_{\mathrm{FU}} \quad (Q_{\mathrm{FU}} > 0)")
st.write(
    "Unit conversion is applied only inside a supported family (g/kg/t, Wh/kWh/MWh, m/km, L/m³). "
    "Unknown units are rejected. Water consumption is converted to GHG using a GHG factor; "
    "it is not added as litres into the kg CO₂e total."
)

st.header("Life-cycle boundaries")
for key, spec in BOUNDARIES.items():
    st.markdown(f"**{spec['label']}** (`{key}`): {spec['explanation']}")
st.write(
    "The prototype calculates only processes represented by entered activity data. "
    "Raw-material extraction, use, and end-of-life are included only if the user supplies "
    "compatible activity rows and factors."
)

st.header("Supported activity categories")
st.write(", ".join(ACTIVITY_CATEGORIES))

st.header("Data-quality indicator")
st.write(
    "The 0–100 score is an **internal EcoTrace heuristic**, not a recognised pedigree matrix "
    "and not a certification. Dimension weights:"
)
st.dataframe(
    pd.DataFrame({"Dimension": list(WEIGHTS), "Weight": list(WEIGHTS.values())}),
    hide_index=True,
)
st.write("Illustrative factors reduce the documentation dimension even when arithmetic is correct.")

st.header("Why AI is separated from the numbers")
st.write(
    "Language models can rephrase calculated summaries. They are optional, disabled by default, "
    "and are not allowed to set emission factors or overwrite the footprint. "
    "The local advisor uses explicit rules on the calculated result."
)

st.header("Screening LCA versus verified LCA")
st.write(
    "A screening result helps a student or plant team see which entered processes dominate. "
    "An independently verified LCA or Environmental Product Declaration requires a defined goal "
    "and scope, additional impact categories, review, and evidence beyond this prototype. "
    "ISO 14040 and ISO 14044 describe relevant principles; **this application does not claim conformity**."
)

st.header("Why this is not a CBAM result")
st.write(
    "EU Carbon Border Adjustment Mechanism reporting has specific system boundaries, "
    "precursor rules, and communication formats. A generic screening total cannot be treated "
    "as a CBAM submission even if the product is steel or aluminium."
)

st.header("Factor registry")
st.write(
    "Every factor below records provenance. Source URLs are included only when a real URL was supplied. "
    "Illustrative rows are demonstration values and are **not** official Indian government factors."
)
factors = [f.model_dump() for f in db.list_factors()]
frame = pd.DataFrame(factors)
st.dataframe(frame, use_container_width=True, hide_index=True)
for factor in db.list_factors():
    if factor.source_url:
        st.markdown(f"- [{factor.factor_id}: {factor.source_title}]({factor.source_url})")
st.caption("No official source URL is claimed for illustrative demonstration factors.")
