# Methodology

Each module's docstring carries its own citations in full; this page
summarizes them in one place.

## Gasifier (`gasifier.py`)

Elemental (C/H/O/N/S) mass balance on coal + O2 + steam feed, with the
exit gas composition (CO/CO2/H2/H2O split, CH4 neglected) resolved via
water-gas-shift equilibrium at the gasifier's own operating
temperature - the standard conceptual-level simplification for
entrained-flow slagging gasifiers (Higman & van der Burgt,
"Gasification", 2nd ed., Elsevier, 2008). WGS equilibrium constant:
Moe, J.M., "Design of water gas shift reactors", Chem. Eng. Prog.
58(3), 1962 (ln K = 4577.8/T - 4.33), widely reproduced in chemical
reaction engineering texts (e.g. Fogler). Coal HHV via Dulong's
formula (as-received basis, a common engineering shortcut - see
Basu, "Biomass Gasification and Pyrolysis").

## Water-gas shift (`shift_reactor.py`)

Same WGS equilibrium correlation, applied as a designed reactor stage
with a specified steam addition and an approach-to-equilibrium
temperature offset - standard industrial shift-reactor design practice
(Twigg, "Catalyst Handbook"; Appl, "Ammonia: Principles and Industrial
Practice").

## Acid gas removal (`acid_gas_removal.py`)

Mass-balance CO2/H2S split plus Souders-Brown flooding diameter +
Kremser theoretical-stages packed-column sizing - the same equations as
the sibling LNG project's amine absorber (GPSA Engineering Data Book
Ch. 19/21; Kohl & Nielsen, "Gas Purification", the standard reference
text for this unit operation).

## Air separation (`air_separation.py`)

Specific-power correlation for cryogenic N2/O2 production (Castle,
W.F., "Air separation and liquefaction: recent developments and
prospects for the beginning of the new millennium", International
Journal of Refrigeration 25(1), 2002).

## Ammonia synthesis (`ammonia_synthesis.py`)

Steady-state recycle-loop mass balance around a fixed per-pass
conversion (not a full reactor kinetics model). Operating conditions
and conversion grounded in a public source found while building this
repo: Alkusayer & Ollerhead, "Ammonia Synthesis for Fertilizer
Production" (WPI Major Qualifying Project report, 2015, publicly
published without restriction) - 450 C / 200 bar, iron catalyst with
potassium promoter, ~18-20% single-pass conversion, consistent with the
textbook-cited 15-25% range (Appl, "Ammonia"). Makeup-gas compressor:
same polytropic-head method as the LNG project's compressor.py (GPSA
Ch. 13).

## Urea synthesis (`urea_synthesis.py`)

Per-pass CO2 conversion via a deliberately simple, explicitly-labeled
illustrative fit (NOT a reproduction of Frejacques (1948) or any
licensor's proprietary correlation - see the module's docstring),
calibrated to the commonly-reported 50-70% conversion range across the
practical N/C = 2.8-4.5 design window. Frejacques, C. (1948), "Bases
theoriques de la synthese industrielle de l'uree", Chimie et Industrie
60, 22-35, is the foundational academic reference the field's
subsequent equilibrium charts trace back to. Operating conditions
(~180 C / 150 bar) corroborated by the same WPI report cited above.
