"""PDF, CSV, and Excel exports for the selected assessment."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config import REPORTS_DIR
from src.report_generator import (
    export_activity_csv,
    export_excel,
    export_factors_csv,
    export_history_csv,
    export_scenario_csv,
    export_summary_csv,
    generate_pdf_report,
)
from src.ui import bootstrap, empty_state, require_assessment
from src.utils import assessment_code

db = bootstrap("Reports")
st.title("Reports & Exports")
row = require_assessment(db)
if not row:
    st.stop()
if not db.get_latest_run(row["id"], "baseline"):
    empty_state("Calculate the selected assessment before exporting.")
    st.stop()

st.write(
    f"Exports are generated from **{assessment_code(row['id'])} · {row['product_name']}** "
    "and the latest saved baseline calculation."
)

if st.button("Generate PDF report", type="primary"):
    path = REPORTS_DIR / f"{assessment_code(row['id'])}.pdf"
    data = generate_pdf_report(db, row["id"], path)
    st.success(f"Wrote {path} ({len(data)} bytes).")
    st.download_button("Download PDF", data=data, file_name=path.name, mime="application/pdf")

st.subheader("CSV downloads")
c1, c2, c3 = st.columns(3)
with c1:
    st.download_button("Activity-level emissions", data=export_activity_csv(db, row["id"]), file_name="activities.csv", mime="text/csv")
    st.download_button("Assessment summary", data=export_summary_csv(db, row["id"]), file_name="summary.csv", mime="text/csv")
with c2:
    st.download_button("Factor registry", data=export_factors_csv(db), file_name="factors.csv", mime="text/csv")
    st.download_button("Scenario comparison", data=export_scenario_csv(db, row["id"]), file_name="scenarios.csv", mime="text/csv")
with c3:
    st.download_button("Calculation history", data=export_history_csv(db, row["id"]), file_name="history.csv", mime="text/csv")

st.subheader("Excel workbook")
xlsx_path = REPORTS_DIR / f"{assessment_code(row['id'])}.xlsx"
if st.button("Build Excel workbook"):
    data = export_excel(db, row["id"], xlsx_path)
    st.download_button(
        "Download Excel",
        data=data,
        file_name=xlsx_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption(f"Copies are also stored under `{REPORTS_DIR}` when generated from the buttons above.")
st.caption("Back up the SQLite database file separately if you need an archive of all assessments.")
