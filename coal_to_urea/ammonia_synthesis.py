"""Ammonia synthesis (Haber-Bosch): N2 + 3 H2 <-> 2 NH3 over a promoted
iron catalyst, high pressure recycle loop with purge.

Method: a steady-state recycle-loop mass balance around a FIXED
per-pass conversion (not a full reactor kinetics/equilibrium model -
real converter design needs multi-bed kinetics with interstage cooling,
well beyond conceptual screening scope). Per-pass conversion and
operating conditions are grounded in a public source found while
building this repo: Alkusayer & Ollerhead, "Ammonia Synthesis for
Fertilizer Production" (WPI Major Qualifying Project report, 2015,
publicly published by Worcester Polytechnic Institute without
restriction) - a designed ammonia loop at 450 C / 200 bar over an
iron catalyst with a potassium promoter, reporting an ~18-20%
single-pass conversion, consistent with the textbook-cited 15-25%
range for promoted-iron Haber-Bosch converters (e.g. Appl, M.,
"Ammonia: Principles and Industrial Practice", Wiley-VCH).

Recycle-loop algebra (see derivation in this module's tests/worked
example): at steady state, EVERY mole of fresh H2+N2 feed must
eventually leave as either NH3 product or purge-stream loss - the
purge fraction, not the per-pass conversion alone, ultimately
determines the loop's overall (fresh-feed-basis) conversion. This is
standard reaction-engineering recycle-reactor treatment (see e.g.
Fogler, "Elements of Chemical Reaction Engineering", recycle reactor
systems), applied here to a binary H2+N2 -> NH3 pseudo-stoichiometry
(4 mol reactant -> 2 mol NH3) since a stoichiometric 3:1 H2:N2 feed
preserves that ratio through the loop.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import CoolProp.CoolProp as CP

from .properties import R_UNIVERSAL, GasMixture


@dataclass
class AmmoniaLoopResult:
    nh3_product_mol_s: float
    nh3_product_mass_flow_kg_s: float
    fresh_feed_mol_s: float
    recycle_mol_s: float
    reactor_inlet_mol_s: float
    overall_conversion: float
    purge_loss_mol_s: float


def ammonia_synthesis_loop(
    h2_feed_mol_s: float,
    n2_feed_mol_s: float,
    single_pass_conversion: float = 0.19,
    purge_fraction: float = 0.02,
) -> AmmoniaLoopResult:
    """h2_feed_mol_s/n2_feed_mol_s: fresh makeup gas feed (should be at
    or near the 3:1 stoichiometric H2:N2 ratio - see
    validate_feed_ratio below for a check). purge_fraction: fraction of
    the UNCONVERTED recycle stream vented each pass to prevent inert
    (Ar, CH4, residual gasifier trace species) buildup - typically a
    few percent; too low risks inert accumulation choking the reaction,
    too high wastes unconverted H2/N2 (the classic ammonia-loop
    purge-rate trade-off).
    """
    if not (0.0 < single_pass_conversion < 1.0):
        raise ValueError("single_pass_conversion must be in (0, 1)")
    if not (0.0 < purge_fraction < 1.0):
        raise ValueError("purge_fraction must be in (0, 1)")

    F = h2_feed_mol_s + n2_feed_mol_s
    X = single_pass_conversion
    p = purge_fraction

    denom = 1.0 - (1.0 - p) * (1.0 - X)
    R = F * (1.0 - p) * (1.0 - X) / denom
    reactor_inlet = F + R
    nh3_produced = 0.5 * X * reactor_inlet
    purge_loss = p * (1.0 - X) * reactor_inlet
    overall_conversion = (2.0 * nh3_produced) / F

    return AmmoniaLoopResult(
        nh3_product_mol_s=nh3_produced,
        nh3_product_mass_flow_kg_s=nh3_produced * 17.031 / 1000.0,
        fresh_feed_mol_s=F,
        recycle_mol_s=R,
        reactor_inlet_mol_s=reactor_inlet,
        overall_conversion=overall_conversion,
        purge_loss_mol_s=purge_loss,
    )


def validate_feed_ratio(h2_feed_mol_s: float, n2_feed_mol_s: float, tolerance: float = 0.05) -> None:
    """Raises ValueError if the feed departs from the stoichiometric 3:1
    H2:N2 ratio by more than `tolerance` (fractional) - a real ammonia
    loop's makeup-gas purification train is specifically designed to
    hit this ratio (from the ASU's N2 and the syngas train's H2); a
    large mismatch here signals an upstream sizing error, not a
    legitimate design choice."""
    ratio = h2_feed_mol_s / n2_feed_mol_s if n2_feed_mol_s > 0 else math.inf
    if abs(ratio - 3.0) > 3.0 * tolerance:
        raise ValueError(
            f"H2:N2 feed ratio {ratio:.2f}:1 departs from the stoichiometric 3:1 "
            f"by more than {tolerance*100:.0f}% - check upstream ASU N2 and shift/AGR H2 sizing."
        )


def makeup_gas_compressor_power(
    h2_feed_mol_s: float, n2_feed_mol_s: float,
    T_in_K: float, P_in_Pa: float, P_out_Pa: float,
    polytropic_efficiency: float = 0.78,
) -> float:
    """Polytropic compression power for the fresh makeup gas train up to
    loop pressure - same method (and citation) as the sibling LNG
    project's compressor.py (GPSA Engineering Data Book Ch. 13):
    H_p = Z*(R/MW)*T*(n/(n-1))*[(P2/P1)^((n-1)/n) - 1], P_gas = mdot*H_p/eta_p.
    """
    if P_out_Pa <= P_in_Pa:
        raise ValueError("P_out must exceed P_in")
    total_mol_s = h2_feed_mol_s + n2_feed_mol_s
    y_h2 = h2_feed_mol_s / total_mol_s
    gas = GasMixture({"Hydrogen": y_h2, "Nitrogen": 1.0 - y_h2})

    MW = gas.molecular_weight() / 1000.0  # kg/mol
    k = gas.cp_over_cv(T_in_K, P_in_Pa)
    Z = gas.compressibility(T_in_K, P_in_Pa)
    n = 1.0 / (1.0 - (k - 1.0) / (k * polytropic_efficiency))
    pressure_ratio = P_out_Pa / P_in_Pa

    R_specific = R_UNIVERSAL / MW
    head = Z * R_specific * T_in_K * (n / (n - 1.0)) * (pressure_ratio ** ((n - 1.0) / n) - 1.0)
    mass_flow_kg_s = total_mol_s * MW
    return mass_flow_kg_s * head / polytropic_efficiency / 1000.0  # kW
