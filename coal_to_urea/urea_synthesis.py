"""Urea synthesis: 2 NH3 + CO2 <-> NH2COONH4 (ammonium carbamate, fast,
essentially complete) <-> CO(NH2)2 + H2O (urea, the slower,
equilibrium-limited dehydration step that actually sets per-pass
conversion).

Operating conditions (~150-250 bar, ~170-190 C) are grounded in the
same public source used for ammonia_synthesis.py: Alkusayer &
Ollerhead's WPI report states ~180 C / 150 bar for the NH3+CO2
reaction feeding a urea plant. Independently corroborated (docs/
VENDOR_REFERENCE.md): Stamicarbon's real CO2-stripping process family
(the actual urea technology reportedly selected for Talcher Fertilizers
Limited, this module's own validation target) publishes a synthesis-
reactor range of 160-240 C / 12-21 MPa (125-195 bar preferred) in its
published process literature -- this module's 180 C / 150 bar default
sits inside both independently sourced ranges.

Per-pass CO2 conversion correlation: the foundational academic
reference for urea synthesis equilibrium is Frejacques, C. (1948),
"Bases theoriques de la synthese industrielle de l'uree", Chimie et
Industrie 60, 22-35 - the basis nearly all subsequent urea process
literature's equilibrium conversion charts trace back to (conversion
rises with the NH3:CO2 feed molar ratio, "N/C ratio", and falls with
water content in the feed, both well-established, uncontested
qualitative trends). This module does NOT reproduce Frejacques' (or
any licensor's, e.g. Stamicarbon/Snamprogetti total-recycle process)
original equilibrium charts/correlations - those weren't available to
verify precisely in the time available. Instead it uses a deliberately
simple, explicitly-labeled illustrative fit calibrated to the commonly-
reported RANGE (roughly 50-70% CO2 conversion per pass across the
practical N/C=2.8-4.5 design window, low water content) rather than
a claim of precise, literature-exact equilibrium prediction - see
docs/VALIDATION.md. Real plants also recycle unconverted NH3/CO2 (as
carbamate, via high-pressure stripping) rather than losing it - not
modeled here; this module reports the per-pass unconverted stream and
flags it as the recycle/stripping duty a real design would size.
"""
from __future__ import annotations

from dataclasses import dataclass

_MW_UREA = 60.06
_MW_H2O = 18.015
_MW_NH3 = 17.031
_MW_CO2 = 44.01


def co2_conversion_per_pass(nh3_to_co2_molar_ratio: float, h2o_to_co2_molar_ratio: float = 0.0) -> float:
    """Illustrative, simplified fit to commonly reported urea per-pass
    CO2 conversion trends (see module docstring) - NOT a reproduction
    of Frejacques (1948) or any licensor's proprietary correlation.

    Roughly: ~50% at N/C=2.8, ~58% at N/C=3.5, ~70% at N/C=4.5 (low
    water feed), reduced by feed water content.
    """
    if nh3_to_co2_molar_ratio <= 2.0:
        raise ValueError("nh3_to_co2_molar_ratio must exceed 2.0 (stoichiometric minimum for urea synthesis)")
    base = 0.171 + 0.118 * nh3_to_co2_molar_ratio
    water_penalty = 0.15 * h2o_to_co2_molar_ratio
    return min(max(base - water_penalty, 0.05), 0.85)


@dataclass
class UreaSynthesisResult:
    urea_produced_mol_s: float
    urea_produced_mass_flow_kg_s: float
    water_produced_mol_s: float
    co2_conversion: float
    unconverted_co2_mol_s: float
    unconverted_nh3_mol_s: float
    nh3_to_co2_molar_ratio: float


def synthesize_urea(
    nh3_feed_mol_s: float,
    co2_feed_mol_s: float,
    h2o_feed_mol_s: float = 0.0,
    conversion_override: float | None = None,
) -> UreaSynthesisResult:
    """Single-pass urea reactor mass balance. Pass `conversion_override`
    to use a conversion from vendor/literature data instead of this
    module's illustrative correlation (see co2_conversion_per_pass).
    """
    if co2_feed_mol_s <= 0:
        raise ValueError("co2_feed_mol_s must be positive")
    n_to_c = nh3_feed_mol_s / co2_feed_mol_s
    h2o_to_co2 = h2o_feed_mol_s / co2_feed_mol_s if co2_feed_mol_s > 0 else 0.0

    conversion = conversion_override if conversion_override is not None else co2_conversion_per_pass(n_to_c, h2o_to_co2)
    if not (0.0 < conversion <= 1.0):
        raise ValueError("conversion must be in (0, 1]")

    urea_mol_s = conversion * co2_feed_mol_s
    nh3_consumed = 2.0 * urea_mol_s
    if nh3_consumed > nh3_feed_mol_s:
        raise ValueError(
            f"Infeasible: conversion {conversion:.2f} at CO2 feed {co2_feed_mol_s:.1f} mol/s needs "
            f"{nh3_consumed:.1f} mol/s NH3, exceeding the {nh3_feed_mol_s:.1f} mol/s fed - "
            "raise the NH3:CO2 ratio or lower the conversion."
        )

    return UreaSynthesisResult(
        urea_produced_mol_s=urea_mol_s,
        urea_produced_mass_flow_kg_s=urea_mol_s * _MW_UREA / 1000.0,
        water_produced_mol_s=urea_mol_s,
        co2_conversion=conversion,
        unconverted_co2_mol_s=co2_feed_mol_s - urea_mol_s,
        unconverted_nh3_mol_s=nh3_feed_mol_s - nh3_consumed,
        nh3_to_co2_molar_ratio=n_to_c,
    )
