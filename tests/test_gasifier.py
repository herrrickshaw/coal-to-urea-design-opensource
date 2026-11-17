import pytest

from coal_to_urea.gasifier import TYPICAL_INDIAN_HIGH_ASH, TYPICAL_US_BITUMINOUS, CoalAnalysis, gasify_coal


def test_coal_analysis_rejects_fractions_not_summing_to_one():
    with pytest.raises(ValueError, match="sum to 1.0"):
        CoalAnalysis(carbon=0.5, hydrogen=0.1, oxygen=0.1, nitrogen=0.1, sulfur=0.1, ash=0.1, moisture=0.1)


def test_hhv_positive_and_in_plausible_range():
    # Coal HHV is typically 15-35 MJ/kg depending on rank/ash - a loose
    # sanity bound (Dulong's formula on as-received basis, see docstring).
    assert 10.0 < TYPICAL_US_BITUMINOUS.hhv_MJ_kg() < 35.0
    assert 10.0 < TYPICAL_INDIAN_HIGH_ASH.hhv_MJ_kg() < 35.0
    # Higher ash/moisture, lower carbon -> lower heating value.
    assert TYPICAL_INDIAN_HIGH_ASH.hhv_MJ_kg() < TYPICAL_US_BITUMINOUS.hhv_MJ_kg()


def test_gasify_coal_mass_and_mole_balance_closes():
    result = gasify_coal(
        TYPICAL_US_BITUMINOUS, coal_mass_flow_kg_s=50.0,
        o2_to_coal_mass_ratio=0.85, steam_to_coal_mass_ratio=0.15,
        gasifier_T_K=1673.15, carbon_conversion=0.98,
    )
    total_frac = sum(result.syngas_composition_mole_frac.values())
    assert total_frac == pytest.approx(1.0, abs=1e-9)
    for frac in result.syngas_composition_mole_frac.values():
        assert frac >= 0.0
    assert result.syngas_molar_flow_mol_s > 0
    assert result.syngas_mass_flow_kg_s > 0


def test_gasify_coal_cold_gas_efficiency_matches_published_range():
    # Found by running this module: the O2/coal ratio must scale with
    # coal.carbon, not be reused verbatim across coal qualities (see
    # gasify_coal's docstring). At a correctly scaled O2 ratio, the
    # Indian high-ash preset's cold gas efficiency should land near
    # CSIR-CIMFR's publicly reported ~65% for Indian high-ash coal
    # gasification (NITI Aayog workshop report, see docs/VALIDATION.md).
    result = gasify_coal(
        TYPICAL_INDIAN_HIGH_ASH, coal_mass_flow_kg_s=80.0,
        o2_to_coal_mass_ratio=0.55, steam_to_coal_mass_ratio=0.10,
        gasifier_T_K=1673.15, carbon_conversion=0.90,
    )
    assert 0.55 < result.cold_gas_efficiency < 0.75


def test_gasify_coal_unscaled_o2_ratio_on_low_carbon_coal_gives_poor_efficiency():
    # The regression this repo's own finding warns against: reusing the
    # bituminous-coal-calibrated O2 ratio directly on high-ash coal
    # over-oxidizes it - cold gas efficiency should be noticeably worse
    # than the scaled case above, not just "a bit lower".
    result = gasify_coal(
        TYPICAL_INDIAN_HIGH_ASH, coal_mass_flow_kg_s=80.0,
        o2_to_coal_mass_ratio=0.75, steam_to_coal_mass_ratio=0.12,
        gasifier_T_K=1673.15, carbon_conversion=0.90,
    )
    assert result.cold_gas_efficiency < 0.50


def test_gasify_coal_rejects_invalid_carbon_conversion():
    with pytest.raises(ValueError, match="carbon_conversion"):
        gasify_coal(TYPICAL_US_BITUMINOUS, 50.0, 0.85, 0.15, 1673.15, carbon_conversion=1.5)


def test_gasify_coal_higher_o2_ratio_shifts_toward_co2_away_from_co():
    # More O2 per unit coal pushes the elemental O budget toward more
    # complete oxidation (more CO2/H2O, less CO/H2) - the qualitative
    # direction any gasifier O2 ratio should move in.
    low_o2 = gasify_coal(TYPICAL_US_BITUMINOUS, 50.0, 0.70, 0.15, 1673.15, carbon_conversion=0.98)
    high_o2 = gasify_coal(TYPICAL_US_BITUMINOUS, 50.0, 1.00, 0.15, 1673.15, carbon_conversion=0.98)
    assert high_o2.syngas_composition_mole_frac["CarbonDioxide"] > low_o2.syngas_composition_mole_frac["CarbonDioxide"]
    assert high_o2.syngas_composition_mole_frac["CarbonMonoxide"] < low_o2.syngas_composition_mole_frac["CarbonMonoxide"]


def test_dulong_hhv_hand_values():
    # 33.87 C + 144.3 (H - O/8) + 9.4 S, MJ/kg
    # bituminous: 22.0155 + 5.0505 + 0.188 = 27.254
    # Indian high-ash: 14.2254 + 3.24675 + 0.1222 = 17.5944
    assert TYPICAL_US_BITUMINOUS.hhv_MJ_kg() == pytest.approx(27.254, rel=1e-5)
    assert TYPICAL_INDIAN_HIGH_ASH.hhv_MJ_kg() == pytest.approx(17.5944, rel=1e-5)


def test_moe_wgs_equilibrium_constant_hand_value():
    from coal_to_urea.gasifier import _wgs_equilibrium_K
    # exp(4577.8/500 - 4.33) = exp(4.8256) = 124.66; K = 1 at T = 4577.8/4.33 = 1057.2 K
    assert _wgs_equilibrium_K(500.0) == pytest.approx(124.661, rel=1e-4)
    assert _wgs_equilibrium_K(4577.8 / 4.33) == pytest.approx(1.0)


def _atoms_out(result):
    n = result.syngas_molar_flow_mol_s
    y = result.syngas_composition_mole_frac
    m = {k: v * n for k, v in y.items()}
    return {
        "C": m["CarbonMonoxide"] + m["CarbonDioxide"],
        "H": 2 * m["Hydrogen"] + 2 * m["Water"] + 2 * m["HydrogenSulfide"],
        "O": m["CarbonMonoxide"] + 2 * m["CarbonDioxide"] + m["Water"],
        "N": 2 * m["Nitrogen"],
        "S": m["HydrogenSulfide"],
    }


@pytest.mark.parametrize("coal", [TYPICAL_US_BITUMINOUS, TYPICAL_INDIAN_HIGH_ASH])
def test_gasifier_conserves_every_element(coal):
    """Atoms in (converted coal C, coal H/O/N/S, moisture, steam, O2) = atoms out."""
    F, o2r, str_, X = 50.0, 0.85, 0.15, 0.98
    if coal is TYPICAL_INDIAN_HIGH_ASH:
        o2r = 0.55
    r = gasify_coal(coal, F, o2r, str_, 1673.15, X)
    h2o_in = F * (coal.moisture + str_) * 1000 / 18.015
    atoms_in = {
        "C": F * coal.carbon * 1000 / 12.011 * X,
        "H": F * coal.hydrogen * 1000 / 1.008 + 2 * h2o_in,
        "O": F * coal.oxygen * 1000 / 15.999 + h2o_in + 2 * F * o2r * 1000 / 31.998,
        "N": F * coal.nitrogen * 1000 / 14.007,
        "S": F * coal.sulfur * 1000 / 32.06,
    }
    out = _atoms_out(r)
    for el in atoms_in:
        assert out[el] == pytest.approx(atoms_in[el], rel=1e-9), el


def test_gasifier_overall_mass_balance():
    """coal + O2 + steam = syngas + unconverted carbon + ash (within MW rounding)."""
    coal, F = TYPICAL_US_BITUMINOUS, 50.0
    r = gasify_coal(coal, F, 0.85, 0.15, 1673.15, 0.98)
    mass_in = F + r.o2_mass_flow_kg_s + r.steam_mass_flow_kg_s
    mass_out = r.syngas_mass_flow_kg_s + r.unconverted_carbon_kg_s + F * coal.ash
    assert mass_out == pytest.approx(mass_in, rel=2e-4)
