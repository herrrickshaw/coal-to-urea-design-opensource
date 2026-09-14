"""Water-gas shift (WGS) reactor: CO + H2O <-> CO2 + H2.

Method: extent-of-reaction equilibrium conversion using the same
Moe (1962) equilibrium constant correlation as gasifier.py's internal
quench assumption, but applied here as a DESIGNED reactor stage with a
specified steam addition and an "approach to equilibrium" temperature
offset - standard industrial shift-reactor design practice (real
catalytic shift reactors don't quite reach true equilibrium; a positive
approach temperature, evaluated as if the reactor ran a few degrees
hotter than actual, is the standard way published design methods
account for this - see e.g. Twigg, M.V. (ed.), "Catalyst Handbook",
2nd ed., Wolfe Publishing, the standard industrial reference for
shift-catalyst design, and Appl, M., "Ammonia: Principles and
Industrial Practice", Wiley-VCH, for shift's role in ammonia-plant
syngas conditioning).

Real ammonia-plant syngas trains use TWO shift stages in series - a
high-temperature (HT) shift (~350-400 C, Fe/Cr catalyst, fast but
equilibrium-limited) followed by a low-temperature (LT) shift
(~200-250 C, Cu/Zn catalyst, slower but reaches a much more favorable
equilibrium at low T) - rather than one stage, because a single-stage
reactor cannot get both fast kinetics AND high conversion (WGS is
exothermic, so its equilibrium favors low T while its kinetics favor
high T - the classic two-stage compromise). This module models ONE
stage; call it twice (HT then LT) for a realistic train, as the worked
example does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq


def _wgs_equilibrium_K(T_K: float) -> float:
    """Same correlation as gasifier.py - Moe (1962), widely reproduced
    in chemical reaction engineering texts (e.g. Fogler)."""
    return math.exp(4577.8 / T_K - 4.33)


@dataclass
class ShiftReactorResult:
    outlet_composition_mole_frac: dict[str, float]
    outlet_molar_flow_mol_s: float
    co_conversion: float
    approach_to_equilibrium_K: float


def shift_reactor(
    inlet_composition_mole_frac: dict[str, float],
    inlet_molar_flow_mol_s: float,
    additional_steam_mol_s: float,
    reactor_T_K: float,
    approach_to_equilibrium_K: float = 15.0,
) -> ShiftReactorResult:
    """Single WGS shift stage. `inlet_composition_mole_frac` must include
    at least "CarbonMonoxide", "Water", "CarbonDioxide", "Hydrogen" keys
    (others, e.g. "Nitrogen"/"HydrogenSulfide", pass through unchanged).

    additional_steam_mol_s: extra steam injected ahead of this stage -
    real shift reactors run with excess steam (typical steam:CO molar
    ratios of 2-5, Appl, "Ammonia") both to drive conversion (Le
    Chatelier) and to suppress carbon-forming side reactions (Boudouard
    reaction, catalyst coking) - not modeled explicitly here, but the
    excess-steam requirement is why this parameter exists rather than
    assuming the gasifier's own steam carryover is enough.
    approach_to_equilibrium_K: the reactor is evaluated as if it ran
    this many degrees HOTTER than reactor_T_K when computing K(T) - a
    positive approach means less conversion than true equilibrium would
    give, matching how real catalytic shift reactors are rated (Twigg,
    "Catalyst Handbook").
    """
    n_CO = inlet_composition_mole_frac["CarbonMonoxide"] * inlet_molar_flow_mol_s
    n_H2O = inlet_composition_mole_frac["Water"] * inlet_molar_flow_mol_s + additional_steam_mol_s
    n_CO2 = inlet_composition_mole_frac["CarbonDioxide"] * inlet_molar_flow_mol_s
    n_H2 = inlet_composition_mole_frac["Hydrogen"] * inlet_molar_flow_mol_s
    others = {
        k: v * inlet_molar_flow_mol_s for k, v in inlet_composition_mole_frac.items()
        if k not in ("CarbonMonoxide", "Water", "CarbonDioxide", "Hydrogen")
    }

    K = _wgs_equilibrium_K(reactor_T_K + approach_to_equilibrium_K)

    def residual(xi: float) -> float:
        return (n_CO2 + xi) * (n_H2 + xi) - K * (n_CO - xi) * (n_H2O - xi)

    xi_max = min(n_CO, n_H2O) - 1e-9
    xi = brentq(residual, 0.0, xi_max)

    species = {
        "CarbonMonoxide": n_CO - xi, "Water": n_H2O - xi,
        "CarbonDioxide": n_CO2 + xi, "Hydrogen": n_H2 + xi,
        **others,
    }
    total = sum(species.values())
    composition = {k: v / total for k, v in species.items()}

    return ShiftReactorResult(
        outlet_composition_mole_frac=composition,
        outlet_molar_flow_mol_s=total,
        co_conversion=xi / n_CO if n_CO > 0 else 0.0,
        approach_to_equilibrium_K=approach_to_equilibrium_K,
    )
