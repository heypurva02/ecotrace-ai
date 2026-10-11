"""Deterministic local sustainability advisor.

Recommendations are derived from calculated results. They do not invent
percentage reductions, cost savings, or regulatory outcomes.
"""

from __future__ import annotations

from typing import Any, Optional

from src.models import CalculationResult, Recommendation


def build_recommendations(
    result: CalculationResult,
    *,
    scenario_summary: Optional[dict[str, Any]] = None,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    total = result.total_kg_co2e
    by_category = result.by_category or {}
    ranked = sorted(by_category.items(), key=lambda item: item[1], reverse=True)
    top_category, top_value = ranked[0] if ranked else (None, 0.0)
    top_share = (top_value / total * 100.0) if total > 0 and top_value else 0.0

    included = [c for c in result.contributions if c.included]
    largest = max(included, key=lambda c: c.contribution_kg_co2e, default=None)

    if largest and total > 0:
        recs.append(
            Recommendation(
                recommendation_id="REC-HOTSPOT",
                title="Investigate the largest calculated emission source",
                explanation=(
                    f"{largest.description} is the largest included contributor in this assessment."
                ),
                supporting_observation=(
                    f"{largest.description} accounts for {largest.percentage:.1f}% "
                    f"({largest.contribution_kg_co2e:,.2f} kg CO₂e) of the assessed total."
                ),
                relevant_activity_or_category=largest.category,
                suggested_action=(
                    "Check the activity quantity, unit, and whether the selected factor "
                    "is geographically and technologically applicable before prioritising changes."
                ),
                expected_direction="Direction unknown until a supported scenario is calculated",
                confidence_status="Observation from this calculation only",
                required_next_data="Primary activity data and a documented factor for this process",
                limitations="A large share can reflect missing data elsewhere, not only a true process hotspot.",
            )
        )

    if top_category == "Electricity" and top_share >= 25:
        recs.append(
            _rule(
                "REC-ELEC",
                "Review electricity consumption and the grid factor",
                f"Electricity accounts for {top_share:.1f}% of the assessed footprint.",
                "Electricity",
                "Investigate metered electricity use, process efficiency, and whether the selected electricity factor matches the supply mix.",
                "Possible reduction if consumption or carbon intensity falls — quantify only with a scenario",
            )
        )
    if top_category == "Raw materials" and top_share >= 25:
        recs.append(
            _rule(
                "REC-MAT",
                "Examine material inputs and recycled-content options",
                f"Raw materials account for {top_share:.1f}% of the assessed footprint.",
                "Raw materials",
                "Evaluate supplier-specific data, mass accuracy, and whether a documented recycled-content pathway exists in the factor registry.",
                "Possible reduction if a lower-intensity documented material factor applies",
            )
        )
    if top_category in {"Inbound transport", "Outbound transport"} and top_share >= 20:
        recs.append(
            _rule(
                "REC-TRANS",
                "Validate transport distances and freight assumptions",
                f"{top_category} accounts for {top_share:.1f}% of the assessed footprint.",
                top_category,
                "Confirm actual distances, vehicle type, load factor, and whether activity data are in tkm.",
                "Possible reduction if distance or freight intensity falls",
            )
        )

    if result.missing_factor_count:
        recs.append(
            _rule(
                "REC-MISSING-FACTOR",
                "Replace missing factors before using the total",
                f"{result.missing_factor_count} activity row(s) were excluded because no compatible factor was available.",
                "Excluded activities",
                "Do not treat the current total as a complete footprint. Obtain a documented factor or keep the process explicitly excluded.",
                "Total may increase when missing processes are added",
                confidence="High — based on excluded rows",
                next_data="Documented factor with matching units",
                limitations="The application will not silently substitute an unrelated factor.",
            )
        )

    illustrative = sum(
        1
        for c in result.contributions
        if c.included and (c.factor_snapshot or {}).get("provenance") == "illustrative"
    )
    if illustrative:
        recs.append(
            _rule(
                "REC-ILLUSTRATIVE",
                "Treat illustrative factors as demonstration data only",
                f"{illustrative} included factor snapshot(s) are classified as illustrative.",
                "Factor registry",
                "Replace illustrative values with documented, applicable sources before any external reporting.",
                "Numerical total is suitable for screening demonstration only",
                confidence="High — from factor provenance",
                next_data="Source organisation, year, geography, and licence for each factor",
                limitations="Arithmetic can be correct while evidence remains unsuitable for disclosure.",
            )
        )

    represented_stages = {c.life_cycle_stage for c in result.contributions if c.included}
    missing_stages = [s for s in result.included_stages if s not in represented_stages]
    if missing_stages:
        recs.append(
            _rule(
                "REC-STAGES",
                "Fill unassessed stages inside the chosen boundary",
                "The boundary includes stages that have no included activity contribution: "
                + ", ".join(missing_stages)
                + ".",
                "System boundary",
                "Collect activity data for those stages or narrow the boundary statement.",
                "Whole-life or even full cradle-to-gate claims are not supported yet",
            )
        )

    quality = result.data_quality or {}
    if quality.get("overall_score") is not None and quality["overall_score"] < 60:
        recs.append(
            _rule(
                "REC-DQ",
                "Improve data quality before decision-making",
                f"Internal data-quality indicator is {quality['overall_score']} ({quality.get('rating')}).",
                "Data quality",
                "Follow the listed improvement steps on the analysis page. This indicator is not a certification.",
                "Better evidence, not automatically a lower footprint",
            )
        )

    if scenario_summary and scenario_summary.get("baseline_kg") is not None:
        baseline = scenario_summary["baseline_kg"]
        scenario = scenario_summary.get("scenario_kg")
        pct = scenario_summary.get("percent_difference")
        if pct is not None and baseline:
            direction = "reduction" if pct > 0 else "increase"
            recs.append(
                Recommendation(
                    recommendation_id="REC-SCENARIO",
                    title="A calculated hypothetical scenario is available",
                    explanation=(
                        "The scenario optimiser used the same calculation engine on modified inputs. "
                        "This is not a measured real-world improvement."
                    ),
                    supporting_observation=(
                        f"Baseline {baseline:,.2f} kg CO₂e versus scenario {scenario:,.2f} kg CO₂e "
                        f"({pct:+.1f}% {direction} relative to baseline)."
                    ),
                    relevant_activity_or_category=str(scenario_summary.get("affected_categories") or "Scenario"),
                    suggested_action="Record the exact modified assumptions alongside any presentation of this comparison.",
                    expected_direction=f"Hypothetical {direction} of {abs(pct):.1f}% in this model",
                    confidence_status="Modelled scenario only",
                    required_next_data="Evidence that the modelled change can be implemented",
                    limitations="Do not count the same modelled reduction more than once or treat it as verified savings.",
                )
            )

    if not recs:
        recs.append(
            _rule(
                "REC-GENERIC",
                "Document assumptions and keep the boundary explicit",
                "No dominant hotspot rule was triggered, or the assessed total is zero.",
                "Assessment",
                "Review excluded rows, factor provenance, and whether the functional unit is clearly defined.",
                "Not estimated",
            )
        )
    return recs


def _rule(
    rec_id: str,
    title: str,
    observation: str,
    category: str,
    action: str,
    direction: str,
    confidence: str = "Heuristic rule applied to this assessment",
    next_data: str = "Supporting primary data for the highlighted process",
    limitations: str = "Rule-based guidance; not experimentally validated.",
) -> Recommendation:
    return Recommendation(
        recommendation_id=rec_id,
        title=title,
        explanation=title + ".",
        supporting_observation=observation,
        relevant_activity_or_category=category,
        suggested_action=action,
        expected_direction=direction,
        confidence_status=confidence,
        required_next_data=next_data,
        limitations=limitations,
    )
