import pytest

from coal_to_urea.shift_reactor import shift_reactor

SYNGAS = {"CarbonMonoxide": 0.44, "CarbonDioxide": 0.09, "Hydrogen": 0.23,
          "Water": 0.23, "HydrogenSulfide": 0.007, "Nitrogen": 0.003}


def test_shift_reactor_mass_balance_closes():
    result = shift_reactor(SYNGAS, inlet_molar_flow_mol_s=1000.0, additional_steam_mol_s=300.0,
                            reactor_T_K=623.15, approach_to_equilibrium_K=20.0)
    total = sum(result.outlet_composition_mole_frac.values())
    assert total == pytest.approx(1.0, abs=1e-9)
    for frac in result.outlet_composition_mole_frac.values():
        assert frac >= 0.0


def test_shift_reactor_converts_co_to_h2():
    result = shift_reactor(SYNGAS, 1000.0, additional_steam_mol_s=300.0,
                            reactor_T_K=623.15, approach_to_equilibrium_K=20.0)
    assert result.co_conversion > 0.5
    assert result.outlet_composition_mole_frac["Hydrogen"] > SYNGAS["Hydrogen"]
    assert result.outlet_composition_mole_frac["CarbonMonoxide"] < SYNGAS["CarbonMonoxide"]


def test_shift_reactor_lower_temperature_gives_higher_equilibrium_conversion():
    # WGS is exothermic - lower T favors CO2/H2 (Le Chatelier), so a
    # colder stage should convert more CO at the same approach margin.
    hot = shift_reactor(SYNGAS, 1000.0, 300.0, reactor_T_K=673.15, approach_to_equilibrium_K=10.0)
    cold = shift_reactor(SYNGAS, 1000.0, 300.0, reactor_T_K=493.15, approach_to_equilibrium_K=10.0)
    assert cold.co_conversion > hot.co_conversion


def test_shift_reactor_more_steam_increases_conversion():
    less_steam = shift_reactor(SYNGAS, 1000.0, additional_steam_mol_s=100.0,
                                reactor_T_K=623.15, approach_to_equilibrium_K=20.0)
    more_steam = shift_reactor(SYNGAS, 1000.0, additional_steam_mol_s=500.0,
                                reactor_T_K=623.15, approach_to_equilibrium_K=20.0)
    assert more_steam.co_conversion > less_steam.co_conversion


def test_shift_reactor_inert_species_pass_through_unchanged_in_absolute_moles():
    result = shift_reactor(SYNGAS, 1000.0, additional_steam_mol_s=300.0,
                            reactor_T_K=623.15, approach_to_equilibrium_K=20.0)
    n2_in_abs = SYNGAS["Nitrogen"] * 1000.0
    n2_out_abs = result.outlet_composition_mole_frac["Nitrogen"] * result.outlet_molar_flow_mol_s
    assert n2_out_abs == pytest.approx(n2_in_abs, rel=1e-6)
