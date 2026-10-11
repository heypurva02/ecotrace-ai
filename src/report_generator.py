"""PDF, CSV, and Excel report generation from saved assessment data."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)

from src.config import APP_FULL_TITLE, APP_NAME, COURSE_CODE, INSTITUTION, METHODOLOGY_VERSION, REPORTS_DIR
from src.database import Database
from src.import_export import write_excel_workbook
from src.recommendations import build_recommendations
from src.utils import assessment_code, format_kg, result_from_run_row

GREEN = colors.HexColor("#1f6b4a")
SAGE = colors.HexColor("#dce8e1")
CHARCOAL = colors.HexColor("#2c3330")
LIGHT = colors.HexColor("#f4f7f5")
DISCLAIMER = (
    "Academic screening prototype. Results are not independently verified, not ISO-certified, "
    "not an Environmental Product Declaration, and not a regulatory filing such as EU CBAM. "
    "Illustrative factors are unsuitable for external reporting."
)


def generate_pdf_report(db: Database, assessment_id: int, output_path: Optional[Path] = None) -> bytes:
    row = db.get_assessment(assessment_id)
    if not row:
        raise ValueError("Assessment not found.")
    baseline = db.get_latest_run(assessment_id, "baseline")
    if not baseline:
        raise ValueError("No saved calculation exists for this assessment.")
    run = db.get_run(baseline["id"])
    result = result_from_run_row(run, run["contributions"])
    activities = db.get_activities(assessment_id)
    scenarios = db.list_scenarios(assessment_id)
    recs = build_recommendations(result)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{APP_NAME} assessment {assessment_code(assessment_id)}",
        author=APP_NAME,
    )
    styles = _styles()
    story: list[Any] = []
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story.append(Paragraph(APP_NAME, styles["brand"]))
    story.append(Paragraph(APP_FULL_TITLE, styles["subtitle"]))
    story.append(Paragraph(f"{COURSE_CODE} · {INSTITUTION}", styles["meta"]))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", color=GREEN, thickness=1.2))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Screening LCA report", styles["eco_h1"]))
    story.append(Paragraph(DISCLAIMER, styles["disclaimer"]))
    story.append(Spacer(1, 8))

    summary_table = [
        ["Assessment ID", assessment_code(assessment_id)],
        ["Assessment name", row["name"]],
        ["Product", f"{row['product_name']} ({row['product_category']})"],
        ["Material", row["material_type"]],
        ["Reporting period", row["reporting_period"]],
        ["Location", row["location"]],
        ["Functional unit", f"{row['functional_unit']} (quantity {row['functional_unit_quantity']})"],
        ["Production quantity", f"{row['production_quantity']} {row['production_quantity_unit']}"],
        ["System boundary", row["boundary"]],
        ["Total assessed footprint", format_kg(result.total_kg_co2e)],
        ["Footprint per functional unit", _fu(result)],
        ["Methodology version", METHODOLOGY_VERSION],
        ["Calculation time", result.calculated_at],
        ["Report generated", generated],
        ["Demo record", "Yes" if row.get("is_demo") else "No"],
    ]
    story.append(_table(summary_table, [55 * mm, 115 * mm]))
    story.append(Spacer(1, 10))

    quality = result.data_quality or {}
    story.append(Paragraph("Data-quality indicator", styles["eco_h2"]))
    story.append(
        Paragraph(
            f"Overall internal score: <b>{quality.get('overall_score', '—')}</b> "
            f"({quality.get('rating', '—')}). {quality.get('label', '')}",
            styles["body"],
        )
    )
    for deduction in (quality.get("deductions") or [])[:8]:
        story.append(Paragraph(f"• {deduction}", styles["bullet"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Emissions by life-cycle stage", styles["eco_h2"]))
    stage_rows = [["Stage", "kg CO₂e", "Share"]]
    for stage, value in sorted((result.by_stage or {}).items(), key=lambda x: -x[1]):
        share = (value / result.total_kg_co2e * 100) if result.total_kg_co2e else 0
        stage_rows.append([stage, f"{value:,.2f}", f"{share:.1f}%"])
    if len(stage_rows) == 1:
        stage_rows.append(["No included stage contributions", "0.00", "—"])
    story.append(_table(stage_rows, [80 * mm, 45 * mm, 45 * mm], header=True))
    story.append(_bar_table(result.by_stage or {}))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Activity-level contributions", styles["eco_h2"]))
    act_rows = [["Activity", "Stage", "Included", "kg CO₂e", "%"]]
    for item in result.contributions:
        act_rows.append(
            [
                item.description[:42],
                item.life_cycle_stage[:22],
                "Yes" if item.included else "No",
                f"{item.contribution_kg_co2e:,.2f}",
                f"{item.percentage:.1f}" if item.included else "—",
            ]
        )
    story.append(_table(act_rows, [58 * mm, 38 * mm, 22 * mm, 28 * mm, 18 * mm], header=True))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Emission factor references used in this run", styles["eco_h2"]))
    story.append(
        Paragraph(
            "Snapshots below were stored at calculation time. Later registry edits do not rewrite this report.",
            styles["body"],
        )
    )
    seen = set()
    factor_rows = [["Factor ID", "Value", "Ref. unit", "Provenance", "Source"]]
    for item in result.contributions:
        if not item.included or not item.factor_id or item.factor_id in seen:
            continue
        seen.add(item.factor_id)
        snap = item.factor_snapshot or {}
        factor_rows.append(
            [
                item.factor_id,
                f"{item.factor_value}",
                str(snap.get("reference_activity_unit") or ""),
                str(snap.get("provenance") or ""),
                f"{snap.get('source_organisation') or ''} — {snap.get('source_title') or ''}"[:48],
            ]
        )
    if len(factor_rows) == 1:
        factor_rows.append(["None", "—", "—", "—", "—"])
    story.append(_table(factor_rows, [32 * mm, 22 * mm, 24 * mm, 28 * mm, 64 * mm], header=True))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Missing-data warnings", styles["eco_h2"]))
    if result.warnings:
        for warning in result.warnings:
            story.append(Paragraph(f"• {warning}", styles["bullet"]))
    else:
        story.append(Paragraph("No calculation warnings were recorded.", styles["body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Methodology and assumptions", styles["eco_h2"]))
    story.append(
        Paragraph(
            "For each included activity, emissions (kg CO₂e) = converted activity quantity × "
            "the selected factor value. Quantities are converted only when the unit family matches "
            "the factor reference unit. The total is the sum of included rows. "
            f"Boundary: {row['boundary']}. AI systems are not used to compute these numbers.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Rule-based recommendations", styles["eco_h2"]))
    story.append(
        Paragraph(
            "The following text is generated by deterministic rules from the calculated result. "
            "It is not experimentally validated advice.",
            styles["body"],
        )
    )
    for rec in recs:
        block = [
            Paragraph(f"<b>{rec.title}</b> ({rec.recommendation_id})", styles["body"]),
            Paragraph(rec.supporting_observation, styles["bullet"]),
            Paragraph(f"Suggested action: {rec.suggested_action}", styles["bullet"]),
            Paragraph(f"Limitations: {rec.limitations}", styles["bullet"]),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 4))

    if scenarios:
        story.append(Paragraph("Saved scenario comparisons", styles["eco_h2"]))
        story.append(
            Paragraph(
                "Scenario results are hypothetical modelled alternatives, not measured improvements.",
                styles["body"],
            )
        )
        for scenario in scenarios:
            base = db.get_run(scenario["baseline_run_id"]) if scenario.get("baseline_run_id") else None
            alt = db.get_run(scenario["scenario_run_id"]) if scenario.get("scenario_run_id") else None
            if not base or not alt:
                continue
            story.append(Paragraph(f"<b>{scenario['name']}</b>", styles["body"]))
            story.append(
                Paragraph(
                    f"Baseline {base['total_kg_co2e']:,.2f} kg CO₂e versus scenario "
                    f"{alt['total_kg_co2e']:,.2f} kg CO₂e. Assumptions: {scenario['modifications_json']}",
                    styles["bullet"],
                )
            )

    story.append(Spacer(1, 10))
    story.append(Paragraph("Limitations and verification disclaimer", styles["eco_h2"]))
    story.append(Paragraph(DISCLAIMER, styles["disclaimer"]))
    story.append(
        Paragraph(
            "ISO 14040/14044 describe LCA principles but this prototype does not claim conformity. "
            "A general screening result cannot be treated as a CBAM submission.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            f"Activity rows stored: {len(activities)}. Included in total: "
            f"{result.included_activity_count}. Excluded: {result.excluded_activity_count}.",
            styles["meta"],
        )
    )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    data = buffer.getvalue()
    target = output_path or (REPORTS_DIR / f"{assessment_code(assessment_id)}.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 8)
    canvas.setFillColor(CHARCOAL)
    canvas.drawString(18 * mm, 10 * mm, f"{APP_NAME} · screening prototype · page {doc.page}")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, DISCLAIMER[:78] + "…")
    canvas.restoreState()


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="brand", fontName="Times-Bold", fontSize=18, textColor=GREEN, spaceAfter=2))
    styles.add(ParagraphStyle(name="subtitle", fontName="Times-Italic", fontSize=9, textColor=CHARCOAL, leading=12))
    styles.add(ParagraphStyle(name="meta", fontName="Times-Roman", fontSize=9, textColor=CHARCOAL, spaceAfter=4))
    styles.add(ParagraphStyle(name="eco_h1", fontName="Times-Bold", fontSize=14, textColor=CHARCOAL, spaceAfter=6))
    styles.add(ParagraphStyle(name="eco_h2", fontName="Times-Bold", fontSize=12, textColor=GREEN, spaceBefore=6, spaceAfter=4))
    styles.add(
        ParagraphStyle(
            name="body", fontName="Times-Roman", fontSize=9, leading=12, alignment=TA_JUSTIFY, textColor=CHARCOAL, spaceAfter=3
        )
    )
    styles.add(
        ParagraphStyle(name="bullet", fontName="Times-Roman", fontSize=9, leading=12, leftIndent=10, textColor=CHARCOAL, spaceAfter=2)
    )
    styles.add(
        ParagraphStyle(
            name="disclaimer",
            fontName="Times-Italic",
            fontSize=8,
            leading=11,
            textColor=CHARCOAL,
            backColor=SAGE,
            borderPadding=4,
            alignment=TA_LEFT,
        )
    )
    return styles


def _table(data, widths, header: bool = False):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), CHARCOAL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5d1cb")),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
    ]
    if header:
        cmds.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("BACKGROUND", (0, 1), (0, -1), colors.white),
            ]
        )
    table.setStyle(TableStyle(cmds))
    return table


def _bar_table(mapping: dict[str, float]):
    if not mapping:
        return Spacer(1, 1)
    maximum = max(mapping.values()) or 1
    data = [["Graphical summary (relative bar length)"]]
    for key, value in sorted(mapping.items(), key=lambda x: -x[1]):
        filled = int(round(24 * value / maximum))
        data.append([f"{key}: {value:,.1f} kg  " + "█" * filled])
    table = Table(data, colWidths=[170 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, -1), CHARCOAL),
                ("BACKGROUND", (0, 0), (-1, 0), SAGE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _fu(result) -> str:
    if result.footprint_per_functional_unit is None:
        return "Not calculated"
    return f"{result.footprint_per_functional_unit:,.4f} kg CO₂e / {result.functional_unit}"


def export_activity_csv(db: Database, assessment_id: int) -> bytes:
    run = db.get_latest_run(assessment_id, "baseline")
    if not run:
        raise ValueError("No calculation to export.")
    full = db.get_run(run["id"])
    frame = pd.DataFrame(full["contributions"])
    return frame.to_csv(index=False).encode("utf-8")


def export_summary_csv(db: Database, assessment_id: int) -> bytes:
    row = db.get_assessment(assessment_id)
    run = db.get_latest_run(assessment_id, "baseline")
    if not row or not run:
        raise ValueError("No calculation to export.")
    frame = pd.DataFrame(
        [
            {
                "assessment_id": assessment_code(assessment_id),
                "product_name": row["product_name"],
                "material": row["material_type"],
                "boundary": row["boundary"],
                "total_kg_co2e": run["total_kg_co2e"],
                "total_tonnes_co2e": run["total_tonnes_co2e"],
                "functional_unit": run["functional_unit"],
                "footprint_per_fu": run["footprint_per_fu"],
                "calculated_at": run["created_at"],
            }
        ]
    )
    return frame.to_csv(index=False).encode("utf-8")


def export_factors_csv(db: Database) -> bytes:
    factors = [f.model_dump() for f in db.list_factors()]
    return pd.DataFrame(factors).to_csv(index=False).encode("utf-8")


def export_scenario_csv(db: Database, assessment_id: int) -> bytes:
    scenarios = db.list_scenarios(assessment_id)
    rows = []
    for scenario in scenarios:
        base = db.get_run(scenario["baseline_run_id"]) if scenario.get("baseline_run_id") else None
        alt = db.get_run(scenario["scenario_run_id"]) if scenario.get("scenario_run_id") else None
        rows.append(
            {
                "scenario_id": scenario["id"],
                "name": scenario["name"],
                "modifications": scenario["modifications_json"],
                "baseline_kg": None if not base else base["total_kg_co2e"],
                "scenario_kg": None if not alt else alt["total_kg_co2e"],
            }
        )
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def export_history_csv(db: Database, assessment_id: int) -> bytes:
    runs = db.list_runs(assessment_id)
    return pd.DataFrame(runs).to_csv(index=False).encode("utf-8")


def export_excel(db: Database, assessment_id: int, path: Optional[Path] = None) -> bytes:
    row = db.get_assessment(assessment_id)
    run = db.get_latest_run(assessment_id, "baseline")
    if not row or not run:
        raise ValueError("No calculation to export.")
    full = db.get_run(run["id"])
    summary = pd.DataFrame([row])
    activities = pd.DataFrame(full["contributions"])
    factors = pd.DataFrame(
        [
            c
            for c in full["contributions"]
            if c.get("included")
        ]
    )
    scenarios = pd.DataFrame(db.list_scenarios(assessment_id))
    quality = pd.DataFrame([{"data_quality_json": run.get("data_quality_json")}])
    return write_excel_workbook(
        {
            "Summary": summary,
            "Activities": activities,
            "Factors used": factors,
            "Scenarios": scenarios if not scenarios.empty else pd.DataFrame({"note": ["No saved scenarios"]}),
            "Data quality": quality,
        },
        path=path,
    )
