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


def test_souders_brown_and_kremser_hand_values():
    # v_flood = 0.04 sqrt((1000-20)/20) = 0.28 m/s; x 0.75 = 0.21 m/s; 1 m3/s -> D = 2.4623 m
    # Kremser, A = 1.5/1 = 1.5, y 0.30 -> 0.01, x_in 0:
    #   N = ln(30 (1 - 1/1.5) + 1/1.5) / ln 1.5 = 5.83805
    r = size_agr_column(1.0, 20.0, 1000.0, y_in_mole_frac=0.30, y_out_target_mole_frac=0.01,
                        x_in_mole_frac=0.0, equilibrium_slope_m=1.0, liquid_to_gas_molar_ratio=1.5)
    assert r.diameter_m == pytest.approx(2.46233, rel=1e-5)
    assert r.n_theoretical_stages == pytest.approx(5.83805, rel=1e-5)
    assert r.packed_height_m == pytest.approx(5.83805 * 0.6, rel=1e-5)


def test_agr_h2s_removed_and_inerts_untouched():
    comp = {"Hydrogen": 0.5, "CarbonDioxide": 0.4, "HydrogenSulfide": 0.01, "Nitrogen": 0.09}
    r = remove_acid_gases(comp, 100.0, co2_removal_fraction=0.97, h2s_removal_fraction=0.999)
    assert r.captured_h2s_molar_flow_mol_s == pytest.approx(0.999)
    assert r.treated_gas_molar_flow_mol_s == pytest.approx(100 - 38.8 - 0.999)
    assert r.captured_co2_mass_flow_kg_s == pytest.approx(38.8 * 44.01 / 1000)
