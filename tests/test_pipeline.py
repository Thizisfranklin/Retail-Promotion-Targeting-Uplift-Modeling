import sqlite3

import numpy as np
import pandas as pd
import pytest

from src import analysis, uplift
from src.config import CONTROL
from src.data import preprocess, validate
from src.pipeline import run
from src.synthetic import make_synthetic


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    p = tmp_path_factory.mktemp("d") / "t.db"
    run(synthetic=True, db=p)
    return p


def test_validate_rejects_bad_data():
    d = make_synthetic(2000)
    validate(d)
    with pytest.raises(ValueError):
        validate(d.assign(conversion=2))
    with pytest.raises(ValueError):
        validate(d.drop(columns="spend"))


def test_no_leakage_in_features():
    assert not set(uplift.FEATURES) & {"visit", "conversion", "spend", "arm", "segment"}


def test_welch_ci_matches_hand_calc():
    agg = pd.DataFrame({"arm": [CONTROL, "Mens E-Mail"], "n": [1000, 1000], "visit_s": [0, 0], "visit_ss": [0, 0],
                        "conversion_s": [50, 80], "conversion_ss": [50, 80], "spend_s": [0, 0], "spend_ss": [0, 0]})
    r = analysis.effects(agg).query("outcome=='conversion'").iloc[0]
    lo, hi, pv = analysis.binary_diff_ci(80, 1000, 50, 1000)
    assert np.isclose(r["diff"], 0.03)
    assert np.isclose([r["lo"], r["hi"], r["p_value"]], [lo, hi, pv]).all()
    assert lo < 0.03 < hi and pv < 0.05


def test_policy_gain_full_equals_ate_and_random_score_near_random():
    rng = np.random.default_rng(1)
    n = 40000
    t = rng.integers(0, 2, n)
    y = (rng.random(n) < 0.05 + 0.02 * t).astype(int)
    g = uplift.policy_gain(y, t, rng.random(n))
    assert abs(g[-1] - n * (y[t == 1].mean() - y[t == 0].mean())) < 1e-6
    assert abs(uplift.auuc_gap(g, n)) < 1.5  # per 1,000 customers; noise only


def test_tables_and_effects_sane(db):
    with sqlite3.connect(db) as con:
        ce = pd.read_sql("SELECT * FROM campaign_effects WHERE outcome='conversion'", con)
        assert len(ce) == 2 and (ce["diff"] > 0).all() and (ce.p_value < 0.05).all()
        assert (ce.lo < ce["diff"]).all() and (ce["diff"] < ce.hi).all()
        assert pd.read_sql("SELECT COUNT(*) c FROM segment_effects", con).c[0] > 0
        s = pd.read_sql("SELECT * FROM uplift_summary", con)
        assert len(s) == 2 and (s.n_train + s.n_val + s.n_test > 0).all()
        c = pd.read_sql("SELECT * FROM uplift_curves", con)
        assert np.isclose(c.groupby("arm").model.last(), c.groupby("arm").random.last()).all()  # send-to-all == end of curve
        assert pd.read_sql("SELECT value FROM meta WHERE key='source'", con).value[0] == "synthetic"


def test_model_finds_planted_heterogeneity(db):
    with sqlite3.connect(db) as con:
        s = pd.read_sql("SELECT * FROM uplift_summary", con)
    assert (s.test_auuc_gap > 0).all()  # holds for synthetic data with planted effect only


def test_wilson_rare_outcome_stays_in_range():
    assert analysis.wilson(0, 30)[0] == 0.0
    assert np.isclose(analysis.wilson(30, 30)[1], 1.0)
    lo, hi, pv = analysis.binary_diff_ci(0, 30, 0, 30)
    assert lo < 0 < hi and pv == 1.0
    assert 0 <= analysis.wilson(1, 30)[0] < analysis.wilson(1, 30)[1] <= 1


def test_mixed_case_original_csv_loads(tmp_path):
    from src.data import load_raw
    p = tmp_path / "original.csv"
    d = make_synthetic(250, seed=7)
    d.columns = [s.title() for s in d.columns]
    d.to_csv(p, index=False)
    got = load_raw(p)
    assert set(got.columns) == set(make_synthetic(2).columns)
    assert len(got) == 250
    assert validate(got)["check"].isin(["three arms", "binary outcomes"]).sum() == 2


def test_failed_pipeline_preserves_existing_database(tmp_path, monkeypatch):
    from src import pipeline
    p = tmp_path / "data" / "test.db"
    p.parent.mkdir()
    p.write_bytes(b"GOOD PRIOR RESULT")
    def fail(_):
        raise RuntimeError("simulated model failure")
    monkeypatch.setattr(pipeline, "run_uplift", fail)
    with pytest.raises(RuntimeError, match="simulated model failure"):
        pipeline.run(synthetic=True, db=p)
    assert p.read_bytes() == b"GOOD PRIOR RESULT"
    assert not list(p.parent.glob(".retail-build-*"))


def test_download_skips_html_and_uses_valid_fallback(tmp_path, monkeypatch):
    import io
    import gzip
    from src import data
    src = make_synthetic(90).to_csv(index=False).encode()
    calls = []
    class Response(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            self.close()
    def fake_urlopen(url, timeout=30):
        calls.append(url)
        return Response(b"<html>Access blocked</html>" if len(calls) == 1 else gzip.compress(src))
    monkeypatch.setattr(data.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(data, "URLS", ["https://bad.example/csv", "https://good.example/data.gz"])
    dest = tmp_path / "data.csv"
    assert data.download(dest) == dest
    assert len(calls) == 2
    assert len(data.load_raw(dest)) == 90
