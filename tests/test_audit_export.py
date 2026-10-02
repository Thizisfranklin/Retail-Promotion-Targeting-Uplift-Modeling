import sqlite3

import pytest

from src.audit import AuditError, audit
from src.export_public import TABLES, export
from src.synthetic import make_synthetic
from src.data import validate, build_db
from src.analysis import run_analysis
from src.uplift import run_uplift


def test_audit_checks_aggregate_and_holdout(tmp_path):
    db = tmp_path / 'test.db'
    d = make_synthetic(n=3000, seed=4)
    build_db(d, 'synthetic', validate(d), db)
    run_analysis(db)
    run_uplift(db)
    assert audit(db) is True
    with pytest.raises((AuditError, ValueError)):
        export(db, tmp_path / 'public.db')
    with sqlite3.connect(db) as con:
        con.execute("UPDATE campaign_effects SET diff=2 WHERE arm='Mens E-Mail' AND outcome='conversion'")
    with pytest.raises(AuditError, match='Stored treatment effect mismatch'):
        audit(db)
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT arm, AVG(conversion) FROM customers GROUP BY arm").fetchall()
        rates = dict(rows)
        real_diff = rates['Mens E-Mail'] - rates['No E-Mail']
        con.execute("UPDATE campaign_effects SET diff=?, hi=hi+0.05 WHERE arm='Mens E-Mail' AND outcome='conversion'", (real_diff,))
    with pytest.raises(AuditError, match='Treatment-effect confidence interval mismatch'):
        audit(db)


def test_export_only_aggregates(tmp_path, monkeypatch):
    db, public = tmp_path / 'source.db', tmp_path / 'dashboard.db'
    d = make_synthetic(n=3000, seed=5)
    build_db(d, 'hillstrom', validate(d), db)
    run_analysis(db)
    run_uplift(db)
    with pytest.raises(ValueError, match='64,000'):
        export(db, public)
    # Exercise only the table-copy mechanics with a mocked verification hook.
    # This deliberately spoofed 3,000-row fixture must never be published.
    with sqlite3.connect(db) as con:
        con.execute("UPDATE meta SET value='64000' WHERE key='n_rows'")
    monkeypatch.setattr('src.audit.audit', lambda **kwargs: True)
    export(db, public)
    with sqlite3.connect(public) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == set(TABLES)
    assert 'customers' not in tables and 'uplift_holdout' not in tables


def test_public_export_covers_every_dashboard_table():
    import re
    from pathlib import Path
    app = (Path(__file__).resolve().parents[1] / 'app.py').read_text()
    reads = set(re.findall(r'load\("([a-z_]+)"\)', app))
    assert reads, 'Static dashboard reads should be discoverable'
    assert reads <= set(TABLES), f'Dashboard requires missing public tables: {reads - set(TABLES)}'
