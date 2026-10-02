"""python -m src.pipeline [--csv PATH] [--synthetic]"""
import argparse
import os
import tempfile
from pathlib import Path

from .analysis import run_analysis
from .config import DB
from .data import build_db, load_raw, validate
from .synthetic import make_synthetic
from .uplift import run_uplift


def run(csv=None, synthetic=False, db=DB):
    df, source = (make_synthetic(), "synthetic") if synthetic else (load_raw(csv), "hillstrom")
    checks = validate(df)
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    # Work on a fresh temporary database. An interrupted or failed model run
    # must never leave a half-updated dashboard or overwrite a good run.
    fd, temp_path = tempfile.mkstemp(prefix=".retail-build-", suffix=".db", dir=db.parent)
    os.close(fd)
    try:
        build_db(df, source, checks, temp_path)
        run_analysis(temp_path)
        run_uplift(temp_path)
        os.replace(temp_path, db)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return source


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="path to Hillstrom CSV (downloaded automatically if omitted)")
    ap.add_argument("--synthetic", action="store_true", help="schema-identical fake data (demo/testing only)")
    a = ap.parse_args()
    print(f"Pipeline complete (source={run(a.csv, a.synthetic)}) -> {DB}")
