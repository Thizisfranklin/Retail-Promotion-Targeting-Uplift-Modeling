"""SQL-based campaign/segment analysis with interval estimates.

For binary outcomes use Wilson intervals and Newcombe's unpooled
interval for the difference in independent randomized group rates. This
avoids the impossible negative group-rate confidence limits of Wald CIs
when conversion is rare. For spend use Welch t intervals.
"""
import sqlite3

import numpy as np
import pandas as pd
from scipy import stats

from .config import ARMS, CONTROL, DB

AGG = ("COUNT(*) n, SUM(visit) visit_s, SUM(visit) visit_ss, SUM(conversion) conversion_s, "
       "SUM(conversion) conversion_ss, SUM(spend) spend_s, SUM(spend*spend) spend_ss")
SQL_ARMS = f"SELECT arm, {AGG} FROM customers GROUP BY arm"
SEGMENT_DIMS = {
    "Past spend band": "history_segment", "Recency of last purchase": "recency_bucket",
    "Channel": "channel", "Area type": "zip_code", "Customer type": "customer_type",
    "Past purchases": "past_purchases",
}
Z = stats.norm.ppf(.975)


def sql_segment(col: str) -> str:
    if col not in SEGMENT_DIMS.values():
        raise ValueError(f"Unsupported segment column: {col}")
    return f"SELECT {col} AS level, arm, {AGG} FROM customers GROUP BY {col}, arm"


def _mv(r, outcome):
    n, total, ss = r["n"], r[f"{outcome}_s"], r[f"{outcome}_ss"]
    if n <= 1:
        raise ValueError("At least two observations required for variance")
    mean = total / n
    return mean, max((ss - n * mean * mean) / (n - 1), 0.0)


def wilson(successes, n):
    """95% Wilson score interval for one binomial proportion."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = successes / n
    den = 1 + Z * Z / n
    center = (p + Z * Z / (2 * n)) / den
    half = Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return max(0., center - half), min(1., center + half)


def binary_diff_ci(success_t, n_t, success_c, n_c):
    """Newcombe score CI for a difference in independent binomial rates."""
    pt, pc = success_t / n_t, success_c / n_c
    lt, ht = wilson(success_t, n_t)
    lc, hc = wilson(success_c, n_c)
    d = pt - pc
    lo = d - np.hypot(pt - lt, hc - pc)
    hi = d + np.hypot(ht - pt, pc - lc)
    # Two-sided unadjusted pooled-score z-test; p-values are exploratory.
    pooled = (success_t + success_c) / (n_t + n_c)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n_t + 1 / n_c))
    pval = 2 * stats.norm.sf(abs(d / se)) if se > 0 else (1.0 if d == 0 else np.nan)
    return float(lo), float(hi), float(pval)


def arm_stats(agg: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in agg.iterrows():
        for outcome in ("conversion", "visit", "spend"):
            mean, variance = _mv(r, outcome)
            if outcome == "spend":
                half = stats.t.ppf(.975, r["n"] - 1) * np.sqrt(variance / r["n"])
                lo, hi = mean - half, mean + half
            else:
                lo, hi = wilson(r[f"{outcome}_s"], r["n"])
            rows.append({"arm": r["arm"], "outcome": outcome, "n": int(r["n"]),
                         "mean": mean, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def effects(agg: pd.DataFrame, by: str = None) -> pd.DataFrame:
    """Email minus no-email outcome; 95% CI and unadjusted exploratory p-value."""
    rows = []
    for level, group in (agg.groupby("level") if by else [(None, agg)]):
        g = group.set_index("arm")
        if CONTROL not in g.index:
            continue
        control = g.loc[CONTROL]
        for arm in ARMS:
            if arm not in g.index or min(g.loc[arm, "n"], control["n"]) < 30:
                continue
            treatment = g.loc[arm]
            for outcome in ("conversion", "visit", "spend"):
                mt, vt = _mv(treatment, outcome)
                mc, vc = _mv(control, outcome)
                diff = mt - mc
                if outcome != "spend":
                    lo, hi, pval = binary_diff_ci(
                        treatment[f"{outcome}_s"], treatment["n"],
                        control[f"{outcome}_s"], control["n"])
                else:
                    s1, s0 = vt / treatment["n"], vc / control["n"]
                    se = np.sqrt(s1 + s0)
                    denom = s1 * s1 / (treatment["n"] - 1) + s0 * s0 / (control["n"] - 1)
                    dof = (s1 + s0) ** 2 / denom if denom else np.inf
                    half = stats.t.ppf(.975, dof) * se if se else 0
                    lo, hi = diff - half, diff + half
                    pval = float(2 * stats.t.sf(abs(diff / se), dof)) if se else (1. if diff == 0 else np.nan)
                rows.append({"level": level, "arm": arm, "outcome": outcome,
                             "n_treat": int(treatment["n"]), "n_control": int(control["n"]),
                             "mean_treat": mt, "mean_control": mc, "diff": diff,
                             "lo": lo, "hi": hi, "p_value": pval,
                             "rel_lift": diff / mc if mc else np.nan})
    return pd.DataFrame(rows)


def run_analysis(db=DB) -> None:
    with sqlite3.connect(db) as con:
        arms = pd.read_sql(SQL_ARMS, con)
        arm_stats(arms).to_sql("arm_stats", con, if_exists="replace", index=False)
        effects(arms).drop(columns="level").to_sql("campaign_effects", con, if_exists="replace", index=False)
        segment_results = []
        for label, col in SEGMENT_DIMS.items():
            segment = effects(pd.read_sql(sql_segment(col), con), by=col)
            segment.insert(0, "dimension", label)
            segment_results.append(segment)
        pd.concat(segment_results).to_sql("segment_effects", con, if_exists="replace", index=False)
