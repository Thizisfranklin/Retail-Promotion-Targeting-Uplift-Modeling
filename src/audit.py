"""Independent, reproducible checks of saved campaign and held-out results.

Run `python -m src.audit` in Codespaces after `python -m src.pipeline`.
No model is refitted: this inspects the actual SQLite output and (when
available) stored held-out predictions from the completed model run.
"""
import argparse
import sqlite3

import numpy as np
import pandas as pd
from scipy.stats import binomtest, chi2_contingency

from .config import ARMS, CONTROL, DB


class AuditError(AssertionError):
    """Saved project results don't match the underlying data."""


def audit(db=DB, require_real=False):
    with sqlite3.connect(db) as con:
        tables = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        source = dict(con.execute("SELECT key, value FROM meta")).get("source")
        count = int(dict(con.execute("SELECT key, value FROM meta"))["n_rows"])
        if require_real and (source != "hillstrom" or count != 64000):
            raise AuditError("Expected the real 64,000-row Hillstrom experiment; don't publish synthetic results.")
        needed = {"customers", "campaign_effects", "arm_stats", "uplift_curves", "uplift_summary"}
        if not needed.issubset(tables):
            raise AuditError(f"Missing analysis tables: {needed - tables}")
        customers = pd.read_sql("SELECT arm, conversion, visit, spend FROM customers", con)
        effects = pd.read_sql("SELECT * FROM campaign_effects", con)
        arms = pd.read_sql("SELECT * FROM arm_stats", con)
        curves = pd.read_sql("SELECT * FROM uplift_curves", con)
        summary = pd.read_sql("SELECT * FROM uplift_summary", con)
        holdout = (pd.read_sql("SELECT * FROM uplift_holdout", con)
                   if "uplift_holdout" in tables else None)

    if len(customers) != count:
        raise AuditError(f"Metadata says {count} customers, but found {len(customers)}")
    if set(customers.arm.unique()) != set(ARMS) | {CONTROL}:
        raise AuditError("Expected exactly three randomized groups")

    print(f"SOURCE: {source} | Rows: {count:,}")
    print("\nINDEPENDENTLY RECOMPUTED GROUP OUTCOMES")
    groups = customers.groupby("arm", sort=True)
    direct = groups.agg(n=("conversion", "size"), conversion=("conversion", "mean"),
                        visit=("visit", "mean"), spend=("spend", "mean"))
    print(direct.round(5).to_string())
    for arm, row in direct.iterrows():
        for outcome in ("conversion", "visit", "spend"):
            saved = arms.query("arm == @arm and outcome == @outcome")
            if len(saved) != 1 or int(saved.iloc[0]["n"]) != int(row["n"]):
                raise AuditError(f"Group count mismatch: {arm} / {outcome}")
            if not np.isclose(saved.iloc[0]["mean"], row[outcome], atol=1e-10):
                raise AuditError(f"Group mean mismatch: {arm} / {outcome}")
            if outcome in ("conversion", "visit"):
                # SciPy's independent binomtest implementation of a Wilson CI.
                successes = int(customers.loc[customers.arm == arm, outcome].sum())
                ci = binomtest(successes, int(row['n'])).proportion_ci(method='wilson')
                if not (np.isclose(saved.iloc[0]['lo'], ci.low, atol=1e-9)
                        and np.isclose(saved.iloc[0]['hi'], ci.high, atol=1e-9)):
                    raise AuditError(f"Group confidence interval mismatch: {arm} / {outcome}")

    print("\nINDEPENDENT TREATMENT-CONTROL CHECK")
    control = customers[customers.arm == CONTROL]
    for arm in ARMS:
        treated = customers[customers.arm == arm]
        for outcome in ("conversion", "visit", "spend"):
            direct_diff = treated[outcome].mean() - control[outcome].mean()
            saved = effects.query("arm == @arm and outcome == @outcome")
            if len(saved) != 1 or not np.isclose(saved.iloc[0]["diff"], direct_diff, atol=1e-10):
                raise AuditError(f"Stored treatment effect mismatch: {arm} / {outcome}")
            if saved.iloc[0]["lo"] > saved.iloc[0]["hi"]:
                raise AuditError(f"Reversed confidence interval: {arm} / {outcome}")
            if outcome in ('conversion', 'visit'):
                # Independently verify Newcombe's unpooled treatment-effect CI
                # using SciPy Wilson intervals rather than src.analysis.wilson.
                t_ci = binomtest(int(treated[outcome].sum()), len(treated)).proportion_ci(method='wilson')
                c_ci = binomtest(int(control[outcome].sum()), len(control)).proportion_ci(method='wilson')
                pt, pc = treated[outcome].mean(), control[outcome].mean()
                independent_lo = direct_diff - np.hypot(pt-t_ci.low, c_ci.high-pc)
                independent_hi = direct_diff + np.hypot(t_ci.high-pt, pc-c_ci.low)
                if not (np.isclose(saved.iloc[0]['lo'], independent_lo, atol=1e-9)
                        and np.isclose(saved.iloc[0]['hi'], independent_hi, atol=1e-9)):
                    raise AuditError(f"Treatment-effect confidence interval mismatch: {arm} / {outcome}")
            if outcome == "conversion":
                # Independent chi-square sanity check of the conversion comparison.
                hits = [int(treated.conversion.sum()), int(control.conversion.sum())]
                sample = [len(treated), len(control)]
                contingency = [[hits[0], sample[0]-hits[0]], [hits[1], sample[1]-hits[1]]]
                _, p, _, _ = chi2_contingency(contingency, correction=False)
                if not np.isclose(p, saved.iloc[0]["p_value"], atol=1e-8):
                    raise AuditError(f"Independent significance check failed: {arm}")
                print(f"{arm}: conversion lift {direct_diff*100:+.3f} percentage points; chi-square p={p:.4g}")

    print("\nHELD-OUT TARGETING CHECK")
    for arm in ARMS:
        curve = curves[curves.arm == arm].sort_values("frac")
        sm = summary[summary.arm == arm]
        if curve.empty or len(sm) != 1:
            raise AuditError(f"Missing held-out curve: {arm}")
        if not np.allclose(curve.random, curve.frac * curve.iloc[-1].model, atol=1e-8):
            raise AuditError(f"Random baseline isn't the linear whole-group effect: {arm}")
        if not np.isclose(curve.iloc[-1].model, curve.iloc[-1].random, atol=1e-8):
            raise AuditError(f"Model and random must meet when everyone gets the email: {arm}")
        if holdout is None:
            print(f"{arm}: baseline/endpoints pass; rerun the updated pipeline to audit individual held-out scores")
            continue
        h = holdout[holdout.arm == arm].sort_values("rank", kind="stable")
        if len(h) != int(sm.iloc[0].n_test):
            raise AuditError(f"Held-out count mismatch: {arm}")
        if not h["score"].is_monotonic_decreasing:
            raise AuditError(f"Predicted uplift isn't ranked descending: {arm}")
        y, t = h.conversion.to_numpy(), h.treatment.to_numpy()
        for _, point in curve.iterrows():
            m = int(round(float(point.frac) * len(h)))
            if m == 0:
                independent_value = 0.
            else:
                subset_y, subset_t = y[:m], t[:m]
                if len(np.unique(subset_t)) < 2:
                    continue
                independent_value = 1000 * (m/len(h)) * (
                    subset_y[subset_t == 1].mean() - subset_y[subset_t == 0].mean())
            if not np.isclose(independent_value, point.model, atol=1e-8):
                raise AuditError(f"Held-out targeting curve differs from stored scores: {arm}, {point.frac:.0%}")
        print(f"{arm}: independently reproduced held-out cumulative curve from {len(h):,} saved test predictions")

    print("\nPASS: saved statistics match independent aggregate and held-out checks.")
    print("NOTE: A passing audit does NOT prove the individual uplift model is effective; interpret its held-out CIs.")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-real", action="store_true", help="Fail rather than accepting synthetic demonstration data")
    args = ap.parse_args()
    audit(require_real=args.require_real)
