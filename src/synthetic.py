"""Schema-identical SYNTHETIC data, for tests and offline demos only (never real results)."""
import numpy as np
import pandas as pd


def make_synthetic(n: int = 30000, seed: int = 0) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    recency = r.integers(1, 13, n)
    history = np.round(r.gamma(2, 150, n) + 20, 2)
    mens, womens, newbie = (r.integers(0, 2, n) for _ in range(3))
    zip_code = r.choice(["Urban", "Surburban", "Rural"], n, p=[.4, .45, .15])
    channel = r.choice(["Phone", "Web", "Multichannel"], n)
    segment = r.choice(["Mens E-Mail", "Womens E-Mail", "No E-Mail"], n)
    z = -3.4 + 0.04 * (12 - recency) + 0.0004 * history
    z = z + (segment == "Mens E-Mail") * (0.1 + 0.6 * mens) + (segment == "Womens E-Mail") * (0.1 + 0.6 * womens)
    conv = (r.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    visit = np.maximum(conv, (r.random(n) < 0.1 + 0.05 * (segment != "No E-Mail")).astype(int))
    spend = np.round(conv * r.gamma(3, 30, n), 2)
    bins = [0, 100, 200, 350, 500, 750, 1000, 1e9]
    labels = ["1) $0 - $100", "2) $100 - $200", "3) $200 - $350", "4) $350 - $500",
              "5) $500 - $750", "6) $750 - $1,000", "7) $1,000 +"]
    return pd.DataFrame({
        "recency": recency, "history_segment": pd.cut(history, bins, labels=labels).astype(str),
        "history": history, "mens": mens, "womens": womens, "zip_code": zip_code, "newbie": newbie,
        "channel": channel, "segment": segment, "visit": visit, "conversion": conv, "spend": spend})
