# Pulsemetrics


> A product analytics case study in competitive pricing, promotional strategy, and experimentation design for restaurant operators on delivery platforms.

[![Status](https://img.shields.io/badge/status-active%20development-blue)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Context & Motivation

This project started from a simple observation: two similar restaurants, same neighborhood, different prices on the app — and the cheaper one wasn't necessarily better. That raised a question worth digging into.

After spending time on Uber Eats and DoorDash comparing restaurants, a few patterns stood out. Some restaurants ran promotions at certain times of day. Some had better ratings but higher prices. And it wasn't always obvious whether a promotion was actually enough to change an ordering decision — especially when a customer already had a restaurant they trusted.

That's the problem this project tries to answer with data: does pricing on delivery platforms actually drive ordering decisions, and can a well-timed promotion meaningfully change a restaurant's competitive position?

---

## The Business Problem

Restaurant owners on food delivery platforms are flying blind on pricing.

They know their own menu prices. They don't know how those prices compare to the twelve similar restaurants within two miles. They don't know whether a 15% promotion will move them from the 70th to the 40th percentile on customer cost — or whether it'll just erode margin without improving their competitive position at all.

And it's not just about price. A customer who already trusts a restaurant — based on ratings, review volume, or past experience — may not be swayed by a competitor's promotion at all. Understanding when promotions work, and when reputation holds customers regardless, is part of the same problem.

This project builds a system to answer that. Not with intuition. With data.

The core questions driving it:

- Where does a restaurant actually sit in its local competitive landscape?
- Are there time-of-day or day-of-week patterns in how customers experience pricing?
- Does a restaurant's reputation — ratings, review volume — moderate how effective competitor promotions are?
- If a restaurant runs a promotion, which discount level is worth it — and how would you know if it worked?

---

## Why This Is a Product Problem, Not Just an Analytics Problem

Pricing tools for restaurants usually stop at benchmarking — here's the average, here's where you rank. That's useful, but it doesn't help an operator make a decision.

This project treats pricing as a **product decision loop**:

```
Understand your position → Identify an opportunity → Simulate your options
        ↑                                                        │
        │                                                        ▼
Measure what actually happened  ←────────  Design the experiment first
```

The experimentation layer is what separates this from a reporting dashboard. Before a restaurant launches a promotion, this system asks: what would success look like, how long would you need to run it, and how would you separate the promotion's effect from a random busy weekend?

---

## What the System Does

### 1. Competitive Positioning
Groups restaurants by cuisine type and proximity, then calculates where each restaurant sits in that local market — average competitor pricing, percentile rankings, and a competitive price index.

The output isn't just a number. It's an answer to: *are we expensive, and compared to who?*

### 2. Reputation as a Variable
Ratings and review volume are included as features alongside price — not as decorative context, but as analytical variables.

The underlying question: does a higher-rated restaurant hold onto customers even when a competitor runs a promotion? Is reputation a buffer against competitive pricing pressure, or does price still win?

This doesn't require building a full review analysis pipeline. Average rating and review volume are treated as numeric signals that may moderate how sensitive customers are to promotions. That relationship — noisy, not deterministic — is built into both the analysis and the synthetic data.

### 3. Statistical Pricing Analysis
Tests whether observed pricing patterns are real or noise.

Example hypothesis: *do customers face higher total costs during nighttime delivery windows?* The analysis uses hypothesis testing, confidence intervals, and regression to evaluate whether that pattern holds after controlling for restaurant type and local market conditions.

Not every hypothesis will confirm. That's intentional.

### 4. Promotional Scenario Modeling
Simulates the downstream effects of different discount levels (10%, 15%, 20%) on:

- Customer-facing total cost
- Competitive rank within the local market
- Estimated margin impact

The goal: *which discount level, if any, actually moves a restaurant into a more competitive position — and at what cost?*

### 5. Experimentation Framework
Outlines how a restaurant would actually measure whether a promotion worked.

This is where context matters most. A promotion running on a Friday night during a local event means something different than the same promotion on a Tuesday afternoon. External factors — weekends, holidays, local events, seasonal demand — can make a promotion look more effective than it is, or mask its true impact entirely.

The framework addresses this directly:

- Pre/post comparison design
- A/B testing considerations and sample size requirements
- Power calculations — how long does a test need to run to detect a real effect?
- Incrementality framing — separating promotion lift from background noise
- How to account for time-of-day and event-driven demand when interpreting results

The goal is to design the measurement before the promotion launches, not after.

---

## A Note on the Data

This project uses synthetic data — and that choice is made carefully.

Synthetic datasets in data science portfolios often have a problem: they're built to confirm the analysis. The promotion always works. The hypothesis always confirms. The ratings always predict the outcome cleanly.

That's not how real data behaves.

Here, the synthetic data is designed to include:

- Noise and ambiguous cases where the right answer isn't obvious
- Scenarios where a promotion improves competitive rank but damages margin
- Higher-rated restaurants that hold customers despite cheaper competitors nearby
- Hypothesis tests that don't always confirm the initial assumption
- Time-of-day and event effects that complicate clean before/after comparisons

When the data says something unexpected, that's not a problem to fix. That's the analysis.

---

## Tech Stack

**Analysis & Modeling**
Python · Pandas · NumPy · Statsmodels · Scikit-learn

**Database**
SQL · PostgreSQL

**Dashboard**
Plotly Dash/ PowerBI

---

## Project Status

| Phase | Status |
|---|---|
| Synthetic data generation & validation | 🔄 In progress |
| Competitive pricing analysis | 🔄 In progress |
| Reputation variable integration | 🔄 In progress |
| Statistical hypothesis testing | 📋 Planned |
| Promotional scenario modeling | 📋 Planned |
| Experimentation framework | 📋 Planned |
| Interactive dashboard | 📋 Planned |

---

## Repository Structure

```
food-delivery-pricing-intelligence/
│
├── data/
│   ├── raw/                        # Synthetic restaurant & pricing records
│   └── processed/                  # Analysis-ready datasets
├── notebooks/
│   ├── 01_market_analysis.ipynb
│   ├── 02_statistical_testing.ipynb
│   ├── 03_promotion_modeling.ipynb
│   └── 04_experimentation_framework.ipynb
├── sql/                            # Pricing queries and market aggregations
├── dashboard/                      # Plotly Dash app
├── reports/                        # Summary findings and visualizations
├── requirements.txt
└── README.md
```

---

## Future Directions

- Real-time competitor price monitoring
- Demand forecasting to model volume response to promotions
- Automated experiment analysis and lift reporting
- Market segmentation by neighborhood and cuisine density
- Dynamic pricing recommendations based on time-of-day and event context

---

## About

Building as a portfolio project exploring how product data science thinking — competitive intelligence, experimentation design, and decision-oriented analysis — applies to a real operational problem in the restaurant industry.

The project is intentionally structured around decisions, not just outputs. Every analysis connects back to a question a restaurant operator or product team would actually ask.
