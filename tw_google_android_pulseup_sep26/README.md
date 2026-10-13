# Speak TW Google Android — tROAS vs pulse-up geo test, September 2026

Side-by-side read of the two Taiwan Google Android app campaigns that ran in September 2026 and of the geo
pulse-up test they were meant to form (Paramark design, Notion "[Paid] Google Android Pulse Up - 2609").

| | tROAS (control) | pulseup (test) |
|---|---|---|
| Campaign id | 23639420764 | 24190362603 |
| Role in the design | BAU, exclude the 4 test regions, budget −32% | Target only the 4 test regions, +≈$8.5K/week on top of BAU share |
| Test regions | — | Hsinchu County, New Taipei City, Pingtung, Taoyuan |
| Window | 1–30 Sep (paused 1 Oct) | 31 Aug – 30 Sep (paused 1 Oct) |

```
queries.sql   BigQuery extracts (project speak-v2-2a1f1), pulled through the BigQuery MCP tool
data/         campaign_daily.csv (spend + attribution SSOT per campaign x day), campaign_signups_by_region.csv,
              tw_daily_by_cell.csv (all-source TW users by OS x test/control region x day), tw_android_weekly_by_region.csv
analyze.py    side-by-side table, geo-split check, test-vs-control difference-in-differences, per-region lift -> output/results.json
```
Rebuild: `python3 analyze.py` (standard library only).

## 1. September side by side (attribution SSOT, Android, Taiwan)

| Metric | tROAS (control) | pulseup (test) |
|---|---|---|
| Spend | $23,698 ($790/day) | $2,801 ($93/day) |
| Impressions / CPM | 4.39M / $5.40 | 0.52M / $5.35 |
| Clicks / CTR | 27,816 / 0.63% | 4,393 / 0.84% |
| Installs / CPI | 5,257 / $4.51 | 620 / $4.52 |
| Sign-ups / install→sign-up | 3,321 / 63% | 300 / 48% |
| Trial starts / sign-up→trial / CPT | 343 / 10.3% / $69 | 34 / 11.3% / $82 |
| Paid (trial converts + purchases) / CPA | 117.1 / $202 | 11.3 / $249 |
| Forecasted LTV / LTV:CAC | $17,903 / 0.76× | $1,749 / 0.62× |

Both campaigns buy the same inventory at the same CPM and CPI. The pulse-up campaign loses at the install→sign-up
step (48% vs 63%) and ends at 0.62× against the 0.80× market target; the control campaign runs at 0.76×. On 34 trials
and 11 paid the pulse-up's funnel rates carry wide error bars, so the attributed gap is directional, not proven.

## 2. Was the geo test executed? No.

| Design | Actual |
|---|---|
| pulseup spends ≈$34K extra over 4 weeks | pulseup spent **$2.8K** in total (8% of design) |
| tROAS budget cut 32% (≈$17K/month) | tROAS spent $23.7K, 5% below August ($24.9K) |
| tROAS excludes the 4 test regions | 27% of tROAS September sign-ups still come from the 4 test regions (28% in August) |
| pulseup targets only the 4 test regions | 48% of pulseup sign-ups come from the test regions; 33% from Taipei City alone |

Region is the IP geography at sign-up. Total Google Android spend in Taiwan rose 6% month on month, with no shift
in where the attributed users live. There was no spend separation between test and control geos, so the test cannot
read incrementality. Paramark's own design note required an $8.5K/week spend gap to detect a 4% lift.

## 3. What the geo data shows anyway (all-source Taiwan Android users, test vs control regions)

Difference-in-differences: September vs the June–July baseline (August is excluded as baseline because of the
3–20 Aug brand promo), test regions vs all other Taiwan regions, Poisson 95% intervals. iOS is the placebo: it
cannot respond to Android spend.

| KPI | Android test-region lift | Android 95% CI | iOS (placebo) lift |
|---|---|---|---|
| Sign-ups | +6.1% | −1.7% to +14.6% | −0.9% |
| Google-attributed sign-ups | +0.7% | −8.5% to +10.7% | — |
| Trial starts | −1.5% | −20.7% to +22.4% | +6.2% |
| Conversions (trial converts + purchases) | −10.7% | −34.1% to +21.0% | +2.0% |
| Purchases + trial starts (Paramark target metric) | −4.3% | −22.1% to +17.6% | +3.1% |

No KPI moves in the test regions, and the only positive number (sign-ups) is inside the placebo's noise. With ≈7
purchases + trial starts per day in the test cell, the minimum detectable lift is roughly ±20%; the designed 4% was
never within reach at these volumes without the planned spend gap.

## 4. Which area performed better

Per test region, control-adjusted lift of Taiwan Android KPIs (weeks of 31 Aug – 28 Sep vs 1 Jun – 27 Jul):

| Region | Sign-ups | Google sign-ups | Trial starts | Conversions | Sep volume (trials / conv per week) |
|---|---|---|---|---|---|
| New Taipei City | +12% [+2%, +23%] | +12% [0%, +26%] | −17% [−36%, +8%] | −28% [−49%, +3%] | 23.4 / 11.8 |
| Taoyuan | −6% [−16%, +7%] | −20% [−31%, −6%] | +27% [−9%, +78%] | +34% [−19%, +120%] | 15.0 / 6.8 |
| Hsinchu County | +45% [+10%, +90%] | +40% [−3%, +102%] | +48% [−29%, +205%] | +4% [−62%, +182%] | 3.2 / 1.4 |
| Pingtung | −21% [−43%, +9%] | −22% [−47%, +14%] | −23% [−72%, +114%] | −5% [−70%, +204%] | 1.2 / 1.0 |

- **Taoyuan** is the only test region where the paid KPIs (trial starts, conversions) moved up, and it did so while
  Google-attributed sign-ups fell, so the lift is not attributable to the pulse-up campaign.
- **New Taipei City** gained sign-ups but lost conversions relative to control. Taipei City, a control region, gained
  Google sign-ups by the same +11%, so the New Taipei sign-up rise reads as a Greater Taipei trend, not a treatment effect.
- **Hsinchu County and Pingtung** run at 1–3 trial starts a week; nothing is readable at that volume.
- Within the campaigns' own attribution (September), Taipei City is the best region for both campaigns
  (tROAS 94 trials / 38 conversions, pulseup 12 / 5), followed by New Taipei (50 / 17 and 10 / 2). Kaohsiung converts
  worst in tROAS (33 trials, 4 conversions).

## 5. Does Google Android have incrementality potential?

Not demonstrated, and this test did not test it. What can be said:

- The channel's attributed economics are below target (0.76× control, 0.62× pulse-up) before any incrementality haircut.
- The same channel in Korea (Paramark geo holdout, August 2026) showed no detectable decline when $22.5K was withheld,
  implying a cost per incremental conversion above ≈$225; the Taiwan MMM estimate used in this design was $211.
- The only clean signal here is that adding 12% more Google Android spend to Taiwan (control +tROAS budget intact,
  plus the pulse-up) left Android purchases + trial starts flat in every region.

Recommended rerun: keep the control exclusions and verify them in Google Ads before day 1 (check the location report
daily, not IP geography after the fact), fund the test cell at the designed $8.5K/week, cut tROAS by the designed 32%,
and measure on Android purchases + trial starts only. At the current ≈7/day in the test cell, four weeks can only
detect a lift of about 20%; either extend to 8 weeks or add Taichung to the test cell to get the detectable lift under 10%.

## Caveats

- Region comes from IP geography at sign-up, which is noisier than Google's location-of-presence targeting; a Google
  Ads geo report (not in the warehouse) is the right check for the exclusions.
- Attribution SSOT uses the attribution-date cohort; forecasted LTV for late-September cohorts is model-based.
- iOS country labels were restated on 6 Oct (iOS SDK issue since 19 Jun); the iOS placebo uses the restated data.
