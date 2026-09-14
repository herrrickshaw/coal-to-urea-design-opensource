"""Coal gasification: elemental mass balance + water-gas-shift
equilibrium quench - a standard conceptual-level approach for a
high-temperature, oxygen-blown, entrained-flow slagging gasifier (the
technology family typically chosen for syngas-to-chemicals routes such
as ammonia/urea - e.g. Shell, GE/Texaco, ConocoPhillips E-Gas style
gasifiers, as opposed to moving-bed or fluidized-bed designs more
common for power/IGCC service, which produce meaningfully more CH4 and
tar and are a poorer fit for this simplified model).

Method: Higman & van der Burgt, "Gasification", 2nd ed. (Elsevier,
2008) - the standard reference text for gasification process
engineering. Real gasifiers involve complex heterogeneous kinetics
(devolatilization, char gasification, combustion) far beyond a
conceptual screening tool's scope; treating the exit gas as
approaching water-gas-shift equilibrium at the gasifier's own operating
temperature is the standard simplification textbooks use for a
first-pass raw syngas composition estimate, not a substitute for a
kinetic gasifier model or vendor performance guarantee. CH4 formation
is neglected (reasonable at entrained-flow slagging temperatures,
typically <1-2 mol% per the same reference; moving-bed/fluidized-bed
gasifiers produce meaningfully more and are a poor fit for this model).

**A real, non-obvious technology-selection nuance found while grounding
this module in public sources** (see docs/VALIDATION.md): a September
2025 NITI Aayog (Government of India) workshop report, "Coal
Gasification Technology for Indian High Ash Content Coal", records an
expert consensus that entrained-flow slagging gasifiers - the type this
module's default parameters describe - are "least suitable" for raw
high-ash (30-45%) Indian coal, because the ash chemistry (high silica/
alumina, low iron/lime) gives a high ash-fusion temperature and poor
slagging behavior; fluidized-bed (non-slagging) designs were the
workshop's preferred choice for Indian coal specifically. Yet India's
first coal-to-urea project actually under construction, Talcher
Fertilizers Limited (a GAIL/Coal India/RCF joint venture, 2,200 MTPD
ammonia / 3,850 MTPD urea = 1.27 mtpa urea, the same capacity as
several other recent Indian urea plants), uses Shell's entrained-flow
gasification process specifically WITH petroleum-coke (petcoke)
blending as the risk-mitigation strategy for feeding high-ash coal to a
slagging design (per ICRA's published credit-rating report on the
project). Independently confirmed via vendor research (docs/
VENDOR_REFERENCE.md): Air Products' own materials (having acquired
Shell's gasification technology and patent portfolio) state "the TFL
Board approved coal gasification technology of Air Products (earlier
Shell)" with "coal blended with pet-coke up to 25%" -- a real,
specific blend ratio ICRA's report did not itself quantify, now
available if a future version of this module adds an explicit
coal/petcoke blend-ratio parameter. This module's simple elemental-balance-plus-WGS-equilibrium
approach is most accurate for entrained-flow, and is a reasonable fit
for a petcoke-blended feed (lower, more consistent ash than raw high-
ash coal) or for lower-ash coal generally; for pure high-ash coal fed to
a non-slagging fluidized-bed design, real carbon conversion is lower
(~85-92%, per the IIT Delhi/Thermax pilot's reported 92% carbon
conversion / 70% cold gas efficiency, and CSIR-CIMFR's reported 65%
cold gas efficiency) and CH4 formation is not negligible - override
`carbon_conversion` accordingly and treat the CH4-free assumption as
more approximate for that technology.

Water-gas-shift equilibrium constant: Moe, J.M., "Design of water gas
shift reactors", Chem. Eng. Prog. 58(3), 1962 - a correlation widely
reproduced in chemical reaction engineering texts (e.g. Fogler,
"Elements of Chemical Reaction Engineering"):

    ln(K) = 4577.8 / T - 4.33          (T in K)

for CO + H2O <-> CO2 + H2 (equimolar reaction, so K equals the mole
(or mole-fraction) ratio directly - no total-moles/pressure dependence).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

# Standard atomic weights, g/mol (IUPAC).
_AW = {"C": 12.011, "H": 1.008, "O": 15.999, "N": 14.007, "S": 32.06}
_MW_H2O = 18.015
_MW_O2 = 31.998

# Standard higher heating values (HHV, liquid water product), kJ/mol -
# widely tabulated combustion thermodynamics (e.g. Perry's Chemical
# Engineers' Handbook; NIST WebBook).
_HHV_KJ_MOL = {"H2": 285.8, "CO": 283.0}


@dataclass
class CoalAnalysis:
    """As-received ultimate analysis, mass fractions summing to 1.0.

    Two illustrative presets are provided as module-level constants
    below (not a claim about any specific mine/seam - override with an
    actual coal analysis): `TYPICAL_US_BITUMINOUS` (ash ~11%) and
    `TYPICAL_INDIAN_HIGH_ASH` (ash ~35%, within the 30-45% range NITI
    Aayog's 2025 workshop report cites as characteristic of Indian
    coal - see this module's docstring). The high-ash case is the more
    relevant default for this repo's worked examples, since India's
    coal-to-urea projects are the real public precedent this module is
    grounded against.
    """
    carbon: float
    hydrogen: float
    oxygen: float
    nitrogen: float
    sulfur: float
    ash: float
    moisture: float

    def __post_init__(self) -> None:
        total = self.carbon + self.hydrogen + self.oxygen + self.nitrogen + self.sulfur + self.ash + self.moisture
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Ultimate analysis mass fractions must sum to 1.0, got {total:.4f}")

    def hhv_MJ_kg(self) -> float:
        """Dulong's formula (as-received mass fractions applied
        directly - a common engineering shortcut; strictly the
        correlation is for dry coal, flagged here rather than silently
        presented as exact): HHV = 33.87 C + 144.3 (H - O/8) + 9.4 S,
        mass fractions, MJ/kg. Widely reproduced, e.g. Basu, "Biomass
        Gasification and Pyrolysis"."""
        return 33.87 * self.carbon + 144.3 * (self.hydrogen - self.oxygen / 8.0) + 9.4 * self.sulfur


# Illustrative presets (not a claim about any specific mine/seam) - see
# CoalAnalysis's docstring.
TYPICAL_US_BITUMINOUS = CoalAnalysis(
    carbon=0.650, hydrogen=0.045, oxygen=0.080, nitrogen=0.013, sulfur=0.020,
    ash=0.112, moisture=0.080,
)
# Ash within NITI Aayog's cited 30-45% range for Indian coal; C/H/O/N/S
# scaled down proportionally from the bituminous case to leave room for
# the higher ash + moisture typical of Indian coal (high inherent
# moisture is also a well-documented characteristic alongside high ash).
TYPICAL_INDIAN_HIGH_ASH = CoalAnalysis(
    carbon=0.420, hydrogen=0.029, oxygen=0.052, nitrogen=0.008, sulfur=0.013,
    ash=0.350, moisture=0.128,
)


@dataclass
class GasifierResult:
    syngas_composition_mole_frac: dict[str, float]
    syngas_molar_flow_mol_s: float
    syngas_mass_flow_kg_s: float
    carbon_conversion: float
    unconverted_carbon_kg_s: float
    cold_gas_efficiency: float
    o2_mass_flow_kg_s: float
    steam_mass_flow_kg_s: float


def _wgs_equilibrium_K(T_K: float) -> float:
    return math.exp(4577.8 / T_K - 4.33)


def gasify_coal(
    coal: CoalAnalysis,
    coal_mass_flow_kg_s: float,
    o2_to_coal_mass_ratio: float,
    steam_to_coal_mass_ratio: float,
    gasifier_T_K: float,
    carbon_conversion: float = 0.98,
) -> GasifierResult:
    """Elemental balance + water-gas-shift equilibrium quench at the
    gasifier's own operating temperature (see module docstring).

    o2_to_coal_mass_ratio: typically 0.7-1.0 kg O2 / kg coal (as-fed)
    for entrained-flow slagging gasifiers burning a higher-rank coal
    (Higman & van der Burgt) - but found by running this function on
    the Indian high-ash preset: that ratio is calibrated to a ~65%
    carbon-content coal and massively over-oxidizes a ~42%-carbon,
    high-ash/high-moisture coal (cold gas efficiency collapsed to ~44%,
    well below any published figure for real projects). The physically
    correct quantity is O2-to-CARBON molar ratio, not O2-to-coal mass
    ratio - a lower-carbon coal needs proportionally less O2 to stay in
    reducing (gasification) conditions rather than tip toward
    combustion. Scaling O2/coal down to ~0.55 for the Indian high-ash
    preset (same O2/C molar ratio as the 0.85 figure at ~65% carbon)
    recovers a ~64% cold gas efficiency - matching CSIR-CIMFR's
    publicly reported 65% CGE for Indian high-ash coal gasification
    (see module docstring). Scale this ratio with coal.carbon when
    switching coal quality: o2_to_coal_mass_ratio_new =
    o2_to_coal_mass_ratio_ref * (coal_new.carbon / coal_ref.carbon).
    steam_to_coal_mass_ratio: typically 0.1-0.3 kg steam / kg coal,
    gasifier-design-dependent.
    gasifier_T_K: typically 1573-1773 K (1300-1500 C) for entrained-flow
    slagging service (above coal ash fusion temperature).
    carbon_conversion: typically 0.95-0.99 for entrained-flow slagging
    gasifiers; the rest leaves as unconverted carbon in slag/char.
    """
    if not (0.0 < carbon_conversion <= 1.0):
        raise ValueError("carbon_conversion must be in (0, 1]")

    n_C_coal = coal_mass_flow_kg_s * coal.carbon * 1000.0 / _AW["C"]
    n_H_atoms_coal = coal_mass_flow_kg_s * coal.hydrogen * 1000.0 / _AW["H"]
    n_O_atoms_coal = coal_mass_flow_kg_s * coal.oxygen * 1000.0 / _AW["O"]
    n_N_atoms_coal = coal_mass_flow_kg_s * coal.nitrogen * 1000.0 / _AW["N"]
    n_S_atoms_coal = coal_mass_flow_kg_s * coal.sulfur * 1000.0 / _AW["S"]
    n_H2O_coal_moisture = coal_mass_flow_kg_s * coal.moisture * 1000.0 / _MW_H2O

    o2_mass_flow = coal_mass_flow_kg_s * o2_to_coal_mass_ratio
    n_O2_fed = o2_mass_flow * 1000.0 / _MW_O2

    steam_mass_flow = coal_mass_flow_kg_s * steam_to_coal_mass_ratio
    n_H2O_steam = steam_mass_flow * 1000.0 / _MW_H2O

    n_C = n_C_coal * carbon_conversion
    unconverted_carbon_kg_s = (n_C_coal - n_C) * _AW["C"] / 1000.0

    n_H_total = n_H_atoms_coal + 2.0 * (n_H2O_coal_moisture + n_H2O_steam)
    n_O_total = n_O_atoms_coal + (n_H2O_coal_moisture + n_H2O_steam) + 2.0 * n_O2_fed
    n_H2eq = n_H_total / 2.0

    K = _wgs_equilibrium_K(gasifier_T_K)

    # From C, O, H balances (see module derivation): nCO + nH2 = A,
    # where A = 2*nC + nH2eq - nO. Combined with WGS equilibrium
    # (nC - nCO)*nH2 = K * nCO * (nH2eq - nH2), this reduces to one
    # equation in nCO alone, solved numerically (brentq) since it's a
    # quadratic-like nonlinear relation not worth hand-solving in code.
    A = 2.0 * n_C + n_H2eq - n_O_total

    def residual(n_CO: float) -> float:
        n_H2 = A - n_CO
        n_CO2 = n_C - n_CO
        n_H2O = n_H2eq - n_H2
        return (n_CO2 * n_H2) - K * n_CO * n_H2O

    lo = max(1e-9, A - n_H2eq)  # nCO such that nH2 <= nH2eq (nH2O >= 0)
    hi = min(n_C, A) - 1e-9      # nCO <= nC (nCO2 >= 0) and nCO <= A (nH2 >= 0)
    if hi <= lo:
        raise ValueError(
            "No physically valid syngas composition for this O2/steam/coal "
            "ratio combination at the given temperature (elemental balance "
            "gives no feasible CO/CO2/H2/H2O split) - try a different "
            "O2-to-coal or steam-to-coal ratio."
        )
    n_CO = brentq(residual, lo, hi)
    n_H2 = A - n_CO
    n_CO2 = n_C - n_CO
    n_H2O = n_H2eq - n_H2
    n_H2S = n_S_atoms_coal
    n_N2 = n_N_atoms_coal / 2.0

    species = {"CarbonMonoxide": n_CO, "CarbonDioxide": n_CO2, "Hydrogen": n_H2,
               "Water": n_H2O, "HydrogenSulfide": n_H2S, "Nitrogen": n_N2}
    total_mol = sum(species.values())
    composition = {k: v / total_mol for k, v in species.items()}

    hhv_syngas_kW = (n_CO * _HHV_KJ_MOL["CO"] + n_H2 * _HHV_KJ_MOL["H2"])  # kJ/s = kW
    hhv_coal_kW = coal_mass_flow_kg_s * coal.hhv_MJ_kg() * 1000.0
    cold_gas_efficiency = hhv_syngas_kW / hhv_coal_kW if hhv_coal_kW > 0 else 0.0

    mw_mix = sum(composition[k] * _species_mw(k) for k in composition)
    syngas_mass_flow = total_mol * mw_mix / 1000.0

    return GasifierResult(
        syngas_composition_mole_frac=composition,
        syngas_molar_flow_mol_s=total_mol,
        syngas_mass_flow_kg_s=syngas_mass_flow,
        carbon_conversion=carbon_conversion,
        unconverted_carbon_kg_s=unconverted_carbon_kg_s,
        cold_gas_efficiency=cold_gas_efficiency,
        o2_mass_flow_kg_s=o2_mass_flow,
        steam_mass_flow_kg_s=steam_mass_flow,
    )


def _species_mw(coolprop_name: str) -> float:
    return {
        "CarbonMonoxide": 28.01, "CarbonDioxide": 44.01, "Hydrogen": 2.016,
        "Water": 18.015, "HydrogenSulfide": 34.08, "Nitrogen": 28.014,
    }[coolprop_name]
