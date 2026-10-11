from src.unit_conversion import UnitConversionError, convert_quantity, units_compatible
import pytest


def test_wh_to_kwh():
    result = convert_quantity(1500, "Wh", "kWh")
    assert result.quantity == pytest.approx(1.5)
    assert "Wh" in result.conversion_applied


def test_g_to_kg():
    result = convert_quantity(2500, "g", "kg")
    assert result.quantity == pytest.approx(2.5)


def test_kg_to_tonnes():
    assert convert_quantity(2500, "kg", "t").quantity == pytest.approx(2.5)


def test_litres_to_m3():
    assert convert_quantity(1500, "L", "m3").quantity == pytest.approx(1.5)


def test_incompatible_units():
    with pytest.raises(UnitConversionError):
        convert_quantity(1, "kWh", "kg")
    assert not units_compatible("kWh", "kg")


def test_unknown_unit():
    with pytest.raises(UnitConversionError):
        convert_quantity(1, "barrels", "kg")
