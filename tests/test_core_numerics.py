"""Hand-computed values, invariants and error paths for the coal-to-urea modules.

Expected numbers are derived on paper from the formulas in each module
docstring. CoolProp mixture state calls are replaced by a fake wherever a
number depends on them (no real high-pressure mixture output is asserted).
"""
import math

import pytest

from coal_to_urea import acid_gas_removal as AGR
from coal_to_urea import air_separation as ASU
from coal_to_urea import ammonia_synthesis as NH3
from coal_to_urea import gasifier as G
from coal_to_urea import properties as P
from coal_to_urea import shift_reactor as SR
from coal_to_urea import urea_synthesis as U

# ----------------------------------------------------------------- properties


def test_gas_mixture_requires_mole_fractions_summing_to_one():
    P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.25})
    P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.2500005})  # within 1e-6
    with pytest.raises(ValueError, match="sum to 1.0"):
        P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.26})
    with pytest.raises(ValueError):
        P.GasMixture({"Hydrogen": 0.74, "Nitrogen": 0.25})


def test_heos_string_format_and_order():
    m = P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.25})
    assert m._heos_string() == "Hydrogen[0.75]&Nitrogen[0.25]"


def test_molecular_weight_is_the_mole_weighted_mean():
    m = P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.25})
    assert m.molecular_weight() == pytest.approx(0.75 * 2.016 + 0.25 * 28.014, rel=1e-3)


@pytest.mark.parametrize("method,output", [
    ("cp_over_cv", None), ("compressibility", "Z"), ("density", "Dmass"), ("enthalpy", "Hmass"),
    ("viscosity", "V"), ("thermal_conductivity", "L"), ("specific_heat", "Cpmass"),
])
def test_state_accessors_request_the_right_coolprop_output(monkeypatch, method, output):
    calls = []

    def fake(out, k1, v1, k2, v2, fluid):
        calls.append((out, k1, v1, k2, v2, fluid))
        return {"Cpmass": 14.0, "Cvmass": 10.0}.get(out, 7.0)

    monkeypatch.setattr(P.CP, "PropsSI", fake)
    m = P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.25})
    result = getattr(m, method)(300.0, 2.0e5)
    if method == "cp_over_cv":
        assert result == pytest.approx(1.4)
        assert [c[0] for c in calls] == ["Cpmass", "Cvmass"]
    else:
        assert result == 7.0 if output not in ("Cpmass",) else result == 14.0
        assert calls[0][0] == output
    assert calls[0][1:] == ("T", 300.0, "P", 2.0e5, "Hydrogen[0.75]&Nitrogen[0.25]")


def test_pure_fluid_prop_passes_state_pairs_through():
    # nitrogen normal boiling point, 77.355 K (NIST)
    assert P.pure_fluid_prop("Nitrogen", "T", P=101325.0, Q=0) == pytest.approx(77.355, abs=0.05)


# ---------------------------------------------------------------- gasifier


def test_coal_analysis_must_sum_to_one_and_dulong_hhv():
    with pytest.raises(ValueError, match="sum to 1.0"):
        G.CoalAnalysis(0.5, 0.05, 0.05, 0.01, 0.01, 0.2, 0.2)
    coal = G.CoalAnalysis(carbon=0.6, hydrogen=0.04, oxygen=0.08, nitrogen=0.01, sulfur=0.02, ash=0.15, moisture=0.10)
    # 33.87*0.6 + 144.3*(0.04 - 0.08/8) + 9.4*0.02
    assert coal.hhv_MJ_kg() == pytest.approx(33.87 * 0.6 + 144.3 * 0.03 + 9.4 * 0.02)


def test_wgs_equilibrium_constant_matches_moe_correlation():
    assert G._wgs_equilibrium_K(1000.0) == pytest.approx(math.exp(4.5778 - 4.33))
    assert G._wgs_equilibrium_K(800.0) > G._wgs_equilibrium_K(1000.0) > G._wgs_equilibrium_K(1600.0)


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.0001])
def test_carbon_conversion_range(bad):
    with pytest.raises(ValueError, match="carbon_conversion"):
        G.gasify_coal(G.TYPICAL_US_BITUMINOUS, 10.0, 0.85, 0.2, 1700.0, carbon_conversion=bad)


def test_full_carbon_conversion_leaves_no_unconverted_carbon():
    r = G.gasify_coal(G.TYPICAL_US_BITUMINOUS, 10.0, 0.85, 0.2, 1700.0, carbon_conversion=1.0)
    assert r.unconverted_carbon_kg_s == 0.0


def _gasify_us(**kw):
    args = dict(coal=G.TYPICAL_US_BITUMINOUS, coal_mass_flow_kg_s=10.0, o2_to_coal_mass_ratio=0.85,
                steam_to_coal_mass_ratio=0.2, gasifier_T_K=1700.0)
    args.update(kw)
    return G.gasify_coal(**args)


def test_gasifier_feed_flows_and_unconverted_carbon_are_exact():
    r = _gasify_us()
    assert r.o2_mass_flow_kg_s == pytest.approx(8.5)
    assert r.steam_mass_flow_kg_s == pytest.approx(2.0)
    assert r.unconverted_carbon_kg_s == pytest.approx(10.0 * 0.650 * 0.02)  # (1 - 0.98) of the coal carbon
    assert r.carbon_conversion == 0.98


def test_gasifier_conserves_carbon_hydrogen_oxygen():
    coal, m = G.TYPICAL_US_BITUMINOUS, 10.0
    r = _gasify_us()
    comp, n = r.syngas_composition_mole_frac, r.syngas_molar_flow_mol_s
    mol = {k: v * n for k, v in comp.items()}
    assert sum(comp.values()) == pytest.approx(1.0)
    n_c_fed = m * coal.carbon * 1000 / 12.011 * 0.98
    assert mol["CarbonMonoxide"] + mol["CarbonDioxide"] == pytest.approx(n_c_fed, rel=1e-9)
    h_atoms_in = m * coal.hydrogen * 1000 / 1.008 + 2 * (m * coal.moisture * 1000 / 18.015 + 2.0 * 1000 / 18.015)
    h_atoms_out = 2 * mol["Hydrogen"] + 2 * mol["Water"]
    assert h_atoms_out == pytest.approx(h_atoms_in, rel=1e-9)
    o_in = (m * coal.oxygen * 1000 / 15.999 + (m * coal.moisture * 1000 / 18.015 + 2.0 * 1000 / 18.015)
            + 2 * 8.5 * 1000 / 31.998)
    o_out = mol["CarbonMonoxide"] + 2 * mol["CarbonDioxide"] + mol["Water"]
    assert o_out == pytest.approx(o_in, rel=1e-9)
    # sulfur leaves as H2S, nitrogen as N2
    assert mol["HydrogenSulfide"] == pytest.approx(m * coal.sulfur * 1000 / 32.06)
    assert mol["Nitrogen"] == pytest.approx(m * coal.nitrogen * 1000 / 14.007 / 2)


def test_gasifier_outlet_sits_on_the_water_gas_shift_equilibrium():
    for T in (1500.0, 1700.0):
        c = _gasify_us(gasifier_T_K=T).syngas_composition_mole_frac
        q = (c["CarbonDioxide"] * c["Hydrogen"]) / (c["CarbonMonoxide"] * c["Water"])
        assert q == pytest.approx(G._wgs_equilibrium_K(T), rel=1e-6)


def test_hotter_gasifier_shifts_toward_co_and_cold_gas_efficiency_is_sane():
    cool, hot = _gasify_us(gasifier_T_K=1400.0), _gasify_us(gasifier_T_K=1800.0)
    assert (hot.syngas_composition_mole_frac["CarbonMonoxide"]
            > cool.syngas_composition_mole_frac["CarbonMonoxide"])
    assert 0.3 < hot.cold_gas_efficiency < 1.0


def test_cold_gas_efficiency_matches_its_definition():
    r = _gasify_us()
    n = r.syngas_molar_flow_mol_s
    c = r.syngas_composition_mole_frac
    hhv_gas = n * (c["CarbonMonoxide"] * 283.0 + c["Hydrogen"] * 285.8)
    assert r.cold_gas_efficiency == pytest.approx(hhv_gas / (10.0 * G.TYPICAL_US_BITUMINOUS.hhv_MJ_kg() * 1000))


def test_syngas_mass_flow_is_the_mole_weighted_molar_mass_times_moles():
    r = _gasify_us()
    mw = sum(f * G._species_mw(k) for k, f in r.syngas_composition_mole_frac.items())
    assert r.syngas_mass_flow_kg_s == pytest.approx(r.syngas_molar_flow_mol_s * mw / 1000.0)
    assert G._species_mw("Hydrogen") == 2.016


def test_zero_heating_value_coal_reports_zero_efficiency():
    # all-carbon coal with hydrogen-oxygen balanced so Dulong HHV is exactly 0 is contrived; use
    # a zero-flow-independent path: HHV of 0 needs C=0, so build C=0, H=O/8 coal.
    coal = G.CoalAnalysis(carbon=0.0, hydrogen=0.1, oxygen=0.8, nitrogen=0.0, sulfur=0.0, ash=0.1, moisture=0.0)
    assert coal.hhv_MJ_kg() == pytest.approx(0.0, abs=1e-12)


def test_over_oxidised_feed_has_no_physical_composition():
    pure_c = G.CoalAnalysis(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="No physically valid"):
        G.gasify_coal(pure_c, 1.0, 20.0, 0.0, 1700.0)


# ------------------------------------------------------------ shift reactor


def _wgs_inlet():
    return {"CarbonMonoxide": 0.40, "Water": 0.20, "CarbonDioxide": 0.05, "Hydrogen": 0.30, "Nitrogen": 0.05}


def test_shift_reactor_conserves_atoms_and_inerts():
    r = SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0)
    out = {k: v * r.outlet_molar_flow_mol_s for k, v in r.outlet_composition_mole_frac.items()}
    assert r.outlet_molar_flow_mol_s == pytest.approx(130.0)  # equimolar reaction, steam adds 30
    assert out["Nitrogen"] == pytest.approx(5.0)
    assert out["CarbonMonoxide"] + out["CarbonDioxide"] == pytest.approx(45.0)  # carbon
    assert out["Hydrogen"] + out["Water"] == pytest.approx(30.0 + 20.0 + 30.0)  # hydrogen atoms / 2
    assert sum(r.outlet_composition_mole_frac.values()) == pytest.approx(1.0)
    assert r.co_conversion == pytest.approx((40.0 - out["CarbonMonoxide"]) / 40.0)


def test_shift_reactor_sits_on_equilibrium_at_t_plus_approach():
    for approach in (0.0, 15.0, 40.0):
        r = SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0, approach_to_equilibrium_K=approach)
        c = r.outlet_composition_mole_frac
        q = c["CarbonDioxide"] * c["Hydrogen"] / (c["CarbonMonoxide"] * c["Water"])
        assert q == pytest.approx(SR._wgs_equilibrium_K(700.0 + approach), rel=1e-6)
        assert r.approach_to_equilibrium_K == approach


def test_shift_conversion_trends():
    base = SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0).co_conversion
    assert SR.shift_reactor(_wgs_inlet(), 100.0, 90.0, 700.0).co_conversion > base          # more steam
    assert SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 550.0).co_conversion > base          # exothermic: colder
    assert SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0, 0.0).co_conversion > base     # no approach penalty
    assert 0.0 < base < 1.0


def test_shift_equilibrium_constant_value():
    assert SR._wgs_equilibrium_K(1000.0) == pytest.approx(math.exp(4577.8 / 1000.0 - 4.33))
    assert SR._wgs_equilibrium_K(1000.0) == G._wgs_equilibrium_K(1000.0)


# --------------------------------------------------------- acid gas removal


def _shifted():
    return {"Hydrogen": 0.50, "CarbonDioxide": 0.30, "HydrogenSulfide": 0.01, "Nitrogen": 0.19}


def test_agr_hand_computed_split():
    r = AGR.remove_acid_gases(_shifted(), 100.0)
    assert r.captured_co2_molar_flow_mol_s == pytest.approx(29.1)        # 30 * 0.97
    assert r.captured_h2s_molar_flow_mol_s == pytest.approx(0.999)       # 1 * 0.999
    assert r.captured_co2_mass_flow_kg_s == pytest.approx(29.1 * 44.01 / 1000.0)
    assert r.treated_gas_molar_flow_mol_s == pytest.approx(100.0 - 29.1 - 0.999)
    t = r.treated_gas_composition_mole_frac
    assert t["Hydrogen"] == pytest.approx(50.0 / 69.901)
    assert t["CarbonDioxide"] == pytest.approx(0.9 / 69.901)
    assert sum(t.values()) == pytest.approx(1.0)
    assert (r.co2_removal_fraction, r.h2s_removal_fraction) == (0.97, 0.999)


def test_agr_removal_fraction_boundaries():
    full = AGR.remove_acid_gases(_shifted(), 100.0, co2_removal_fraction=1.0, h2s_removal_fraction=1.0)
    assert full.treated_gas_composition_mole_frac["CarbonDioxide"] == pytest.approx(0.0, abs=1e-12)
    none = AGR.remove_acid_gases(_shifted(), 100.0, co2_removal_fraction=0.0, h2s_removal_fraction=0.0)
    assert none.treated_gas_molar_flow_mol_s == pytest.approx(100.0)
    for kw in ({"co2_removal_fraction": -0.01}, {"co2_removal_fraction": 1.01},
               {"h2s_removal_fraction": -0.01}, {"h2s_removal_fraction": 1.01}):
        with pytest.raises(ValueError, match="must be in"):
            AGR.remove_acid_gases(_shifted(), 100.0, **kw)


def test_agr_without_acid_gases_passes_gas_through():
    r = AGR.remove_acid_gases({"Hydrogen": 0.75, "Nitrogen": 0.25}, 40.0)
    assert r.captured_co2_molar_flow_mol_s == 0.0
    assert r.captured_h2s_molar_flow_mol_s == 0.0
    assert r.treated_gas_molar_flow_mol_s == pytest.approx(40.0)


def _col(**kw):
    args = dict(gas_volumetric_flow_m3_s=2.0, gas_density_kg_m3=10.0, liquid_density_kg_m3=1000.0,
                y_in_mole_frac=0.05, y_out_target_mole_frac=0.001, x_in_mole_frac=0.0,
                equilibrium_slope_m=0.5, liquid_to_gas_molar_ratio=1.0)
    args.update(kw)
    return AGR.size_agr_column(**args)


def test_agr_column_hand_computed():
    r = _col()
    v_design = 0.04 * math.sqrt(99.0) * 0.75           # Souders-Brown flood x 75 %
    area = 2.0 / v_design
    assert r.diameter_m == pytest.approx(math.sqrt(4 * area / math.pi))
    # A = 1.0/0.5 = 2 ; N = ln(50*(1-1/2) + 1/2) / ln 2 = ln 25.5 / ln 2
    assert r.n_theoretical_stages == pytest.approx(math.log(25.5) / math.log(2.0))
    assert r.packed_height_m == pytest.approx(r.n_theoretical_stages * 0.6)
    assert r.percent_of_flood == pytest.approx(75.0)
    r2 = _col(hetp_m=1.0, design_fraction_of_flood=0.5)
    assert r2.packed_height_m == pytest.approx(r2.n_theoretical_stages)
    assert r2.percent_of_flood == pytest.approx(50.0)
    assert r2.diameter_m > r.diameter_m  # lower fraction of flood -> bigger column


def test_agr_column_rejects_absorption_factor_at_or_below_one():
    with pytest.raises(ValueError, match="Absorption factor"):
        _col(liquid_to_gas_molar_ratio=0.5)   # A == 1 exactly
    with pytest.raises(ValueError, match="Absorption factor"):
        _col(liquid_to_gas_molar_ratio=0.4)
    assert _col(liquid_to_gas_molar_ratio=0.51).n_theoretical_stages > 0


def test_agr_column_rejects_unreachable_target():
    with pytest.raises(ValueError, match="below what's achievable"):
        _col(x_in_mole_frac=0.01, y_out_target_mole_frac=0.005)   # y_eq = 0.005 == target
    with pytest.raises(ValueError, match="below what's achievable"):
        _col(x_in_mole_frac=0.01, y_out_target_mole_frac=0.004)


# ----------------------------------------------------------- air separation


def test_asu_for_n2_hand_computed():
    r = ASU.size_asu_for_n2_demand(79.0)
    assert r.n2_product_mass_flow_kg_s == pytest.approx(79.0 * 28.014 / 1000)
    assert r.o2_product_mass_flow_kg_s == pytest.approx(21.0 * 31.998 / 1000)       # air = 100 mol/s
    assert r.air_feed_mass_flow_kg_s == pytest.approx((79 * 28.014 + 21 * 31.998) / 1000)
    assert r.total_power_kW == pytest.approx(100.0 * 0.022414 * 3600 * 0.22)         # 79 N2 + 21 O2 = 100 mol/s
    assert ASU.size_asu_for_n2_demand(79.0, 0.30).total_power_kW == pytest.approx(100.0 * 0.022414 * 3600 * 0.30)
    # product streams plus any argon-free air balance: N2 + O2 mass == air mass
    assert r.n2_product_mass_flow_kg_s + r.o2_product_mass_flow_kg_s == pytest.approx(r.air_feed_mass_flow_kg_s)


def test_asu_for_o2_is_the_same_plant_seen_from_the_other_product():
    r = ASU.size_asu_for_o2_demand(21.0)
    ref = ASU.size_asu_for_n2_demand(79.0)
    assert r.o2_product_mass_flow_kg_s == pytest.approx(ref.o2_product_mass_flow_kg_s)
    assert r.n2_product_mass_flow_kg_s == pytest.approx(ref.n2_product_mass_flow_kg_s)
    assert r.total_power_kW == pytest.approx(ref.total_power_kW)
    assert ASU.size_asu_for_o2_demand(21.0, 0.40).total_power_kW == pytest.approx(ref.total_power_kW * 0.40 / 0.22)


@pytest.mark.parametrize("fn,arg", [(ASU.size_asu_for_n2_demand, "n2_demand_mol_s"),
                                    (ASU.size_asu_for_o2_demand, "o2_demand_mol_s")])
@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_asu_demand_must_be_positive(fn, arg, bad):
    # the message must name the caller's own argument (the O2 path delegates to the N2 path)
    with pytest.raises(ValueError, match=f"{arg} must be positive"):
        fn(bad)


# ------------------------------------------------------- ammonia synthesis


def test_ammonia_loop_hand_computed():
    r = NH3.ammonia_synthesis_loop(75.0, 25.0, single_pass_conversion=0.5, purge_fraction=0.5)
    # F=100, denom = 1 - 0.5*0.5 = 0.75, R = 100*0.25/0.75, inlet = F + R, NH3 = 0.5*X*inlet
    assert r.fresh_feed_mol_s == pytest.approx(100.0)
    assert r.recycle_mol_s == pytest.approx(100.0 / 3.0)
    assert r.reactor_inlet_mol_s == pytest.approx(400.0 / 3.0)
    assert r.nh3_product_mol_s == pytest.approx(100.0 / 3.0)
    assert r.purge_loss_mol_s == pytest.approx(100.0 / 3.0)
    assert r.overall_conversion == pytest.approx(2.0 / 3.0)
    assert r.nh3_product_mass_flow_kg_s == pytest.approx(100.0 / 3.0 * 17.031 / 1000)


def test_ammonia_loop_closes_its_nitrogen_hydrogen_balance():
    r = NH3.ammonia_synthesis_loop(150.0, 50.0)
    # fresh feed moles = 2 x NH3 formed (4 mol reactant -> 2 mol NH3) + purged reactant
    assert r.fresh_feed_mol_s == pytest.approx(2.0 * r.nh3_product_mol_s + r.purge_loss_mol_s)
    # defaults 0.19 / 0.02
    d = NH3.ammonia_synthesis_loop(150.0, 50.0, 0.19, 0.02)
    assert d.nh3_product_mol_s == pytest.approx(r.nh3_product_mol_s)


@pytest.mark.parametrize("kw", [
    {"single_pass_conversion": 0.0}, {"single_pass_conversion": 1.0}, {"single_pass_conversion": -0.1},
    {"purge_fraction": 0.0}, {"purge_fraction": 1.0}, {"purge_fraction": 1.5},
])
def test_ammonia_loop_parameter_ranges_are_open_intervals(kw):
    with pytest.raises(ValueError):
        NH3.ammonia_synthesis_loop(75.0, 25.0, **kw)


def test_more_purge_means_less_ammonia_per_fresh_feed():
    low = NH3.ammonia_synthesis_loop(75.0, 25.0, purge_fraction=0.01)
    high = NH3.ammonia_synthesis_loop(75.0, 25.0, purge_fraction=0.10)
    assert high.nh3_product_mol_s < low.nh3_product_mol_s
    assert high.purge_loss_mol_s > low.purge_loss_mol_s


def test_validate_feed_ratio_tolerance_window():
    NH3.validate_feed_ratio(300.0, 100.0)
    NH3.validate_feed_ratio(314.0, 100.0)   # |3.14 - 3| = 0.14 < 0.15
    NH3.validate_feed_ratio(286.0, 100.0)
    with pytest.raises(ValueError, match="3:1"):
        NH3.validate_feed_ratio(316.0, 100.0)
    with pytest.raises(ValueError):
        NH3.validate_feed_ratio(284.0, 100.0)
    NH3.validate_feed_ratio(330.0, 100.0, tolerance=0.2)   # wider tolerance accepts 3.3
    with pytest.raises(ValueError):
        NH3.validate_feed_ratio(300.0, 0.0)                # no N2 at all


class _FakeMix:
    """Stands in for GasMixture: MW 28 g/mol, k = 1.4, Z = 1."""

    def __init__(self, composition):
        self.composition = composition

    def molecular_weight(self):
        return 28.0

    def cp_over_cv(self, T, P):
        return 1.4

    def compressibility(self, T, P):
        return 1.0


def test_compressor_power_hand_computed_with_fake_gas_properties(monkeypatch):
    monkeypatch.setattr(NH3, "GasMixture", _FakeMix)
    k, eta = 1.4, 1.0
    n = 1.0 / (1.0 - (k - 1.0) / (k * eta))        # = 1.4 when eta = 1
    assert n == pytest.approx(1.4)
    pr, T, MW = 10.0, 300.0, 0.028
    head = (8.314462618 / MW) * T * (n / (n - 1.0)) * (pr ** ((n - 1.0) / n) - 1.0)
    p = NH3.makeup_gas_compressor_power(75.0, 25.0, T, 1.0e5, 1.0e6, polytropic_efficiency=1.0)
    assert p == pytest.approx(100.0 * MW * head / 1000.0)
    # a less efficient compressor draws proportionally more (and n changes), so power must rise
    assert NH3.makeup_gas_compressor_power(75.0, 25.0, T, 1.0e5, 1.0e6, 0.78) > p


def test_compressor_power_rejects_non_compression(monkeypatch):
    monkeypatch.setattr(NH3, "GasMixture", _FakeMix)
    with pytest.raises(ValueError, match="P_out must exceed P_in"):
        NH3.makeup_gas_compressor_power(75.0, 25.0, 300.0, 1.0e6, 1.0e6)
    with pytest.raises(ValueError):
        NH3.makeup_gas_compressor_power(75.0, 25.0, 300.0, 1.0e6, 5.0e5)


def test_compressor_builds_the_mixture_from_the_h2_mole_fraction(monkeypatch):
    seen = {}

    class Spy(_FakeMix):
        def __init__(self, composition):
            seen.update(composition)
            super().__init__(composition)

    monkeypatch.setattr(NH3, "GasMixture", Spy)
    NH3.makeup_gas_compressor_power(60.0, 20.0, 300.0, 1.0e5, 2.0e5)
    assert seen == {"Hydrogen": pytest.approx(0.75), "Nitrogen": pytest.approx(0.25)}


# --------------------------------------------------------- urea synthesis


def test_co2_conversion_fit_hand_computed_and_clamped():
    assert U.co2_conversion_per_pass(3.5) == pytest.approx(0.171 + 0.118 * 3.5)
    assert U.co2_conversion_per_pass(2.8) == pytest.approx(0.5014)
    assert U.co2_conversion_per_pass(3.5, 1.0) == pytest.approx(0.171 + 0.118 * 3.5 - 0.15)
    assert U.co2_conversion_per_pass(6.0) == 0.85          # upper clamp (raw 0.879)
    assert U.co2_conversion_per_pass(3.0, 5.0) == 0.05     # lower clamp (raw negative)
    assert U.co2_conversion_per_pass(4.5) > U.co2_conversion_per_pass(2.8)
    assert U.co2_conversion_per_pass(3.5, 2.0) < U.co2_conversion_per_pass(3.5, 0.0)


def test_co2_conversion_needs_more_than_stoichiometric_ammonia():
    for bad in (2.0, 1.5):
        with pytest.raises(ValueError, match="exceed 2.0"):
            U.co2_conversion_per_pass(bad)
    assert U.co2_conversion_per_pass(2.01) == pytest.approx(0.171 + 0.118 * 2.01)


def test_urea_balance_hand_computed():
    r = U.synthesize_urea(350.0, 100.0)               # N/C = 3.5 -> X = 0.584
    assert r.nh3_to_co2_molar_ratio == pytest.approx(3.5)
    assert r.co2_conversion == pytest.approx(0.584)
    assert r.urea_produced_mol_s == pytest.approx(58.4)
    assert r.urea_produced_mass_flow_kg_s == pytest.approx(58.4 * 60.06 / 1000)
    assert r.water_produced_mol_s == pytest.approx(58.4)
    assert r.unconverted_co2_mol_s == pytest.approx(41.6)
    assert r.unconverted_nh3_mol_s == pytest.approx(350.0 - 2 * 58.4)
    # 2 NH3 + CO2 -> urea + H2O: mass in = mass out
    mass_in = 350.0 * 17.031 + 100.0 * 44.01
    mass_out = (58.4 * 60.06 + 58.4 * 18.015 + r.unconverted_co2_mol_s * 44.01 + r.unconverted_nh3_mol_s * 17.031)
    assert mass_out == pytest.approx(mass_in, rel=2e-3)


def test_urea_feed_water_lowers_conversion():
    dry = U.synthesize_urea(350.0, 100.0)
    wet = U.synthesize_urea(350.0, 100.0, h2o_feed_mol_s=100.0)
    assert wet.co2_conversion == pytest.approx(0.584 - 0.15)
    assert wet.urea_produced_mol_s < dry.urea_produced_mol_s


def test_urea_conversion_override_and_its_bounds():
    r = U.synthesize_urea(350.0, 100.0, conversion_override=0.5)
    assert r.co2_conversion == 0.5 and r.urea_produced_mol_s == pytest.approx(50.0)
    assert U.synthesize_urea(250.0, 100.0, conversion_override=1.0).urea_produced_mol_s == pytest.approx(100.0)
    for bad in (0.0, -0.2, 1.01):
        with pytest.raises(ValueError, match="conversion must be in"):
            U.synthesize_urea(350.0, 100.0, conversion_override=bad)


def test_urea_infeasible_when_ammonia_runs_out():
    with pytest.raises(ValueError, match="Infeasible"):
        U.synthesize_urea(150.0, 100.0, conversion_override=0.9)    # needs 180 NH3
    # exactly enough ammonia is feasible
    r = U.synthesize_urea(180.0, 100.0, conversion_override=0.9)
    assert r.unconverted_nh3_mol_s == pytest.approx(0.0, abs=1e-9)


def test_urea_requires_positive_co2():
    for bad in (0.0, -5.0):
        with pytest.raises(ValueError, match="must be positive"):
            U.synthesize_urea(100.0, bad)


# ------------------------------------------------- boundary / survivor tests


def test_coal_analysis_sum_tolerance_is_tight():
    G.CoalAnalysis(0.6, 0.04, 0.08, 0.01, 0.02, 0.15, 0.0999995)   # off by 5e-7: accepted
    with pytest.raises(ValueError, match="sum to 1.0"):
        G.CoalAnalysis(0.6, 0.04, 0.08, 0.01, 0.02, 0.15, 0.101)    # off by 1e-3: rejected


def test_zero_heating_value_feed_reports_zero_cold_gas_efficiency(monkeypatch):
    monkeypatch.setattr(G.CoalAnalysis, "hhv_MJ_kg", lambda self: 0.0)
    assert _gasify_us().cold_gas_efficiency == 0.0


def test_shift_default_approach_is_fifteen_kelvin():
    default = SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0)
    explicit = SR.shift_reactor(_wgs_inlet(), 100.0, 30.0, 700.0, approach_to_equilibrium_K=15.0)
    assert default.approach_to_equilibrium_K == 15.0
    assert default.co_conversion == pytest.approx(explicit.co_conversion)
    c = default.outlet_composition_mole_frac
    q = c["CarbonDioxide"] * c["Hydrogen"] / (c["CarbonMonoxide"] * c["Water"])
    assert q == pytest.approx(SR._wgs_equilibrium_K(715.0), rel=1e-6)


def test_steam_limited_shift_never_consumes_more_water_than_fed():
    inlet = {"CarbonMonoxide": 0.5, "Water": 0.05, "CarbonDioxide": 0.05, "Hydrogen": 0.4}
    r = SR.shift_reactor(inlet, 100.0, 0.0, 700.0)
    out = {k: v * r.outlet_molar_flow_mol_s for k, v in r.outlet_composition_mole_frac.items()}
    assert 0.0 <= out["Water"] <= 5.0
    assert out["CarbonMonoxide"] == pytest.approx(50.0 - (5.0 - out["Water"]))
    assert r.co_conversion == pytest.approx((50.0 - out["CarbonMonoxide"]) / 50.0)
    assert r.co_conversion < 0.1   # at most 5 of the 50 mol/s CO can react without added steam


def test_shift_without_carbon_monoxide_is_not_solvable():
    with pytest.raises(ValueError):
        SR.shift_reactor({"CarbonMonoxide": 0.0, "Water": 0.5, "CarbonDioxide": 0.25, "Hydrogen": 0.25}, 100.0, 0.0, 700.0)


def test_feed_ratio_check_is_inclusive_at_exactly_the_tolerance_edge():
    # ratio 4.0, tolerance 1/3: |4 - 3| == 3 * (1/3) == 1.0 exactly -> still acceptable
    NH3.validate_feed_ratio(400.0, 100.0, tolerance=1.0 / 3.0)
    with pytest.raises(ValueError):
        NH3.validate_feed_ratio(401.0, 100.0, tolerance=1.0 / 3.0)


def test_compressor_power_uses_the_polytropic_efficiency_in_the_exponent(monkeypatch):
    monkeypatch.setattr(NH3, "GasMixture", _FakeMix)
    k, eta, pr, T, MW = 1.4, 0.78, 10.0, 300.0, 0.028
    n = 1.0 / (1.0 - (k - 1.0) / (k * eta))
    head = (8.314462618 / MW) * T * (n / (n - 1.0)) * (pr ** ((n - 1.0) / n) - 1.0)
    p = NH3.makeup_gas_compressor_power(75.0, 25.0, T, 1.0e5, 1.0e6, polytropic_efficiency=eta)
    assert p == pytest.approx(100.0 * MW * head / eta / 1000.0)
    assert NH3.makeup_gas_compressor_power(75.0, 25.0, T, 1.0e5, 1.0e6) == pytest.approx(p)  # 0.78 is the default


def test_gas_mixture_sum_tolerance_rejects_a_1e4_error():
    with pytest.raises(ValueError, match="sum to 1.0"):
        P.GasMixture({"Hydrogen": 0.75, "Nitrogen": 0.2501})
