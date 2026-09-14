import pytest

from coal_to_urea.acid_gas_removal import remove_acid_gases, size_agr_column

SHIFTED_GAS = {"CarbonMonoxide": 0.009, "CarbonDioxide": 0.363, "Hydrogen": 0.460,
                "Water": 0.160, "HydrogenSulfide": 0.005, "Nitrogen": 0.003}


def test_remove_acid_gases_mass_balance_closes():
    result = remove_acid_gases(SHIFTED_GAS, 1000.0, co2_removal_fraction=0.97, h2s_removal_fraction=0.999)
    total = sum(result.treated_gas_composition_mole_frac.values())
    assert total == pytest.approx(1.0, abs=1e-9)
    for frac in result.treated_gas_composition_mole_frac.values():
        assert frac >= 0.0


def test_remove_acid_gases_captures_expected_co2():
    n_co2_in = SHIFTED_GAS["CarbonDioxide"] * 1000.0
    result = remove_acid_gases(SHIFTED_GAS, 1000.0, co2_removal_fraction=0.97, h2s_removal_fraction=0.999)
    assert result.captured_co2_molar_flow_mol_s == pytest.approx(n_co2_in * 0.97, rel=1e-9)
    assert result.captured_co2_mass_flow_kg_s > 0
    # Treated gas CO2 mole fraction should drop sharply.
    assert result.treated_gas_composition_mole_frac["CarbonDioxide"] < 0.02


def test_remove_acid_gases_rejects_invalid_fraction():
    with pytest.raises(ValueError):
        remove_acid_gases(SHIFTED_GAS, 1000.0, co2_removal_fraction=1.5)


def test_size_agr_column_returns_positive_sane_dimensions():
    result = size_agr_column(
        gas_volumetric_flow_m3_s=5.0, gas_density_kg_m3=20.0, liquid_density_kg_m3=1010.0,
        y_in_mole_frac=0.363, y_out_target_mole_frac=0.005, x_in_mole_frac=0.001,
        equilibrium_slope_m=0.4, liquid_to_gas_molar_ratio=0.8,
    )
    assert result.diameter_m > 0
    assert result.n_theoretical_stages > 0
    assert result.packed_height_m > 0


def test_size_agr_column_rejects_infeasible_absorption_factor():
    with pytest.raises(ValueError, match="Absorption factor"):
        size_agr_column(
            gas_volumetric_flow_m3_s=5.0, gas_density_kg_m3=20.0, liquid_density_kg_m3=1010.0,
            y_in_mole_frac=0.363, y_out_target_mole_frac=0.005, x_in_mole_frac=0.001,
            equilibrium_slope_m=0.4, liquid_to_gas_molar_ratio=0.1,  # A < 1
        )
