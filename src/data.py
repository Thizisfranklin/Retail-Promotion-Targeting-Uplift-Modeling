"""Ingestion, validation, preprocessing and SQLite loading."""
import gzip
import io
import sqlite3
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import ARMS, CONTROL, DB, RAW, URLS

REQUIRED = ["recency", "history_segment", "history", "mens", "womens", "zip_code", "newbie",
            "channel", "segment", "visit", "conversion", "spend"]


def download(dest: Path = RAW) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    errs = []
    for u in URLS:
        try:
            with urllib.request.urlopen(u, timeout=30) as response:
                raw = response.read()
            candidate = gzip.decompress(raw) if u.endswith(".gz") else raw
            # Blocked hosts sometimes return an HTML error page with HTTP 200.
            header = pd.read_csv(io.BytesIO(candidate), nrows=0)
            if not set(REQUIRED).issubset({c.strip().lower() for c in header.columns}):
                raise ValueError("Download did not contain the expected Hillstrom CSV columns")
            dest.write_bytes(candidate)
            return dest
        except Exception as e:  # try next mirror
            errs.append(f"{u}: {e}")
    raise RuntimeError("Could not download Hillstrom data. Save the CSV manually to "
                       f"{dest} (see README). Errors:\n" + "\n".join(errs))


def load_raw(path=None) -> pd.DataFrame:
    """Read either original mixed-case CSV or the lower-case dataset mirror.

    Verify content before processing: blocked downloads sometimes save an HTML
    error page with a .csv extension.
    """
    path = Path(path or RAW)
    if not path.exists():
        download(path)
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeError) as exc:
        raise ValueError(f"Could not read Hillstrom CSV at {path}: {exc}") from exc
    df.columns = df.columns.str.strip().str.lower()
    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names after case normalization")
    return df


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Return a table of checks; raise on hard failures."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    checks = []
    def add(name, ok, detail, hard=True):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        if hard and not ok:
            raise ValueError(f"Validation failed: {name} - {detail}")
    add("no nulls", df[REQUIRED].isna().sum().sum() == 0, "null count in required columns")
    add("three arms", set(df.segment) == set(ARMS) | {CONTROL}, str(sorted(df.segment.unique())))
    add("binary outcomes", df[["visit", "conversion", "mens", "womens", "newbie"]].isin([0, 1]).all().all(), "0/1 columns")
    add("numeric features finite", np.isfinite(df[["recency", "history", "spend"]].to_numpy(dtype=float)).all(),
        "recency, history and spend must be finite")
    add("recency 1-12", df.recency.between(1, 12).all(), "months since last purchase must be 1-12")
    add("history >= 0", (df.history >= 0).all(), "historical spend must be nonnegative")
    add("spend >= 0", (df.spend >= 0).all(), f"min spend {df.spend.min():.2f}")
    # Randomized assignment does not guarantee identical realized group sizes.
    # A significant chi-square result can occur by chance and is diagnostic,
    # not a reason to reject otherwise valid randomized observations.
    p = stats.chisquare(df.segment.value_counts().values).pvalue
    add("arm sizes ~ equal thirds", p > 0.001, f"chi-square p={p:.3f}", hard=False)
    bad = int(((df.conversion == 0) & (df.spend > 0)).sum())
    add("spend>0 only when converted", bad == 0, f"{bad} rows violate", hard=False)
    add("conversion implies visit", bool((df.visit >= df.conversion).all()), "visit >= conversion", hard=False)
    return pd.DataFrame(checks)


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["arm"] = d["segment"]
    d["recency_bucket"] = pd.cut(d.recency, [0, 3, 6, 9, 12],
                                 labels=["1-3 mo", "4-6 mo", "7-9 mo", "10-12 mo"]).astype(str)
    d["customer_type"] = np.where(d.newbie == 1, "New (<12 mo)", "Existing")
    d["past_purchases"] = np.select(
        [(d.mens == 1) & (d.womens == 1), d.mens == 1, d.womens == 1],
        ["Men's & women's", "Men's only", "Women's only"], "Neither")
    d.insert(0, "customer_id", np.arange(len(d)))
    return d


def balance_check(d: pd.DataFrame) -> pd.DataFrame:
    """Standardized mean differences of pre-treatment covariates vs control (randomization check)."""
    rows, c = [], d[d.arm == CONTROL]
    for arm in ARMS:
        t = d[d.arm == arm]
        for f in ["recency", "history", "mens", "womens", "newbie"]:
            sd = np.sqrt((t[f].var() + c[f].var()) / 2)
            rows.append({"arm": arm, "feature": f, "smd": (t[f].mean() - c[f].mean()) / sd})
    return pd.DataFrame(rows)


def build_db(df: pd.DataFrame, source: str, checks: pd.DataFrame, db: Path = DB) -> None:
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    d = preprocess(df)
    with sqlite3.connect(db) as con:
        d.to_sql("customers", con, if_exists="replace", index=False)
        checks.to_sql("validation_checks", con, if_exists="replace", index=False)
        balance_check(d).to_sql("balance_checks", con, if_exists="replace", index=False)
        pd.DataFrame({"key": ["source", "n_rows"], "value": [source, str(len(d))]}).to_sql(
            "meta", con, if_exists="replace", index=False)
        con.execute("CREATE INDEX IF NOT EXISTS ix_arm ON customers(arm)")
