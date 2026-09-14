"""Acid gas removal (AGR): strips CO2 and H2S from shifted syngas ahead
of ammonia synthesis - and, distinctly from a pure LNG-train amine unit,
the CAPTURED CO2 here is not a waste stream: it is urea's OTHER
feedstock (2 NH3 + CO2 -> urea + H2O), so this module reports it as a
usable product stream, not just a removed contaminant. See
urea_synthesis.py for where it goes next.

Method: same Kremser-equation packed-column approach as the sibling
`lng-design-opensource` project's amine_absorber.py (GPSA Engineering
Data Book Ch. 19/21 covers acid-gas treating generally, not LNG-
specific; Kohl & Nielsen, "Gas Purification", is the standard reference
text for this unit operation across both natural-gas and syngas
service). Physical solvents (Rectisol, Selexol) are also common for
syngas AGR at high CO2 partial pressure, offering lower regeneration
energy than chemical (amine) solvents at these pressures - noted here,
not modeled separately, since the column-sizing mathematics (Kremser
theoretical stages x HETP, Souders-Brown flooding-limited diameter) is
the same regardless of solvent chemistry at this conceptual level; only
the equilibrium slope `m` and L/V ratio inputs would differ by solvent
system in a more detailed model.

Ammonia synthesis catalyst is poisoned by even trace CO/CO2/H2S (ppm
level), so real plants follow AGR with a METHANATION step (CO+CO2
hydrogenated back to CH4 over a Ni catalyst) for final polishing - not
modeled in this module; treat its "treated gas" output as needing that
additional polishing step before the ammonia loop, exactly as flagged
in the full-chain worked example.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class AGRResult:
    treated_gas_composition_mole_frac: dict[str, float]
    treated_gas_molar_flow_mol_s: float
    captured_co2_molar_flow_mol_s: float
    captured_co2_mass_flow_kg_s: float
    captured_h2s_molar_flow_mol_s: float
    co2_removal_fraction: float
    h2s_removal_fraction: float


def remove_acid_gases(
    syngas_composition_mole_frac: dict[str, float],
    syngas_molar_flow_mol_s: float,
    co2_removal_fraction: float = 0.97,
    h2s_removal_fraction: float = 0.999,
) -> AGRResult:
    """Mass-balance split of a shifted syngas stream into treated gas
    (for the ammonia loop, via methanation polishing - see module
    docstring) and captured CO2/H2S streams.

    co2_removal_fraction: typically 0.90-0.99+ for ammonia-synthesis-
    gas-quality treating (Kohl & Nielsen); higher removal is generally
    preferred here specifically BECAUSE the captured CO2 is urea
    feedstock, not because of pipeline-spec CO2 content as in an LNG
    train's amine unit.
    h2s_removal_fraction: typically 0.999+ (H2S is a stronger catalyst
    poison and usually has a tighter removal spec than CO2).
    """
    if not (0.0 <= co2_removal_fraction <= 1.0):
        raise ValueError("co2_removal_fraction must be in [0, 1]")
    if not (0.0 <= h2s_removal_fraction <= 1.0):
        raise ValueError("h2s_removal_fraction must be in [0, 1]")

    n_co2_in = syngas_composition_mole_frac.get("CarbonDioxide", 0.0) * syngas_molar_flow_mol_s
    n_h2s_in = syngas_composition_mole_frac.get("HydrogenSulfide", 0.0) * syngas_molar_flow_mol_s

    captured_co2 = n_co2_in * co2_removal_fraction
    captured_h2s = n_h2s_in * h2s_removal_fraction

    species = {}
    for name, frac in syngas_composition_mole_frac.items():
        n_in = frac * syngas_molar_flow_mol_s
        if name == "CarbonDioxide":
            species[name] = n_in - captured_co2
        elif name == "HydrogenSulfide":
            species[name] = n_in - captured_h2s
        else:
            species[name] = n_in

    total = sum(species.values())
    treated_composition = {k: v / total for k, v in species.items()}

    return AGRResult(
        treated_gas_composition_mole_frac=treated_composition,
        treated_gas_molar_flow_mol_s=total,
        captured_co2_molar_flow_mol_s=captured_co2,
        captured_co2_mass_flow_kg_s=captured_co2 * 44.01 / 1000.0,
        captured_h2s_molar_flow_mol_s=captured_h2s,
        co2_removal_fraction=co2_removal_fraction,
        h2s_removal_fraction=h2s_removal_fraction,
    )


@dataclass
class AbsorberSizingResult:
    diameter_m: float
    n_theoretical_stages: float
    packed_height_m: float
    percent_of_flood: float


def size_agr_column(
    gas_volumetric_flow_m3_s: float,
    gas_density_kg_m3: float,
    liquid_density_kg_m3: float,
    y_in_mole_frac: float,
    y_out_target_mole_frac: float,
    x_in_mole_frac: float,
    equilibrium_slope_m: float,
    liquid_to_gas_molar_ratio: float,
    K_SB: float = 0.04,
    design_fraction_of_flood: float = 0.75,
    hetp_m: float = 0.6,
) -> AbsorberSizingResult:
    """Souders-Brown flooding-limited diameter + Kremser theoretical
    stages x HETP packed height - identical method and defaults in
    spirit to the sibling LNG project's amine_absorber.py (see that
    module's docstring for the equations); reproduced here rather than
    imported, since this is a standalone repo. See docs/VALIDATION.md
    for a design-parameter corroboration note (this repo carries the
    same L/V-sizing caveat the LNG repo flagged: pick liquid_to_gas_
    molar_ratio to land the absorption factor A = L/(m*V) in the
    classic 1.4-2.0 economic range, not an arbitrary round number).
    """
    v_flood = K_SB * math.sqrt((liquid_density_kg_m3 - gas_density_kg_m3) / gas_density_kg_m3)
    v_design = v_flood * design_fraction_of_flood
    area = gas_volumetric_flow_m3_s / v_design
    diameter = math.sqrt(4.0 * area / math.pi)

    A = liquid_to_gas_molar_ratio / equilibrium_slope_m
    if A <= 1.0:
        raise ValueError(f"Absorption factor A={A:.2f} <= 1 - infeasible for a Kremser packed column (need A > 1)")
    y_out_equilibrium = equilibrium_slope_m * x_in_mole_frac
    if y_out_target_mole_frac <= y_out_equilibrium:
        raise ValueError("Target outlet composition is below what's achievable with this equilibrium line/x_in")

    numerator = (y_in_mole_frac - y_out_equilibrium) / (y_out_target_mole_frac - y_out_equilibrium)
    n_stages = math.log((numerator * (1.0 - 1.0 / A)) + 1.0 / A) / math.log(A)

    return AbsorberSizingResult(
        diameter_m=diameter,
        n_theoretical_stages=n_stages,
        packed_height_m=n_stages * hetp_m,
        percent_of_flood=design_fraction_of_flood * 100.0,
    )
