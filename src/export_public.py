"""Export only non-person-level analytical results for public Streamlit hosting.

Run from Codespaces after verifying the real dataset and `python -m src.audit --require-real`.
The complete raw/customer dataset is intentionally NOT exported.
"""
import sqlite3
from pathlib import Path

from .config import DB, ROOT

PUBLIC_DB = ROOT / 'data' / 'dashboard.db'
TABLES = ('meta', 'arm_stats', 'campaign_effects', 'segment_effects',
          'uplift_curves', 'uplift_summary', 'uplift_model_selection',
          'uplift_quintiles')


def export(db=DB, dest=PUBLIC_DB):
    dest = Path(dest)
    with sqlite3.connect(db) as source:
        meta = dict(source.execute('SELECT key, value FROM meta').fetchall())
        if meta.get('source') != 'hillstrom' or meta.get('n_rows') != '64000':
            raise ValueError('Refusing to publish: run the 64,000-row real Hillstrom analysis first.')
        from .audit import audit
        audit(db=db, require_real=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix('.db.tmp')
        if tmp.exists():
            tmp.unlink()
        try:
            with sqlite3.connect(tmp) as public:
                for table in TABLES:
                    ddl = source.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name=?', (table,)).fetchone()
                    if ddl is None:
                        raise ValueError(f'Missing required table: {table}')
                    public.execute(ddl[0])
                    # SQLite-to-SQLite copy avoids adding another data serializer.
                    cols = [col[1] for col in source.execute(f'PRAGMA table_info("{table}")')]
                    marks = ','.join('?' for _ in cols)
                    public.executemany(f'INSERT INTO "{table}" VALUES ({marks})', source.execute(f'SELECT * FROM "{table}"'))
            tmp.replace(dest)
        finally:
            if tmp.exists():
                tmp.unlink()
    print(f'Exported aggregated public dashboard to {dest} (no customer rows or held-out predictions).')
    return dest


if __name__ == '__main__':
    export()
