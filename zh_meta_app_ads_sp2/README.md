# Speak ZH iOS app ads — SP2 vs LTV/CAC vs old SP vs IPM (1 Jun – 7 Oct 2026)

Dashboard: https://claude.ai/artifact/WqnC6svrUi54xaV1oJay54 (same page as `report/index.html`).

Every iOS app ad with spend in the Meta ad account **Speak ZH** (act 1148917790153640: Taiwan + Hong Kong campaigns), 417 ads and
$663K of spend, scored three ways and read against a simulated LTV/CAC:

| Score | Definition |
|---|---|
| **SP2 (new)** | Efficiency Index × Scale Index. `EI = (K ÷ CPI) ÷ 0.8`, K = market SSOT LTV per Meta-reported install (TW $11.74, HK $5.19), CPI = spend ÷ Meta installs; EI = 1 ⇔ projected 0.8× LTV/CAC. `SI = spend/day ÷ campaign median spend/day`, clipped 0.25–4. Scalable winner = EI ≥ 1 and SP2 ≥ 2. |
| **SP (old)** | Option B from the SP dashboard skill: spend-weighted CTR and click-to-trial ratios against the placement benchmark of the other ads in the same market. P1 = SP ≥ 2 and ≥ 10 installs; P2 = P1 and ≥ 10 trials and CPFT ≤ $55. |
| **IPM** | Meta installs per 1,000 impressions; gate = at or above the market pooled IPM with ≥ 10 installs. |
| **LTV/CAC** | 10,000-draw Monte Carlo per ad (SSOT trial starts, Beta trial-to-paid, per-ad Gamma multiplier anchored on Meta-observed purchases, AppsFlyer plan mix, 36-month LTV per paid user), calibrated per market. Old SP, IPM, EI and SP2 are re-scored in every draw so correlations, AUCs and gate lifts carry 90% intervals. |

Web campaigns in the same account have no install event, so the install-based SP2 cannot score them and they are excluded.

```
queries.sql          BigQuery extracts (project speak-v2-2a1f1); results were pulled through the BigQuery MCP tool and converted with bqjson2csv.py
data/                ad x placement funnel, ad attributes, ad x day, attribution SSOT per ad x market, AppsFlyer plan mix per ad x market, calibration.json
analyze.py           model + simulation + SP2 / old SP / IPM scoring + comparison statistics -> output/results.json, output/ads_scored.csv
report/template.html dashboard (inline SVG, no external JS); report/build.py embeds results.json -> report/index.html
```

Rebuild: `python3 analyze.py && python3 report/build.py` (pandas, numpy, scipy, scikit-learn). `N_SIM=500 python3 analyze.py` for a quick pass.

## Headline results (303 ads with ≥ $100 spend)

- Rank correlation with LTV/CAC (point / median of draws): EI 0.53 / 0.36, SP2 0.40 / 0.31, old SP 0.35 / 0.26, IPM 0.23 / 0.19. AUC for reaching 0.8×: EI 0.82, SP2 0.76, old SP 0.69, IPM 0.69.
- SP2 winner gate: 16 ads, $31K, 1.08× spend-weighted, 64% hit rate (90% 45–81%). Old P1 gate: 127 ads, $533K, 0.58×, 28%. Old P2 gate: 15 ads, $32K, 1.54×, 67%. SP2 captures 15% of the spend that ends on target, P1 captures 90%.
- Where the two phase systems disagree, LTV/CAC sides with SP2: 105 old P1/P2 winners are Watch or Pause under SP2 ($491K, 0.54×, 14 of 105 on target); 2 ads go the other way. Go/no-go agreement 65%.
- At $100 of cumulative spend SP2 reads the final LTV/CAC at ρ 0.39 (AUC 0.76) vs 0.17 (0.59) for the old SP proxy and 0.18 (0.69) for IPM.
- Hong Kong: K is $5.19 per install against a pooled CPI of $14.62, so no HK ad clears EI ≥ 1 and only 1 of 81 analyzed ads ends at or above 0.8×; the SP2 gates select nothing there by design.
- Scaling campaigns: SP2's correlation turns negative (Taiwan scaling ρ −0.19 vs old SP 0.61) because the Scale Index rewards the budget winners whose CPI has drifted furthest; use EI or the old SP to rank ads that are already scaled. SP2 is a gate for what to scale, not a ranking of scaled ads.
