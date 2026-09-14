import pytest

from coal_to_urea.urea_synthesis import co2_conversion_per_pass, synthesize_urea


def test_co2_conversion_rejects_substoichiometric_ratio():
    with pytest.raises(ValueError, match="2.0"):
        co2_conversion_per_pass(1.5)


def test_co2_conversion_increases_with_nh3_to_co2_ratio():
    low = co2_conversion_per_pass(2.8)
    high = co2_conversion_per_pass(4.5)
    assert 0.0 < low < high < 1.0


def test_co2_conversion_decreases_with_water_content():
    dry = co2_conversion_per_pass(3.5, h2o_to_co2_molar_ratio=0.0)
    wet = co2_conversion_per_pass(3.5, h2o_to_co2_molar_ratio=1.0)
    assert wet < dry


def test_co2_conversion_in_commonly_reported_range_at_typical_ratio():
    # N/C~3.5 is a typical practical design point - conversion should
    # land in the commonly reported ~50-70% per-pass range.
    conversion = co2_conversion_per_pass(3.5)
    assert 0.45 < conversion < 0.75


def test_synthesize_urea_mass_balance_closes():
    result = synthesize_urea(nh3_feed_mol_s=1400.0, co2_feed_mol_s=400.0)
    assert result.urea_produced_mol_s > 0
    assert result.water_produced_mol_s == pytest.approx(result.urea_produced_mol_s)
    assert result.unconverted_co2_mol_s == pytest.approx(400.0 - result.urea_produced_mol_s)
    assert result.unconverted_nh3_mol_s == pytest.approx(1400.0 - 2.0 * result.urea_produced_mol_s)
    assert result.unconverted_co2_mol_s >= 0
    assert result.unconverted_nh3_mol_s >= 0


def test_synthesize_urea_respects_conversion_override():
    result = synthesize_urea(1400.0, 400.0, conversion_override=0.5)
    assert result.urea_produced_mol_s == pytest.approx(200.0)
    assert result.co2_conversion == pytest.approx(0.5)


def test_synthesize_urea_rejects_infeasible_nh3_shortage():
    # Forcing near-total CO2 conversion but starving NH3 must fail
    # loudly, not silently produce more urea than NH3 allows.
    with pytest.raises(ValueError, match="Infeasible"):
        synthesize_urea(nh3_feed_mol_s=100.0, co2_feed_mol_s=400.0, conversion_override=0.8)


def test_synthesize_urea_rejects_nonpositive_co2_feed():
    with pytest.raises(ValueError):
        synthesize_urea(1400.0, 0.0)
