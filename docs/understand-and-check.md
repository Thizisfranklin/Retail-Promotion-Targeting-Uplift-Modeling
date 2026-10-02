# How this project works — and how to check it

This is a guided explanation to read with the [interactive dashboard](../app.py), not a claim that a model must produce a positive result.

## 1. What are we testing?

Suppose a customer purchases after receiving an email. Would they have purchased anyway? We can't observe *both* outcomes for the same person. The Hillstrom experiment helps by randomly assigning **64,000 past customers** to one of three groups: men's email, women's email or no email. By comparing group averages, we can estimate the **average extra purchases caused by sending each email** under the experimental assumptions.

**Check:** Run `python -m src.audit --require-real`. It verifies your local SQLite `meta` says `hillstrom` and `64000`, and directly recomputes each group's purchase rate, website visit rate and average spend from the `customers` table. Don't run `--synthetic` and then describe those figures as real findings.

## 2. What do the two percentages mean?

From the verified dashboard run, roughly **0.57%** of customers assigned no email purchased, compared with **1.25%** for the men's email and **0.89%** for the women's email. The *difference* is the estimated average incremental effect: about **+0.68 percentage points** and **+0.31 percentage points**, respectively. This is **not** a 0.68% or 0.31% relative gain. The app separately reports website visits and average spend **per assigned person**, not profit.

**Check:** The audit performs the subtraction again using raw saved group outcomes, checks it matches `campaign_effects`, and compares the binary-outcome p-value with an independent chi-square calculation. The app's Wilson and Newcombe confidence intervals are more suitable than simple Wald intervals for these low conversion rates.

## 3. What are the customer charts saying?

The second chart repeats email-versus-control comparisons within groups based on **information that existed before** the emails: purchase history, previous spending, channel, area type and so on. A large dot or non-overlapping-looking lines are **not proof** that two groups truly have different treatment effects. A claim about meaningful differences *between* subgroups would require an explicit interaction test and careful treatment of multiple comparisons. Here they are **exploratory**.

**Check:** Hover over each dot to read its two group sample sizes. Smaller groups generally have noisier results. Don't select a 'winning' subgroup after looking through all six dropdown options.

## 4. What does the machine learning do?

A **T-Learner** trains one model on people randomized to receive an email and another model on people who did not receive one. For a customer, it subtracts the two models' predicted purchase probabilities to estimate *potential* uplift. It does **not** know whether an individual purchase was caused by an email. Separate models are built for the men's and women's emails, each compared with no email.

The project uses **60% training / 20% validation / 20% held-out test** per email-versus-control comparison. Logistic regression and a small gradient-boosted model are compared on the validation set; only the selected model is evaluated on the test set. Only pre-email information is used as model features. This prevents direct outcome leakage, but doesn't guarantee that the uplift estimates are reliable.

**Check:** `src/uplift.py` lists every predictive feature. Neither `conversion`, `visit` nor `spend` is included. Updated pipeline runs also save anonymous held-out predictions to the **local** `uplift_holdout` table, so the audit can independently reconstruct the targeting curve without training again. That table is *not* published with the dashboard.

## 5. Did targeting actually improve the decision?

At the same share of customers emailed, compare the model's ranking against **random targeting** using actual held-out outcomes. At an illustrative 30% budget, the real-data dashboard showed:

| Campaign | Model | Random | Model minus random (95% CI) |
| --- | ---: | ---: | ---: |
| Men's email | 0.91 | 1.97 | -1.06 (-2.96 to +1.00) |
| Women's email | 1.39 | 0.91 | +0.49 (-1.03 to +2.29) |

Values are estimated **extra purchases per 1,000 eligible customers**, not per 1,000 people emailed. Both difference intervals include zero: **we have not established an advantage for the model**. Examining many different marketing budgets after seeing the test results increases the danger of misleading conclusions. Sending to everyone is shown only as a 100%-budget reference, *not* a fair 30%-budget comparison.

**Check:** Look at the **lower part of the targeting chart** (model minus random). At 30%, does its interval cross zero? Inspect the overall held-out AUUC gap too; that measures the area between the two targeting curves. The intervals are approximate and do not account for every source of model-selection uncertainty.

## 6. What went wrong or remains unknown?

This isn't a failed project. It answers the first question using randomized evidence, while the personalized targeting question remains unresolved. Three practical limitations matter:

- **Rare purchases:** Small differences are hard to estimate reliably, particularly for small customer groups and the held-out test set.
- **Experiment age and horizon:** It's a two-week outcome from 2008. We don't know whether the same effects would hold in a modern campaign.
- **No costs:** Without campaign sending costs and product margins, we cannot claim that targeting increases profit or that sending to everyone is financially preferable.

A future study could test a *pre-specified* subgroup hypothesis or run a fresh randomized experiment, rather than adding multiple models until one happens to look favorable.

## The exact audit command

```bash
python -m src.pipeline          # real data; use --csv FILE if download fails
python -m src.audit --require-real
pytest -q
```

The audit fails if stored campaign numbers don't match independent recomputation. On newly generated databases it also checks the held-out targeting curves directly from saved, anonymized scores. **Passing does not prove that uplift targeting is effective, that assumptions are valid for today's customers, or that another sample would produce the same results.** Those are scientific questions, not just software tests.
