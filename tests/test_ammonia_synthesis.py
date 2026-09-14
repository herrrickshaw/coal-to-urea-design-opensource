import pytest

from coal_to_urea.ammonia_synthesis import (
    ammonia_synthesis_loop,
    makeup_gas_compressor_power,
    validate_feed_ratio,
)


def test_validate_feed_ratio_accepts_stoichiometric_feed():
    validate_feed_ratio(1500.0, 500.0)  # exactly 3:1


def test_validate_feed_ratio_rejects_off_ratio_feed():
    with pytest.raises(ValueError, match="stoichiometric"):
        validate_feed_ratio(1000.0, 1000.0)  # 1:1, way off


def test_ammonia_loop_mass_balance_h2_n2_atoms_conserved():
    F_h2, F_n2 = 1500.0, 500.0
    result = ammonia_synthesis_loop(F_h2, F_n2, single_pass_conversion=0.19, purge_fraction=0.02)
    # Every mole of fresh feed (H2+N2) must leave as NH3 (2 mol reactant
    # per mol NH3... i.e. NH3*2 mol reactant-equivalent) or purge loss.
    fresh_total = F_h2 + F_n2
    accounted = 2.0 * result.nh3_product_mol_s + result.purge_loss_mol_s
    assert accounted == pytest.approx(fresh_total, rel=1e-6)


def test_ammonia_loop_overall_conversion_exceeds_single_pass():
    # The whole point of the recycle loop - overall conversion should be
    # much higher than the single-pass conversion.
    result = ammonia_synthesis_loop(1500.0, 500.0, single_pass_conversion=0.19, purge_fraction=0.02)
    assert result.overall_conversion > 0.19


def test_ammonia_loop_lower_purge_gives_higher_overall_conversion():
    low_purge = ammonia_synthesis_loop(1500.0, 500.0, 0.19, purge_fraction=0.01)
    high_purge = ammonia_synthesis_loop(1500.0, 500.0, 0.19, purge_fraction=0.05)
    assert low_purge.overall_conversion > high_purge.overall_conversion


def test_ammonia_loop_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        ammonia_synthesis_loop(1500.0, 500.0, single_pass_conversion=1.5)
    with pytest.raises(ValueError):
        ammonia_synthesis_loop(1500.0, 500.0, 0.19, purge_fraction=0.0)


def test_makeup_gas_compressor_power_positive_and_increases_with_ratio():
    low = makeup_gas_compressor_power(1500.0, 500.0, 313.15, 40e5, 100e5)
    high = makeup_gas_compressor_power(1500.0, 500.0, 313.15, 40e5, 200e5)
    assert 0 < low < high


def test_makeup_gas_compressor_power_rejects_bad_pressure_ordering():
    with pytest.raises(ValueError):
        makeup_gas_compressor_power(1500.0, 500.0, 313.15, 200e5, 100e5)
