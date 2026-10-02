"""T-Learner uplift model with train/validation/test split and randomized-data policy evaluation.

Policy value is estimated on the held-out test set as: (customers targeted) x (treated mean - control mean)
within the targeted group. Because treatment was randomized, this is an unbiased estimate of the
incremental conversions from emailing that group. Predicted uplift is never used as an outcome.
"""
import sqlite3

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import ARMS, CAT_FEATURES, CONTROL, DB, NUM_FEATURES, SEED

FEATURES = NUM_FEATURES + CAT_FEATURES
FRACS = np.linspace(0, 1, 21)
_trap = getattr(np, "trapezoid", None) or np.trapz


def _logreg():
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
                             ("n", StandardScaler(), NUM_FEATURES)])
    return make_pipeline(pre, LogisticRegression(C=0.5, max_iter=1000))


def _hgb():
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES), ("n", "passthrough", NUM_FEATURES)])
    return make_pipeline(pre, HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=120,
                                                             l2_regularization=1.0, random_state=SEED))


CANDIDATES = {"Logistic regression": _logreg, "Gradient boosting": _hgb}


class TLearner:
    """Two outcome models (treated / control); uplift = P(buy | email) - P(buy | no email)."""
    def __init__(self, make):
        self.make = make

    def fit(self, X, y, t):
        self.m1 = self.make().fit(X[t == 1], y[t == 1])
        self.m0 = self.make().fit(X[t == 0], y[t == 0])
        return self

    def predict(self, X):
        return self.m1.predict_proba(X)[:, 1] - self.m0.predict_proba(X)[:, 1]


def policy_gain(y, t, score, fracs=FRACS):
    """Estimated incremental conversions (in this sample) from emailing the top-`frac` by score."""
    o = np.argsort(-score, kind="stable")
    y, t = y[o], t[o]
    c1, n1, c0, n0 = np.cumsum(y * t), np.cumsum(t), np.cumsum(y * (1 - t)), np.cumsum(1 - t)
    out = []
    for f in fracs:
        m = int(round(f * len(y)))
        if m == 0:
            out.append(0.0)
        elif n1[m - 1] > 0 and n0[m - 1] > 0:
            out.append(m * (c1[m - 1] / n1[m - 1] - c0[m - 1] / n0[m - 1]))
        else:
            out.append(np.nan)
    return np.array(out)


def auuc_gap(gain, n):
    """Area between model curve and random-targeting line, in incremental conversions per 1,000 customers."""
    rand = FRACS * gain[-1]
    return float(_trap((gain - rand) / n * 1000, FRACS))


def evaluate(y, t, score, B=300, seed=SEED):
    n, rng = len(y), np.random.default_rng(seed)
    g = policy_gain(y, t, score)
    boots = []
    for _ in range(B):
        i = rng.integers(0, n, n)
        boots.append(policy_gain(y[i], t[i], score[i]))
    boots = np.array(boots)
    rand_b = FRACS[None, :] * boots[:, -1:]
    gap_b = boots - rand_b
    q = lambda a: np.nanpercentile(a, [2.5, 97.5], axis=0)
    auuc_b = np.array([auuc_gap(b, n) for b in boots])
    curve = pd.DataFrame({"frac": FRACS, "model": g / n * 1000, "random": FRACS * g[-1] / n * 1000,
                          "model_lo": q(boots)[0] / n * 1000, "model_hi": q(boots)[1] / n * 1000,
                          "gap": (g - FRACS * g[-1]) / n * 1000,
                          "gap_lo": q(gap_b)[0] / n * 1000, "gap_hi": q(gap_b)[1] / n * 1000})
    return curve, auuc_gap(g, n), tuple(np.nanpercentile(auuc_b, [2.5, 97.5]))


def run_uplift(db=DB):
    with sqlite3.connect(db) as con:
        df = pd.read_sql("SELECT arm, conversion, " + ", ".join(FEATURES) + " FROM customers", con)
        curves, summ, groups, sel, holdout = [], [], [], [], []
        for arm in ARMS:
            d = df[df.arm.isin([arm, CONTROL])].reset_index(drop=True)
            t, y, X = (d.arm == arm).astype(int).values, d.conversion.values, d[FEATURES]
            strat = t.astype(str) + y.astype(str)
            i_tr, i_rest = train_test_split(np.arange(len(d)), test_size=0.4, stratify=strat, random_state=SEED)
            i_va, i_te = train_test_split(i_rest, test_size=0.5, stratify=strat[i_rest], random_state=SEED)
            fitted, val = {}, {}
            for name, mk in CANDIDATES.items():  # fit on train; choose on validation only
                fitted[name] = TLearner(mk).fit(X.iloc[i_tr], y[i_tr], t[i_tr])
                s = fitted[name].predict(X.iloc[i_va])
                val[name] = auuc_gap(policy_gain(y[i_va], t[i_va], s), len(i_va))
            best = max(val, key=val.get)
            s_te = fitted[best].predict(X.iloc[i_te])
            yt, tt = y[i_te], t[i_te]
            # Save anonymized held-out outcomes/scores locally for an independent audit.
            # Do not export this row-level table to the public dashboard.
            order = np.argsort(-s_te, kind="stable")
            holdout.append(pd.DataFrame({"arm": arm, "rank": np.arange(len(order)),
                                        "score": s_te[order], "treatment": tt[order],
                                        "conversion": yt[order]}))
            curve, auuc, ci = evaluate(yt, tt, s_te)
            curve.insert(0, "arm", arm)
            curves.append(curve)
            ate = yt[tt == 1].mean() - yt[tt == 0].mean()
            summ.append({"arm": arm, "selected_model": best, "n_train": len(i_tr), "n_val": len(i_va), "n_test": len(i_te),
                         "test_ate": ate, "test_auuc_gap": auuc, "auuc_lo": ci[0], "auuc_hi": ci[1],
                         "auuc_ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0)})
            sel += [{"arm": arm, "model": k, "val_auuc_gap": v, "selected": k == best} for k, v in val.items()]
            q = pd.qcut(pd.Series(s_te).rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5])
            for k in range(1, 6):
                m = (q == k).values
                a, b = yt[m & (tt == 1)], yt[m & (tt == 0)]
                se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
                groups.append({"arm": arm, "group": f"Top {k*20-19}-{k*20}%" if k > 1 else "Top 20%", "n": int(m.sum()),
                               "pred_uplift": s_te[m].mean(), "obs_uplift": a.mean() - b.mean(), "se": se})
        pd.concat(holdout, ignore_index=True).to_sql("uplift_holdout", con, if_exists="replace", index=False)
        pd.concat(curves).to_sql("uplift_curves", con, if_exists="replace", index=False)
        pd.DataFrame(summ).to_sql("uplift_summary", con, if_exists="replace", index=False)
        pd.DataFrame(sel).to_sql("uplift_model_selection", con, if_exists="replace", index=False)
        pd.DataFrame(groups).to_sql("uplift_quintiles", con, if_exists="replace", index=False)
