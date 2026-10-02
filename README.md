# Retail Marketing Intelligence — Customer Targeting & Incremental Impact

**Status: real-data analysis completed in GitHub Codespaces and reviewed from the dashboard screenshots. The repository does not include the downloaded CSV or generated SQLite database; reproduce the results locally before interpreting new runs.** This repository investigates a narrower question than purchase propensity: *Who should receive an email because it changes their purchase probability, rather than because they would have purchased anyway?*

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
| Business dashboard | `app.py` | Data-driven executive summary and three interactive Plotly visualizations (targeting figure includes a same-budget gap/uncertainty panel) |
| Interpretation helpers | `src/presentation.py` | Tested, data-dependent plain-English descriptions of confidence intervals |
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

The GitHub Actions workflow runs these tests plus a separate synthetic pipeline/table check on pushes and pull requests. **Passing synthetic tests does not verify conclusions on real Hillstrom data.** A real-data run was subsequently completed by the project owner in GitHub Codespaces. The database source was independently checked in that environment and returned `('source', 'hillstrom')`, `('n_rows', '64000')`. The figures below were transcribed from the resulting dashboard screenshots; the generated database is not committed, so rerun the pipeline to reproduce exact machine-readable estimates in a new environment.

**Codespaces reproducibility check:**

```bash
python -m src.pipeline
python -c 'import sqlite3; con=sqlite3.connect("data/retail.db"); print(con.execute("SELECT * FROM meta").fetchall()); print(con.execute("SELECT arm, outcome, diff, lo, hi FROM campaign_effects WHERE outcome="conversion"").fetchall()); print(con.execute("SELECT arm, test_auuc_gap, auuc_lo, auuc_hi FROM uplift_summary").fetchall())'
streamlit run app.py --server.address 0.0.0.0
```

Check the `meta` source is `hillstrom` and the row count is `64000` before documenting real results. Synthetic smoke tests remain intentionally separate.

## Findings: historical randomized email experiment (real data)

The project owner executed the pipeline on the real 64,000-customer Hillstrom dataset in GitHub Codespaces, checked the SQLite `meta` table (`source=hillstrom`, `n_rows=64000`) and shared dashboard screenshots. **Values here are rounded exactly as displayed in that dashboard**, not claims that the dataset was independently re-run within this repository. Source experiment: **2008**, with outcomes observed for **two weeks**.

### 1. Did either campaign affect customer behavior?

The primary metric is **conversion** (whether an assigned customer made a purchase), reported as *percentage-point differences* relative to the independently randomized no-email group. The following intervals are the project's **unadjusted 95% Newcombe intervals** for differences in conversion rates:

| Campaign vs. no email | Conversion-rate increase | Unadjusted 95% CI | Interpretation |
| --- | ---: | ---: | --- |
| Men's merchandise email | **+0.68 percentage points** | **+0.50 to +0.86 pp** | Positive experimental average effect on conversion |
| Women's merchandise email | **+0.31 percentage points** | **+0.15 to +0.47 pp** | Positive experimental average effect on conversion |

The dashboard's approximate group conversion rates were **0.57%** (no email), **1.25%** (men's email) and **0.89%** (women's email). These rounded group rates are descriptive; the reported differences above come from the dashboard's underlying calculations. The two emails were each compared separately with no email. **Do not conclude that the men's email would work better than the women's email for a given individual** from these two independent-looking comparisons: both share a control group, and that is a different research question.

Secondary outcomes also increased relative to the no-email control in the displayed estimates:

| Campaign | Website visits: estimated increase (95% CI) | Average spend per assigned customer: increase (95% CI) |
| --- | ---: | ---: |
| Men's email | +7.66 pp (+7.00 to +8.32) | +$0.77 (+$0.49 to +$1.05) |
| Women's email | +4.52 pp (+3.89 to +5.16) | +$0.42 (+$0.17 to +$0.68) |

**Average spend is not profit**. Email delivery costs, customer contact costs, product margins and long-term outcomes are unavailable. Report these as historical experimental effects, not present-day projections.

### 2. Do some customer segments respond differently?

Exploratory charts suggest variation by previous purchases, spending history, marketing channel and other pre-email characteristics. **They do not establish true differences in treatment effects between segments.** Individual subgroup intervals, small sample sizes, multiple exploratory comparisons and overlapping estimates can make apparently different points misleading. Confirm proposed segment differences with a direct interaction test and an independent randomized experiment before using them as business targeting rules.

### 3. Did model-based targeting outperform random targeting?

The model was selected using validation data, then evaluated once on a **held-out 20% pairwise test sample** for each campaign. Incremental purchases below are estimated from randomized outcomes, normalized **per 1,000 eligible customers**, not based solely on predicted probabilities. At an *illustrative* budget of emailing 30% of eligible customers:

| Campaign | Model targeting | Random targeting (same budget) | Model minus random (pointwise 95% CI) |
| --- | ---: | ---: | ---: |
| Men's email | 0.91 | 1.97 | **-1.06** (-2.96 to +1.00) |
| Women's email | 1.39 | 0.91 | **+0.49** (-1.03 to +2.29) |

Both chosen-budget confidence intervals include zero. The *overall* area between the model and random curves (AUUC gap) also remains inconclusive on the held-out set:

| Campaign | Held-out AUUC gap | Illustrative 95% bootstrap CI |
| --- | ---: | ---: |
| Men's email | -0.52 | -1.73 to +0.63 |
| Women's email | +0.77 | -0.33 to +2.05 |

**Main finding:** randomized evidence supports an average increase in purchases from *sending these emails*, but it does **not** establish that this T-Learner improves targeting relative to random selection. This is a valid, potentially useful negative/inconclusive machine-learning result. Do not present the 30% budget as a test-set-optimized choice; it was chosen as an illustration for interpreting the curves.

**Budget comparison matters:** the "send to everyone" diamond shows what happens when **100%** are contacted, not an equal-cost alternative to contacting the top 30%. The comparison for ranking quality is the model versus random targeting **at the same share emailed**. The dashboard now displays this difference and its confidence interval directly below the cumulative impact chart. No send costs or ROI are estimated.

## Limitations

- A single **2008 experiment** with a two-week outcome window; it is not current customer behavior or proof of deployment value today.
- Conversion is rare, so personalized targeting results can be highly variable. Positive validation performance does not imply a reliable held-out benefit.
- Segment comparisons, two campaigns, and multiple targeting budgets introduce multiplicity and selection risk. No multiple-comparison adjustments or formal segment-interaction tests are included; do not cherry-pick a favorable budget from the test set.
- Bootstrap bands are **pointwise**, conditional on the selected model and one held-out experiment; they do not cover model-selection variability, multiple budget searches or end-to-end deployment uncertainty.
- We do **not** model campaign-send cost, profitability or real-time policy deployment. A fresh randomized rollout would be needed before business use.
