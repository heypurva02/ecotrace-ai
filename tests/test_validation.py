from src.models import ActivityInput, AssessmentInput, EmissionFactor, ProductInput
from src.validation import split_issues, validate_activities, validate_assessment, validate_product

FACTOR = EmissionFactor(
    factor_id="EF-TEST",
    name="t",
    activity_category="Electricity",
    material_or_activity_type="e",
    factor_value=1,
    reference_activity_unit="kWh",
    provenance="illustrative",
)


def test_blank_product_name():
    issues = validate_product(ProductInput(name="  ", category="c", material_type="Aluminium"))
    assert any(i.level == "error" for i in issues)


def test_other_material_warning():
    issues = validate_product(ProductInput(name="P", category="c", material_type="Other"))
    assert any(i.level == "warning" for i in issues)


def test_non_positive_production():
    assessment = AssessmentInput(
        name="A",
        production_quantity=0,
        production_quantity_unit="units",
        functional_unit="1",
        functional_unit_quantity=1,
        reporting_period="2024",
        location="India",
        boundary="cradle_to_gate",
    )
    errors, _ = split_issues(validate_assessment(assessment))
    assert errors


def test_negative_quantity():
    issues = validate_activities(
        [
            ActivityInput(
                category="Electricity",
                description="e",
                life_cycle_stage="Manufacturing",
                quantity=-2,
                quantity_unit="kWh",
                factor_id="EF-TEST",
            )
        ],
        {"EF-TEST": FACTOR},
    )
    assert any("negative" in i.message.lower() for i in issues)
