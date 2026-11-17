# Coal-to-Urea conceptual sizing (open source)

Literature-grounded conceptual sizing tools for a coal-gasification-to-urea complex: gasifier, water-gas shift,
acid gas removal, air separation, ammonia synthesis and urea synthesis. It is for process engineers and students
who need first-pass mass balances and equipment sizes, and it produces printed stream tables, a Python API and an
interactive Streamlit app. Sibling project to
[lng-design-opensource](https://github.com/herrrickshaw/lng-design-opensource), with the same discipline:
public-domain/textbook correlations only, CoolProp for real thermodynamic properties, every method cited,
every module tested, every worked example actually run end to end.

> Status: research-only. Fully generic and literature-only; nothing derives from any proprietary vendor, licensor
> or client engineering data. Educational screening tool, not a substitute for a licensed simulator or vendor data.

New to this repo? See [How to use this repo with AI](HOW_TO_USE_WITH_AI.md).

## What it does
- Elemental mass balance plus water-gas-shift equilibrium for an entrained-flow gasifier (`gasify_coal`).
- Two-stage (HT/LT) water-gas shift with an approach-to-equilibrium temperature offset (`shift_reactor`).
- CO2/H2S split with captured CO2 reported as urea feedstock, and Kremser/Souders-Brown column sizing (`acid_gas_removal`).
- Cryogenic ASU sized from N2 or O2 demand with a specific-power correlation (`air_separation`).
- Ammonia recycle-loop balance and polytropic makeup compressor power (`ammonia_synthesis`).
- Urea reactor balance with an illustrative per-pass CO2 conversion fit (`urea_synthesis`).

## Quick start
```bash
git clone https://github.com/herrrickshaw/coal-to-urea-design-opensource.git
cd coal-to-urea-design-opensource
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python examples/full_chain_worked_example.py     # coal -> urea, end to end
streamlit run streamlit_app.py                   # interactive app
```

## How it works
Streams are plain dicts of CoolProp-named mole fractions plus a molar flow (mol/s); each stage is a pure function.

| Stage | Module | Method | Output |
|---|---|---|---|
| Gasifier | `gasifier.py` | Elemental balance + WGS equilibrium quench (Higman & van der Burgt, "Gasification") | Syngas composition/flow, cold gas efficiency, carbon conversion |
| Shift | `shift_reactor.py` | WGS equilibrium conversion (Moe 1962), HT/LT staged | Shifted syngas, CO conversion |
| AGR | `acid_gas_removal.py` | Mass-balance split + Kremser column sizing (GPSA Ch. 19/21; Kohl & Nielsen) | Treated gas, captured CO2 and H2S |
| ASU | `air_separation.py` | Specific-power correlation (Castle, 2002) | N2 and O2 streams, power |
| Ammonia | `ammonia_synthesis.py` | Recycle-loop balance at fixed per-pass conversion (public WPI report); polytropic compressor (GPSA Ch. 13) | NH3 production, overall conversion, compressor power |
| Urea | `urea_synthesis.py` | Simplified per-pass CO2 conversion fit (Frejacques 1948 as foundational reference) | Urea production, unconverted NH3/CO2 |

Shared molecular weights and the Moe (1962) `ln K = 4577.8/T - 4.33` correlation live in `constants.py`;
CoolProp mixture helpers are in `properties.py`.

`examples/full_chain_worked_example.py` chains every module on one basis (Indian high-ash coal, per NITI Aayog's 2025
workshop report) and lands within **14% of Talcher Fertilizers Limited's real, public 1.27 mtpa urea capacity**
(this example: 1.10 mtpa), the same size as several other recently commissioned Indian urea plants.
`docs/VALIDATION.md` records the sources and findings along the way (an O2/coal ratio that must scale with coal
quality; the large CO2 surplus coal-based routes produce relative to gas-based ammonia routes).

`docs/VENDOR_REFERENCE.md` confirms the three core process-technology assumptions against Talcher's own publicly
announced licensors: Air Products (gasification, formerly Shell, with a 25% petcoke blend ratio), KBR (ammonia
synthesis) and Stamicarbon (urea; its published 160-240 C / 125-195 bar range corroborates the 180 C / 150 bar default).

## Repository layout
| Path | Purpose |
|---|---|
| `coal_to_urea/` | Library: one module per unit operation, plus `constants.py` and `properties.py` |
| `examples/full_chain_worked_example.py` | End-to-end run with benchmark comparison (`main()`) |
| `streamlit_app.py` | Interactive UI, one tab per unit plus a full chain |
| `tests/` | pytest suite per module, plus a golden-baseline guard (`golden_baseline.json`) |
| `docs/` | `METHODOLOGY.md` (citations), `VALIDATION.md`, `VENDOR_REFERENCE.md` |
| `graphify-out/` | Generated knowledge-graph output; not hand-edited |

## Data sources
No datasets are consumed at run time. Benchmarks and citations are public documents listed in `docs/`:
NITI Aayog (Sept 2025) coal gasification workshop report, ICRA's credit-rating report on Talcher Fertilizers,
Air Products/KBR/Stamicarbon public materials, and the WPI ammonia-synthesis MQP (Alkusayer & Ollerhead, 2015).

## Configuration
None. All parameters are function arguments with documented defaults. No secrets are needed or committed.

## Testing
```bash
pytest -q          # 42 tests, including exact-equality checks against the pre-refactor outputs
ruff check .
```

## Limitations and known issues
- Conceptual screening only: fixed single-pass conversions, no reactor kinetics, no recycle/stripping sizing for urea,
  no methanation step after AGR, CH4 formation neglected in the gasifier.
- The urea conversion fit is illustrative (calibrated to the commonly reported 50-70% range), not Frejacques' or
  any licensor's correlation.
- Entrained-flow slagging is "least suitable" for raw 30-45% ash Indian coal per NITI Aayog; carbon conversion
  and CH4 must be overridden for fluidized-bed duty (see the `gasifier.py` docstring).
- The O2:coal mass ratio must be scaled with coal carbon content when switching coal quality.
- Talcher is used only as a public validation benchmark.

## Related repositories
- [lng-design-opensource](https://github.com/herrrickshaw/lng-design-opensource): sibling LNG process sizing project.
- Prior art (not dependencies): [DWSIM](https://github.com/DanWBR/dwsim5), [IDAES](https://github.com/IDAES/idaes-pse),
  [BioSTEAM](https://github.com/BioSTEAMDevelopmentGroup/biosteam). No existing open-source project covers
  coal-to-urea specifically.

## Licence
`pyproject.toml` declares MIT; there is no LICENSE file in the repository yet.
