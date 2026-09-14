# External validation

## A real public project as the validation benchmark

While researching this repo's grounding, two genuinely public sources
turned out to give strong, real-world validation:

1. **NITI Aayog (Government of India), "Coal Gasification Technology
   for Indian High Ash Content Coal"** (workshop report, September
   2025). Records an expert consensus that entrained-flow slagging
   gasifiers - the technology this repo's `gasifier.py` most directly
   models - are "least suitable" for raw high-ash (30-45%) Indian coal,
   with fluidized-bed (non-slagging) designs preferred instead. Also
   reports real project performance figures used to cross-check this
   repo: IIT Delhi/Thermax's Coal-to-Methanol pilot achieved 92% carbon
   conversion / 70% cold gas efficiency on >45%-ash coal; CSIR-CIMFR's
   PFBG pilot reported up to 65% cold gas efficiency.
2. **ICRA credit-rating report on Talcher Fertilizers Limited** (a
   GAIL/Coal India/RCF joint venture), February 2025. Gives real,
   public numbers for India's first coal-to-urea project under
   construction: 2,200 MTPD ammonia / 3,850 MTPD urea (1.27 mtpa urea),
   using Shell's entrained-flow gasification process WITH petroleum-
   coke (petcoke) blending specifically to manage high-ash-coal risk.
   1.27 mtpa is also the capacity of several other recently
   commissioned Indian urea plants (Ramagundam, Matix, three HURL
   trains) - the de facto standard modern single-train size, and the
   benchmark `examples/full_chain_worked_example.py` targets.

Both are used as intended by this project's "literature-only" scope:
public reports (a government think-tank workshop summary, a published
credit-rating agency report), not any project's confidential
engineering data.

## Gasifier — a real finding: O2 ratio must scale with coal quality

Running `gasify_coal` on the Indian high-ash coal preset with the SAME
O2-to-coal mass ratio used for a higher-carbon bituminous coal (0.85)
collapsed cold gas efficiency to ~44% - far below any published figure.
The physically correct quantity is O2-to-CARBON molar ratio, not
O2-to-coal mass ratio: a lower-carbon, higher-ash/moisture coal needs
proportionally less O2 to stay in reducing (gasification) conditions.
Scaling the ratio down to 0.55 (same O2/C molar ratio) recovered a
~64% cold gas efficiency - matching CSIR-CIMFR's publicly reported ~65%
almost exactly. Locked in as `tests/test_gasifier.py::test_gasify_coal_
unscaled_o2_ratio_on_low_carbon_coal_gives_poor_efficiency` and the
correctly-scaled companion test.

## Full-chain worked example — landed within 14% of a real plant, and a genuine CO2-surplus finding

`examples/full_chain_worked_example.py` chains all six modules on the
Indian high-ash coal basis and produces **1.10 mtpa urea**, vs. Talcher
Fertilizers Limited's real, public **1.27 mtpa** - a 13.6% gap for a
first-pass conceptual model built from six independently-simplified
unit operations (fixed conversions, no recycle/stripping trains sized),
not tuned to hit this number in advance.

Along the way, an unplanned run surfaced a real process characteristic:
feeding ALL of the acid-gas-removal unit's captured CO2 to the urea
reactor made the NH3:CO2 feed ratio physically infeasible (below urea
synthesis's stoichiometric minimum of 2:1) - coal gasification produces
far more carbon (as CO2, after shift) per unit of H2/NH3 than a
natural-gas route does. The example now allocates only the CO2 needed
to hit a realistic N/C=3.5 design ratio to urea and reports the rest
(77% of captured CO2, in this basis) as a surplus vent/CCUS-capture
candidate - not a modeling bug, but the same real driver behind coal-
based ammonia/urea's documented higher CO2 footprint than gas-based
routes, and exactly the CCUS integration need the NITI Aayog workshop
report above flags repeatedly for Indian coal gasification projects.

## What was deliberately not modeled in this first pass

- Ammonia converter reactor kinetics/multi-bed design (fixed per-pass
  conversion used instead - see `ammonia_synthesis.py`'s docstring).
- Urea reactor's own recycle/high-pressure CO2 stripping train (the
  unconverted NH3/CO2 stream is reported, not sized further).
- Methanation polishing between acid gas removal and the ammonia loop
  (real plants need this to protect the iron catalyst from residual
  CO/CO2 - flagged explicitly in `acid_gas_removal.py` and the worked
  example, not silently omitted).
- Equipment mechanical sizing (vessel diameters, valve/exchanger
  selection) beyond the AGR column - a natural next extension, matching
  how the sibling LNG project grew its equipment-sizing depth over
  many iterations rather than all at once.
