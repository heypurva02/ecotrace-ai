"""Explicit unit conversions for supported LCA activity units.

Unsupported units are rejected. This is not a universal unit engine.
"""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_MASS = {"g": 0.001, "kg": 1.0, "t": 1000.0, "tonne": 1000.0, "tonnes": 1000.0}
SUPPORTED_ENERGY = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}
SUPPORTED_DISTANCE = {"m": 0.001, "km": 1.0}
SUPPORTED_VOLUME = {"l": 0.001, "litre": 0.001, "litres": 0.001, "m3": 1.0, "m^3": 1.0}
SUPPORTED_TKM = {"tkm": 1.0, "t.km": 1.0, "tonne-km": 1.0}
SUPPORTED_COUNT = {"unit": 1.0, "units": 1.0, "piece": 1.0, "pieces": 1.0}


class UnitConversionError(ValueError):
    """Raised when two units cannot be converted."""


@dataclass(frozen=True)
class ConversionResult:
    quantity: float
    from_unit: str
    to_unit: str
    conversion_applied: str


def normalise_unit(unit: str) -> str:
    if unit is None:
        raise UnitConversionError("Unit is missing.")
    text = str(unit).strip().lower()
    text = text.replace(" ", "")
    aliases = {
        "kgco2e": "kg_co2e",
        "kgco2eq": "kg_co2e",
        "tco2e": "t_co2e",
        "kwh": "kWh",
        "wh": "Wh",
        "mwh": "MWh",
        "m³": "m3",
        "cubicmetre": "m3",
        "cubicmetres": "m3",
        "cubicmeter": "m3",
        "liter": "L",
        "liters": "L",
        "litre": "L",
        "litres": "L",
        "l": "L",
        "ton": "t",
        "tons": "t",
        "tonne": "t",
        "tonnes": "t",
        "gram": "g",
        "grams": "g",
        "metre": "m",
        "meter": "m",
        "metres": "m",
        "meters": "m",
        "kilometre": "km",
        "kilometer": "km",
        "tkm": "tkm",
        "t·km": "tkm",
    }
    if text in aliases:
        return aliases[text]
    if text in {"kg", "g", "t", "km", "m", "m3", "unit", "units", "piece", "pieces"}:
        return "units" if text in {"unit", "units", "piece", "pieces"} else text
    return str(unit).strip()


def _family(unit: str) -> tuple[str, dict[str, float], str]:
    key = str(unit).strip().lower().replace(" ", "")
    if key in SUPPORTED_MASS:
        return "mass", SUPPORTED_MASS, "kg"
    if key in SUPPORTED_ENERGY:
        return "energy", SUPPORTED_ENERGY, "kWh"
    if key in SUPPORTED_DISTANCE:
        return "distance", SUPPORTED_DISTANCE, "km"
    if key in SUPPORTED_VOLUME:
        return "volume", SUPPORTED_VOLUME, "m3"
    if key in SUPPORTED_TKM:
        return "tkm", SUPPORTED_TKM, "tkm"
    if key in SUPPORTED_COUNT:
        return "count", SUPPORTED_COUNT, "units"
    raise UnitConversionError(
        f"Unsupported unit '{unit}'. Supported families: mass (g, kg, t), "
        "energy (Wh, kWh, MWh), distance (m, km), volume (L, m3), "
        "freight (tkm), count (units)."
    )


def same_family(unit_a: str, unit_b: str) -> bool:
    try:
        return _family(unit_a)[0] == _family(unit_b)[0]
    except UnitConversionError:
        return False


def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> ConversionResult:
    """Convert quantity into the factor reference unit when families match."""
    from_key = str(from_unit).strip().lower().replace(" ", "")
    to_key = str(to_unit).strip().lower().replace(" ", "")
    fam_from, table_from, _ = _family(from_unit)
    fam_to, table_to, _ = _family(to_unit)
    if fam_from != fam_to:
        raise UnitConversionError(
            f"Incompatible units: cannot convert {from_unit} to {to_unit}."
        )
    if from_key not in table_from or to_key not in table_to:
        raise UnitConversionError(
            f"Incompatible units: cannot convert {from_unit} to {to_unit}."
        )
    base = quantity * table_from[from_key]
    converted = base / table_to[to_key]
    if from_key == to_key:
        applied = "none"
    else:
        applied = f"{from_unit} -> {to_unit} (family {fam_from})"
    return ConversionResult(
        quantity=converted,
        from_unit=from_unit,
        to_unit=to_unit,
        conversion_applied=applied,
    )


def units_compatible(activity_unit: str, reference_unit: str) -> bool:
    try:
        convert_quantity(1.0, activity_unit, reference_unit)
        return True
    except UnitConversionError:
        return False
