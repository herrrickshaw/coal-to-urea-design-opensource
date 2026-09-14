"""Cryogenic air separation unit (ASU): produces the O2 the gasifier
needs AND the N2 the ammonia synthesis loop needs, from the same air
feed - a genuine shared-utility integration point in a coal-to-urea
complex (mirroring how the sibling LNG project's cascade_loops.py PMR
loop absorbs heat from two sources at once).

Method: a specific-power correlation, the standard conceptual-level
approach for cryogenic distillation ASUs (full column/exchanger design
is out of scope - see e.g. Castle, W.F., "Air separation and
liquefaction: recent developments and prospects for the beginning of
the new millennium", International Journal of Refrigeration 25(1),
2002, for representative specific-power figures for cryogenic ASU
product streams). Air is treated as a fixed 79/21 mol% N2/O2 mixture
(ignoring Ar, ~1 mol% - a standard simplification for conceptual N2/O2
balances; real ASUs separate a third Ar column, not modeled here).
"""
from __future__ import annotations

from dataclasses import dataclass

_AIR_N2_MOLE_FRAC = 0.79
_AIR_O2_MOLE_FRAC = 0.21
_MW_N2 = 28.014
_MW_O2 = 31.998

# Typical published specific power for cryogenic ASU product gas,
# kWh per Nm3 of product (illustrative range 0.10-0.40 kWh/Nm3
# depending on product purity/pressure - Castle, 2002, and general
# cryogenic engineering practice; override with vendor data when
# available).
DEFAULT_SPECIFIC_POWER_KWH_PER_NM3 = 0.22
_NM3_PER_MOL = 0.022414  # ideal-gas molar volume at 0 C, 1 atm (Nm3/mol)


@dataclass
class ASUResult:
    n2_product_mass_flow_kg_s: float
    o2_product_mass_flow_kg_s: float
    air_feed_mass_flow_kg_s: float
    total_power_kW: float


def size_asu_for_n2_demand(
    n2_demand_mol_s: float,
    specific_power_kWh_per_Nm3: float = DEFAULT_SPECIFIC_POWER_KWH_PER_NM3,
) -> ASUResult:
    """Size an ASU to meet a target N2 product molar flow, reporting the
    co-produced O2 stream (fixed by air's N2:O2 ratio) - this O2 stream
    is what feeds `gasifier.gasify_coal`'s `o2_to_coal_mass_ratio` feed,
    the process-integration link this module exists to make explicit.
    """
    if n2_demand_mol_s <= 0:
        raise ValueError("n2_demand_mol_s must be positive")

    air_mol_s = n2_demand_mol_s / _AIR_N2_MOLE_FRAC
    o2_mol_s = air_mol_s * _AIR_O2_MOLE_FRAC

    n2_mass = n2_demand_mol_s * _MW_N2 / 1000.0
    o2_mass = o2_mol_s * _MW_O2 / 1000.0
    air_mass = air_mol_s * (_AIR_N2_MOLE_FRAC * _MW_N2 + _AIR_O2_MOLE_FRAC * _MW_O2) / 1000.0

    total_product_Nm3_s = (n2_demand_mol_s + o2_mol_s) * _NM3_PER_MOL
    power_kW = total_product_Nm3_s * 3600.0 * specific_power_kWh_per_Nm3

    return ASUResult(
        n2_product_mass_flow_kg_s=n2_mass,
        o2_product_mass_flow_kg_s=o2_mass,
        air_feed_mass_flow_kg_s=air_mass,
        total_power_kW=power_kW,
    )


def size_asu_for_o2_demand(
    o2_demand_mol_s: float,
    specific_power_kWh_per_Nm3: float = DEFAULT_SPECIFIC_POWER_KWH_PER_NM3,
) -> ASUResult:
    """Size an ASU to meet a target O2 product molar flow (the
    gasifier's own demand), reporting the co-produced N2 available for
    the ammonia loop - the reverse framing of size_asu_for_n2_demand,
    useful when the gasifier's O2 need is the binding constraint rather
    than the ammonia loop's N2 need."""
    if o2_demand_mol_s <= 0:
        raise ValueError("o2_demand_mol_s must be positive")
    air_mol_s = o2_demand_mol_s / _AIR_O2_MOLE_FRAC
    n2_mol_s = air_mol_s * _AIR_N2_MOLE_FRAC
    return size_asu_for_n2_demand(n2_mol_s, specific_power_kWh_per_Nm3)
