"""Interactive coal-gasification-to-urea conceptual sizing tool.

Run with: streamlit run streamlit_app.py

All methods are cited public-domain correlations - see README.md and
docs/METHODOLOGY.md for sources.
"""
from __future__ import annotations

import streamlit as st

from coal_to_urea.acid_gas_removal import remove_acid_gases, size_agr_column
from coal_to_urea.air_separation import size_asu_for_n2_demand
from coal_to_urea.ammonia_synthesis import ammonia_synthesis_loop, makeup_gas_compressor_power
from coal_to_urea.gasifier import TYPICAL_INDIAN_HIGH_ASH, TYPICAL_US_BITUMINOUS, CoalAnalysis, gasify_coal
from coal_to_urea.shift_reactor import shift_reactor
from coal_to_urea.urea_synthesis import co2_conversion_per_pass, synthesize_urea

st.set_page_config(page_title="Coal-to-Urea Conceptual Sizing", layout="wide")
st.title("Coal Gasification to Urea (open-source)")
st.caption(
    "Independent open-source conceptual sizing using public-domain correlations "
    "(Higman & van der Burgt, GPSA, Frejacques 1948) and CoolProp thermodynamics. "
    "Not derived from any proprietary vendor/client data. See README.md and "
    "docs/METHODOLOGY.md for citations, and the disclaimer at the bottom of this page."
)

tab_gasifier, tab_shift, tab_agr, tab_asu, tab_ammonia, tab_urea, tab_chain = st.tabs([
    "Gasifier", "Water-Gas Shift", "Acid Gas Removal", "Air Separation",
    "Ammonia Synthesis", "Urea Synthesis", "Full Chain",
])

# ---------------------------------------------------------------------
with tab_gasifier:
    st.header("Coal gasifier")
    st.caption("Elemental balance + water-gas-shift equilibrium quench (Higman & van der Burgt).")
    coal_preset = st.radio("Coal preset", ["Indian high-ash (NITI Aayog, ash ~35%)", "US bituminous (ash ~11%)"])
    coal = TYPICAL_INDIAN_HIGH_ASH if "Indian" in coal_preset else TYPICAL_US_BITUMINOUS
    st.caption(f"HHV: {coal.hhv_MJ_kg():.1f} MJ/kg (Dulong's formula, as-received)")

    c1, c2, c3 = st.columns(3)
    with c1:
        coal_flow = st.number_input("Coal mass flow (kg/s)", min_value=1.0, value=145.0)
    with c2:
        o2_ratio = st.number_input(
            "O2:coal mass ratio", min_value=0.1, value=0.55 if "Indian" in coal_preset else 0.85,
            help="Scale with coal.carbon when switching coal quality - see gasifier.py docstring.",
        )
    with c3:
        steam_ratio = st.number_input("Steam:coal mass ratio", min_value=0.0, value=0.10 if "Indian" in coal_preset else 0.15)
    c1, c2 = st.columns(2)
    with c1:
        gasifier_T_C = st.number_input("Gasifier temperature (°C)", value=1400.0)
    with c2:
        carbon_conv = st.slider("Carbon conversion", 0.80, 0.99, 0.90 if "Indian" in coal_preset else 0.98)

    if st.button("Run gasifier", type="primary"):
        try:
            g = gasify_coal(coal, coal_flow, o2_ratio, steam_ratio, gasifier_T_C + 273.15, carbon_conv)
            st.session_state["gasifier_result"] = g
            colA, colB, colC = st.columns(3)
            colA.metric("Syngas flow", f"{g.syngas_molar_flow_mol_s:,.0f} mol/s")
            colB.metric("Cold gas efficiency", f"{g.cold_gas_efficiency*100:.1f}%")
            colC.metric("O2 feed", f"{g.o2_mass_flow_kg_s:.1f} kg/s")
            st.write({k: f"{v*100:.2f}%" for k, v in g.syngas_composition_mole_frac.items()})
        except ValueError as e:
            st.error(str(e))

# ---------------------------------------------------------------------
with tab_shift:
    st.header("Water-gas shift reactor")
    st.caption("Single stage - call twice (HT ~350°C, LT ~220°C) for a realistic train.")
    if "gasifier_result" not in st.session_state:
        st.info("Run the Gasifier tab first.")
    else:
        g = st.session_state["gasifier_result"]
        c1, c2, c3 = st.columns(3)
        with c1:
            shift_T_C = st.number_input("Reactor temperature (°C)", value=350.0, key="shift_T")
        with c2:
            steam_add_frac = st.number_input("Additional steam (fraction of inlet flow)", min_value=0.0, value=0.30, key="shift_steam")
        with c3:
            approach_K = st.number_input("Approach to equilibrium (K)", min_value=0.0, value=20.0, key="shift_approach")
        if st.button("Run shift stage", type="primary"):
            r = shift_reactor(g.syngas_composition_mole_frac, g.syngas_molar_flow_mol_s,
                                g.syngas_molar_flow_mol_s * steam_add_frac, shift_T_C + 273.15, approach_K)
            st.session_state["shift_result"] = r
            colA, colB = st.columns(2)
            colA.metric("CO conversion", f"{r.co_conversion*100:.1f}%")
            colB.metric("H2 mole fraction", f"{r.outlet_composition_mole_frac['Hydrogen']*100:.1f}%")
            st.write({k: f"{v*100:.2f}%" for k, v in r.outlet_composition_mole_frac.items()})

# ---------------------------------------------------------------------
with tab_agr:
    st.header("Acid gas removal")
    st.caption("Captured CO2 becomes urea's feedstock, not just a removed contaminant.")
    if "shift_result" not in st.session_state:
        st.info("Run the Water-Gas Shift tab first.")
    else:
        r = st.session_state["shift_result"]
        c1, c2 = st.columns(2)
        with c1:
            co2_removal = st.slider("CO2 removal fraction", 0.80, 0.999, 0.97)
        with c2:
            h2s_removal = st.slider("H2S removal fraction", 0.90, 0.9999, 0.999)
        if st.button("Run AGR", type="primary"):
            agr = remove_acid_gases(r.outlet_composition_mole_frac, r.outlet_molar_flow_mol_s, co2_removal, h2s_removal)
            st.session_state["agr_result"] = agr
            colA, colB, colC = st.columns(3)
            colA.metric("CO2 captured", f"{agr.captured_co2_mass_flow_kg_s:.1f} kg/s")
            colB.metric("Treated gas H2", f"{agr.treated_gas_composition_mole_frac['Hydrogen']*100:.1f}%")
            colC.metric("Treated gas flow", f"{agr.treated_gas_molar_flow_mol_s:,.0f} mol/s")
            st.warning("Methanation polishing needed before the ammonia loop - not modeled here.")

# ---------------------------------------------------------------------
with tab_asu:
    st.header("Air separation unit (N2 makeup)")
    n2_demand = st.number_input("N2 demand (mol/s)", min_value=1.0, value=1900.0)
    specific_power = st.number_input("Specific power (kWh/Nm3)", min_value=0.05, value=0.22)
    if st.button("Size ASU", type="primary"):
        asu = size_asu_for_n2_demand(n2_demand, specific_power)
        colA, colB, colC = st.columns(3)
        colA.metric("N2 product", f"{asu.n2_product_mass_flow_kg_s:.1f} kg/s")
        colB.metric("O2 co-product", f"{asu.o2_product_mass_flow_kg_s:.1f} kg/s")
        colC.metric("Power", f"{asu.total_power_kW:,.0f} kW")

# ---------------------------------------------------------------------
with tab_ammonia:
    st.header("Ammonia synthesis (Haber-Bosch loop)")
    c1, c2 = st.columns(2)
    with c1:
        h2_feed = st.number_input("H2 feed (mol/s)", min_value=1.0, value=3400.0)
    with c2:
        n2_feed = st.number_input("N2 feed (mol/s)", min_value=1.0, value=1133.0)
    c1, c2 = st.columns(2)
    with c1:
        single_pass = st.slider("Single-pass conversion", 0.10, 0.30, 0.19)
    with c2:
        purge = st.slider("Purge fraction", 0.005, 0.10, 0.02)
    if st.button("Solve ammonia loop", type="primary"):
        nh3 = ammonia_synthesis_loop(h2_feed, n2_feed, single_pass, purge)
        power = makeup_gas_compressor_power(h2_feed, n2_feed, 313.15, 40e5, 200e5)
        st.session_state["nh3_result"] = nh3
        colA, colB, colC = st.columns(3)
        colA.metric("NH3 produced", f"{nh3.nh3_product_mass_flow_kg_s:,.1f} kg/s")
        colB.metric("Overall conversion", f"{nh3.overall_conversion*100:.1f}%")
        colC.metric("Makeup compressor", f"{power:,.0f} kW")

# ---------------------------------------------------------------------
with tab_urea:
    st.header("Urea synthesis")
    c1, c2 = st.columns(2)
    with c1:
        nh3_feed = st.number_input("NH3 feed (mol/s)", min_value=1.0, value=3470.0, key="urea_nh3")
    with c2:
        co2_feed = st.number_input("CO2 feed (mol/s)", min_value=1.0, value=990.0, key="urea_co2")
    if st.button("Run urea reactor", type="primary"):
        try:
            u = synthesize_urea(nh3_feed, co2_feed)
            colA, colB, colC = st.columns(3)
            colA.metric("Urea produced", f"{u.urea_produced_mass_flow_kg_s:.1f} kg/s")
            colB.metric("N/C ratio", f"{u.nh3_to_co2_molar_ratio:.2f}")
            colC.metric("CO2 conversion", f"{u.co2_conversion*100:.1f}%")
            st.caption(f"Unconverted (recycle duty, not sized): {u.unconverted_co2_mol_s:.0f} mol/s CO2, "
                       f"{u.unconverted_nh3_mol_s:.0f} mol/s NH3")
        except ValueError as e:
            st.error(str(e))

# ---------------------------------------------------------------------
with tab_chain:
    st.header("Full chain: coal → urea")
    st.caption("Runs every module in sequence on one consistent basis - see examples/full_chain_worked_example.py.")
    st.markdown(
        "This mirrors the repo's own worked example, validated against Talcher Fertilizers "
        "Limited's real, public 1.27 mtpa urea capacity (see docs/VALIDATION.md). "
        "Use the individual tabs above to explore each unit interactively, or run "
        "`python examples/full_chain_worked_example.py` from a terminal for the full "
        "printed trace including the CO2-surplus finding."
    )

st.divider()
st.caption(
    "**Disclaimer**: this tool implements textbook/public-domain conceptual sizing "
    "methods for early-stage screening only. It is not a substitute for a rigorous "
    "process simulator, reactor kinetics model, or vendor-certified equipment data "
    "for detailed design."
)
