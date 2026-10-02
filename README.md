# Retail Marketing Intelligence — Customer Targeting & Incremental Impact

**Status: working MVP on synthetic data. Real Hillstrom results and the real-data Streamlit UI remain unverified until run with the actual dataset.** This repository investigates a narrower question than purchase propensity: *Who should receive an email because it changes their purchase probability, rather than because they would have purchased anyway?*

## Business problem and dataset

This is an analysis of Kevin Hillstrom's [2008 MineThatData email experiment](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html). Approximately 64,000 past customers were randomized to a men's merchandise email, women's merchandise email or no-email control. The following two weeks provide three outcomes: `visit`, `conversion` and `spend`. Historical predictors include past spending, recency, previous men's/women's purchases, zip-code class, customer tenure and shopping channel. **Primary outcome: conversion.** The interventions are emails—not necessarily discounts. There is no item-level transaction ledger or known email-send cost.

**Why randomized assignment matters:** observed conversion rates alone cannot identify whom emails persuaded. The no-email group provides a basis for average incremental-effect estimates, subject to standard experiment assumptions. Personalized uplift predictions are estimates; they do not reveal any particular individual's causal effect.

Source files are downloaded into `data/raw/`, which is **not committed**. Cite the original author if you reuse the data. The project's source code may be redistributed, but the original experiment does not appear to include an explicit data redistribution license.

## Quick start

Requirements: Python 3.11+ and network access for initial installation and dataset download.

**Windows PowerShell**

```powershell
git clone https://github.com/Thizisfranklin/Retail-Promotion-Targeting-Uplift-Modeling.git
cd Retail-Promotion-Targeting-Uplift-Modeling
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m src.pipeline
streamlit run app.py
```

**macOS / Linux**

```bash
git clone https://github.com/Thizisfranklin/Retail-Promotion-Targeting-Uplift-Modeling.git
cd Retail-Promotion-Targeting-Uplift-Modeling
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.pipeline
streamlit run app.py
```

Open the local dashboard URL printed by Streamlit (typically http://localhost:8501). `python -m src.pipeline` tries the official MineThatData CSV and the scikit-uplift dataset mirror. If network access prevents download, manually download Hillstrom's CSV using the source link and run:

```bash
python -m src.pipeline --csv path/to/downloaded/hillstrom.csv
```

A CSV with uppercase column headers (as in some copies of the original) is supported. The loader checks that downloaded content is CSV and rejects HTML error pages. The pipeline builds into a temporary database and replaces the dashboard DB **only after all steps succeed**.

### Local offline demo (explicitly fake data)

```bash
python -m src.pipeline --synthetic
streamlit run app.py
pytest -q
```

**Synthetic figures are not research results.** The dashboard prominently labels them, and the cached views refresh when the database changes. Rerun the real pipeline before reporting findings. Never commit synthetic numbers as real findings.

## Implementation

| Component | File | Purpose |
|---|---|---|
| Loading, validation and SQLite | `src/data.py` | Validate source fields, group assignment, outcomes and pretreatment features; build relational analysis store |
| Reproducible orchestration | `src/pipeline.py` | Ingest → validation → SQL analysis → modeling → atomically publish completed results |
| Statistical estimates | `src/analysis.py` | SQL aggregates and control-group comparisons for campaigns and pretreatment segments |
| Modeling and evaluation | `src/uplift.py` | Pairwise T-Learners, validation selection, held-out policy-value curves with uncertainty |
| Business dashboard | `app.py` | Three interactive Plotly visualizations in a minimal Streamlit UI |
| Testing | `tests/` | Pipeline/unit tests plus Streamlit widget smoke tests when installed |
| Continuous integration | `.github/workflows/verify.yml` | Install and test the synthetic pipeline and dashboard on pushes/PRs |

### Three business questions

1. **Do either of the emails increase purchases?** Group conversion rates with 95% Wilson score intervals, and email-minus-control differences with 95% Newcombe intervals. Unadjusted pooled-score p-values for binary outcomes are exploratory. Visit uses the same approach; spend uses Welch t intervals.
2. **How do estimates differ across customer segments?** Pre-email segment definitions only; compare estimated effects and sample sizes. Segment confidence intervals are **exploratory and unadjusted for multiple comparisons**. Apparent subgroup differences should not be assumed to be meaningful treatment-effect heterogeneity without a direct interaction test and preferably replication.
3. **Can a model prioritize customers more effectively than random selection?** Compare estimated incremental purchases per 1,000 eligible customers at multiple targeting budgets using the held-out experiment. Model-based targeting is compared with the expected random-targeting line and the send-to-all endpoint. This **does not** account for sending costs or optimize net profits.

### Modeling and evaluation details

- For **each email type separately**, compare that email with the no-email arm. A customer in the other email arm is not part of that pairwise model. Pairwise splits are separate, meaning the control pool can be reused across analyses; therefore **do not** treat cross-campaign estimates as independent.
- Split 60% training / 20% validation / 20% held-out testing, stratified by treatment and observed conversion. Do not use the test split for choosing a model or a targeting budget.
- Predictors are pre-email `recency`, `history`, `mens`, `womens`, `newbie`, `zip_code` and `channel`. `visit`, `conversion`, `spend`, and experimental assignment are excluded from predictive features.
- For each treatment, fit a separate treated-outcome and control-outcome estimator (T-Learner). Choose between simple logistic regression and small gradient boosting **on validation AUUC**, then report test-set outcomes once. Validation selection may itself be noisy at low conversion rates.
- Ranking customers by model-predicted uplift is evaluated against the **observed randomized outcomes** in the held-out sample. Policy value at the top *k*% is estimated as *k*-group size times (treated conversion rate − control conversion rate), rescaled to per 1,000 eligible customers. This uses realized randomization and assumes treatment assignment is independent of pre-email predictors. The curve starts at zero; sending to everyone uses the whole-sample difference.
- Resample the held-out evaluation rows with replacement to calculate illustrative 95% bootstrap intervals (300 replicates). Bands are pointwise, not simultaneous; they omit uncertainty from model selection/training and should be interpreted cautiously. Small top-ranked groups can be especially noisy.

## Reproducibility and verification

Use `pytest -q` to check validation, original-case CSV handling, source download fallback, interval calculations, features/leakage guard, policy math, end-to-end synthetic analysis, dashboard smoke tests (when Streamlit is installed) and failure-safe DB replacement.

The GitHub Actions workflow runs these tests plus a separate synthetic pipeline/table check on pushes and pull requests. **Passing synthetic tests does not verify conclusions on real Hillstrom data.** To complete the real-data milestone, run `python -m src.pipeline`, inspect the source field in `meta` (it must be `hillstrom`), read the two real-data treatment estimates and CI values, inspect segment sample sizes and held-out targeting curves, and confirm the dashboard controls and charts in a browser. Only then add real observed results and screenshots here.

## Findings

**Pending real-data execution.** No experiment result or model advantage is claimed from synthetic demo data. Record the actual conversion effects and 95% intervals for each campaign and the held-out AUUC gap before drawing conclusions.

## Limitations

- A single **2008 experiment** with a two-week outcome window; it is not current customer behavior or proof of deployment value today.
- Conversion is rare, so personalized targeting results can be highly variable. Positive validation performance does not imply a reliable held-out benefit.
- Segment comparisons, two campaigns, and multiple targeting budgets introduce multiplicity and selection risk; do not cherry-pick a favorable budget from the test set.
- Bootstrap bands are conditional on the selected model and one held-out experiment; they do not measure end-to-end deployment uncertainty.
- We do **not** model campaign-send cost, profitability or real-time policy deployment. A fresh randomized rollout would be needed before business use.
