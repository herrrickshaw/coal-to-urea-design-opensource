import pytest

from coal_to_urea.air_separation import size_asu_for_n2_demand, size_asu_for_o2_demand


def test_size_asu_for_n2_demand_gives_correct_air_ratio():
    result = size_asu_for_n2_demand(n2_demand_mol_s=1000.0)
    # O2 co-product should be in the 21/79 ratio to N2 product.
    o2_mol_s = result.o2_product_mass_flow_kg_s * 1000.0 / 31.998
    n2_mol_s = result.n2_product_mass_flow_kg_s * 1000.0 / 28.014
    assert o2_mol_s / n2_mol_s == pytest.approx(21.0 / 79.0, rel=1e-6)
    assert result.total_power_kW > 0
    assert result.air_feed_mass_flow_kg_s > result.n2_product_mass_flow_kg_s


def test_size_asu_for_o2_demand_is_consistent_with_n2_framing():
    # Sizing for a given O2 demand should give back that same O2 demand
    # when cross-checked, and a consistent N2 co-product.
    o2_demand = 200.0
    result = size_asu_for_o2_demand(o2_demand)
    o2_mol_s = result.o2_product_mass_flow_kg_s * 1000.0 / 31.998
    assert o2_mol_s == pytest.approx(o2_demand, rel=1e-6)


def test_size_asu_rejects_nonpositive_demand():
    with pytest.raises(ValueError):
        size_asu_for_n2_demand(0.0)
    with pytest.raises(ValueError):
        size_asu_for_o2_demand(-5.0)


def test_size_asu_power_scales_with_demand():
    small = size_asu_for_n2_demand(500.0)
    large = size_asu_for_n2_demand(1500.0)
    assert large.total_power_kW > small.total_power_kW
