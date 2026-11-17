"""Deterministic reference cases whose numeric outputs are frozen in
golden_baseline.json (captured from the pre-refactor code on `main`)."""
from __future__ import annotations

import dataclasses
from typing import Any

from coal_to_urea.acid_gas_removal import remove_acid_gases, size_agr_column
from coal_to_urea.air_separation import size_asu_for_n2_demand, size_asu_for_o2_demand
from coal_to_urea.ammonia_synthesis import ammonia_synthesis_loop, makeup_gas_compressor_power
from coal_to_urea.gasifier import TYPICAL_INDIAN_HIGH_ASH, TYPICAL_US_BITUMINOUS, gasify_coal
from coal_to_urea.shift_reactor import shift_reactor
from coal_to_urea.urea_synthesis import co2_conversion_per_pass, synthesize_urea


def _d(obj: Any) -> Any:
    return dataclasses.asdict(obj)


def compute_cases() -> dict[str, Any]:
    out: dict[str, Any] = {}
    g_in = gasify_coal(TYPICAL_INDIAN_HIGH_ASH, 145.0, 0.55, 0.10, 1673.15, 0.90)
    g_us = gasify_coal(TYPICAL_US_BITUMINOUS, 50.0, 0.85, 0.15, 1673.15, 0.98)
    out["gasifier_indian"] = _d(g_in)
    out["gasifier_us"] = _d(g_us)
    out["hhv"] = [TYPICAL_INDIAN_HIGH_ASH.hhv_MJ_kg(), TYPICAL_US_BITUMINOUS.hhv_MJ_kg()]
    ht = shift_reactor(g_in.syngas_composition_mole_frac, g_in.syngas_molar_flow_mol_s,
                       g_in.syngas_molar_flow_mol_s * 0.30, 623.15, 20.0)
    lt = shift_reactor(ht.outlet_composition_mole_frac, ht.outlet_molar_flow_mol_s,
                       ht.outlet_molar_flow_mol_s * 0.10, 493.15, 10.0)
    out["shift_ht"], out["shift_lt"] = _d(ht), _d(lt)
    agr = remove_acid_gases(lt.outlet_composition_mole_frac, lt.outlet_molar_flow_mol_s, 0.97, 0.999)
    out["agr"] = _d(agr)
    out["agr_column"] = _d(size_agr_column(10.0, 30.0, 1000.0, 0.15, 0.001, 0.0, 0.5, 0.9))
    out["asu_n2"] = _d(size_asu_for_n2_demand(1000.0))
    out["asu_o2"] = _d(size_asu_for_o2_demand(500.0))
    h2 = agr.treated_gas_composition_mole_frac["Hydrogen"] * agr.treated_gas_molar_flow_mol_s
    n2 = h2 / 3.0
    nh3 = ammonia_synthesis_loop(h2, n2, 0.19, 0.02)
    out["ammonia"] = _d(nh3)
    out["compressor_kW"] = makeup_gas_compressor_power(h2, n2, 313.15, 40e5, 200e5)
    out["urea_fit"] = [co2_conversion_per_pass(r, w) for r in (2.8, 3.5, 4.5) for w in (0.0, 0.5)]
    co2 = min(nh3.nh3_product_mol_s / 3.5, agr.captured_co2_molar_flow_mol_s)
    out["urea"] = _d(synthesize_urea(nh3.nh3_product_mol_s, co2))
    return out
