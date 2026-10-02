"""Streamlit dashboard: python -m src.pipeline && streamlit run app.py"""
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analysis import SEGMENT_DIMS
from src.config import ARM_LABEL, ARMS, CONTROL, DB
from src.presentation import campaign_evidence, targeting_evidence, targeting_budget_evidence

COL = {CONTROL: "#8c8c8c", "Mens E-Mail": "#1f77b4", "Womens E-Mail": "#d6336c"}
OUT = {"conversion": "Purchase rate", "visit": "Website visit rate", "spend": "Average spend ($)"}

st.set_page_config(page_title="Email Targeting & Incremental Impact", layout="wide")


@st.cache_data
def _load_cached(table, database_revision):
    # Revision participates in Streamlit's cache key; never mix results from
    # a previous synthetic run with newly rebuilt real-data tables.
    with sqlite3.connect(DB) as con:
        return pd.read_sql(f"SELECT * FROM {table}", con)


def load(table):
    stat = DB.stat()
    return _load_cached(table, (stat.st_mtime_ns, stat.st_size))


if not DB.exists():
    st.error("Database not found. Run `python -m src.pipeline` first (see README).")
    st.stop()

source = load("meta").set_index("key").value["source"]
st.title("Which customers should get the email?")
st.caption("Randomized email experiment (Hillstrom): customers were randomly sent a men's email, a women's email, "
           "or no email, then tracked for two weeks.")
if source != "hillstrom":
    st.warning("SYNTHETIC DEMO DATA - numbers below are fake and for testing the app only.")
else:
    st.caption("Historical 2008 experiment · Real Hillstrom data · Not a live marketing campaign")

# Executive summary is always computed from the *currently loaded* database.
# Never hardcode real-data results: someone can run --synthetic after a real run.
conv_effects = load("campaign_effects").query("outcome == 'conversion'").set_index("arm")
uplift_overall = load("uplift_summary").set_index("arm")
num_customers = int(load("meta").set_index("key").loc["n_rows", "value"])
st.subheader("Executive summary")
st.write(f"**{num_customers:,} customers** were assigned to a men's email, a women's email, "
         "or no email. Conversion (a purchase within two weeks) is the primary outcome.")
summary_columns = st.columns(3)
for column, arm in zip(summary_columns[:2], ARMS):
    finding = conv_effects.loc[arm]
    column.metric(f"{ARM_LABEL[arm]}: incremental purchases",
                  f"{finding['diff'] * 100:+.2f} pp")
    column.caption(f"95% CI {finding['lo'] * 100:+.2f} to {finding['hi'] * 100:+.2f} pp. "
                   f"{campaign_evidence(finding['lo'], finding['hi'])}.")
no_clear_advantage = all(uplift_overall.loc[arm, "auuc_lo"] <= 0 <= uplift_overall.loc[arm, "auuc_hi"]
                         for arm in ARMS)
summary_columns[2].metric("Model-based targeting",
                          "Not established" if no_clear_advantage else "See held-out results")
summary_columns[2].caption(
    "Neither email model shows a clear held-out advantage over random targeting."
    if no_clear_advantage else "Results differ by campaign; see the held-out intervals below."
)
st.info("**What this means:** These emails can change average purchasing behavior, "
        "but that alone does not demonstrate that a model can reliably identify which individuals "
        "to target. The experiment did not measure sending costs or profit.")

# ---------- 1. Campaign effectiveness ----------
st.header("1. Did the emails actually increase purchases?")
st.write("*Why it matters:* randomized comparison estimates the average causal effect of each email, under the experiment assumptions. "
         "Intervals show how much each number could move by chance.")
o = st.radio("Outcome", list(OUT), format_func=OUT.get, horizontal=True, key="o1")
sc = 100 if o != "spend" else 1
unit = "%" if o != "spend" else "$"
a, e = load("arm_stats").query("outcome==@o"), load("campaign_effects").query("outcome==@o")
fig = make_subplots(rows=1, cols=2, subplot_titles=(f"{OUT[o]} by group (95% CI)", "Increase vs. no email (95% CI)"))
for arm in [CONTROL, *ARMS]:
    r = a[a.arm == arm].iloc[0]
    fig.add_bar(x=[ARM_LABEL[arm]], y=[r["mean"] * sc], marker_color=COL[arm], showlegend=False,
                error_y=dict(type="data", array=[(r.hi - r["mean"]) * sc], arrayminus=[(r["mean"] - r.lo) * sc]),
                hovertemplate=f"{ARM_LABEL[arm]}<br>{OUT[o]}: %{{y:.2f}}{unit}<br>Customers: {r.n:,}<extra></extra>",
                row=1, col=1)
for _, r in e.iterrows():
    fig.add_scatter(x=[ARM_LABEL[r.arm]], y=[r["diff"] * sc], mode="markers", showlegend=False, marker=dict(size=12, color=COL[r.arm]),
                    error_y=dict(type="data", array=[(r.hi - r["diff"]) * sc], arrayminus=[(r["diff"] - r.lo) * sc]),
                    hovertemplate=f"{ARM_LABEL[r.arm]}<br>Effect: %{{y:+.2f}}{'pp' if o != 'spend' else '$'}<br>p={r.p_value:.3g}"
                                  f"<br>Treated n={r.n_treat:,} / control n={r.n_control:,}<extra></extra>", row=1, col=2)
fig.add_hline(y=0, line_dash="dash", line_color="#999", row=1, col=2)
fig.update_yaxes(title_text=f"{OUT[o]} ({unit})", row=1, col=1)
fig.update_yaxes(title_text="Difference (percentage points)" if o != "spend" else "Difference ($)", row=1, col=2)
fig.update_layout(height=400, margin=dict(t=50, b=10))
st.plotly_chart(fig, width="stretch")
cols = st.columns(2)
for c, (_, r) in zip(cols, e.iterrows()):
    c.metric(f"{ARM_LABEL[r.arm]} effect", f"{r['diff']*sc:+.2f} {'pp' if o != 'spend' else '$'}",
             f"95% CI {r.lo*sc:+.2f} to {r.hi*sc:+.2f}; p={r.p_value:.3g}", delta_color="off")
    c.caption(f"{r.n_treat:,} emailed vs {r.n_control:,} not emailed")

# ---------- 2. Segments ----------
st.header("2. Does the email work better for some customers?")
st.write("*Why it matters:* segment differences may identify promising hypotheses for future testing. "
         "Segments were defined from pre-email information only. Many segments are compared, so treat "
         "isolated differences cautiously.")
c1, c2 = st.columns(2)
camp = c1.selectbox("Campaign", list(ARMS), format_func=ARM_LABEL.get)
dim = c2.selectbox("Customer segment", list(SEGMENT_DIMS))
s = load("segment_effects").query("outcome=='conversion' and arm==@camp and dimension==@dim").sort_values("level")
ov = load("campaign_effects").query("outcome=='conversion' and arm==@camp").iloc[0]["diff"] * 100
fig = go.Figure(go.Scatter(
    x=s["diff"] * 100, y=s.level, mode="markers", marker=dict(size=11, color=COL[camp]),
    error_x=dict(type="data", array=(s.hi - s["diff"]) * 100, arrayminus=(s["diff"] - s.lo) * 100),
    customdata=s[["n_treat", "n_control", "mean_control", "mean_treat"]].values,
    hovertemplate="%{y}<br>Effect: %{x:+.2f} pp<br>Emailed n=%{customdata[0]:,}, control n=%{customdata[1]:,}"
                  "<br>Purchase rate: %{customdata[2]:.2%} (no email) vs %{customdata[3]:.2%} (email)<extra></extra>"))
fig.add_vline(x=0, line_dash="dash", line_color="#999")
fig.add_vline(x=ov, line_color=COL[camp], opacity=.4, annotation_text="overall", annotation_position="top")
fig.update_layout(height=120 + 60 * len(s), xaxis_title="Increase in purchase rate vs. no email (percentage points, 95% CI)",
                  yaxis_title="", margin=dict(t=30, b=10))
st.plotly_chart(fig, width="stretch")
st.caption("95% intervals crossing zero indicate an inconclusive effect estimate for that segment. Multiple exploratory segments are compared without a multiplicity adjustment.")

# ---------- 3. Targeting ----------
st.header("3. Would smarter targeting beat emailing everyone?")
st.write("*Why it matters:* a model ranks customers by predicted extra purchases from the email (a 'T-Learner': one model "
         "of buying with the email, one without). We judge it on 20% of customers never used for training, using "
         "the randomized groups, not the model's own predictions.")
camp3 = st.selectbox("Campaign", list(ARMS), format_func=ARM_LABEL.get, key="c3")
cv = load("uplift_curves").query("arm==@camp3")
sm = load("uplift_summary").query("arm==@camp3").iloc[0]
f = st.slider("Share of customers to email (highest predicted effect first)", 5, 100, 30, 5, format="%d%%") / 100
# One primary figure with two coordinated views. The lower panel exposes the
# decision-relevant model-minus-random *gap* and its uncertainty.
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.13,
                    row_heights=[0.67, 0.33],
                    subplot_titles=("Estimated incremental purchases", "Model minus random (including uncertainty)"))
x = cv.frac * 100
fig.add_scatter(x=x, y=cv.model_hi, line=dict(width=0), showlegend=False, hoverinfo="skip", row=1, col=1)
fig.add_scatter(x=x, y=cv.model_lo, fill="tonexty", fillcolor="rgba(0,150,136,.15)", line=dict(width=0),
                name="Model pointwise 95% CI", hoverinfo="skip", row=1, col=1)
fig.add_scatter(x=x, y=cv.model, name="Model-based targeting", line=dict(color="#009688", width=3),
                hovertemplate="Email top %{x:.0f}%<br>%{y:.2f} extra purchases per 1,000 eligible customers<extra></extra>",
                row=1, col=1)
fig.add_scatter(x=x, y=cv.random, name="Random targeting (same budget)",
                line=dict(color="#666", dash="dash"), row=1, col=1)
end = cv.iloc[-1]
fig.add_scatter(x=[100], y=[end.model], mode="markers", name="Email everyone (100% budget)",
                marker=dict(size=12, symbol="diamond", color="#292929"), row=1, col=1)
fig.add_scatter(x=x, y=cv.gap_hi, line=dict(width=0), showlegend=False, hoverinfo="skip", row=2, col=1)
fig.add_scatter(x=x, y=cv.gap_lo, line=dict(width=0), fill="tonexty", fillcolor="rgba(20,93,173,.16)",
                name="Gap pointwise 95% CI", hoverinfo="skip", row=2, col=1)
fig.add_scatter(x=x, y=cv.gap, name="Model minus random", line=dict(color="#145dad", width=2),
                hovertemplate="Email top %{x:.0f}%<br>Gap: %{y:+.2f} per 1,000 eligible customers<extra></extra>",
                row=2, col=1)
fig.add_hline(y=0, line_color="#555", line_dash="dash", row=2, col=1)
for row in (1, 2):
    fig.add_vline(x=f * 100, line_color="#e8590c", opacity=.8, row=row, col=1)
fig.update_layout(height=620, margin=dict(t=60, b=20, l=10, r=10),
                  legend=dict(orientation="h", y=1.10, x=0, font=dict(size=11)))
fig.update_yaxes(title_text="Extra purchases / 1,000 eligible", row=1, col=1)
fig.update_yaxes(title_text="Difference / 1,000", row=2, col=1)
fig.update_xaxes(title_text="Share of eligible customers emailed (%)", row=2, col=1)
st.plotly_chart(fig, width="stretch")
r = cv.iloc[(cv.frac - f).abs().argmin()]
m = st.columns(3)
m[0].metric("Model (chosen budget)", f"{r.model:.2f}",
            help="Estimated extra purchases per 1,000 eligible customers, not per 1,000 emailed")
m[1].metric("Random (same budget)", f"{r.random:.2f}")
m[2].metric("Difference: model - random", f"{r.gap:+.2f}",
            help=f"95% pointwise bootstrap CI {r.gap_lo:+.2f} to {r.gap_hi:+.2f}")
st.write(f"**At {f:.0%} coverage:** {targeting_budget_evidence(r.gap_lo, r.gap_hi)}. "
         f"Estimated gap: {r.gap:+.2f} extra purchases per 1,000 eligible customers "
         f"(95% CI {r.gap_lo:+.2f} to {r.gap_hi:+.2f}).")
st.info(f"**Across all tested budgets:** {targeting_evidence(sm.auuc_lo, sm.auuc_hi)}. "
        f"Area between model and random curves (AUUC gap): {sm.test_auuc_gap:+.2f} "
        f"(95% CI {sm.auuc_lo:+.2f} to {sm.auuc_hi:+.2f}). "
        "If an interval spans zero, the observed difference could reflect sampling noise. "
        "Do not choose the most flattering test-set budget after seeing these results.")
st.caption(f"**Different budget:** Sending to everyone (100% coverage) is estimated at "
           f"{end.model:.2f} extra purchases per 1,000 eligible customers. "
           "It is NOT an equal-budget alternative to emailing a smaller group: a fair comparison "
           "holds the share emailed constant. Sending costs and profit were not measured. "
           f"Selected model: {sm.selected_model} (chosen using validation data). "
           f"Held-out test: {int(sm.n_test):,} customers. Bands are pointwise bootstrap estimates "
           "conditional on this fitted model and test split; a rollout would require a new controlled test.")
with st.expander("Method details and sanity checks"):
    st.write("Customers split 60% train / 20% validation / 20% test, stratified. Only pre-email features are used "
             "(recency, past spend, past purchases, new customer, area, channel).")
    st.dataframe(load("uplift_model_selection").query("arm==@camp3"), hide_index=True)
    q = load("uplift_quintiles").query("arm==@camp3")
    st.write("Test customers grouped by predicted uplift. These noisy observed estimates need not decline monotonically:")
    st.dataframe(q, hide_index=True)
    st.dataframe(load("validation_checks"), hide_index=True)
