"""FinTrace dashboard entrypoint: streamlit run src/fintrace/dashboard.py

All analysis is local. This dashboard is an illustrative research tool, not investment advice.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, replace
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import altair as alt
import pandas as pd
import streamlit as st

from fintrace.backtest import ForecastObservation, backtest, bias_by_analyst_metric
from fintrace.compare import ModelComparator
from fintrace.excel import ExcelIngestor
from fintrace.memory import append_note, read_notes
from fintrace.narrative import ClaimKind, NarrativeClaim, review_claim
from fintrace.presentation import histogram_rows, is_repeat_submission, narrative_input_spec
from fintrace.risk import TriangularRange, monte_carlo, stress_fragility
from fintrace.valuation import DCFInputs, DRIVERS, LABELS, calculate_dcf, attribute_dcf_change

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "examples" / "sample_models"
SAMPLE_FORECASTS = ROOT / "examples" / "sample_forecasts.csv"
NOTES = ROOT / "outputs" / "analyst_journal.jsonl"

st.set_page_config(page_title="FinTrace | Decision Intelligence", page_icon="📊", layout="wide")
st.markdown("""<style>
    .block-container {max-width: 1250px; padding-top: 1.6rem; padding-bottom: 3rem;}
    h1, h2, h3 {letter-spacing: -.035em;}
    .eyebrow {font-size: .74rem; letter-spacing: .17em; color: #2b807d; font-weight: 700; margin-bottom: 8px;}
    .hero {padding: 1.5rem 1.8rem; border:1px solid rgba(120,140,160,.30); border-radius:18px;
           background:linear-gradient(112deg,rgba(29,89,104,.12),rgba(75,106,99,.025)); margin-bottom:1.6rem;}
    .reasoning-chain {display:flex; gap:.45rem; align-items:center; flex-wrap:wrap; margin:1.1rem 0;}
    .reasoning-chain span {background:rgba(45,126,123,.13); border:1px solid rgba(64,142,136,.35); border-radius:10px; padding:.7rem .9rem; font-weight:600; font-size:.9rem;}
    .reasoning-chain b {font-weight:500; color:#2b807d;}
    .muted {color:#7a8b96;font-size:.87rem;}
    div[data-testid="stMetric"] {border:1px solid rgba(128,147,156,.23); padding:1rem; border-radius:12px;}
    div[data-testid="stTabs"] button {font-weight:600;}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="eyebrow">FINTRACE  /  RESEARCH WORKSPACE</div>'
            '<h1>Financial decisions, made traceable.</h1>'
            '<p>Evidence → assumptions → calculations → outcomes → judgement. '
            'Explore the model, not just the headline value.</p></div>', unsafe_allow_html=True)

st.sidebar.markdown("### ◈ FinTrace")
st.sidebar.caption("Local demo · analyst-controlled · no external API calls")
st.sidebar.markdown("**Interpretation matters**")
st.sidebar.info("All valuations use fictional numbers unless you enter your own. Scenario analytics do not re-evaluate uploaded Excel formulas.")
st.sidebar.caption("Assumption classifications are heuristics, not proof of intent. Narrative checks are questions, not accusations.")

view_tabs = st.tabs(["Overview", "Excel comparison", "DCF attribution", "Thesis fragility", "Monte Carlo", "Backtesting & bias", "Analyst memory", "Narrative review"])

# Shared illustrative DCF baseline; model actuals and analyst forecasts are separate demonstrations.
base = DCFInputs()

with view_tabs[0]:
    st.subheader("Explore the financial reasoning chain")
    st.markdown("The core workflow is **record evidence → identify assumptions → map downstream dependence → test alternative scenarios → review outcomes**.")
    a,b,c,d = st.columns(4)
    a.metric("Evidence lineage", "Available")
    b.metric("Workbook support", ".xlsx / .xlsm")
    c.metric("Scenario valuation", "5-year DCF")
    d.metric("Analysis modules", "7 tools")
    st.markdown("""<div class="reasoning-chain"><span>Evidence</span><b>→</b><span>Assumptions</span>
    <b>→</b><span>Calculations</span><b>→</b><span>Outcomes</span><b>→</b><span>Judgement</span></div>""",
    unsafe_allow_html=True)
    st.markdown("#### Where to start")
    st.write("1. Open **Excel comparison** to inspect our two fictional workbook versions or upload your own.")
    st.write("2. Open **DCF attribution** to see an exact, internally reconciled explanation of a *separate illustrative DCF* value change.")
    st.write("3. Explore **Thesis fragility** and **Monte Carlo** to question the assumptions, then **Backtesting** and **Narrative review** to evaluate what held up.")
    st.warning("This demonstration has separate Excel-lineage and parametrised-DCF engines. Connecting arbitrary Excel formulas to numerical attribution is future work.")

with view_tabs[1]:
    st.subheader("Workbook version intelligence")
    st.caption("Compare two analyst-owned files. FinTrace reads them; it does not modify or calculate Excel cells.")
    mode = st.radio("Workbook source", ["Use example workbooks", "Upload two workbooks"], horizontal=True)
    old_file = new_file = None
    if mode == "Upload two workbooks":
        old_file = st.file_uploader("Earlier version", type=["xlsx", "xlsm"], key="old_sheet")
        new_file = st.file_uploader("Revised version", type=["xlsx", "xlsm"], key="new_sheet")
    if st.button("Compare workbook versions", type="primary", key="compare"):
        try:
            if mode == "Use example workbooks":
                old, new = MODELS / "model_v1.xlsx", MODELS / "model_v2.xlsx"
                report = ModelComparator().compare_files(old, new)
            else:
                if old_file is None or new_file is None:
                    st.error("Upload both workbook versions first.")
                    st.stop()
                with TemporaryDirectory() as temp:
                    old = Path(temp) / ("before" + Path(old_file.name).suffix)
                    new = Path(temp) / ("after" + Path(new_file.name).suffix)
                    old.write_bytes(old_file.getvalue())
                    new.write_bytes(new_file.getvalue())
                    report = ModelComparator().compare_files(old, new)
            st.session_state["workbook_report"] = report
        except Exception as exc:
            st.error(f"Could not inspect workbook: {exc}")
    report = st.session_state.get("workbook_report")
    if report:
        m1,m2,m3 = st.columns(3)
        m1.metric("Changed cells", len(report.changes))
        m2.metric("Assumption candidates", len(report.assumption_changes))
        m3.metric("Potentially affected outputs", len(report.impacted_output_refs))
        rows = [{"Cell": c.ref, "Label": c.label or "", "Classification": c.classification.value,
                 "Before": str(c.before_value if c.before_formula is None else c.before_formula),
                 "After": str(c.after_value if c.after_formula is None else c.after_formula),
                 "Potentially impacted": ", ".join(c.impacted_outputs)} for c in report.changes]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button("Download JSON report", data=report.model_dump_json(indent=2),
                           file_name="model_comparison.json", mime="application/json")
        if report.warnings:
            st.warning(f"{len(report.warnings)} unresolved reference warning(s). Some dependencies may be incomplete.")

with view_tabs[2]:
    st.subheader("Numerical DCF change attribution")
    st.caption("Exact Shapley allocation across four changes in FinTrace's own five-year DCF; not arbitrary Excel formula attribution.")
    st.markdown("All valuations use **£ millions** and fixed base revenue of £850m; other model parameters are kept constant.")
    cols = st.columns(4)
    defaults_old = [.08,.20,.10,.025]
    defaults_new = [.06,.19,.115,.020]
    prior, revised = {}, {}
    for idx,key in enumerate(DRIVERS):
        with cols[idx]:
            st.markdown(f"**{LABELS[key]}**")
            prior[key] = st.number_input("Old (%)", value=100*defaults_old[idx], step=0.5, key=f"old_{key}")/100
            revised[key] = st.number_input("New (%)", value=100*defaults_new[idx], step=0.5, key=f"new_{key}")/100
    try:
        old_model = replace(base, **prior)
        new_model = replace(base, **revised)
        attr = attribute_dcf_change(old_model, new_model)
        old_val, new_val, delta = attr.old_equity_value, attr.new_equity_value, attr.total_change
        a,b,c = st.columns(3)
        a.metric("Old equity value", f"£{old_val:,.1f}m")
        b.metric("New equity value", f"£{new_val:,.1f}m")
        c.metric("Change", f"£{delta:+,.1f}m", delta=f"{(delta/abs(old_val))*100:+.1f}%" if old_val else None)
        st.markdown("#### Contribution to value change (£m)")
        contribution = pd.DataFrame([{"Driver": LABELS[k], "Contribution (£m)": v} for k,v in attr.contributions.items()])
        driver_chart = (alt.Chart(contribution).mark_bar(cornerRadiusEnd=3)
            .encode(x=alt.X("Contribution (£m):Q", axis=alt.Axis(format="+,.0f", title="Contribution (£m)")),
                    y=alt.Y("Driver:N", sort=None, title=None),
                    tooltip=[alt.Tooltip("Driver:N"),
                             alt.Tooltip("Contribution (£m):Q", format="+,.2f")]))
        st.altair_chart(driver_chart, use_container_width=True)
        st.dataframe(contribution.style.format({"Contribution (£m)":"{:+,.2f}"}), use_container_width=True, hide_index=True)
        st.caption(f"Reconciliation: sum of contributions £{sum(attr.contributions.values()):+,.2f}m = value change £{delta:+,.2f}m (up to rounding). Order averaged across 24 paths.")
    except ValueError as exc:
        st.error(str(exc))

with view_tabs[3]:
    st.subheader("Thesis fragility / stress concentration")
    st.caption("Set an adverse case for each driver. This is a one-at-a-time stress test, not a forecast probability.")
    default_adverse = {"revenue_growth":.04,"ebit_margin":.16,"wacc":.13,"terminal_growth":.015}
    stress_values = {}
    for col,key in zip(st.columns(4),DRIVERS):
        with col:
            stress_values[key] = st.number_input(LABELS[key] + " adverse (%)", value=default_adverse[key]*100, step=.5)/100
    try:
        stress = stress_fragility(base,stress_values)
        st.metric("Isolated downside in largest 2 drivers / sum of isolated downsides", f"{stress.largest_two_concentration_pct:.1f}%")
        df = pd.DataFrame([{"Driver":LABELS[key],"Stressed equity value (£m)":v,
                            "Isolated downside (£m)":stress.downside_amounts[key]}
                           for key,v in stress.stressed_values.items()])
        largest = max(stress.downside_amounts, key=stress.downside_amounts.get)
        st.caption(f"Largest isolated vulnerability: {LABELS[largest]} "
                   f"(£{stress.downside_amounts[largest]:,.1f}m downside in the selected stress).")
        stress_chart = (alt.Chart(df).mark_bar(cornerRadiusEnd=3)
            .encode(x=alt.X("Isolated downside (£m):Q", axis=alt.Axis(format=",.0f")),
                    y=alt.Y("Driver:N", sort="-x", title=None),
                    tooltip=[alt.Tooltip("Driver:N"),
                             alt.Tooltip("Isolated downside (£m):Q", format=",.2f")]))
        st.altair_chart(stress_chart, use_container_width=True)
        st.dataframe(df.style.format({"Stressed equity value (£m)":"{:,.2f}",
                                     "Isolated downside (£m)":"{:,.2f}"}),
                     hide_index=True,use_container_width=True)
        st.info("The concentration percentage tells you where isolated downside is concentrated. It is NOT a confidence score, likelihood of loss or additive combined-case loss.")
    except ValueError as exc:
        st.error(str(exc))

with view_tabs[4]:
    st.subheader("Monte Carlo scenario distribution")
    st.caption("Independent triangular assumptions (low / most likely / high). Bounds are analyst-supplied, not calibrated probabilities.")
    preset = {"revenue_growth":(.03,.08,.12),"ebit_margin":(.15,.20,.23),
              "wacc":(.085,.105,.14),"terminal_growth":(.01,.02,.03)}
    distributions={}
    for col,key in zip(st.columns(4),DRIVERS):
        with col:
            st.markdown(f"**{LABELS[key]}**")
            low,mode_,high=preset[key]
            low=st.number_input("Low (%)",value=low*100,step=.5,key=f"mc_low_{key}")/100
            mode_=st.number_input("Likely (%)",value=mode_*100,step=.5,key=f"mc_mode_{key}")/100
            high=st.number_input("High (%)",value=high*100,step=.5,key=f"mc_high_{key}")/100
            distributions[key]=TriangularRange(low,mode_,high)
    sims, seed_, hurdle = st.columns(3)
    with sims: n_trials=st.select_slider("Simulation count",options=[500,1000,3000,10000],value=3000)
    with seed_: seed=st.number_input("Random seed",min_value=0,value=42,step=1)
    with hurdle: threshold=st.number_input("Equity hurdle (£m)",value=1000.,step=100.)
    if st.button("Run Monte Carlo",type="primary"):
        try:
            result=monte_carlo(base,distributions,trials=n_trials,seed=int(seed),hurdle=threshold)
            st.session_state["monte_result"]=result
        except ValueError as exc:
            st.error(str(exc))
    sim=st.session_state.get("monte_result")
    if sim:
        p1,p2,p3,p4=st.columns(4)
        p1.metric("P5",f"£{sim.p05:,.0f}m")
        p2.metric("Median",f"£{sim.p50:,.0f}m")
        p3.metric("P95",f"£{sim.p95:,.0f}m")
        p4.metric("P(above hurdle)",f"{100*sim.probability_above_hurdle:.1f}%")
        distribution_df = pd.DataFrame(histogram_rows(sim.samples, bins=32))
        bars = (alt.Chart(distribution_df).mark_bar(opacity=0.82)
            .encode(x=alt.X("lower:Q", axis=alt.Axis(title="Scenario equity value (£m)",
                                                       format=",.0f"), scale=alt.Scale(zero=False)),
                    x2="upper:Q",
                    y=alt.Y("frequency:Q", title="Simulations"),
                    tooltip=[alt.Tooltip("lower:Q", title="From (£m)", format=",.0f"),
                             alt.Tooltip("upper:Q", title="To (£m)", format=",.0f"),
                             alt.Tooltip("frequency:Q", title="Count")]))
        quantiles = pd.DataFrame({"Value": [sim.p05, sim.p50, sim.p95],
                                   "Marker": ["P5", "Median", "P95"]})
        rules = (alt.Chart(quantiles).mark_rule(strokeDash=[5, 4], size=2)
            .encode(x="Value:Q", color=alt.Color("Marker:N", title="Percentile"),
                    tooltip=[alt.Tooltip("Marker:N"),
                             alt.Tooltip("Value:Q", title="Equity (£m)", format=",.0f")]))
        st.altair_chart((bars + rules).properties(height=330), use_container_width=True)
        st.warning("Scenario frequencies are conditional on the distributions you chose and their independence assumption. They do not represent objective market probabilities.")

with view_tabs[5]:
    st.subheader("Historical forecast backtesting & analyst bias")
    st.caption("Only actuals released by the selected evaluation date are scored. Distinct measures/units are analysed separately.")
    upload=st.file_uploader("Optional forecast CSV (otherwise use the bundled fictional example)",type=["csv"])
    observed_by=st.date_input("Evaluate information available by",value=date(2026,10,13))
    template="analyst,metric,as_of,target_date,actual_released_on,forecast,actual\n"
    with st.expander("Required CSV columns"):
        st.code(template)
    if st.button("Evaluate forecasts"):
        try:
            text_data=upload.getvalue().decode("utf-8-sig") if upload else SAMPLE_FORECASTS.read_text(encoding="utf-8")
            csv_rows=list(csv.DictReader(StringIO(text_data)))
            observations=[ForecastObservation(analyst=x["analyst"],metric=x["metric"],
                         as_of=date.fromisoformat(x["as_of"]),target_date=date.fromisoformat(x["target_date"]),
                         actual_released_on=date.fromisoformat(x["actual_released_on"]),
                         forecast=float(x["forecast"]),actual=float(x["actual"])) for x in csv_rows]
            results=bias_by_analyst_metric(observations,observed_by=observed_by)
            if not results:
                st.warning("No outcomes were observable by that date.")
            else:
                table=pd.DataFrame([{"Analyst / metric":k,"Forecasts":v.n,"Mean error":v.mean_error,
                        "MAE":v.mae,"RMSE":v.rmse,"WAPE (%)":v.wape_pct,"Over-forecasts":v.optimistic_count}
                        for k,v in results.items()])
                st.dataframe(table.style.format({"Mean error":"{:+,.2f}","MAE":"{:,.2f}",
                                                  "RMSE":"{:,.2f}","WAPE (%)":"{:.2f}"}, na_rep="—"),
                             use_container_width=True,hide_index=True)
                with st.expander("How to interpret forecast errors"):
                    st.markdown("**Mean error:** average forecast minus actual; positive suggests over-forecasting. "
                                "**MAE:** typical absolute miss, in the metric's own units. "
                                "**RMSE:** penalises larger errors. "
                                "**WAPE:** absolute error divided by total absolute actual values; "
                                "not defined when that denominator is zero.")
                st.caption("Errors are evaluated separately by analyst and metric. These examples are fictional.")
        except (ValueError,KeyError,UnicodeDecodeError) as exc:
            st.error(f"Invalid forecast dataset: {exc}")

with view_tabs[6]:
    st.subheader("Analyst memory: preserve your rationale")
    st.caption("Entries are appended to outputs/analyst_journal.jsonl on this computer. Nothing is sent to a third-party API.")
    with st.form("memory_form"):
        author=st.text_input("Analyst",value="Demo analyst")
        subject=st.text_input("Assumption / topic",value="EBIT margin")
        prev=st.text_input("Prior view",value="20%")
        revised_view=st.text_input("Updated view",value="19%")
        why=st.text_area("Why was it changed?",value="Revised outlook after higher costs")
        source=st.text_input("Evidence source reference",value="Illustrative board update, page 3")
        submitted=st.form_submit_button("Append reasoning note",type="primary")
    if submitted:
        try:
            if is_repeat_submission(read_notes(NOTES), analyst=author, subject=subject,
                                    prior_assumption=prev, revised_assumption=revised_view,
                                    rationale=why, evidence_reference=source):
                st.warning("That exact entry was just recorded. No duplicate was added.")
            else:
                note=append_note(NOTES,analyst=author,subject=subject,prior_assumption=prev,
                       revised_assumption=revised_view,rationale=why,evidence_reference=source)
                st.success(f"Recorded note {note.id[:8]} without changing earlier entries.")
        except ValueError as exc:
            st.error(str(exc))
    notes=read_notes(NOTES)
    if notes:
        st.dataframe(pd.DataFrame([asdict(n) for n in reversed(notes)]),hide_index=True,use_container_width=True)
    else:
        st.info("No journal entries yet. Record an assumption revision above.")

with view_tabs[7]:
    st.subheader("Narrative vs numbers: review questions")
    st.caption("Enter a source-attributed claim and comparable data. The tool checks a narrow measurable proposition; it does not infer deception or parse filings.")
    kind=st.selectbox("Claim type",options=list(ClaimKind),format_func=lambda x:x.value.replace("_"," ").title())
    statement=st.text_area("Source claim",value="We are seeing margin expansion.")
    source_name=st.text_input("Source document",value="ExampleCo annual report (fictional)")
    location=st.text_input("Page / precise citation",value="Page 7")
    spec = narrative_input_spec(kind)
    st.caption(f"Enter **{spec.unit}** consistently across all relevant periods. "
               "EBIT margins are entered as percentages (e.g. 20 for 20%).")
    if kind is ClaimKind.REVENUE_ACCELERATION:
        p1,p2,p3=st.columns(3)
        with p1:
            earlier=st.number_input("Period T-2", value=float(spec.earlier),
                                    step=5.0, key=f"narr_earlier_{kind.value}")
    else:
        earlier=None
        p2,p3=st.columns(2)
    with p2:
        prior=st.number_input(f"Period T-1 ({spec.unit})", value=spec.prior,
                              step=1.0 if spec.divisor == 100 else 5.0,
                              key=f"narr_prior_{kind.value}")
    with p3:
        current=st.number_input(f"Period T ({spec.unit})", value=spec.current,
                                step=1.0 if spec.divisor == 100 else 5.0,
                                key=f"narr_current_{kind.value}")
    if st.button("Review source claim"):
        try:
            claim=NarrativeClaim(statement,source_name,location,kind)
            response=review_claim(claim, prior_prior=None if earlier is None else earlier/spec.divisor,
                                  prior=prior/spec.divisor, current=current/spec.divisor)
            if response.status.value == "tension":
                st.warning("Question for analyst review: " + response.question)
            elif response.status.value == "aligned":
                st.success("Consistent with supplied numbers: " + response.question)
            else:
                st.info(response.question)
            st.caption(f"Evidence: {source_name} · {location} · {response.disclaimer}")
        except ValueError as exc:
            st.error(str(exc))

st.divider()
st.caption("FinTrace · Open-source analyst companion · Modelled scenarios are not investment recommendations · Work in progress")
