"""Shared physical constants and the water-gas-shift equilibrium constant.

Single home for values previously copy-pasted across modules (molecular
weights in g/mol, the Moe 1962 K(T) correlation).
"""
from __future__ import annotations

import math

# Molecular weights, g/mol.
MW_H2O = 18.015
MW_O2 = 31.998
MW_N2 = 28.014
MW_CO2 = 44.01
MW_NH3 = 17.031
MW_UREA = 60.06
MW_CO = 28.01
MW_H2 = 2.016
MW_H2S = 34.08


def wgs_equilibrium_K(T_K: float) -> float:
    """Water-gas-shift equilibrium constant, CO + H2O <-> CO2 + H2 (T in K).

    Moe, J.M., Chem. Eng. Prog. 58(3), 1962: ln(K) = 4577.8 / T - 4.33.
    """
    return math.exp(4577.8 / T_K - 4.33)
