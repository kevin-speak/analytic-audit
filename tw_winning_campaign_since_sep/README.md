# TW iOS "winning" campaign (120216508762540167) — per-ad performance & LTV/CAC since 1 Sep 2026

Campaign `tw_meta_standard_ios_tw-en_pros_trial_ongoing_winning`, Speak ZH ad account. Window 2026-09-01 .. 2026-10-06
(latest BigQuery day). Ad status from the Meta Marketing API on 2026-10-08.

```
queries.sql        BigQuery extracts
data/              meta_funnel.csv (Meta funnel per ad), ssot_ads.csv (attribution SSOT per ad), meta_status.csv (Meta API status)
output_ads.csv     joined per-ad table with conversion rates and LTV/CAC
table.md           same table in markdown
```

## Definitions
- **LTV/CAC (attributed)** = SSOT `ltv` for installs attributed to the ad ÷ Meta spend on the ad. Same definition as `tw_app_ads_ltv_cac_mc`.
- **LTV/CAC (incl. unattributed share)** = attributed × 1.256. 20% of the campaign's SSOT LTV ($5,116 of $25,075, 882 installs)
  sits on "No Ad ID" rows. Spreading it pro rata by spend raises every ad by the same factor.
- SSOT trial→paid is modeled at a flat 0.37 and LTV per trial is a flat ~$38.9 for every ad, so within this window
  LTV/CAC is entirely driven by cost per SSOT trial (CPFT): LTV/CAC = 1.0 ⇔ CPFT ≈ $39; 0.85 ⇔ CPFT ≈ $46.
- Conversion rates: CTR = clicks/impressions; IPM = Meta installs per 1,000 impressions; install→trial = SSOT trials / SSOT installs.

## Campaign totals since 1 Sep
Spend $25,075 · SSOT installs 4,829 · SSOT trials 635 · modeled paid 234 · SSOT LTV $25,075 → campaign LTV/CAC **1.00**
(0.80 counting only ad-attributed LTV).

## Highlights
- **Paused but LTV/CAC ≥ 1**
  - `120249918296230167` morning.jason / 26Q3 og-video: 1.10 attributed (1.38 scaled), $316 spend, 9 trials. Small sample; last spend 15 Sep.
  - `120248790253970167` eaglish.fam / product og-video: 0.91 attributed but **1.14 scaled**, the campaign's best large ad ($4,436 spend,
    103 trials, CPFT $43, IPM 0.64). Weekly attributed LTV/CAC was 0.92 → 0.84 → 1.05, no decay before it was switched off on 30 Sep.
- **Active but LTV/CAC < 0.85**
  - `120250258111880167` mip-christines_talk / english-environment: 0.58 attributed (0.73 scaled), $204 spend, 3 trials, CPFT $68.
  - `120246191401160167` harryspeaks / 0601 is borderline at 0.86 (1.09 scaled); fine on the scaled view.
- Biggest spender `120249917976060167` (Qing testimonial, $6,285) ran at 0.62 and was paused 2 Oct; the Sep 21 week alone burned $2,608 for $460 LTV.
- `120250659554660167` shasha77 (ACTIVE, launched 6 Oct) shows 1.32 on one day of data ($516); Meta reports $2,422 spent by 8 Oct, so re-check in a week.
