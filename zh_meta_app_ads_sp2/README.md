# Speak ZH iOS app ads — SP2 vs LTV/CAC vs old SP vs IPM, October 2026

Dashboard: https://claude.ai/artifact/WqnC6svrUi54xaV1oJay54 (same page as `report/index.html`).

Every iOS app ad with spend in the Meta ad account **Speak ZH** (act 1148917790153640: Taiwan + Hong Kong campaigns) between
**1 and 7 Oct 2026** (the attribution SSOT runs two days behind the Meta funnel, so both are cut at 7 Oct): 33 ads, $15.4K of spend,
scored three ways on that window's data alone and read against a simulated LTV/CAC:

| Score | Definition |
|---|---|
| **SP2 (new)** | Efficiency Index × Scale Index. `EI = (K ÷ CPI) ÷ 0.8`, K = market SSOT LTV per Meta-reported install, CPI = spend ÷ Meta installs; EI = 1 ⇔ projected 0.8× LTV/CAC. `SI = spend/day ÷ campaign median spend/day`, clipped 0.25–4. Scalable winner = EI ≥ 1 and SP2 ≥ 2. |
| **SP (old)** | Option B from the SP dashboard skill: spend-weighted CTR and click-to-trial ratios against the placement benchmark of the other ads in the same market. P1 = SP ≥ 2 and ≥ 10 installs; P2 = P1 and ≥ 10 trials and CPFT ≤ $55. |
| **IPM** | Meta installs per 1,000 impressions; gate = at or above the market pooled IPM with ≥ 10 installs. |
| **LTV/CAC** | 10,000-draw Monte Carlo per ad (October SSOT trial starts, Beta trial-to-paid, per-ad Gamma multiplier anchored on Meta-observed purchases, AppsFlyer plan mix, 36-month LTV per paid user). Old SP, IPM, EI and SP2 are re-scored in every draw so correlations, AUCs and gate lifts carry 90% intervals. |

Ad-level inputs are October only. A week of cohorts is too few to calibrate market constants on, so trial-to-paid, LTV per paid user and K
(TW $11.74, HK $5.19 per install) are estimated on the trailing 1 Jun – 7 Oct window; the plan-mix prior uses October AppsFlyer trials.
Web campaigns in the same account have no install event, so the install-based SP2 cannot score them and they are excluded.

```
queries.sql          BigQuery extracts (project speak-v2-2a1f1); results were pulled through the BigQuery MCP tool and converted with bqjson2csv.py
data/                *_oct.csv = October ad x placement funnel, attribution SSOT and AppsFlyer plan mix per ad x market; the Jun-Oct files feed the
                     market constants and the ANALYSIS=full run; ad_daily.csv (Jun 1 - Oct 7) is filtered to the window; calibration.json
analyze.py           model + simulation + SP2 / old SP / IPM scoring + comparison statistics -> output/results.json, output/ads_scored.csv
report/template.html dashboard (inline SVG, no external JS); report/build.py embeds results.json -> report/index.html
```

Rebuild: `python3 analyze.py && python3 report/build.py` (pandas, numpy, scipy, scikit-learn). `ANALYSIS=full python3 analyze.py` reruns
the 1 Jun – 7 Oct version (417 ads); `N_SIM=500` for a quick pass.

## October results (23 ads with ≥ $100 spend; small sample, intervals are wide)

- Rank correlation with LTV/CAC (point / median of draws): EI 0.70 / 0.52, SP2 0.30 / 0.31, old SP −0.23 / −0.13, IPM −0.12 / −0.04.
  AUC for reaching 0.8×: EI 0.89, SP2 0.66, old SP 0.31, IPM 0.40. Pooling the two markets hurts the old SP most: its benchmark is relative
  to the ad's own market, so Hong Kong ads post high SPs (up to 10.6) while every Hong Kong ad sits below 0.5× LTV/CAC.
- SP2 winner gate: 2 ads (the shasha77 interview creative in the winning and testing campaigns), $2.9K, 0.81× spend-weighted, 1 of 2 on target.
  EI ≥ 1: 6 ads, $6.7K, 0.96×, 4 of 6 on target. Old P1 gate: 19 of 23 ads, $13.7K, 0.68×, 5 of 19 on target. Old P2: 4 ads, $5.3K, 0.78×, 2 of 4.
- Disagreements: 13 old P1/P2 winners are Watch or Pause under SP2 (10 Hong Kong ads, 3 Taiwan), $6.9K, 0.42× spend-weighted, 1 of 13 on
  target; no ad goes the other way. Go/no-go agreement 43%.
- Taiwan (10 ads): 0.98× spend-weighted, 5 of 10 on target; the winning campaign runs at 1.00×. No score separates ads reliably on 10 ads.
- Hong Kong (13 ads): 0.28× spend-weighted, none on target; K is $5.19 per install against a pooled CPI of $15.52, so no HK ad clears EI ≥ 1
  while the old SP calls 10 of them P1 winners.
