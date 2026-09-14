"""Thermophysical property helpers built on CoolProp.

Same pattern as the sibling `lng-design-opensource` project: CoolProp's
HEOS backend supports arbitrary mixtures via a
"Component1[molefrac1]&Component2[molefrac2]&..." string, used directly
wherever CoolProp covers the component, so results trace to a
peer-reviewed equation of state rather than a fitted shortcut.
"""
from __future__ import annotations

from dataclasses import dataclass

import CoolProp.CoolProp as CP

R_UNIVERSAL = 8.314462618  # J/mol-K


@dataclass
class GasMixture:
    """A CoolProp HEOS mixture, keyed by CoolProp fluid names.

    Example
    -------
    >>> syngas = GasMixture({"Hydrogen": 0.35, "CarbonMonoxide": 0.30,
    ...                       "CarbonDioxide": 0.15, "Water": 0.15, "Nitrogen": 0.05})
    >>> syngas.molecular_weight()  # g/mol
    """

    composition: dict[str, float]  # component -> mole fraction (sums to 1)

    def __post_init__(self) -> None:
        total = sum(self.composition.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Mole fractions must sum to 1.0, got {total}")

    def _heos_string(self) -> str:
        parts = [f"{name}[{frac}]" for name, frac in self.composition.items()]
        return "&".join(parts)

    def molecular_weight(self) -> float:
        """g/mol"""
        return CP.PropsSI("M", self._heos_string()) * 1000.0

    def prop(self, output: str, T: float, P: float) -> float:
        """Generic CoolProp state lookup at (T [K], P [Pa]) for the mixture."""
        return CP.PropsSI(output, "T", T, "P", P, self._heos_string())

    def cp_over_cv(self, T: float, P: float) -> float:
        return self.prop("Cpmass", T, P) / self.prop("Cvmass", T, P)

    def compressibility(self, T: float, P: float) -> float:
        return self.prop("Z", T, P)

    def density(self, T: float, P: float) -> float:
        return self.prop("Dmass", T, P)

    def enthalpy(self, T: float, P: float) -> float:
        return self.prop("Hmass", T, P)

    def viscosity(self, T: float, P: float) -> float:
        return self.prop("V", T, P)

    def thermal_conductivity(self, T: float, P: float) -> float:
        return self.prop("L", T, P)

    def specific_heat(self, T: float, P: float) -> float:
        return self.prop("Cpmass", T, P)


def pure_fluid_prop(fluid: str, output: str, **state) -> float:
    """Thin wrapper for CP.PropsSI on a pure fluid, keyword state pairs.

    e.g. pure_fluid_prop('Nitrogen', 'T', P=101325, Q=0)
    """
    (k1, v1), (k2, v2) = list(state.items())
    return CP.PropsSI(output, k1, v1, k2, v2, fluid)
