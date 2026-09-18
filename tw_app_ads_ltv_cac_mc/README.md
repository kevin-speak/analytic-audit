# Speak ZH Taiwan iOS app ads — Monte Carlo LTV/CAC analysis (1 Jun – 15 Sep 2026)

Compares every iOS app ad in the Taiwan testing / winning / scaling campaigns on LTV/CAC vs
(1) SP score, (2) IPM, (3) trial per impression, (4) Phase 1 winner, (5) Phase 2 winner,
per campaign stage and overall. 4,000-draw Monte Carlo over conversion counts, trial-to-paid
rate, plan mix, LTV forecast error and the sampling noise in CTR / CTI / IPM / TPI.

```
queries.sql          BigQuery extracts (project speak-v2-2a1f1)
data/                extracted inputs (Meta ad x placement funnel, ad attributes, AppsFlyer plan mix, attribution SSOT)
simulate.py          model + simulation -> output/results.json, output/ads_scored.csv
report/template.html visual report template (inline SVG charts, no external JS)
report/build.py      embeds results.json into report/index.html
```

Rebuild: `python3 simulate.py && python3 report/build.py` (needs pandas, numpy, scipy).

Phase rules and the SP Option B formula follow the SP dashboard skill (Taiwan: SP >= 2.0, CPFT <= $55).
