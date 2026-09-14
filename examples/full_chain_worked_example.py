"""End-to-end worked example: coal -> syngas -> shift -> acid gas
removal -> ammonia synthesis -> urea synthesis, chaining every module
in this repo on ONE consistent basis, the way an actual plant works.

Basis: Indian high-ash coal (NITI Aayog 2025 workshop report's cited
30-45% ash range), entrained-flow gasification with petcoke-style O2
ratio scaling (see gasifier.py's docstring for why raw O2/coal ratios
don't transfer across coal quality), targeting a urea production rate
comparable to the REAL public benchmark this repo is validated against:
Talcher Fertilizers Limited's 2,200 MTPD ammonia / 3,850 MTPD urea
(1.27 mtpa) plant - the same capacity shared by several other recent
Indian urea plants (Ramagundam, Matix, three HURL trains), making it
the de facto standard modern single-train Indian urea plant size (see
docs/VALIDATION.md for the public source).

Run: python examples/full_chain_worked_example.py
"""
from __future__ import annotations

from coal_to_urea.acid_gas_removal import remove_acid_gases
from coal_to_urea.air_separation import size_asu_for_n2_demand
from coal_to_urea.ammonia_synthesis import (
    ammonia_synthesis_loop,
    makeup_gas_compressor_power,
    validate_feed_ratio,
)
from coal_to_urea.gasifier import TYPICAL_INDIAN_HIGH_ASH, gasify_coal
from coal_to_urea.shift_reactor import shift_reactor
from coal_to_urea.urea_synthesis import synthesize_urea

MTPA_TO_KG_S = 1.0e9 / (365.25 * 24 * 3600)
REAL_TALCHER_UREA_MTPA = 1.27  # public benchmark - see module docstring

COAL_MASS_FLOW_KG_S = 145.0   # iterated to land near the real benchmark

print("=" * 78)
print("COAL-TO-UREA FULL CHAIN WORKED EXAMPLE")
print("=" * 78)
print(f"Coal feed: {COAL_MASS_FLOW_KG_S:.1f} kg/s, Indian high-ash preset "
      f"(ash {TYPICAL_INDIAN_HIGH_ASH.ash*100:.0f}%, HHV {TYPICAL_INDIAN_HIGH_ASH.hhv_MJ_kg():.1f} MJ/kg)")

# ---------------------------------------------------------------------
# Gasifier
# ---------------------------------------------------------------------
g = gasify_coal(
    TYPICAL_INDIAN_HIGH_ASH, COAL_MASS_FLOW_KG_S,
    o2_to_coal_mass_ratio=0.55, steam_to_coal_mass_ratio=0.10,
    gasifier_T_K=1673.15, carbon_conversion=0.90,
)
print(f"\nGasifier: {g.syngas_molar_flow_mol_s:,.0f} mol/s syngas, "
      f"CGE {g.cold_gas_efficiency*100:.1f}%, O2 feed {g.o2_mass_flow_kg_s:.1f} kg/s")
print("  Composition:", {k: f"{v*100:.1f}%" for k, v in g.syngas_composition_mole_frac.items()})

# ---------------------------------------------------------------------
# Two-stage water-gas shift (HT then LT)
# ---------------------------------------------------------------------
ht = shift_reactor(
    g.syngas_composition_mole_frac, g.syngas_molar_flow_mol_s,
    additional_steam_mol_s=g.syngas_molar_flow_mol_s * 0.30,
    reactor_T_K=623.15, approach_to_equilibrium_K=20.0,
)
lt = shift_reactor(
    ht.outlet_composition_mole_frac, ht.outlet_molar_flow_mol_s,
    additional_steam_mol_s=ht.outlet_molar_flow_mol_s * 0.10,
    reactor_T_K=493.15, approach_to_equilibrium_K=10.0,
)
print(f"\nHT shift (350 C): CO conversion {ht.co_conversion*100:.1f}%")
print(f"LT shift (220 C): CO conversion {lt.co_conversion*100:.1f}% (cumulative), "
      f"H2 mole frac {lt.outlet_composition_mole_frac['Hydrogen']*100:.1f}%")

# ---------------------------------------------------------------------
# Acid gas removal - captured CO2 becomes urea's other feedstock
# ---------------------------------------------------------------------
agr = remove_acid_gases(lt.outlet_composition_mole_frac, lt.outlet_molar_flow_mol_s,
                          co2_removal_fraction=0.97, h2s_removal_fraction=0.999)
print(f"\nAcid gas removal: {agr.captured_co2_mass_flow_kg_s:.1f} kg/s CO2 captured "
      f"({agr.captured_co2_molar_flow_mol_s:,.0f} mol/s) - urea feedstock")
print(f"  Treated gas H2 mole frac: {agr.treated_gas_composition_mole_frac['Hydrogen']*100:.1f}% "
      "(methanation polishing needed before the ammonia loop - not modeled here, see module docstring)")

# ---------------------------------------------------------------------
# ASU: N2 makeup for the ammonia loop (sized to the treated gas's own
# H2 flow, to hit the stoichiometric 3:1 H2:N2 ratio)
# ---------------------------------------------------------------------
h2_available_mol_s = agr.treated_gas_composition_mole_frac["Hydrogen"] * agr.treated_gas_molar_flow_mol_s
n2_required_mol_s = h2_available_mol_s / 3.0
asu = size_asu_for_n2_demand(n2_required_mol_s)
print(f"\nASU: {n2_required_mol_s:,.0f} mol/s N2 makeup, {asu.total_power_kW:,.0f} kW, "
      f"co-produced O2 {asu.o2_product_mass_flow_kg_s:.1f} kg/s "
      f"(vs. gasifier's own O2 demand {g.o2_mass_flow_kg_s:.1f} kg/s - a separate ASU train "
      "typically also serves the gasifier; not the same air feed as this N2-only sizing)")

validate_feed_ratio(h2_available_mol_s, n2_required_mol_s)

# ---------------------------------------------------------------------
# Ammonia synthesis loop
# ---------------------------------------------------------------------
nh3 = ammonia_synthesis_loop(h2_available_mol_s, n2_required_mol_s,
                               single_pass_conversion=0.19, purge_fraction=0.02)
compressor_power = makeup_gas_compressor_power(h2_available_mol_s, n2_required_mol_s,
                                                  T_in_K=313.15, P_in_Pa=40e5, P_out_Pa=200e5)
print(f"\nAmmonia synthesis: {nh3.nh3_product_mass_flow_kg_s:,.1f} kg/s NH3 "
      f"({nh3.overall_conversion*100:.1f}% overall conversion), "
      f"makeup compressor {compressor_power:,.0f} kW")

# ---------------------------------------------------------------------
# Urea synthesis - closes the loop: AGR's CO2 + ammonia loop's NH3.
#
# Found by running this example, not assumed in advance: coal
# gasification produces far more carbon (as CO2, after shift) per unit
# of H2/NH3 than a natural-gas route does - captured CO2 here
# (4,321 mol/s) vastly exceeds what the urea reaction's stoichiometry
# (N/C ~3-4.5) can actually consume against the NH3 available. Only the
# CO2 needed to hit a realistic N/C target is fed to the urea reactor;
# the rest is reported as surplus (vent or CCUS-capture candidate) -
# this asymmetry is a well-documented real driver behind coal-based
# ammonia/urea's higher CO2 footprint than gas-based routes, and
# exactly the CCUS integration need the NITI Aayog workshop report
# (docs/VALIDATION.md) flags repeatedly for Indian coal gasification
# projects, not a modeling artifact.
# ---------------------------------------------------------------------
TARGET_N_TO_C_RATIO = 3.5
co2_needed_for_target_ratio = nh3.nh3_product_mol_s / TARGET_N_TO_C_RATIO
co2_to_urea = min(co2_needed_for_target_ratio, agr.captured_co2_molar_flow_mol_s)
surplus_co2_mol_s = agr.captured_co2_molar_flow_mol_s - co2_to_urea
print(f"\nCO2 allocation: {co2_to_urea:,.0f} mol/s to urea (N/C target {TARGET_N_TO_C_RATIO:.1f}), "
      f"{surplus_co2_mol_s:,.0f} mol/s surplus ({100.0*surplus_co2_mol_s/agr.captured_co2_molar_flow_mol_s:.0f}% "
      "of captured CO2 - vent or CCUS-capture candidate, not modeled further here)")

urea = synthesize_urea(nh3_feed_mol_s=nh3.nh3_product_mol_s, co2_feed_mol_s=co2_to_urea)
urea_mtpa = urea.urea_produced_mass_flow_kg_s / MTPA_TO_KG_S
print(f"\nUrea synthesis: N/C ratio {urea.nh3_to_co2_molar_ratio:.2f}, "
      f"per-pass CO2 conversion {urea.co2_conversion*100:.1f}%")
print(f"  Urea produced: {urea.urea_produced_mass_flow_kg_s:.1f} kg/s = {urea_mtpa:.2f} mtpa")
print(f"  Unconverted (recycle/stripping duty, not sized here): "
      f"{urea.unconverted_co2_mol_s:,.0f} mol/s CO2, {urea.unconverted_nh3_mol_s:,.0f} mol/s NH3")

# ---------------------------------------------------------------------
print("\n" + "=" * 78)
print("Comparison against the real public benchmark")
print("=" * 78)
delta_pct = 100.0 * (urea_mtpa / REAL_TALCHER_UREA_MTPA - 1.0)
print(f"  This example: {urea_mtpa:.2f} mtpa urea")
print(f"  Talcher Fertilizers Limited (real, public - see docs/VALIDATION.md): "
      f"{REAL_TALCHER_UREA_MTPA:.2f} mtpa urea")
print(f"  Difference: {delta_pct:+.1f}%")
print(
    "\nNote: this is a conceptual, module-chained estimate using simplified "
    "correlations throughout (fixed single-pass conversions, an illustrative "
    "urea equilibrium fit, no recycle/stripping/purge-gas-recovery sizing) - "
    "landing in the right ballpark of a real plant's capacity is a useful "
    "sanity check, not a claim of engineering-grade accuracy. See each "
    "module's docstring and docs/VALIDATION.md for the specific "
    "simplifications and what would need real vendor/kinetic data to remove."
)
