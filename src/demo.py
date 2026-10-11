"""Load a small, labelled demonstration dataset without duplicating records."""

from __future__ import annotations

from src.database import Database
from src.factor_registry import seed_registry
from src.models import ActivityInput, AssessmentInput, ProductInput
from src.services import create_and_calculate, persist_scenario, compute_unsaved_scenario

DEMO_AL = "DEMO-AL-CAN-2024"
DEMO_STEEL = "DEMO-STEEL-BRACKET-2024"


def ensure_factors(db: Database) -> None:
    seed_registry(db)


def demo_already_loaded(db: Database) -> bool:
    return db.find_demo_assessment(DEMO_AL) is not None


def load_demonstration_dataset(db: Database) -> dict[str, int]:
    """Idempotent demo loader. Does not overwrite user assessments."""
    ensure_factors(db)
    created: dict[str, int] = {}
    existing_al = db.find_demo_assessment(DEMO_AL)
    if existing_al:
        created["aluminium"] = existing_al
    else:
        created["aluminium"] = _load_aluminium(db)
    existing_st = db.find_demo_assessment(DEMO_STEEL)
    if existing_st:
        created["steel"] = existing_st
    else:
        created["steel"] = _load_steel(db)
    return created


def _load_aluminium(db: Database) -> int:
    product = ProductInput(
        name="Aluminium beverage-can body (demonstration)",
        category="Packaging component",
        material_type="Aluminium",
        notes=(
            "Synthetic demonstration product for the CSL225 prototype. "
            "Activity quantities are invented for teaching and are not plant measurements."
        ),
        is_demo=True,
    )
    assessment = AssessmentInput(
        name="Demo — aluminium can body, 10,000 units",
        production_quantity=10000,
        production_quantity_unit="units",
        functional_unit="1 can body",
        functional_unit_quantity=10000,
        reporting_period="2024 (synthetic demonstration year)",
        location="Gurugram, Haryana, India (illustrative location)",
        boundary="cradle_to_gate",
        notes=(
            "Demonstration assessment. Factors are illustrative. One chemical process row "
            "is intentionally left without a factor to show exclusion behaviour."
        ),
        is_demo=True,
        data_origin="demonstration",
    )
    activities = [
        ActivityInput(
            category="Raw materials",
            description="Primary aluminium sheet (synthetic quantity)",
            life_cycle_stage="Raw material supply",
            quantity=150,
            quantity_unit="kg",
            factor_id="EF-AL-PRIM-ILLUS",
            data_origin="demonstration",
            supplier_note="Demo mill A",
            evidence_reference="Synthetic demonstration record",
        ),
        ActivityInput(
            category="Raw materials",
            description="Recycled aluminium (synthetic quantity)",
            life_cycle_stage="Raw material supply",
            quantity=50,
            quantity_unit="kg",
            factor_id="EF-AL-REC-ILLUS",
            data_origin="demonstration",
            supplier_note="Demo scrap stream",
            evidence_reference="Synthetic demonstration record",
        ),
        ActivityInput(
            category="Electricity",
            description="Forming and finishing electricity",
            life_cycle_stage="Manufacturing",
            quantity=450,
            quantity_unit="kWh",
            factor_id="EF-ELEC-IN-GRID-ILLUS",
            data_origin="estimated",
            evidence_reference="Synthetic electricity estimate",
        ),
        ActivityInput(
            category="Fuel and direct energy use",
            description="On-site diesel for handling equipment",
            life_cycle_stage="Manufacturing",
            quantity=40,
            quantity_unit="L",
            factor_id="EF-DIESEL-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Inbound transport",
            description="Coil inbound freight",
            life_cycle_stage="Inbound logistics",
            quantity=80,
            quantity_unit="tkm",
            factor_id="EF-TRUCK-TKM-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Outbound transport",
            description="Finished goods outbound freight",
            life_cycle_stage="Outbound logistics",
            quantity=45,
            quantity_unit="tkm",
            factor_id="EF-TRUCK-TKM-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Water consumption",
            description="Process and wash water",
            life_cycle_stage="Manufacturing",
            quantity=8,
            quantity_unit="m3",
            factor_id="EF-WATER-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Waste treatment",
            description="Offcut scrap to landfill (non-recycled fraction)",
            life_cycle_stage="Manufacturing",
            quantity=12,
            quantity_unit="kg",
            factor_id="EF-WASTE-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Manufacturing processes",
            description="Surface-treatment chemicals (no factor available)",
            life_cycle_stage="Manufacturing",
            quantity=6,
            quantity_unit="kg",
            factor_id=None,
            data_origin="estimated",
            evidence_reference="Intentionally unmapped to demonstrate missing-factor handling",
        ),
    ]
    payload = create_and_calculate(db, product, assessment, activities, demo_key=DEMO_AL)
    scenario = compute_unsaved_scenario(
        db,
        payload["assessment_id"],
        {
            "electricity_multiplier": 0.80,
            "electricity_factor_id": "EF-ELEC-RE-MIX-ILLUS",
            "transport_distance_multiplier": 0.70,
            "recycled_share": 0.60,
        },
    )
    persist_scenario(
        db,
        payload["assessment_id"],
        "Demo efficiency and recycled-content case",
        "Electricity −20%, illustrative lower-carbon electricity factor, transport −30%, recycled aluminium share 60%. Hypothetical only.",
        scenario,
    )
    return payload["assessment_id"]


def _load_steel(db: Database) -> int:
    product = ProductInput(
        name="Pressed steel bracket (demonstration)",
        category="Fabricated metal product",
        material_type="Steel",
        notes="Synthetic demonstration steel product for comparison in the prototype.",
        is_demo=True,
    )
    assessment = AssessmentInput(
        name="Demo — steel bracket, 2,000 units",
        production_quantity=2000,
        production_quantity_unit="units",
        functional_unit="1 bracket",
        functional_unit_quantity=2000,
        reporting_period="2024 (synthetic demonstration year)",
        location="Gurugram, Haryana, India (illustrative location)",
        boundary="cradle_to_gate",
        notes="Second demonstration assessment for steel versus aluminium comparison.",
        is_demo=True,
        data_origin="demonstration",
    )
    activities = [
        ActivityInput(
            category="Raw materials",
            description="Primary steel coil",
            life_cycle_stage="Raw material supply",
            quantity=420,
            quantity_unit="kg",
            factor_id="EF-STEEL-BOF-ILLUS",
            data_origin="demonstration",
        ),
        ActivityInput(
            category="Raw materials",
            description="Recycled steel input",
            life_cycle_stage="Raw material supply",
            quantity=80,
            quantity_unit="kg",
            factor_id="EF-STEEL-EAF-ILLUS",
            data_origin="demonstration",
        ),
        ActivityInput(
            category="Electricity",
            description="Pressing and welding electricity",
            life_cycle_stage="Manufacturing",
            quantity=310,
            quantity_unit="kWh",
            factor_id="EF-ELEC-IN-GRID-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Inbound transport",
            description="Coil inbound freight",
            life_cycle_stage="Inbound logistics",
            quantity=120,
            quantity_unit="tkm",
            factor_id="EF-TRUCK-TKM-ILLUS",
            data_origin="estimated",
        ),
        ActivityInput(
            category="Outbound transport",
            description="Bracket outbound freight",
            life_cycle_stage="Outbound logistics",
            quantity=60,
            quantity_unit="tkm",
            factor_id="EF-TRUCK-TKM-ILLUS",
            data_origin="estimated",
        ),
    ]
    payload = create_and_calculate(db, product, assessment, activities, demo_key=DEMO_STEEL)
    return payload["assessment_id"]
