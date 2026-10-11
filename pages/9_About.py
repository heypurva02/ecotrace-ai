"""Academic about page."""

from __future__ import annotations

import streamlit as st

from src.config import APP_FULL_TITLE, APP_NAME, COURSE_CODE, INSTITUTION, METHODOLOGY_VERSION
from src.ui import bootstrap

db = bootstrap("About")
st.title("About the Project")
st.markdown(f"### {APP_NAME}")
st.write(APP_FULL_TITLE)
st.write(f"{COURSE_CODE} minor project · {INSTITUTION}")
st.write(f"Methodology version {METHODOLOGY_VERSION}")

st.header("Problem")
st.write(
    "Industrial teams and students often hold activity data in spreadsheets but lack a transparent "
    "way to map those data to emission factors, keep an audit trail, and test simple what-if changes "
    "without treating a language model as a calculator."
)

st.header("What this prototype does")
st.write(
    "It validates inputs, applies documented (including clearly labelled illustrative) factors, "
    "stores immutable calculation runs in SQLite, compares scenarios with the same engine, "
    "scores data completeness heuristically, and exports PDF/CSV/Excel reports."
)

st.header("What it does not do")
st.markdown(
    """
- It is not ISO 14040/14044 certified.
- It does not produce an Environmental Product Declaration.
- It does not generate EU CBAM filings.
- It does not claim that a low score means a product is environmentally friendly.
- AI recommendations are not experimentally validated.
- Illustrative factors are not official government factors.
"""
)

st.header("How to explain the architecture in a viva")
st.markdown(
    """
1. **Problem** — screening industrial GHG data locally.
2. **LCA** — activity data × compatible factor, inside a stated boundary.
3. **Why data are hard** — mixed units, missing processes, secondary factors.
4. **Activity data** — measured or estimated quantities.
5. **Factors** — registry rows with provenance.
6. **Formula** — converted quantity × factor; sum included rows.
7. **Units** — small explicit converter; reject unknown units.
8. **Boundary** — cradle-to-gate, gate-to-gate, or selected stages.
9. **Registry** — SQLite + CSV seed; snapshots stored per run.
10. **Determinism** — no LLM in `src/calculations.py`; identical inputs hash to the same fingerprint.
11. **AI role** — explain and rule-based advice only.
12. **Data quality** — documented heuristic weights.
13. **Scenarios** — copy inputs, modify, recalculate, save on confirmation.
14. **History** — SQLite with foreign keys.
15. **PDF** — ReportLab from the selected assessment.
16. **Limitations** — illustrative factors, incomplete stages, no uncertainty model.
17. **Future work** — replace illustrative factors with documented national/EPD sources, add more impact categories, independent review.
"""
)

st.header("Database location")
st.code(str(db.path))
st.write("Copy that file to back up all assessments. Restarting the app does not delete it.")
