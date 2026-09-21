# TW Pacing Dashboard (Hex)

Hex project: https://app.hex.tech/019c0c49-ab2d-7003-aa7a-3b9870aa8d91/hex/TW-Pacing-Dashboard-034SlmYfnVqGKn3UwCFDQU/draft/logic
Project id: `01a0c4e8-64a3-71c6-bdb7-3f9eb344e6a6` · created 2026-09-21 from the US H2'26 Pacing Dashboard (`019f4d2e-77e0-75c1-864a-35af54bf0084`).

`cells.md` is the full source of every cell (SQL / Python / markdown) as built, in notebook order, so the project can be
rebuilt or diffed without the Hex API.

## What it is

The US dashboard re-targeted to Taiwan and re-shaped around the TW plan. The TW plan
(Google Sheet `1rp_xCAGLHWoafH5LvL6QLIj_nUOeb4XWxljkwUEERG0`, "TW LTV Tracking Model") is a channel-level
booked-LTV / spend / LTV/CAC plan with a paid funnel block; it has no ARR targets. So:

| US section | TW equivalent |
|---|---|
| Scorecard on Exit ARR / Net-new ARR / subs / spend / LTV / LTV/CAC | Scorecard on total spend, total booked LTV, blended LTV/CAC, and Paid / Influencer / Branded search / Organic rows, plus a paid-funnel scorecard (installs, CPI, install→signup, signup→trial, trial→conversion, new subs, LTV/sub) |
| Plan = ARR Model sheet, Jul–Dec | Plan = Sep 2026 (Q3 tracking tab) + Oct–Dec 2026 ([Conservative] Bottom-up funnel review – Q4). Jul/Aug are not paced. |
| Runwayer, Freemium, Tier1 layers | Dropped (do not exist in TW) |
| Segments: Runwayer RW/Speak-managed, Speak App | Segments: Paid app iOS / Android / Web, Influencer, Branded search, Brand; scope Ongoing / Promo / Brand / Untagged |
| Native chart + INPUT cells | Plotly code cells (the API cannot create chart/input cells). Dataframe names are stable so native charts can be bound later. |

Targets: blended LTV/CAC 1.5x (all spend), paid LTV/CAC 0.85x.

## Bases (reconciled to the sheet on 2026-09-21)

- Total booked LTV = `cohort_ltv_daily_marketing.revenue_ltv` @ m35, `country='Taiwan'` (Jul $476,457 vs sheet $476,787; Aug $1,197,745 vs $1,198,446).
- Channel booked LTV = attribution table realised `ltv` by `bucketed_channel` (Jul Paid $192,727 vs sheet $193,065). Capped at today−5.
- Spend = `marketing_spend_daily`, all TW rows (brand, agency, PR, research included).
- Blended LTV/CAC July 1.385 vs sheet 1.38.

## Sections (notebook order)

1. Header, READ FIRST gotchas, definitions
2. Pacing: plan targets, channel scorecard, paid-funnel scorecard, daily bases, trailing-7d table, flight paths
3. Where we are: exit ARR / subscribers, subscriber bridge
4. Spend efficiency: blended LTV/CAC (forecasted, blended, paid), attributed vs organic, segments monthly/weekly, cash CAC payback
5. Plan mix
6. Conversion funnel (install and signup cohorts)
7. Monitoring: LTV multiplier drift, M12 retention, media mix, ARR reconciliation
8. Churn forecasting (US per-plan settings kept for now, per Kevin)

## Not done / follow-ups

- App layout (tabs) must be arranged in the Hex app builder; the API only creates notebook cells.
- Plan literals live in two places (`tw_monthly_plan_targets` and the inline `plan` CTEs of the two scorecard cells). Update both when the sheet changes, or wire a Sheets connection.
- Churn model still uses US M12 caps / plan anchors; TW empirical M12 is ~26% app store, ~41% paddle, ~31% play store.
- No daily schedule set yet (US runs 10:05 PT daily).
