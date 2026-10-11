"""Shared Streamlit layout, theme, and widgets."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import APP_NAME, INSTITUTION
from src.database import Database, get_db
from src.factor_registry import seed_registry
from src.utils import assessment_code, format_kg, format_percent

FOREST = "#1f6b4a"
SAGE = "#7d9b8a"
BG = "#f4f7f5"
TEXT = "#2c3330"
CARD = "#ffffff"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(color=TEXT, family="Source Sans 3, Segoe UI, sans-serif", size=13),
    margin=dict(l=10, r=10, t=40, b=10),
    colorway=[FOREST, SAGE, "#4f6f5a", "#c4a35a", "#6b7280", "#8f4b3a"],
)

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family: "Source Sans 3", "Segoe UI", sans-serif; color: {TEXT}; }}
.stApp {{ background: {BG}; }}
section[data-testid="stSidebar"] {{ background: #eef4f0; border-right: 1px solid #d5e0d9; }}
.et-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 8px 0 18px; }}
.et-card {{ background: {CARD}; border: 1px solid #d7e2db; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(31,107,74,0.05); }}
.et-card h4 {{ margin: 0; font-size: 0.78rem; letter-spacing: 0.02em; text-transform: uppercase; color: {SAGE}; font-weight: 600; }}
.et-card .et-value {{ font-size: 1.35rem; font-weight: 700; color: {TEXT}; margin-top: 6px; }}
.et-card .et-hint {{ font-size: 0.8rem; color: #5b675f; margin-top: 4px; }}
.et-banner {{ background: {CARD}; border-left: 4px solid {FOREST}; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }}
.et-disclaimer {{ font-size: 0.78rem; color: #5b675f; border-top: 1px solid #d5e0d9; margin-top: 18px; padding-top: 8px; }}
.et-empty {{ background: {CARD}; border: 1px dashed #b7c9be; padding: 28px; border-radius: 10px; text-align: center; }}
h1, h2, h3 {{ color: {TEXT}; }}
div[data-testid="stMetricValue"] {{ color: {FOREST}; }}
</style>
"""


def bootstrap(page_title: str) -> Database:
    st.set_page_config(
        page_title=f"{APP_NAME} · {page_title}",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    db = get_db()
    seed_registry(db)
    _sidebar(db)
    return db


def _sidebar(db: Database) -> None:
    with st.sidebar:
        st.markdown(f"### 🌿 {APP_NAME}")
        st.caption("Product Sustainability Assessment")
        selected = st.session_state.get("selected_assessment_id")
        assessments = db.list_assessments()
        if assessments:
            labels = {
                int(a["id"]): f"{assessment_code(a['id'])} · {a['product_name']}"
                for a in assessments
            }
            options = list(labels.keys())
            index = options.index(int(selected)) if selected in options else 0
            chosen = st.selectbox(
                "Selected assessment",
                options,
                index=index,
                format_func=lambda i: labels[i],
            )
            st.session_state.selected_assessment_id = int(chosen)
            current = db.get_assessment(int(chosen))
            if current:
                st.caption(
                    f"{current['material_type']} · {current['boundary']} · "
                    f"{current['production_quantity']} {current['production_quantity_unit']}"
                )
        else:
            st.info("No assessment exists yet. Create one or load the demonstration dataset.")
            st.session_state.selected_assessment_id = None
        st.markdown(
            f'<p class="et-disclaimer">Academic screening prototype for {INSTITUTION}. '
            "Not certified, not verified, and not a regulatory filing.</p>",
            unsafe_allow_html=True,
        )


def kpi_row(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (title, value, hint) in zip(cols, items):
        with col:
            st.markdown(
                f'<div class="et-card"><h4>{title}</h4>'
                f'<div class="et-value">{value}</div>'
                f'<div class="et-hint">{hint}</div></div>',
                unsafe_allow_html=True,
            )


def empty_state(message: str) -> None:
    st.markdown(f'<div class="et-empty">{message}</div>', unsafe_allow_html=True)


def issue_table(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    frame = pd.DataFrame(items)
    st.dataframe(frame, use_container_width=True, hide_index=True)


def selected_id() -> Optional[int]:
    value = st.session_state.get("selected_assessment_id")
    return int(value) if value else None


def require_assessment(db: Database) -> Optional[dict[str, Any]]:
    assessment_id = selected_id()
    if not assessment_id:
        empty_state("Select or create an assessment to continue.")
        return None
    row = db.get_assessment(assessment_id)
    if not row:
        empty_state("The selected assessment could not be found.")
        return None
    return row


def chart_by_category(by_category: dict[str, float]):
    if not by_category or sum(by_category.values()) <= 0:
        empty_state("No included emissions to chart by category.")
        return
    frame = pd.DataFrame({"Category": list(by_category.keys()), "kg CO2e": list(by_category.values())})
    fig = px.pie(frame, names="Category", values="kg CO2e", hole=0.55)
    fig.update_layout(**PLOTLY_LAYOUT, showlegend=True, title="Emissions by activity category")
    fig.update_traces(hovertemplate="%{label}<br>%{value:,.2f} kg CO₂e<br>%{percent}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


def chart_by_stage(by_stage: dict[str, float]):
    if not by_stage:
        empty_state("No included emissions to chart by stage.")
        return
    frame = pd.DataFrame({"Stage": list(by_stage.keys()), "kg CO2e": list(by_stage.values())})
    fig = px.bar(frame, x="Stage", y="kg CO2e", title="Emissions by life-cycle stage")
    fig.update_layout(**PLOTLY_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def chart_sources(contributions) -> None:
    included = [c for c in contributions if getattr(c, "included", False) or (isinstance(c, dict) and c.get("included"))]
    if not included:
        empty_state("No ranked emission sources to display.")
        return
    rows = []
    for item in included:
        if hasattr(item, "description"):
            rows.append(
                {
                    "Activity": item.description,
                    "kg CO2e": item.contribution_kg_co2e,
                    "percent": item.percentage,
                    "unit": item.quantity_unit,
                }
            )
        else:
            rows.append(
                {
                    "Activity": item.get("description"),
                    "kg CO2e": item.get("contribution_kg_co2e"),
                    "percent": item.get("percentage"),
                    "unit": item.get("quantity_unit"),
                }
            )
    frame = pd.DataFrame(rows).sort_values("kg CO2e")
    fig = px.bar(frame, x="kg CO2e", y="Activity", orientation="h", title="Ranked emission sources")
    fig.update_layout(**PLOTLY_LAYOUT, height=max(320, 36 * len(frame)))
    fig.update_traces(
        customdata=frame[["percent", "unit"]],
        hovertemplate="%{y}<br>%{x:,.2f} kg CO₂e<br>%{customdata[0]:.1f}%<extra></extra>",
    )
    st.plotly_chart(fig, use_container_width=True)


def chart_percentages(contributions) -> None:
    included = [c for c in contributions if getattr(c, "included", True)]
    rows = []
    for item in included:
        if hasattr(item, "percentage"):
            if item.included:
                rows.append({"Activity": item.description, "Share %": item.percentage})
        elif item.get("included"):
            rows.append({"Activity": item.get("description"), "Share %": item.get("percentage") or 0})
    if not rows:
        empty_state("No contribution percentages available.")
        return
    frame = pd.DataFrame(rows)
    fig = px.bar(frame, x="Activity", y="Share %", title="Contribution percentage")
    fig.update_layout(**PLOTLY_LAYOUT, xaxis_tickangle=-25)
    st.plotly_chart(fig, use_container_width=True)


def chart_baseline_scenario(baseline_kg: float, scenario_kg: float) -> None:
    fig = go.Figure(
        data=[
            go.Bar(name="Baseline", x=["Assessed footprint"], y=[baseline_kg], marker_color=SAGE),
            go.Bar(name="Scenario", x=["Assessed footprint"], y=[scenario_kg], marker_color=FOREST),
        ]
    )
    fig.update_layout(barmode="group", yaxis_title="kg CO₂e", title="Baseline versus alternative scenario", **PLOTLY_LAYOUT)
    st.plotly_chart(fig, use_container_width=True)


def delta_caption(percent: Optional[float], absolute: float) -> None:
    if percent is None:
        st.warning("Percentage difference is undefined because the baseline total is zero.")
        return
    colour = FOREST if percent > 0 else "#8f4b3a" if percent < 0 else TEXT
    word = "modelled reduction" if percent > 0 else "modelled increase" if percent < 0 else "no modelled change"
    st.markdown(
        f"<div class='et-banner'><b style='color:{colour}'>{format_percent(percent)} {word}</b>"
        f"<br>{format_kg(absolute)} absolute difference. Hypothetical modelled result only.</div>",
        unsafe_allow_html=True,
    )
