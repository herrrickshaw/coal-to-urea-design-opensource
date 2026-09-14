# coal-to-urea-design-opensource

Open-source, literature-grounded conceptual sizing tools for a
coal-gasification-to-urea complex: gasifier &rarr; water-gas shift
&rarr; acid gas removal &rarr; air separation &rarr; ammonia synthesis
&rarr; urea synthesis. Sibling project to
[lng-design-opensource](https://github.com/herrrickshaw/lng-design-opensource),
same discipline: public-domain/textbook correlations only, CoolProp for
real thermodynamic properties, every method cited, every module tested,
every worked example actually run end to end.

**Scope**: fully generic and literature-only. Nothing here derives from
any proprietary vendor, licensor, or client engineering data. See
`docs/METHODOLOGY.md` for citations and `docs/VALIDATION.md` for
cross-checks against public sources, including a real project (Talcher
Fertilizers Limited, India) used as a validation benchmark.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                        # 37 tests
python examples/full_chain_worked_example.py     # coal -> urea, end to end
streamlit run streamlit_app.py                   # interactive app
```

## Modules

| Module | Method | Key outputs |
|---|---|---|
| `coal_to_urea/gasifier.py` | Elemental mass balance + water-gas-shift equilibrium quench (Higman & van der Burgt, "Gasification") | Syngas composition/flow, cold gas efficiency, carbon conversion |
| `coal_to_urea/shift_reactor.py` | WGS equilibrium conversion (Moe 1962 correlation), HT/LT staged | Shifted syngas composition, CO conversion |
| `coal_to_urea/acid_gas_removal.py` | Mass-balance CO2/H2S split + Kremser-equation column sizing (GPSA Ch. 19/21; Kohl & Nielsen, "Gas Purification") | Treated gas, captured CO2 (urea feedstock), captured H2S |
| `coal_to_urea/air_separation.py` | Specific-power correlation, cryogenic ASU (Castle, 2002) | N2 (ammonia loop) + O2 (gasifier) product streams, power |
| `coal_to_urea/ammonia_synthesis.py` | Recycle-loop mass balance around a fixed per-pass conversion (grounded in a public WPI report); polytropic compressor (GPSA Ch. 13) | NH3 production, overall conversion, compressor power |
| `coal_to_urea/urea_synthesis.py` | Simplified per-pass CO2 conversion fit (Frejacques 1948 as the field's foundational reference) | Urea production, unconverted NH3/CO2 |

## Validated against a real public project

`examples/full_chain_worked_example.py` chains every module on one
basis (Indian high-ash coal, per NITI Aayog's 2025 workshop report) and
lands within **14% of Talcher Fertilizers Limited's real, public 1.27
mtpa urea capacity** - the same size as several other recently
commissioned Indian urea plants. See `docs/VALIDATION.md` for the
sources and for honestly-reported findings along the way (an O2/coal
ratio that must scale with coal quality, a large CO2 surplus that
coal-based routes produce relative to gas-based ammonia routes).

## Process technology confirmed against Talcher's own real licensors

`docs/VENDOR_REFERENCE.md` independently confirms all THREE of this
project's core process-technology assumptions against Talcher's own
real, board-approved or publicly announced licensors: **Air Products**
(gasification technology, formerly Shell's - "TFL Board approved coal
gasification technology of Air Products (earlier Shell)", with a real,
previously undocumented **25% petcoke blend ratio**), **KBR** (ammonia
synthesis, "License and Basic Engineering Design, catalyst, and
proprietary process equipment"), and **Stamicarbon** (urea synthesis -
its real CO2-stripping process's published 160-240 C / 125-195 bar
operating range independently corroborates this project's own existing
180 C / 150 bar default). All three are confirmed for the SAME real
plant this repo already validates against, not generic industry
examples.

## Related open-source work

No existing open-source project covers coal-to-urea specifically (a
literature search while building this repo found only commercial
Aspen Plus studies). Related open-source process-simulation projects
worth knowing about: [DWSIM](https://github.com/DanWBR/dwsim5) (general
GPL chemical process simulator), [IDAES](https://github.com/IDAES/idaes-pse)
(DOE-backed equation-oriented flowsheet optimization, Python/Pyomo),
[BioSTEAM](https://github.com/BioSTEAMDevelopmentGroup/biosteam)
(biorefinery TEA, Python) - none of these are dependencies of this
repo, but are cited here as related prior art.

## Disclaimer

This tool implements textbook/public-domain conceptual sizing methods
for early-stage screening only. It is not a substitute for a rigorous
process simulator, reactor kinetics model, or vendor-certified
equipment data for detailed design. Always validate against a licensed
simulator and vendor data before committing to equipment specifications.
