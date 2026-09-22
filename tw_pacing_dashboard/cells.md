# TW Pacing Dashboard — cell inventory

Exported 2026-09-21 via the Hex API. Notebook order. Project `01a0c4e8-64a3-71c6-bdb7-3f9eb344e6a6`.

## [0] [MARKDOWN] Hero header
_cell id `01a0c4ea-13c8-7410-a057-8c7fa221b51d` · static `01a0c4ea-13c8-7410-a057-927831f04326`_
# TW pacing
**Where TW marketing is landing vs the TW LTV Tracking Model plan**

Spend · booked LTV · LTV/CAC by channel · paid funnel · plan mix · conversion · refreshed daily

Start with **Pacing**; use the remaining sections for spend efficiency, plan mix, conversion funnel, monitoring and churn forecasting. Metric definitions and source notes are in the Definitions cell at the top and the READ FIRST cell for editors.

_Plan horizon: Sep 2026 (Q3 tracking-tab targets) and Oct–Dec 2026 ([Conservative] Bottom-up funnel review – Q4). July and August are shown as actuals only._

## [1] [MARKDOWN] 🛑 READ FIRST — build conventions & gotchas
_cell id `01a0c4ea-9870-75d2-a67f-d52f960c81f6` · static `01a0c4ea-9870-75d2-a67f-dad3d3241e05`_
# 🛑 READ FIRST — build conventions & known gotchas (any AI/LLM editing this dashboard)

**If you are an AI/agent working on this project, read this cell before running or changing anything.**

1. **Read before you build.** Metrics here mirror the TW LTV Tracking Model sheet and the Mode boards it reads from. Trace definitions, don't invent them.
2. **Capture every mistake or learning** in this cell. It is the shared memory for every future editor.

## Source-of-truth pointers
- **Committed plan = TW LTV Tracking Model** Google Sheet (`1rp_xCAGLHWoafH5LvL6QLIj_nUOeb4XWxljkwUEERG0`). Sep 2026 targets come from the Q3 tracking tab ("July Actual / July Target …" block, Sep Target column). Oct–Dec 2026 come from the tab **[Conservative] Bottom-up funnel review – Q4** (updated 2026-09-14). July and August are deliberately NOT paced (Kevin, 2026-09-21).
- Plan literals live in TWO places by necessity: `tw_monthly_plan_targets` (for DuckDB/Python consumers) and the inline `plan` CTE inside the BigQuery scorecard cells (BigQuery cells cannot read kernel dataframes). Update both when the sheet changes.
- **Total booked LTV** = `cohort_ltv_daily_marketing.revenue_ltv` @ `month_index = 35`, `country = 'Taiwan'`, dated at `first_transaction_date` (lag-free). Ties to the sheet's monthly "Total Booked LTV" within 0.1% (Jul $476,457 vs $476,787; Aug $1,197,745 vs $1,198,446).
- **Channel booked LTV** (Paid / Influencer / Branded search) = realised `ltv` in `marketing_attribution_aggregate_attribution_date_cohort`, grouped by that table's `bucketed_channel`, dated at `attribution_date`. This is the Mode "LTV/CAC by Country" basis the sheet uses. It is NOT `forecasted_ltv` (the US dashboard uses forecasted for segments; TW deliberately matches the sheet). Ties Jul Paid $192,727 vs sheet $193,065; Influencer $38,453 vs $38,422.
- **Organic + other** = total − paid − influencer − branded search, a residual, computed on the attribution window so both legs cover the same days.
- **Spend** = `marketing_spend_daily`, `UDFs.country_group_marketing(country) = 'Taiwan'`, ALL rows (brand production, agency, PR, research included — the sheet's "Mode basis"). Channel spend uses the table's `bucketed_channel` ('Paid', 'Influencer', 'Paid Branded Search').
- **Targets**: blended LTV/CAC 1.5x (all spend), paid LTV/CAC 0.85x (Kevin, 2026-09-21). Plan ratios in the sheet are slightly different (Sep 1.53x / 0.83x) and are shown as "Plan"; the target line is shown separately.
- **Country filters by table**: `user_daily_arr`/`cohort_ltv_*` → `country_group`/`country = 'Taiwan'`; spend + attribution → `UDFs.country_group_marketing(country) = 'Taiwan'`; `transaction_ltv_forecasted` → `country_group_marketing = 'Taiwan'`; `canonical.users`/`canonical.transactions` → `country = 'TW'`; `analytics.first_installs` → `country = 'Taiwan'`.
- **Timezone** = `Asia/Taipei` for as-of and week boundaries (Sunday weeks).

## TW-specific data facts (verified 2026-09-21)
- No Runwayer, no Freemium All-Access test, no Tier1/WW spend in TW. None of that US machinery exists here.
- **Attribution bakes for ~4 days**: channel LTV, installs, signups, trials are capped at `today − 5` (`attr_cap`). Spend and total LTV run through `as_of` (yesterday). Channel LTV/CAC ratios use spend on the SAME capped window so they are like-for-like; the spend rows show the full as-of window. Both dates are emitted as columns.
- **Influencer spend lands at month end in batches** (sheet note). Mid-month influencer LTV/CAC reads very high; do not trade on it before month close.
- **Committed spend is forward-dated**: `marketing_spend_daily` already carries ~$60–70K/month of Oct–Dec brand/agency contracts. Any cell that divides LTV by spend must cap spend at a data-detected watermark (see the Blended cell header, ported from the US build).
- Campaign names carry `_ongoing_` (BAU) but never `_test_`; stage is a suffix (`testing`, `winning`, `scaling`); promo campaigns carry `promo_disc`; brand campaigns carry `brandmarketing`. Apple Search Ads campaigns (`TW_ASA_*`) follow no convention. The segment classifier in the Blended section reflects this.
- Plan mix is annual-heavy (app_store annual regular is the largest cohort; paddle web annual is second). Quarterly / semiannual are negligible. An `unlimited` tier exists with a handful of users and is folded into Premium Plus.
- TW M12 revenue retention on annual cohorts is materially higher than the US (~26% app store, ~41% paddle, ~31% play store on cohorts Jun-24 → Aug-25). The churn model below still uses the US caps/overrides for now (Kevin, 2026-09-21: "use the US setting for now").

## Hex build gotchas (inherited from the US build — do not relearn them)
- **ONE errored cell aborts the whole "Run all" and publish.** Chase every erroring cell to zero before publishing.
- **Jinja renders EVERYWHERE in a cell — including SQL comments and MARKDOWN.** Never show raw Jinja delimiters in documentation cells.
- **Validate every new BigQuery cell directly against BigQuery** before wiring it into charts. A 0-second error is a compile/reference problem, not data.
- **Never regex / find-and-replace inside a cell's SQL.** Rewrite the full cell source.
- **Charts in this build are Plotly code cells** (the API used to create this project cannot create native chart or INPUT cells). Native charts can be created in-app and bound to the same dataframes; keep dataframe names stable.
- **pandas in code cells:** `df.groupby(keys).agg(**named)` then vectorized ratios; never average per-cell ratios — always SUM(num)/SUM(den) after rolling up.

_Created 2026-09-21 from the US H2'26 Pacing Dashboard (019f4d2e-77e0-75c1-864a-35af54bf0084) by reading every cell and re-targeting to TW._

## [2] [MARKDOWN] Definitions & sources
_cell id `01a0c4ea-c565-76e9-9b64-2f0a06f97006` · static `01a0c4ea-c565-76e9-9b64-30ccbdf27758`_
## 📚 Definitions & sources
_How the headline metrics are defined and where they come from — every number ties back to the TW LTV Tracking Model sheet and its Mode boards._

- **Total marketing spend** — all TW spend in `marketing_spend_daily` (paid media, influencer, brand production, agency, PR, research). Same basis as the sheet's "Total Spend (USD) – ARR".
- **Total booked LTV** — cohort LTV at month 35 (`cohort_ltv_daily_marketing.revenue_ltv`), dated at cohort start, TW. Same basis as the sheet's "Total Booked LTV" and Mode "LTV/CAC by Country".
- **Blended LTV/CAC** — Total booked LTV ÷ Total marketing spend. **Target 1.5×**.
- **Paid / Influencer / Branded search booked LTV** — realised attributed LTV from the attribution table by `bucketed_channel`. **Paid LTV/CAC target 0.85×.** Attributed figures are capped at today − 5 while attribution bakes.
- **Organic + other** — Total booked LTV minus the three attributed channels (residual; includes brand, referral, affiliate, lifecycle).
- **Paid funnel** — attributed installs, signups, trial starts and conversions for `bucketed_channel = 'Paid'` (Meta, Google, Apple Search non-brand, DSPs). CPI = paid spend ÷ installs; rates are SUM/SUM over the window.
- **Plan** — Sep 2026 from the sheet's Q3 tracking tab; Oct–Dec 2026 from the [Conservative] Q4 tab. Projected = trailing-7-day run rate carried to period end. Pace = Projected ÷ Plan. Q3 QTD = Sep only (July/Aug are not paced).
- **Exit ARR / subscribers** — month-end standing ARR and subscriber count, TW (`user_daily_arr`, `country_group = 'Taiwan'`); no plan line (the TW plan has no ARR targets).
- **Retention / renewal cliff** — gross revenue retention on TW annual cohorts; the forecast model still uses the US per-plan settings for now.

_All amounts USD. As-of = yesterday Asia/Taipei, or the latest loaded ARR day if the pipeline lags._

## [3] [MARKDOWN] Scorecard header
_cell id `01a0c4ea-cfea-74d5-abb6-0e9d292c518e` · static `01a0c4ea-cfea-74d5-abb6-1050ed113ff0`_
## Pacing to plan
Actual vs TW LTV Tracking Model plan · month- and quarter-to-date · projections use the trailing 7-day run rate

**Status:** green = at or ahead · amber = within 10% · red = off plan · red spend = over budget (outside ±10%)

_Attributed channel rows (Paid / Influencer / Branded search / Organic residual) are capped at `attributed_through`; spend and total LTV run to `as_of_date`. Influencer spend posts in month-end batches, so its mid-month ratio is not a decision input._

## [4] [SQL] TW monthly plan targets
_cell id `01a0c4ec-06f6-74ec-980f-4add4297c18b` · static `01a0c4ec-06f6-74ec-980f-4ff4c5cbd923`_
```sql
-- output: tw_monthly_plan_targets  (BigQuery)
-- TW committed plan targets — source of truth: TW LTV Tracking Model (Google Sheet 1rp_xCAGLHWoafH5LvL6QLIj_nUOeb4XWxljkwUEERG0).
-- Sep 2026  = Q3 tracking tab ("Sep Target" column). Jul/Aug are NOT paced (Kevin, 2026-09-21).
-- Oct-Dec   = tab "[Conservative] Bottom-up funnel review - Q4" (updated 2026-09-14). Benchmark blended 1.53x.
-- All USD. org_ltv_target = total - paid - influencer - branded search so the rows add up (the Sep tab's own organic
-- figure, 324,382, ignores branded search; we keep the total and make organic the residual).
-- Branded-search Sep spend is not in the sheet; set equal to its LTV target (1.0x, the Q4 assumption).
-- Funnel plan (paid): installs, CPI, install->signup, signup->trial, trial->conversion, new subs, LTV/sub.
-- This cell serves DuckDB/Python consumers; the BigQuery scorecard cells carry the SAME literals inline. Update both.
SELECT DATE '2026-09-01' AS month_start,
    322924.0 AS total_spend_target, 495110.0 AS total_ltv_target,
    180000.0 AS paid_spend_target, 150027.0 AS paid_ltv_target,
    25000.0 AS inf_spend_target, 20700.0 AS inf_ltv_target,
    12000.0 AS bs_spend_target, 12000.0 AS bs_ltv_target,
    312383.0 AS org_ltv_target,
    25714.0 AS paid_installs_target, 7.00 AS paid_cpi_target, 0.51 AS paid_install_su_target, 0.26 AS paid_su_trial_target,
    0.40 AS paid_trial_conv_target, 1364.0 AS paid_new_subs_target, 110.0 AS paid_ltv_per_sub_target
UNION ALL SELECT DATE '2026-10-01', 363124.0, 456430.0, 230000.0, 192830.0, 12000.0, 9600.0, 9000.0, 9000.0, 245000.0, 32857.0, 7.00, 0.46, 0.29, 0.40, 1753.0, 110.0
UNION ALL SELECT DATE '2026-11-01', 376124.0, 477830.0, 230000.0, 192830.0, 20000.0, 16000.0, 9000.0, 9000.0, 260000.0, 32857.0, 7.00, 0.46, 0.29, 0.40, 1753.0, 110.0
UNION ALL SELECT DATE '2026-12-01', 348124.0, 454535.0, 230000.0, 196535.0, 0.0, 0.0, 8000.0, 8000.0, 250000.0, 32857.0, 7.00, 0.46, 0.29, 0.39, 1709.0, 115.0
```

## [5] [SQL] 01 Scorecard — channel pacing
_cell id `01a0c4ed-30fa-707f-b358-9a99b21f6721` · static `01a0c4ed-30fa-707f-b358-9e389eb08780`_
```sql
-- output: tw_scorecard  (BigQuery)
-- 01 Scorecard — TW pacing-to-plan by channel. Plan = TW LTV Tracking Model (Sep = Q3 tracking tab; Oct-Dec = [Conservative] Q4 tab).
-- Bases (all verified vs the sheet 2026-09-21, see READ FIRST):
--   Total spend      = marketing_spend_daily, all TW rows, through as_of_date (yesterday Asia/Taipei or last loaded ARR day).
--   Total booked LTV = cohort_ltv_daily_marketing.revenue_ltv @ m35 by first_transaction_date (lag-free), through as_of_date.
--   Channel LTV      = attribution table realised ltv by bucketed_channel, attribution_date <= attr_cap (today-5: attribution bakes ~4 days).
--   Channel LTV/CAC  = channel LTV / channel spend on the SAME capped window (like-for-like). Spend ROWS use the as-of window.
--   Organic + other  = total - paid - influencer - branded search, on the capped window (residual).
-- Period: MTD = current month; QTD = current quarter but never before 2026-09-01 (Jul/Aug are not paced), so Q3 QTD == Sep.
-- Projected = trailing-7-day run rate x remaining days (attributed rows use the run rate ending attr_cap). Pace = Projected / Plan.
-- Target column: blended 1.5x, paid 0.85x (Kevin 2026-09-21). Plan ratios come from the sheet and differ slightly.
WITH params AS (
  SELECT LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
               (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr`
                WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS as_of_date,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS attr_cap,
         DATE '2026-09-01' AS plan_start
),
pe AS (
  SELECT as_of_date, attr_cap, plan_start,
    GREATEST(DATE_TRUNC(as_of_date, QUARTER), plan_start) AS p_start,
    DATE_SUB(DATE_ADD(DATE_TRUNC(as_of_date, QUARTER), INTERVAL 1 QUARTER), INTERVAL 1 DAY) AS p_end,
    DATE_TRUNC(as_of_date, MONTH) AS m_start,
    LAST_DAY(as_of_date, MONTH) AS m_end
  FROM params
),
plan AS (
  -- SAME literals as tw_monthly_plan_targets (BigQuery cannot read kernel frames). Update both.
  SELECT DATE '2026-09-01' AS mo, 322924.0 spend_t, 495110.0 ltv_t, 180000.0 paid_spend_t, 150027.0 paid_ltv_t, 25000.0 inf_spend_t, 20700.0 inf_ltv_t, 12000.0 bs_spend_t, 12000.0 bs_ltv_t, 312383.0 org_ltv_t
  UNION ALL SELECT DATE '2026-10-01', 363124.0, 456430.0, 230000.0, 192830.0, 12000.0, 9600.0, 9000.0, 9000.0, 245000.0
  UNION ALL SELECT DATE '2026-11-01', 376124.0, 477830.0, 230000.0, 192830.0, 20000.0, 16000.0, 9000.0, 9000.0, 260000.0
  UNION ALL SELECT DATE '2026-12-01', 348124.0, 454535.0, 230000.0, 196535.0, 0.0, 0.0, 8000.0, 8000.0, 250000.0
),
plan_m AS (SELECT p.* FROM plan p, pe WHERE p.mo = pe.m_start),
plan_q AS (SELECT SUM(spend_t) spend_t, SUM(ltv_t) ltv_t, SUM(paid_spend_t) paid_spend_t, SUM(paid_ltv_t) paid_ltv_t, SUM(inf_spend_t) inf_spend_t, SUM(inf_ltv_t) inf_ltv_t, SUM(bs_spend_t) bs_spend_t, SUM(bs_ltv_t) bs_ltv_t, SUM(org_ltv_t) org_ltv_t FROM plan p, pe WHERE p.mo BETWEEN pe.p_start AND pe.p_end),
spend_daily AS (
  SELECT CAST(s.date_start AS DATE) AS day,
    SUM(s.spend) AS spend_all,
    SUM(IF(s.bucketed_channel = 'Paid', s.spend, 0)) AS spend_paid,
    SUM(IF(s.bucketed_channel = 'Influencer', s.spend, 0)) AS spend_inf,
    SUM(IF(s.bucketed_channel = 'Paid Branded Search', s.spend, 0)) AS spend_bs
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` s CROSS JOIN pe
  WHERE CAST(s.date_start AS DATE) BETWEEN pe.p_start AND pe.as_of_date
    AND COALESCE(s.spend, 0) > 0 AND `speak-v2-2a1f1`.UDFs.country_group_marketing(s.country) = 'Taiwan'
  GROUP BY day),
total_ltv_daily AS (
  SELECT c.first_transaction_date AS day, SUM(c.revenue_ltv) AS ltv_total
  FROM `speak-v2-2a1f1.analytics.cohort_ltv_daily_marketing` c CROSS JOIN pe
  WHERE c.first_transaction_date BETWEEN pe.p_start AND pe.as_of_date AND c.country = 'Taiwan' AND c.month_index = 35
  GROUP BY day),
attr_daily AS (
  SELECT a.attribution_date AS day,
    SUM(IF(a.bucketed_channel = 'Paid', a.ltv, 0)) AS ltv_paid,
    SUM(IF(a.bucketed_channel = 'Influencer', a.ltv, 0)) AS ltv_inf,
    SUM(IF(a.bucketed_channel = 'Paid Branded Search', a.ltv, 0)) AS ltv_bs
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` a CROSS JOIN pe
  WHERE a.attribution_date BETWEEN pe.p_start AND pe.attr_cap
    AND `speak-v2-2a1f1`.UDFs.country_group_marketing(a.country) = 'Taiwan'
  GROUP BY day),
daily AS (
  SELECT d.day,
    COALESCE(s.spend_all, 0) spend_all, COALESCE(s.spend_paid, 0) spend_paid, COALESCE(s.spend_inf, 0) spend_inf, COALESCE(s.spend_bs, 0) spend_bs,
    COALESCE(t.ltv_total, 0) ltv_total,
    COALESCE(a.ltv_paid, 0) ltv_paid, COALESCE(a.ltv_inf, 0) ltv_inf, COALESCE(a.ltv_bs, 0) ltv_bs
  FROM (SELECT day FROM spend_daily UNION DISTINCT SELECT day FROM total_ltv_daily UNION DISTINCT SELECT day FROM attr_daily) d
  LEFT JOIN spend_daily s USING (day) LEFT JOIN total_ltv_daily t USING (day) LEFT JOIN attr_daily a USING (day)),
fa AS (
  SELECT
    DATE_DIFF(pe.m_end, pe.as_of_date, DAY) AS m_rem, DATE_DIFF(pe.p_end, pe.as_of_date, DAY) AS q_rem,
    DATE_DIFF(pe.m_end, pe.attr_cap, DAY) AS m_rem_c, DATE_DIFF(pe.p_end, pe.attr_cap, DAY) AS q_rem_c,
    SUM(IF(d.day >= pe.m_start, spend_all, 0)) spend_all_mtd, SUM(spend_all) spend_all_qtd, SUM(IF(d.day > DATE_SUB(pe.as_of_date, INTERVAL 7 DAY), spend_all, 0)) / 7 spend_all_r7,
    SUM(IF(d.day >= pe.m_start, ltv_total, 0)) ltv_total_mtd, SUM(ltv_total) ltv_total_qtd, SUM(IF(d.day > DATE_SUB(pe.as_of_date, INTERVAL 7 DAY), ltv_total, 0)) / 7 ltv_total_r7,
    SUM(IF(d.day >= pe.m_start, spend_paid, 0)) spend_paid_mtd, SUM(spend_paid) spend_paid_qtd, SUM(IF(d.day > DATE_SUB(pe.as_of_date, INTERVAL 7 DAY), spend_paid, 0)) / 7 spend_paid_r7,
    SUM(IF(d.day >= pe.m_start, spend_inf, 0)) spend_inf_mtd, SUM(spend_inf) spend_inf_qtd, SUM(IF(d.day > DATE_SUB(pe.as_of_date, INTERVAL 7 DAY), spend_inf, 0)) / 7 spend_inf_r7,
    SUM(IF(d.day >= pe.m_start, spend_bs, 0)) spend_bs_mtd, SUM(spend_bs) spend_bs_qtd, SUM(IF(d.day > DATE_SUB(pe.as_of_date, INTERVAL 7 DAY), spend_bs, 0)) / 7 spend_bs_r7,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, ltv_paid, 0)) ltv_paid_mtd, SUM(IF(d.day <= pe.attr_cap, ltv_paid, 0)) ltv_paid_qtd, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, ltv_paid, 0)) / 7 ltv_paid_r7,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, ltv_inf, 0)) ltv_inf_mtd, SUM(IF(d.day <= pe.attr_cap, ltv_inf, 0)) ltv_inf_qtd, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, ltv_inf, 0)) / 7 ltv_inf_r7,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, ltv_bs, 0)) ltv_bs_mtd, SUM(IF(d.day <= pe.attr_cap, ltv_bs, 0)) ltv_bs_qtd, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, ltv_bs, 0)) / 7 ltv_bs_r7,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, ltv_total, 0)) ltv_total_mtd_c, SUM(IF(d.day <= pe.attr_cap, ltv_total, 0)) ltv_total_qtd_c, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, ltv_total, 0)) / 7 ltv_total_r7_c,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, spend_paid, 0)) spend_paid_mtd_c, SUM(IF(d.day <= pe.attr_cap, spend_paid, 0)) spend_paid_qtd_c, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, spend_paid, 0)) / 7 spend_paid_r7_c,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, spend_inf, 0)) spend_inf_mtd_c, SUM(IF(d.day <= pe.attr_cap, spend_inf, 0)) spend_inf_qtd_c, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, spend_inf, 0)) / 7 spend_inf_r7_c,
    SUM(IF(d.day >= pe.m_start AND d.day <= pe.attr_cap, spend_bs, 0)) spend_bs_mtd_c, SUM(IF(d.day <= pe.attr_cap, spend_bs, 0)) spend_bs_qtd_c, SUM(IF(d.day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY) AND d.day <= pe.attr_cap, spend_bs, 0)) / 7 spend_bs_r7_c
  FROM daily d CROSS JOIN pe
  GROUP BY pe.m_end, pe.as_of_date, pe.p_end, pe.attr_cap),
raw AS (
  SELECT 1 sort, 'Total marketing spend' metric, 'usd' unit, FALSE up_good, CAST(NULL AS FLOAT64) target,
    spend_all_mtd mtd_a, pm.spend_t mtd_p, spend_all_mtd + spend_all_r7 * m_rem mtd_j,
    spend_all_qtd qtd_a, pq.spend_t qtd_p, spend_all_qtd + spend_all_r7 * q_rem qtd_j FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 2, 'Total booked LTV (cohort m35)', 'usd', TRUE, NULL,
    ltv_total_mtd, pm.ltv_t, ltv_total_mtd + ltv_total_r7 * m_rem,
    ltv_total_qtd, pq.ltv_t, ltv_total_qtd + ltv_total_r7 * q_rem FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 3, 'Blended LTV/CAC (all spend)', 'ratio', TRUE, 1.5,
    SAFE_DIVIDE(ltv_total_mtd, spend_all_mtd), SAFE_DIVIDE(pm.ltv_t, pm.spend_t), SAFE_DIVIDE(ltv_total_mtd + ltv_total_r7 * m_rem, spend_all_mtd + spend_all_r7 * m_rem),
    SAFE_DIVIDE(ltv_total_qtd, spend_all_qtd), SAFE_DIVIDE(pq.ltv_t, pq.spend_t), SAFE_DIVIDE(ltv_total_qtd + ltv_total_r7 * q_rem, spend_all_qtd + spend_all_r7 * q_rem) FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 4, 'Paid spend', 'usd', FALSE, NULL,
    spend_paid_mtd, pm.paid_spend_t, spend_paid_mtd + spend_paid_r7 * m_rem,
    spend_paid_qtd, pq.paid_spend_t, spend_paid_qtd + spend_paid_r7 * q_rem FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 5, 'Paid booked LTV (attributed)', 'usd', TRUE, NULL,
    ltv_paid_mtd, pm.paid_ltv_t, ltv_paid_mtd + ltv_paid_r7 * m_rem_c,
    ltv_paid_qtd, pq.paid_ltv_t, ltv_paid_qtd + ltv_paid_r7 * q_rem_c FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 6, 'Paid LTV/CAC', 'ratio', TRUE, 0.85,
    SAFE_DIVIDE(ltv_paid_mtd, spend_paid_mtd_c), SAFE_DIVIDE(pm.paid_ltv_t, pm.paid_spend_t), SAFE_DIVIDE(ltv_paid_mtd + ltv_paid_r7 * m_rem_c, spend_paid_mtd_c + spend_paid_r7_c * m_rem_c),
    SAFE_DIVIDE(ltv_paid_qtd, spend_paid_qtd_c), SAFE_DIVIDE(pq.paid_ltv_t, pq.paid_spend_t), SAFE_DIVIDE(ltv_paid_qtd + ltv_paid_r7 * q_rem_c, spend_paid_qtd_c + spend_paid_r7_c * q_rem_c) FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 7, 'Influencer spend', 'usd', FALSE, NULL,
    spend_inf_mtd, pm.inf_spend_t, spend_inf_mtd + spend_inf_r7 * m_rem,
    spend_inf_qtd, pq.inf_spend_t, spend_inf_qtd + spend_inf_r7 * q_rem FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 8, 'Influencer booked LTV (attributed)', 'usd', TRUE, NULL,
    ltv_inf_mtd, pm.inf_ltv_t, ltv_inf_mtd + ltv_inf_r7 * m_rem_c,
    ltv_inf_qtd, pq.inf_ltv_t, ltv_inf_qtd + ltv_inf_r7 * q_rem_c FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 9, 'Influencer LTV/CAC', 'ratio', TRUE, NULL,
    SAFE_DIVIDE(ltv_inf_mtd, spend_inf_mtd_c), SAFE_DIVIDE(pm.inf_ltv_t, pm.inf_spend_t), SAFE_DIVIDE(ltv_inf_mtd + ltv_inf_r7 * m_rem_c, spend_inf_mtd_c + spend_inf_r7_c * m_rem_c),
    SAFE_DIVIDE(ltv_inf_qtd, spend_inf_qtd_c), SAFE_DIVIDE(pq.inf_ltv_t, pq.inf_spend_t), SAFE_DIVIDE(ltv_inf_qtd + ltv_inf_r7 * q_rem_c, spend_inf_qtd_c + spend_inf_r7_c * q_rem_c) FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 10, 'Branded search spend', 'usd', FALSE, NULL,
    spend_bs_mtd, pm.bs_spend_t, spend_bs_mtd + spend_bs_r7 * m_rem,
    spend_bs_qtd, pq.bs_spend_t, spend_bs_qtd + spend_bs_r7 * q_rem FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 11, 'Branded search booked LTV (attributed)', 'usd', TRUE, NULL,
    ltv_bs_mtd, pm.bs_ltv_t, ltv_bs_mtd + ltv_bs_r7 * m_rem_c,
    ltv_bs_qtd, pq.bs_ltv_t, ltv_bs_qtd + ltv_bs_r7 * q_rem_c FROM fa, plan_m pm, plan_q pq
  UNION ALL SELECT 12, 'Organic + other booked LTV (residual)', 'usd', TRUE, NULL,
    ltv_total_mtd_c - ltv_paid_mtd - ltv_inf_mtd - ltv_bs_mtd, pm.org_ltv_t, (ltv_total_mtd_c - ltv_paid_mtd - ltv_inf_mtd - ltv_bs_mtd) + (ltv_total_r7_c - ltv_paid_r7 - ltv_inf_r7 - ltv_bs_r7) * m_rem_c,
    ltv_total_qtd_c - ltv_paid_qtd - ltv_inf_qtd - ltv_bs_qtd, pq.org_ltv_t, (ltv_total_qtd_c - ltv_paid_qtd - ltv_inf_qtd - ltv_bs_qtd) + (ltv_total_r7_c - ltv_paid_r7 - ltv_inf_r7 - ltv_bs_r7) * q_rem_c FROM fa, plan_m pm, plan_q pq
)
SELECT sort, metric AS `Metric`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_a/1e3) ELSE FORMAT('%.2fx', mtd_a) END AS `MTD Actual`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_p/1e3) ELSE FORMAT('%.2fx', mtd_p) END AS `MTD Plan`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_j/1e3) ELSE FORMAT('%.2fx', mtd_j) END AS `MTD Projected`,
  CASE WHEN mtd_p IS NULL OR mtd_p = 0 THEN '—' ELSE CONCAT(
    CASE WHEN up_good THEN (CASE WHEN SAFE_DIVIDE(mtd_j, mtd_p) >= 1.0 THEN '🟢 ' WHEN SAFE_DIVIDE(mtd_j, mtd_p) >= 0.9 THEN '🟡 ' ELSE '🔴 ' END)
         ELSE (CASE WHEN SAFE_DIVIDE(mtd_j, mtd_p) BETWEEN 0.9 AND 1.1 THEN '🟢 ' WHEN SAFE_DIVIDE(mtd_j, mtd_p) BETWEEN 0.75 AND 1.25 THEN '🟡 ' ELSE '🔴 ' END) END,
    CAST(ROUND(SAFE_DIVIDE(mtd_j, mtd_p) * 100) AS INT64), '%') END AS `MTD Pace`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_a/1e3) ELSE FORMAT('%.2fx', qtd_a) END AS `QTD Actual`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_p/1e3) ELSE FORMAT('%.2fx', qtd_p) END AS `QTD Plan`,
  CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_j/1e3) ELSE FORMAT('%.2fx', qtd_j) END AS `QTD Projected`,
  CASE WHEN qtd_p IS NULL OR qtd_p = 0 THEN '—' ELSE CONCAT(
    CASE WHEN up_good THEN (CASE WHEN SAFE_DIVIDE(qtd_j, qtd_p) >= 1.0 THEN '🟢 ' WHEN SAFE_DIVIDE(qtd_j, qtd_p) >= 0.9 THEN '🟡 ' ELSE '🔴 ' END)
         ELSE (CASE WHEN SAFE_DIVIDE(qtd_j, qtd_p) BETWEEN 0.9 AND 1.1 THEN '🟢 ' WHEN SAFE_DIVIDE(qtd_j, qtd_p) BETWEEN 0.75 AND 1.25 THEN '🟡 ' ELSE '🔴 ' END) END,
    CAST(ROUND(SAFE_DIVIDE(qtd_j, qtd_p) * 100) AS INT64), '%') END AS `QTD Pace`,
  IF(target IS NULL, '—', FORMAT('%.2fx', target)) AS `Target`,
  (SELECT as_of_date FROM pe) AS as_of_date, (SELECT attr_cap FROM pe) AS attributed_through
FROM raw ORDER BY sort
```

## [6] [SQL] 02 Scorecard — paid funnel
_cell id `01a0c4ee-0c5a-723c-ac97-bea214d24697` · static `01a0c4ee-0c5a-723c-ac97-c036c44d9e60`_
```sql
-- output: tw_paid_funnel_scorecard  (BigQuery)
-- 02 Scorecard — TW paid funnel vs plan (the rows the team reviews weekly in the sheet's PAID block).
-- Source = attribution table, bucketed_channel = 'Paid' (Meta, Google, Apple Search non-brand, DSPs), attribution_date basis,
-- capped at attr_cap (today-5) because attribution bakes ~4 days. Spend = marketing_spend_daily bucketed_channel = 'Paid' on the SAME window.
-- Rates are SUM/SUM over the window. Volume rows project with the trailing-7-day run rate; ratio rows are ratios of projected components.
-- Plan: Sep = Q3 tracking tab Sep Target; Oct-Dec = [Conservative] Q4 tab (installs = spend/CPI; subs = installs x three rates).
-- QTD plan for rates is volume-weighted across the months in the period. Q3 QTD == Sep (Jul/Aug not paced).
WITH params AS (
  SELECT LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
               (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr`
                WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS as_of_date,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS attr_cap,
         DATE '2026-09-01' AS plan_start
),
pe AS (
  SELECT as_of_date, attr_cap, plan_start,
    GREATEST(DATE_TRUNC(as_of_date, QUARTER), plan_start) AS p_start,
    DATE_SUB(DATE_ADD(DATE_TRUNC(as_of_date, QUARTER), INTERVAL 1 QUARTER), INTERVAL 1 DAY) AS p_end,
    DATE_TRUNC(as_of_date, MONTH) AS m_start,
    LAST_DAY(as_of_date, MONTH) AS m_end
  FROM params
),
plan AS (
  -- SAME literals as tw_monthly_plan_targets. Update both.
  SELECT DATE '2026-09-01' AS mo, 180000.0 spend_t, 25714.0 installs_t, 7.00 cpi_t, 0.51 inst_su_t, 0.26 su_trial_t, 0.40 trial_conv_t, 1364.0 subs_t, 110.0 ltv_sub_t, 150027.0 ltv_t
  UNION ALL SELECT DATE '2026-10-01', 230000.0, 32857.0, 7.00, 0.46, 0.29, 0.40, 1753.0, 110.0, 192830.0
  UNION ALL SELECT DATE '2026-11-01', 230000.0, 32857.0, 7.00, 0.46, 0.29, 0.40, 1753.0, 110.0, 192830.0
  UNION ALL SELECT DATE '2026-12-01', 230000.0, 32857.0, 7.00, 0.46, 0.29, 0.39, 1709.0, 115.0, 196535.0
),
plan_m AS (SELECT p.* FROM plan p, pe WHERE p.mo = pe.m_start),
plan_q AS (SELECT SUM(spend_t) spend_t, SUM(installs_t) installs_t, SAFE_DIVIDE(SUM(spend_t), SUM(installs_t)) cpi_t,
  SAFE_DIVIDE(SUM(installs_t * inst_su_t), SUM(installs_t)) inst_su_t,
  SAFE_DIVIDE(SUM(installs_t * inst_su_t * su_trial_t), SUM(installs_t * inst_su_t)) su_trial_t,
  SAFE_DIVIDE(SUM(subs_t), SUM(installs_t * inst_su_t * su_trial_t)) trial_conv_t,
  SUM(subs_t) subs_t, SAFE_DIVIDE(SUM(ltv_t), SUM(subs_t)) ltv_sub_t, SUM(ltv_t) ltv_t
  FROM plan p, pe WHERE p.mo BETWEEN pe.p_start AND pe.p_end),
spend_daily AS (
  SELECT CAST(s.date_start AS DATE) AS day, SUM(s.spend) AS spend
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` s CROSS JOIN pe
  WHERE CAST(s.date_start AS DATE) BETWEEN pe.p_start AND pe.attr_cap AND s.bucketed_channel = 'Paid'
    AND COALESCE(s.spend, 0) > 0 AND `speak-v2-2a1f1`.UDFs.country_group_marketing(s.country) = 'Taiwan'
  GROUP BY day),
attr_daily AS (
  SELECT a.attribution_date AS day, SUM(a.installs) installs, SUM(a.signups) signups, SUM(a.trial_starts) trial_starts,
    SUM(a.trial_converts_and_initial_purchases) subs, SUM(a.ltv) ltv
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` a CROSS JOIN pe
  WHERE a.attribution_date BETWEEN pe.p_start AND pe.attr_cap AND a.bucketed_channel = 'Paid'
    AND `speak-v2-2a1f1`.UDFs.country_group_marketing(a.country) = 'Taiwan'
  GROUP BY day),
daily AS (
  SELECT d.day, COALESCE(s.spend, 0) spend, COALESCE(a.installs, 0) installs, COALESCE(a.signups, 0) signups,
    COALESCE(a.trial_starts, 0) trial_starts, COALESCE(a.subs, 0) subs, COALESCE(a.ltv, 0) ltv
  FROM (SELECT day FROM spend_daily UNION DISTINCT SELECT day FROM attr_daily) d
  LEFT JOIN spend_daily s USING (day) LEFT JOIN attr_daily a USING (day)),
fa AS (
  SELECT DATE_DIFF(pe.m_end, pe.attr_cap, DAY) m_rem, DATE_DIFF(pe.p_end, pe.attr_cap, DAY) q_rem,
    SUM(IF(day >= pe.m_start, spend, 0)) spend_mtd, SUM(spend) spend_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), spend, 0)) / 7 spend_r7,
    SUM(IF(day >= pe.m_start, installs, 0)) inst_mtd, SUM(installs) inst_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), installs, 0)) / 7 inst_r7,
    SUM(IF(day >= pe.m_start, signups, 0)) su_mtd, SUM(signups) su_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), signups, 0)) / 7 su_r7,
    SUM(IF(day >= pe.m_start, trial_starts, 0)) ts_mtd, SUM(trial_starts) ts_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), trial_starts, 0)) / 7 ts_r7,
    SUM(IF(day >= pe.m_start, subs, 0)) subs_mtd, SUM(subs) subs_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), subs, 0)) / 7 subs_r7,
    SUM(IF(day >= pe.m_start, ltv, 0)) ltv_mtd, SUM(ltv) ltv_qtd, SUM(IF(day > DATE_SUB(pe.attr_cap, INTERVAL 7 DAY), ltv, 0)) / 7 ltv_r7
  FROM daily CROSS JOIN pe GROUP BY pe.m_end, pe.attr_cap, pe.p_end),
proj AS (
  SELECT *, spend_mtd + spend_r7 * m_rem spend_mj, spend_qtd + spend_r7 * q_rem spend_qj,
    inst_mtd + inst_r7 * m_rem inst_mj, inst_qtd + inst_r7 * q_rem inst_qj,
    su_mtd + su_r7 * m_rem su_mj, su_qtd + su_r7 * q_rem su_qj,
    ts_mtd + ts_r7 * m_rem ts_mj, ts_qtd + ts_r7 * q_rem ts_qj,
    subs_mtd + subs_r7 * m_rem subs_mj, subs_qtd + subs_r7 * q_rem subs_qj,
    ltv_mtd + ltv_r7 * m_rem ltv_mj, ltv_qtd + ltv_r7 * q_rem ltv_qj
  FROM fa),
raw AS (
  SELECT 1 sort, 'Paid spend (attributed window)' metric, 'usd' unit, FALSE up_good, spend_mtd mtd_a, pm.spend_t mtd_p, spend_mj mtd_j, spend_qtd qtd_a, pq.spend_t qtd_p, spend_qj qtd_j FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 2, 'Installs', 'count', TRUE, inst_mtd, pm.installs_t, inst_mj, inst_qtd, pq.installs_t, inst_qj FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 3, 'CPI', 'usd2', FALSE, SAFE_DIVIDE(spend_mtd, inst_mtd), pm.cpi_t, SAFE_DIVIDE(spend_mj, inst_mj), SAFE_DIVIDE(spend_qtd, inst_qtd), pq.cpi_t, SAFE_DIVIDE(spend_qj, inst_qj) FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 4, 'Install → Signup', 'pct', TRUE, SAFE_DIVIDE(su_mtd, inst_mtd), pm.inst_su_t, SAFE_DIVIDE(su_mj, inst_mj), SAFE_DIVIDE(su_qtd, inst_qtd), pq.inst_su_t, SAFE_DIVIDE(su_qj, inst_qj) FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 5, 'Signup → Trial start', 'pct', TRUE, SAFE_DIVIDE(ts_mtd, su_mtd), pm.su_trial_t, SAFE_DIVIDE(ts_mj, su_mj), SAFE_DIVIDE(ts_qtd, su_qtd), pq.su_trial_t, SAFE_DIVIDE(ts_qj, su_qj) FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 6, 'Trial start → Conversion', 'pct', TRUE, SAFE_DIVIDE(subs_mtd, ts_mtd), pm.trial_conv_t, SAFE_DIVIDE(subs_mj, ts_mj), SAFE_DIVIDE(subs_qtd, ts_qtd), pq.trial_conv_t, SAFE_DIVIDE(subs_qj, ts_qj) FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 7, 'New subscribers (trial converts + initial purchases)', 'count', TRUE, subs_mtd, pm.subs_t, subs_mj, subs_qtd, pq.subs_t, subs_qj FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 8, 'LTV per subscriber', 'usd2', TRUE, SAFE_DIVIDE(ltv_mtd, subs_mtd), pm.ltv_sub_t, SAFE_DIVIDE(ltv_mj, subs_mj), SAFE_DIVIDE(ltv_qtd, subs_qtd), pq.ltv_sub_t, SAFE_DIVIDE(ltv_qj, subs_qj) FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 9, 'Paid booked LTV', 'usd', TRUE, ltv_mtd, pm.ltv_t, ltv_mj, ltv_qtd, pq.ltv_t, ltv_qj FROM proj, plan_m pm, plan_q pq
  UNION ALL SELECT 10, 'Paid LTV/CAC (target 0.85x)', 'ratio', TRUE, SAFE_DIVIDE(ltv_mtd, spend_mtd), SAFE_DIVIDE(pm.ltv_t, pm.spend_t), SAFE_DIVIDE(ltv_mj, spend_mj), SAFE_DIVIDE(ltv_qtd, spend_qtd), SAFE_DIVIDE(pq.ltv_t, pq.spend_t), SAFE_DIVIDE(ltv_qj, spend_qj) FROM proj, plan_m pm, plan_q pq
),
fmt AS (
  SELECT *,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_a/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', mtd_a) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(mtd_a) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', mtd_a*100) ELSE FORMAT('%.2fx', mtd_a) END f_mtd_a,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_p/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', mtd_p) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(mtd_p) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', mtd_p*100) ELSE FORMAT('%.2fx', mtd_p) END f_mtd_p,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', mtd_j/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', mtd_j) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(mtd_j) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', mtd_j*100) ELSE FORMAT('%.2fx', mtd_j) END f_mtd_j,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_a/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', qtd_a) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(qtd_a) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', qtd_a*100) ELSE FORMAT('%.2fx', qtd_a) END f_qtd_a,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_p/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', qtd_p) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(qtd_p) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', qtd_p*100) ELSE FORMAT('%.2fx', qtd_p) END f_qtd_p,
    CASE unit WHEN 'usd' THEN FORMAT('$%.0fK', qtd_j/1e3) WHEN 'usd2' THEN FORMAT('$%.2f', qtd_j) WHEN 'count' THEN FORMAT("%'d", CAST(ROUND(qtd_j) AS INT64)) WHEN 'pct' THEN FORMAT('%.1f%%', qtd_j*100) ELSE FORMAT('%.2fx', qtd_j) END f_qtd_j,
    SAFE_DIVIDE(mtd_j, mtd_p) r_m, SAFE_DIVIDE(qtd_j, qtd_p) r_q
  FROM raw)
SELECT sort, metric AS `Metric`, f_mtd_a AS `MTD Actual`, f_mtd_p AS `MTD Plan`, f_mtd_j AS `MTD Projected`,
  CASE WHEN r_m IS NULL THEN '—' ELSE CONCAT(
    CASE WHEN up_good THEN (CASE WHEN r_m >= 1.0 THEN '🟢 ' WHEN r_m >= 0.9 THEN '🟡 ' ELSE '🔴 ' END)
         ELSE (CASE WHEN r_m BETWEEN 0.9 AND 1.1 THEN '🟢 ' WHEN r_m BETWEEN 0.75 AND 1.25 THEN '🟡 ' ELSE '🔴 ' END) END,
    CAST(ROUND(r_m * 100) AS INT64), '%') END AS `MTD Pace`,
  f_qtd_a AS `QTD Actual`, f_qtd_p AS `QTD Plan`, f_qtd_j AS `QTD Projected`,
  CASE WHEN r_q IS NULL THEN '—' ELSE CONCAT(
    CASE WHEN up_good THEN (CASE WHEN r_q >= 1.0 THEN '🟢 ' WHEN r_q >= 0.9 THEN '🟡 ' ELSE '🔴 ' END)
         ELSE (CASE WHEN r_q BETWEEN 0.9 AND 1.1 THEN '🟢 ' WHEN r_q BETWEEN 0.75 AND 1.25 THEN '🟡 ' ELSE '🔴 ' END) END,
    CAST(ROUND(r_q * 100) AS INT64), '%') END AS `QTD Pace`,
  (SELECT attr_cap FROM pe) AS attributed_through
FROM fmt ORDER BY sort
```

## [7] [SQL] TW channel daily (spend + attributed)
_cell id `01a0c4ef-596a-74e0-8e91-8caf5f90e5e4` · static `01a0c4ef-596a-74e0-8e91-914e08883e09`_
```sql
-- output: tw_channel_daily  (BigQuery)
-- ============================================================================
-- DATASET: tw_channel_daily  -- day x bucketed_channel: spend + attributed outcomes (TW)
-- spend      = marketing_spend_daily (all TW rows; bucketed_channel from the table), through as_of_date.
-- attributed = marketing_attribution_aggregate_attribution_date_cohort by its bucketed_channel, attribution_date basis,
--              through attr_cap = today-5 (Asia/Taipei) because attribution bakes ~4 days. Days after attr_cap carry
--              spend only; attributed_complete = FALSE flags them so consumers never divide full spend by empty LTV.
-- ltv = realised attributed LTV (the sheet / Mode basis); forecasted_ltv emitted alongside for the Blended section.
-- Window: 2026-06-01 onward (trailing windows + flight paths). Feeds tw_trailing_7d, tw_flight_path_source, media mix.
-- ============================================================================
WITH pe AS (
  SELECT LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
               (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr`
                WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS as_of_date,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS attr_cap,
         DATE '2026-06-01' AS start_date
),
spend AS (
  SELECT CAST(s.date_start AS DATE) AS day, s.bucketed_channel AS channel, SUM(s.spend) AS spend
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` s CROSS JOIN pe
  WHERE CAST(s.date_start AS DATE) BETWEEN pe.start_date AND pe.as_of_date
    AND COALESCE(s.spend, 0) > 0 AND `speak-v2-2a1f1`.UDFs.country_group_marketing(s.country) = 'Taiwan'
  GROUP BY 1, 2),
attr AS (
  SELECT a.attribution_date AS day, a.bucketed_channel AS channel,
    SUM(a.ltv) AS ltv, SUM(a.forecasted_ltv) AS forecasted_ltv, SUM(a.installs) AS installs, SUM(a.signups) AS signups,
    SUM(a.trial_starts) AS trial_starts, SUM(a.trial_converts_and_initial_purchases) AS conversions
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` a CROSS JOIN pe
  WHERE a.attribution_date BETWEEN pe.start_date AND pe.attr_cap
    AND `speak-v2-2a1f1`.UDFs.country_group_marketing(a.country) = 'Taiwan'
  GROUP BY 1, 2)
SELECT COALESCE(s.day, a.day) AS day, COALESCE(s.channel, a.channel, 'Unknown') AS channel,
  COALESCE(s.spend, 0) AS spend, COALESCE(a.ltv, 0) AS ltv, COALESCE(a.forecasted_ltv, 0) AS forecasted_ltv,
  COALESCE(a.installs, 0) AS installs, COALESCE(a.signups, 0) AS signups, COALESCE(a.trial_starts, 0) AS trial_starts, COALESCE(a.conversions, 0) AS conversions,
  COALESCE(s.day, a.day) <= pe.attr_cap AS attributed_complete, pe.as_of_date, pe.attr_cap
FROM spend s FULL JOIN attr a USING (day, channel) CROSS JOIN pe
ORDER BY day, channel
```

## [8] [SQL] TW total LTV daily (cohort m35 + forecasted)
_cell id `01a0c4ef-8bb3-707a-a0a4-277441f5b2fb` · static `01a0c4ef-8bb3-707a-a0a4-293ef8f923b0`_
```sql
-- output: tw_total_ltv_daily  (BigQuery)
-- ============================================================================
-- DATASET: tw_total_ltv_daily  -- TW total booked LTV by day, two bases side by side
-- ltv_booked            = cohort_ltv_daily_marketing.revenue_ltv @ m35 by first_transaction_date (the sheet / Mode
--                         "Total Booked LTV" basis; lag-free at cohort start). THE pacing basis for total LTV.
-- forecasted_ltv_cohort = same table, forecasted_ltv (trial-start anchored).
-- new_ltv_forecasted    = transaction_ltv_forecasted.forecasted_ltv by ds (populated for 100% of rows at trial start;
--                         the US "New LTV Forecasted" KPI). new_ltv_booked_txn = booked_ltv (fills ~7 days late).
-- new_payers            = cohort users_initial (paid-date anchored). trial_starts_ltv_table = Trial Start rows in the LTV table.
-- Window: 2026-06-01 -> as_of_date. Newest day is partially loaded exactly like the LTV tables themselves.
-- ============================================================================
WITH pe AS (
  SELECT LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
               (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr`
                WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS as_of_date,
         DATE '2026-06-01' AS start_date
),
cohort AS (
  SELECT c.first_transaction_date AS day, SUM(c.revenue_ltv) AS ltv_booked, SUM(c.forecasted_ltv) AS forecasted_ltv_cohort, SUM(c.users_initial) AS new_payers
  FROM `speak-v2-2a1f1.analytics.cohort_ltv_daily_marketing` c CROSS JOIN pe
  WHERE c.first_transaction_date BETWEEN pe.start_date AND pe.as_of_date AND c.country = 'Taiwan' AND c.month_index = 35
  GROUP BY 1),
txn AS (
  SELECT t.ds AS day, SUM(t.forecasted_ltv) AS new_ltv_forecasted, SUM(t.booked_ltv) AS new_ltv_booked_txn,
    COUNTIF(t.type = 'Trial Start') AS trial_starts_ltv_table
  FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` t CROSS JOIN pe
  WHERE t.country_group_marketing = 'Taiwan' AND t.ds BETWEEN pe.start_date AND pe.as_of_date
  GROUP BY 1)
SELECT COALESCE(c.day, x.day) AS day, COALESCE(c.ltv_booked, 0) AS ltv_booked, COALESCE(c.forecasted_ltv_cohort, 0) AS forecasted_ltv_cohort,
  COALESCE(c.new_payers, 0) AS new_payers, COALESCE(x.new_ltv_forecasted, 0) AS new_ltv_forecasted, COALESCE(x.new_ltv_booked_txn, 0) AS new_ltv_booked_txn,
  COALESCE(x.trial_starts_ltv_table, 0) AS trial_starts_ltv_table
FROM cohort c FULL JOIN txn x USING (day) ORDER BY day
```

## [9] [SQL] ARR KPI daily base
_cell id `01a0c4ef-c464-767f-8432-7c59bb501105` · static `01a0c4ef-c464-767f-8432-83d412d4df8d`_
```sql
-- output: tw_arr_kpi_daily_base  (BigQuery)
-- ARR KPI daily base (TW) — verbatim port of the US cell with country_group = 'Taiwan' and Asia/Taipei as-of.
-- Exit ARR / New ARR / churn components from plan_type_daily_arr; New LTV (forecasted) from transaction_ltv_forecasted
-- (forecasted_ltv is populated at trial start for 100% of rows, so it is lag-free; booked_ltv fills ~7 days late).
-- Window from 2026-07-01 (enough for the trailing 5-week comparisons). Heavy scan: keep the window short.
WITH params AS (
    SELECT DATE '2026-07-01' AS start_date,
        LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
              (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr` WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS end_date
),
arr_daily AS (
    SELECT day,
        SUM(arr_usd_gross_less_taxes) AS exit_arr,
        SUM(first_time_purchaser_arr_less_taxes) AS new_arr,
        SUM(expansion_arr_less_taxes) AS expansion_arr,
        SUM(churned_arr_less_taxes) AS churned_arr,
        SUM(churn_refund_arr_less_taxes) AS churn_refund_arr,
        SUM(contraction_arr_less_taxes) AS contraction_arr,
        SUM(resurrection_arr_less_taxes) AS resurrected_arr,
        SUM(fx_change_arr_final) AS fx_change_arr,
        COUNT(DISTINCT first_time_purchaser_arr_users) AS new_subscribers,
        COUNT(DISTINCT churned_arr_users) AS churned_subscribers,
        COUNT(DISTINCT subscribers) AS active_subscribers
    FROM `speak-v2-2a1f1.analytics.plan_type_daily_arr` CROSS JOIN params
    WHERE country_group = 'Taiwan' AND ds BETWEEN DATE_SUB(params.start_date, INTERVAL 1 DAY) AND params.end_date
    GROUP BY day
),
ltv_daily AS (
    SELECT ds AS day, SUM(forecasted_ltv) AS new_ltv_booked
    FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` CROSS JOIN params
    WHERE country_group_marketing = 'Taiwan' AND ds BETWEEN params.start_date AND params.end_date
    GROUP BY ds
),
daily_with_lags AS (
    SELECT d.*, LAG(d.exit_arr) OVER (ORDER BY d.day) AS beginning_arr,
        d.exit_arr - LAG(d.exit_arr) OVER (ORDER BY d.day) AS net_incremental_arr,
        d.churned_arr + d.churn_refund_arr AS gross_churn_arr,
        COALESCE(l.new_ltv_booked, 0) AS new_ltv_booked
    FROM arr_daily AS d LEFT JOIN ltv_daily AS l ON d.day = l.day
)
SELECT day, exit_arr, beginning_arr, net_incremental_arr, new_arr, gross_churn_arr, resurrected_arr, new_ltv_booked, new_subscribers, active_subscribers,
    expansion_arr, churned_arr, churn_refund_arr, contraction_arr, fx_change_arr,
    net_incremental_arr - new_arr AS churn_arr,
    net_incremental_arr - (new_arr + expansion_arr + churned_arr + churn_refund_arr + contraction_arr + resurrected_arr + fx_change_arr) AS arr_reconciliation_residual
FROM daily_with_lags
WHERE day BETWEEN (SELECT start_date FROM params) AND (SELECT end_date FROM params)
ORDER BY day
```

## [10] [SQL] ARR KPI total trial starts daily
_cell id `01a0c4ef-dd30-753c-aba8-afb47435296d` · static `01a0c4ef-dd30-753c-aba8-b291c714c03f`_
```sql
-- output: tw_trial_starts_daily  (BigQuery)
-- Total trial starts per day (TW), all platforms — port of the US cell. canonical.users country = 'TW', no employees, no B2B.
WITH params AS (
    SELECT DATE '2026-06-01' AS start_date,
        LEAST(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 DAY),
              (SELECT MAX(day) FROM `speak-v2-2a1f1.analytics.user_daily_arr` WHERE ds BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 5 DAY) AND CURRENT_DATE())) AS end_date
),
tw_users AS (
    SELECT id AS user_id FROM `speak-v2-2a1f1.canonical.users`
    WHERE country = 'TW' AND is_employee = FALSE AND organization_id IS NULL
)
SELECT DATE(e.timestamp, 'Asia/Taipei') AS day, COUNT(DISTINCT e.user_id) AS total_trial_starts
FROM `speak-v2-2a1f1.speak_server.speak_payments_trial_started` AS e
INNER JOIN tw_users AS u ON e.user_id = u.user_id
CROSS JOIN params
WHERE DATE(e.timestamp, 'Asia/Taipei') BETWEEN params.start_date AND params.end_date
    AND e.payment_platform IN ('APP_STORE', 'PLAY_STORE', 'paddle', 'stripe')
GROUP BY day ORDER BY day
```

## [11] [SQL] Trailing 7d, daily avg by week
_cell id `01a0c4f0-8a34-7728-8466-74acb64620a3` · static `01a0c4f0-8a34-7728-8466-78b8be9b4701`_
```sql
-- output: tw_trailing_7d  (DuckDB dataframe SQL)
-- Trailing 7-day daily averages vs the prior 7d, the week 2 weeks ago and the week 4 weeks ago (TW). Port of the US cell.
-- Flows (ARR, LTV, spend, trials, subs) = window SUM / 7. Stock (Exit ARR) = AVG of the daily level. Ratios = window sum / window sum.
-- TWO ANCHORS: ARR / spend / total-LTV rows anchor at the ARR base's last day; attributed (paid) rows anchor at the
-- attribution cap (today-5) so their last 7 days are fully baked. Anchors are emitted as columns.
WITH b AS (SELECT CAST(MAX(day) AS DATE) AS max_day FROM tw_arr_kpi_daily_base),
bc AS (SELECT CAST(MAX(day) AS DATE) AS max_day FROM tw_channel_daily WHERE attributed_complete),
periods AS (
  SELECT 1 AS rk, (max_day - INTERVAL '6 days')::DATE AS ps, max_day::DATE AS pe FROM b
  UNION ALL SELECT 2, (max_day - INTERVAL '13 days')::DATE, (max_day - INTERVAL '7 days')::DATE FROM b
  UNION ALL SELECT 3, (max_day - INTERVAL '20 days')::DATE, (max_day - INTERVAL '14 days')::DATE FROM b
  UNION ALL SELECT 5, (max_day - INTERVAL '34 days')::DATE, (max_day - INTERVAL '28 days')::DATE FROM b),
periods_c AS (
  SELECT 1 AS rk, (max_day - INTERVAL '6 days')::DATE AS ps, max_day::DATE AS pe FROM bc
  UNION ALL SELECT 2, (max_day - INTERVAL '13 days')::DATE, (max_day - INTERVAL '7 days')::DATE FROM bc
  UNION ALL SELECT 3, (max_day - INTERVAL '20 days')::DATE, (max_day - INTERVAL '14 days')::DATE FROM bc
  UNION ALL SELECT 5, (max_day - INTERVAL '34 days')::DATE, (max_day - INTERVAL '28 days')::DATE FROM bc),
arr AS (
  SELECT p.rk, AVG(d.exit_arr) AS exit_arr, SUM(d.new_arr) / 7.0 AS new_arr, SUM(d.churn_arr) / 7.0 AS churn_arr,
    SUM(d.net_incremental_arr) / 7.0 AS net_arr, SUM(d.new_ltv_booked) / 7.0 AS new_ltv_fcst, SUM(d.new_subscribers) / 7.0 AS initial_purchases
  FROM periods p LEFT JOIN tw_arr_kpi_daily_base d ON CAST(d.day AS DATE) BETWEEN p.ps AND p.pe GROUP BY p.rk),
tot AS (
  SELECT p.rk, SUM(t.ltv_booked) / 7.0 AS ltv_booked, SUM(t.ltv_booked) AS ltv_booked_sum
  FROM periods p LEFT JOIN tw_total_ltv_daily t ON CAST(t.day AS DATE) BETWEEN p.ps AND p.pe GROUP BY p.rk),
sp AS (
  SELECT p.rk, SUM(c.spend) / 7.0 AS spend_all, SUM(c.spend) AS spend_all_sum,
    SUM(CASE WHEN c.channel = 'Paid' THEN c.spend ELSE 0 END) / 7.0 AS spend_paid
  FROM periods p LEFT JOIN tw_channel_daily c ON CAST(c.day AS DATE) BETWEEN p.ps AND p.pe GROUP BY p.rk),
pd AS (
  SELECT p.rk, SUM(CASE WHEN c.channel = 'Paid' THEN c.ltv ELSE 0 END) AS paid_ltv_sum,
    SUM(CASE WHEN c.channel = 'Paid' THEN c.spend ELSE 0 END) AS paid_spend_sum_c,
    SUM(CASE WHEN c.channel = 'Paid' THEN c.installs ELSE 0 END) / 7.0 AS paid_installs,
    SUM(CASE WHEN c.channel = 'Paid' THEN c.conversions ELSE 0 END) / 7.0 AS paid_subs
  FROM periods_c p LEFT JOIN tw_channel_daily c ON CAST(c.day AS DATE) BETWEEN p.ps AND p.pe GROUP BY p.rk),
tr AS (
  SELECT p.rk, SUM(t.total_trial_starts) / 7.0 AS trials
  FROM periods p LEFT JOIN tw_trial_starts_daily t ON CAST(t.day AS DATE) BETWEEN p.ps AND p.pe GROUP BY p.rk),
w AS (SELECT * FROM arr JOIN tot USING (rk) JOIN sp USING (rk) JOIN pd USING (rk) JOIN tr USING (rk)),
ml AS (
  SELECT 'Exit ARR' AS metric, 1 AS sort, rk, exit_arr::DOUBLE AS v FROM w
  UNION ALL SELECT 'New ARR', 2, rk, new_arr::DOUBLE FROM w
  UNION ALL SELECT 'Churn ARR', 3, rk, churn_arr::DOUBLE FROM w
  UNION ALL SELECT 'Net incremental ARR', 4, rk, net_arr::DOUBLE FROM w
  UNION ALL SELECT 'Total booked LTV (cohort m35)', 5, rk, ltv_booked::DOUBLE FROM w
  UNION ALL SELECT 'New LTV forecasted (trial start)', 6, rk, new_ltv_fcst::DOUBLE FROM w
  UNION ALL SELECT 'Total marketing spend', 7, rk, spend_all::DOUBLE FROM w
  UNION ALL SELECT 'Blended LTV/CAC', 8, rk, (ltv_booked_sum / NULLIF(spend_all_sum, 0))::DOUBLE FROM w
  UNION ALL SELECT 'Paid spend', 9, rk, spend_paid::DOUBLE FROM w
  UNION ALL SELECT 'Paid attributed LTV', 10, rk, (paid_ltv_sum / 7.0)::DOUBLE FROM w
  UNION ALL SELECT 'Paid LTV/CAC', 11, rk, (paid_ltv_sum / NULLIF(paid_spend_sum_c, 0))::DOUBLE FROM w
  UNION ALL SELECT 'Paid installs', 12, rk, paid_installs::DOUBLE FROM w
  UNION ALL SELECT 'Paid new subscribers', 13, rk, paid_subs::DOUBLE FROM w
  UNION ALL SELECT 'Total trial starts', 14, rk, trials::DOUBLE FROM w
  UNION ALL SELECT 'Initial purchases (all)', 15, rk, initial_purchases::DOUBLE FROM w),
pv AS (
  SELECT metric, sort,
    MAX(CASE WHEN rk = 1 THEN v END) AS v1, MAX(CASE WHEN rk = 2 THEN v END) AS v2,
    MAX(CASE WHEN rk = 3 THEN v END) AS v3, MAX(CASE WHEN rk = 5 THEN v END) AS v5
  FROM ml GROUP BY metric, sort)
SELECT metric AS "Metric",
  CASE
    WHEN metric = 'Exit ARR' THEN '$' || printf('%.2fM', v1 / 1000000.0)
    WHEN metric IN ('Blended LTV/CAC', 'Paid LTV/CAC') THEN printf('%.2fx', v1)
    WHEN metric IN ('Paid installs', 'Paid new subscribers', 'Total trial starts', 'Initial purchases (all)') THEN printf('%.0f', v1)
    WHEN v1 < 0 THEN '-$' || printf('%.1fK', ABS(v1) / 1000.0)
    ELSE '$' || printf('%.1fK', v1 / 1000.0) END AS "Last 7d (avg/day)",
  printf('%+.1f%%', 100.0 * (v1 - v2) / NULLIF(ABS(v2), 0)) AS "vs Prev 7d",
  printf('%+.1f%%', 100.0 * (v1 - v3) / NULLIF(ABS(v3), 0)) AS "vs 2wk prior",
  printf('%+.1f%%', 100.0 * (v1 - v5) / NULLIF(ABS(v5), 0)) AS "vs 4wk prior",
  CASE WHEN sort BETWEEN 10 AND 13 THEN (SELECT max_day FROM bc) ELSE (SELECT max_day FROM b) END AS window_end
FROM pv ORDER BY sort
```

## [12] [SQL] Flight path source (cumulative actual vs plan)
_cell id `01a0c4f0-f76e-7253-a60d-2fda0c1e696e` · static `01a0c4f0-f76e-7253-a60d-3339895abb48`_
```sql
-- output: tw_flight_path_source  (DuckDB dataframe SQL)
-- Flight path (TW): cumulative actual vs plan across the pacing period, with three projection lenses and a low/high band.
-- Port of the US cell. Period = current quarter, but never before 2026-09-01 (Jul/Aug are not paced): Q3 == Sep.
-- Metrics: Total Spend, Total LTV Booked (cohort m35), Paid Spend, Paid LTV Booked (attributed, capped at today-5 so its
-- as_of_day is earlier than the spend metrics'). Plan = tw_monthly_plan_targets spread evenly across each month's days.
WITH metric_map AS (
    SELECT 'Total Spend' AS metric, 'total_spend_target' AS target_column
    UNION ALL SELECT 'Total LTV Booked', 'total_ltv_target'
    UNION ALL SELECT 'Paid Spend', 'paid_spend_target'
    UNION ALL SELECT 'Paid LTV Booked', 'paid_ltv_target'
),
bounds AS (
    SELECT GREATEST(CAST(DATE_TRUNC('quarter', MAX(CAST(day AS DATE))) AS DATE), DATE '2026-09-01') AS q_start,
           CAST(DATE_TRUNC('quarter', MAX(CAST(day AS DATE))) + INTERVAL '3 months' - INTERVAL '1 day' AS DATE) AS q_end
    FROM tw_arr_kpi_daily_base
),
day_spine AS (
    SELECT (b.q_start + g.i::INTEGER)::DATE AS day
    FROM bounds b CROSS JOIN range(0, 100) AS g(i)
    WHERE g.i::INTEGER <= DATE_DIFF('day', b.q_start, b.q_end)
),
plan_daily AS (
    SELECT d.day, m.metric,
        CASE m.target_column
            WHEN 'total_spend_target' THEN p.total_spend_target
            WHEN 'total_ltv_target' THEN p.total_ltv_target
            WHEN 'paid_spend_target' THEN p.paid_spend_target
            WHEN 'paid_ltv_target' THEN p.paid_ltv_target END
        / DATE_DIFF('day', CAST(p.month_start AS DATE), (CAST(p.month_start AS DATE) + INTERVAL '1 month')::DATE) AS plan_value
    FROM day_spine d CROSS JOIN metric_map m
    INNER JOIN tw_monthly_plan_targets p ON CAST(DATE_TRUNC('month', d.day) AS DATE) = CAST(p.month_start AS DATE)
),
actual_daily AS (
    SELECT CAST(day AS DATE) AS day, 'Total Spend' AS metric, SUM(spend) AS actual_value FROM tw_channel_daily GROUP BY 1
    UNION ALL SELECT CAST(day AS DATE), 'Total LTV Booked', SUM(ltv_booked) FROM tw_total_ltv_daily GROUP BY 1
    UNION ALL SELECT CAST(day AS DATE), 'Paid Spend', SUM(spend) FROM tw_channel_daily WHERE channel = 'Paid' GROUP BY 1
    UNION ALL SELECT CAST(day AS DATE), 'Paid LTV Booked', SUM(ltv) FROM tw_channel_daily WHERE channel = 'Paid' AND attributed_complete GROUP BY 1
),
actual_in_period AS (
    SELECT a.* FROM actual_daily a, bounds b WHERE a.day BETWEEN b.q_start AND b.q_end
),
metric_as_of AS (
    SELECT metric, MAX(day) AS as_of_day FROM actual_in_period WHERE actual_value IS NOT NULL GROUP BY metric
),
actual_cumulative AS (
    SELECT p.day, p.metric,
        SUM(a.actual_value) OVER (PARTITION BY p.metric ORDER BY p.day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS actual_cumulative,
        SUM(p.plan_value)  OVER (PARTITION BY p.metric ORDER BY p.day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS plan_cumulative
    FROM plan_daily p LEFT JOIN actual_in_period a ON p.day = a.day AND p.metric = a.metric
),
run_rate_inputs AS (
    SELECT a.metric, m.as_of_day, b.q_start,
        SUM(CASE WHEN CAST(DATE_TRUNC('month', a.day) AS DATE) = CAST(DATE_TRUNC('month', m.as_of_day) AS DATE) THEN a.actual_value ELSE 0 END) AS current_month_actual,
        DATE_DIFF('day', CAST(DATE_TRUNC('month', m.as_of_day) AS DATE), m.as_of_day) + 1 AS current_month_days_elapsed,
        SUM(CASE WHEN a.day BETWEEN GREATEST(b.q_start, (m.as_of_day - INTERVAL '6 days')::DATE) AND m.as_of_day THEN a.actual_value ELSE 0 END) AS trailing_7d_actual,
        LEAST(7, DATE_DIFF('day', b.q_start, m.as_of_day) + 1) AS trailing_7d_denominator,
        SUM(CASE WHEN a.day = m.as_of_day THEN a.actual_value ELSE 0 END) AS raw_yesterday_value
    FROM actual_in_period a INNER JOIN metric_as_of m ON a.metric = m.metric CROSS JOIN bounds b
    GROUP BY a.metric, m.as_of_day, b.q_start
),
run_rates AS (
    SELECT metric, as_of_day,
        current_month_actual / NULLIF(current_month_days_elapsed, 0) AS current_month_avg,
        trailing_7d_actual / NULLIF(trailing_7d_denominator, 0) AS trailing_7d_avg,
        CASE WHEN DATE_DIFF('day', q_start, as_of_day) + 1 >= 2 THEN raw_yesterday_value ELSE current_month_actual / NULLIF(current_month_days_elapsed, 0) END AS yesterday_value
    FROM run_rate_inputs
),
as_of_actual AS (
    SELECT c.metric, r.as_of_day, c.actual_cumulative AS as_of_actual_cumulative, r.current_month_avg, r.trailing_7d_avg, r.yesterday_value
    FROM actual_cumulative c INNER JOIN run_rates r ON c.metric = r.metric AND c.day = r.as_of_day
),
projection AS (
    SELECT c.day, c.metric, c.plan_cumulative, a.as_of_day,
        CASE WHEN c.day <= a.as_of_day THEN c.actual_cumulative END AS actual_cumulative,
        CASE WHEN c.day >= a.as_of_day THEN a.as_of_actual_cumulative + a.current_month_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0) END AS projection_current_month_avg,
        CASE WHEN c.day >= a.as_of_day THEN a.as_of_actual_cumulative + a.trailing_7d_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0) END AS projection_7d_avg,
        CASE WHEN c.day >= a.as_of_day THEN a.as_of_actual_cumulative + a.yesterday_value * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0) END AS projection_yesterday,
        CASE WHEN c.day >= a.as_of_day THEN LEAST(
            a.as_of_actual_cumulative + a.current_month_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0),
            a.as_of_actual_cumulative + a.trailing_7d_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0),
            a.as_of_actual_cumulative + a.yesterday_value * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0)) END AS projection_low,
        CASE WHEN c.day >= a.as_of_day THEN GREATEST(
            a.as_of_actual_cumulative + a.current_month_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0),
            a.as_of_actual_cumulative + a.trailing_7d_avg * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0),
            a.as_of_actual_cumulative + a.yesterday_value * GREATEST(DATE_DIFF('day', a.as_of_day, c.day), 0)) END AS projection_high
    FROM actual_cumulative c INNER JOIN as_of_actual a ON c.metric = a.metric
)
SELECT * FROM projection ORDER BY metric, day
```

## [13] [CODE] Chart — flight paths (cumulative actual vs plan)
_cell id `01a0c4f1-3419-70d8-a056-47faf565dfda` · static `01a0c4f1-3419-70d8-a056-4969db8eac3f`_
```python
# Flight paths: 2x2 small multiples, one axis each (Total Spend, Total LTV Booked, Paid Spend, Paid LTV Booked).
# Actual = solid blue, Plan = dashed grey, projection (7d avg) = orange dashed, low/high band = translucent orange.
# Plotly code cell (native charts can be bound to tw_flight_path_source later; keep the dataframe name stable).
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_fp = tw_flight_path_source.copy()
_fp["day"] = pd.to_datetime(_fp["day"])
_metrics = ["Total Spend", "Total LTV Booked", "Paid Spend", "Paid LTV Booked"]
_C_ACT, _C_PLAN, _C_PROJ, _C_BAND = "#2a78d6", "#52514e", "#eb6834", "rgba(235,104,52,0.15)"

fig = make_subplots(rows=2, cols=2, subplot_titles=_metrics, vertical_spacing=0.14, horizontal_spacing=0.08)
for i, m in enumerate(_metrics):
    r, c = i // 2 + 1, i % 2 + 1
    d = _fp[_fp["metric"] == m].sort_values("day")
    if d.empty:
        continue
    proj = d[d["projection_low"].notna()]
    fig.add_trace(go.Scatter(x=proj["day"], y=proj["projection_high"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=r, col=c)
    fig.add_trace(go.Scatter(x=proj["day"], y=proj["projection_low"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor=_C_BAND,
                             name="Projection range", showlegend=(i == 0), hoverinfo="skip"), row=r, col=c)
    fig.add_trace(go.Scatter(x=d["day"], y=d["plan_cumulative"], mode="lines", name="Plan (cumulative)", line=dict(color=_C_PLAN, width=2, dash="dash"),
                             showlegend=(i == 0), hovertemplate="%{x|%b %d}<br>Plan $%{y:,.0f}<extra></extra>"), row=r, col=c)
    fig.add_trace(go.Scatter(x=d["day"], y=d["actual_cumulative"], mode="lines", name="Actual (cumulative)", line=dict(color=_C_ACT, width=2.5),
                             showlegend=(i == 0), hovertemplate="%{x|%b %d}<br>Actual $%{y:,.0f}<extra></extra>"), row=r, col=c)
    fig.add_trace(go.Scatter(x=proj["day"], y=proj["projection_7d_avg"], mode="lines", name="Projection (7d run rate)", line=dict(color=_C_PROJ, width=2, dash="dot"),
                             showlegend=(i == 0), hovertemplate="%{x|%b %d}<br>Projected $%{y:,.0f}<extra></extra>"), row=r, col=c)
    _as_of = d["as_of_day"].iloc[0]
    fig.add_vline(x=pd.Timestamp(_as_of), line=dict(color="#c3c2b7", width=1, dash="dot"), row=r, col=c)

fig.update_yaxes(tickprefix="$", tickformat=",.0s", gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False, tickformat="%b %d")
fig.update_layout(height=620, template="plotly_white", margin=dict(l=40, r=20, t=60, b=40),
                  legend=dict(orientation="h", y=-0.08, x=0), hovermode="x unified",
                  title=dict(text="Pacing period flight paths — cumulative actual vs plan (Paid LTV capped at today-5)", font=dict(size=14)))
fig
```

## [14] [MARKDOWN] Section — Where we are
_cell id `01a0c4f1-3e4d-766c-b505-cf82a78a0b33` · static `01a0c4f1-3e4d-766c-b505-d2881a16be2b`_
## Where we are
Exit ARR and subscribers by month · net-subscriber bridge · monthly spend, booked LTV and LTV/CAC history

_Current month is month-to-date. The TW plan carries no ARR targets, so these are actuals-only trend views._

## [15] [SQL] TW Monthly Exit ARR + Exit Subscribers (north-star)
_cell id `01a0c4f3-4ff8-70a7-ba52-d056a97531b1` · static `01a0c4f3-4ff8-70a7-ba52-d500807934f6`_
```sql
-- output: tw_monthly_exit_arr_subs  (BigQuery)
-- TW Monthly Exit ARR + Exit Subscribers (North Star board basis) — port of the US cell with country_group = 'Taiwan', Asia/Taipei.
-- Exit ARR = arr_usd_gross_less_taxes_month_end; Exit Subs = arr_usd_gross_users_month_end.
-- RECENCY-ROBUST: picks the LATEST POPULATED ds per month (historical month-ends + last 7 days as candidates), so the most
-- recent mature month always shows even though user_daily_arr lags ~1-2 days. is_month_to_date flags the in-progress month.
WITH tz AS (SELECT CURRENT_DATE('Asia/Taipei') AS today)
SELECT month, as_of_day, is_month_to_date, exit_subscribers, exit_arr
FROM (
  SELECT DATE_TRUNC(a.ds, MONTH) AS month, a.ds AS as_of_day, a.ds < LAST_DAY(a.ds) AS is_month_to_date,
    SUM(a.arr_usd_gross_users_month_end) AS exit_subscribers, SUM(a.arr_usd_gross_less_taxes_month_end) AS exit_arr,
    ROW_NUMBER() OVER (PARTITION BY DATE_TRUNC(a.ds, MONTH) ORDER BY a.ds DESC) AS rn
  FROM `speak-v2-2a1f1.analytics.user_daily_arr` a, tz
  WHERE a.country_group = 'Taiwan'
    AND a.ds IN (
      LAST_DAY(DATE_SUB(tz.today, INTERVAL 1 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 2 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 3 MONTH)),
      LAST_DAY(DATE_SUB(tz.today, INTERVAL 4 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 5 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 6 MONTH)),
      LAST_DAY(DATE_SUB(tz.today, INTERVAL 7 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 8 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 9 MONTH)),
      LAST_DAY(DATE_SUB(tz.today, INTERVAL 10 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 11 MONTH)), LAST_DAY(DATE_SUB(tz.today, INTERVAL 12 MONTH)),
      LAST_DAY(DATE_SUB(tz.today, INTERVAL 13 MONTH)),
      DATE_SUB(tz.today, INTERVAL 1 DAY), DATE_SUB(tz.today, INTERVAL 2 DAY), DATE_SUB(tz.today, INTERVAL 3 DAY), DATE_SUB(tz.today, INTERVAL 4 DAY),
      DATE_SUB(tz.today, INTERVAL 5 DAY), DATE_SUB(tz.today, INTERVAL 6 DAY), DATE_SUB(tz.today, INTERVAL 7 DAY))
  GROUP BY month, a.ds)
WHERE rn = 1 ORDER BY month
```

## [16] [SQL] TW monthly subscriber bridge (New / Net Churn / Net Incremental + net growth %)
_cell id `01a0c4f3-8c53-727e-aed2-1907cfd8084a` · static `01a0c4f3-8c53-727e-aed2-1d2ef7e2cd4b`_
```sql
-- output: tw_monthly_subscriber_bridge  (BigQuery)
-- New, Net Churn & Net Incremental Subscribers — monthly, TW (B2C). Port of the US replica of the North Star board query.
-- COUNT(DISTINCT ...) PER DAY, then SUM the days into the calendar month (NOT a monthly distinct).
--   New Subscribers = COUNT(DISTINCT first_time_purchaser_arr_users); Net Churn = SUM(churn_refund_arr_users_day) (already negative)
--   - COUNT(DISTINCT churned_arr_users) + COUNT(DISTINCT resurrection_arr_users); Net Incremental = New + Net Churn.
--   net_growth_rate = Net Incremental / prior month-end subscriber base; NULL on the current MTD month. Long format.
WITH daily AS (
    SELECT day,
        COUNT(DISTINCT first_time_purchaser_arr_users) AS new_users,
        IFNULL(SUM(churn_refund_arr_users_day), 0) AS churn_refund_users,
        -COUNT(DISTINCT churned_arr_users) AS churned_users,
        COUNT(DISTINCT resurrection_arr_users) AS resurrected_users
    FROM `speak-v2-2a1f1.analytics.user_daily_arr`
    WHERE country_group = 'Taiwan'
        AND ds >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 13 MONTH), MONTH)
        AND ds <= CURRENT_DATE('Asia/Taipei') - INTERVAL 1 DAY
        AND day <= CURRENT_DATE('Asia/Taipei') - INTERVAL 1 DAY
    GROUP BY day
),
monthly AS (
    SELECT DATE_TRUNC(day, MONTH) AS month, SUM(new_users) AS new_subscribers,
        SUM(churn_refund_users + churned_users + resurrected_users) AS net_churn_subscribers,
        SUM(new_users + churn_refund_users + churned_users + resurrected_users) AS net_incremental_subscribers,
        MAX(day) AS month_max_day
    FROM daily GROUP BY month
),
exit_subs AS (
    SELECT month, exit_subscribers FROM (
        SELECT DATE_TRUNC(ds, MONTH) AS month, ds, SUM(arr_usd_gross_users_month_end) AS exit_subscribers,
            ROW_NUMBER() OVER (PARTITION BY DATE_TRUNC(ds, MONTH) ORDER BY ds DESC) AS rn
        FROM `speak-v2-2a1f1.analytics.user_daily_arr`
        WHERE country_group = 'Taiwan'
            AND ds >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 13 MONTH), MONTH)
            AND ds <= CURRENT_DATE('Asia/Taipei') - INTERVAL 1 DAY
        GROUP BY month, ds
    ) WHERE rn = 1
),
final AS (
    SELECT m.month, m.new_subscribers, m.net_churn_subscribers, m.net_incremental_subscribers,
        CASE WHEN m.month_max_day >= LAST_DAY(m.month) AND ep.exit_subscribers > 0 THEN m.net_incremental_subscribers / ep.exit_subscribers END AS net_growth_rate
    FROM monthly m LEFT JOIN exit_subs ep ON ep.month = DATE_SUB(m.month, INTERVAL 1 MONTH)
    WHERE m.month >= DATE_TRUNC(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 12 MONTH), MONTH)
)
SELECT month, series, subscribers, net_growth_rate FROM (
    SELECT month, 'New Subscribers' AS series, new_subscribers AS subscribers, net_growth_rate, 1 AS sort_order FROM final
    UNION ALL SELECT month, 'Net Churn Subscribers', net_churn_subscribers, net_growth_rate, 2 FROM final
    UNION ALL SELECT month, 'Net Incremental Subscribers', net_incremental_subscribers, net_growth_rate, 3 FROM final
) ORDER BY month, sort_order
```

## [17] [CODE] Charts — Exit ARR, Exit subscribers, subscriber bridge
_cell id `01a0c4f3-c8dc-741c-ab1c-e3a056f97234` · static `01a0c4f3-c8dc-741c-ab1c-e6d4b47a2ce5`_
```python
# Where we are: Exit ARR (monthly), Exit subscribers (monthly), subscriber bridge (grouped bars), net growth rate (own axis — no dual axes).
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_e = tw_monthly_exit_arr_subs.copy(); _e["month"] = pd.to_datetime(_e["month"])
_b = tw_monthly_subscriber_bridge.copy(); _b["month"] = pd.to_datetime(_b["month"])
_C1, _C2, _C3, _MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#9ec5f4"

fig = make_subplots(rows=2, cols=2, subplot_titles=["Exit ARR — monthly (current month MTD, lighter)", "Exit subscribers — monthly",
                                                    "New / Net churn / Net incremental subscribers", "Net subscriber growth rate (closed months)"],
                    vertical_spacing=0.16, horizontal_spacing=0.08)
_col = [_MUTED if m else _C1 for m in _e["is_month_to_date"]]
fig.add_trace(go.Bar(x=_e["month"], y=_e["exit_arr"], marker_color=_col, name="Exit ARR", showlegend=False,
                     hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=_e["month"], y=_e["exit_subscribers"], marker_color=_col, name="Exit subscribers", showlegend=False,
                     hovertemplate="%{x|%b %Y}<br>%{y:,.0f}<extra></extra>"), row=1, col=2)
for s, c in [("New Subscribers", _C1), ("Net Churn Subscribers", _C2), ("Net Incremental Subscribers", _C3)]:
    d = _b[_b["series"] == s]
    fig.add_trace(go.Bar(x=d["month"], y=d["subscribers"], name=s, marker_color=c, hovertemplate="%{x|%b %Y}<br>" + s + ": %{y:,.0f}<extra></extra>"), row=2, col=1)
_g = _b[_b["series"] == "New Subscribers"].dropna(subset=["net_growth_rate"])
fig.add_trace(go.Scatter(x=_g["month"], y=_g["net_growth_rate"], mode="lines+markers", name="Net growth rate", line=dict(color=_C1, width=2), marker=dict(size=8),
                         showlegend=False, hovertemplate="%{x|%b %Y}<br>%{y:.2%}<extra></extra>"), row=2, col=2)
fig.update_yaxes(tickprefix="$", tickformat=",.2s", row=1, col=1)
fig.update_yaxes(tickformat=",.0f", row=1, col=2)
fig.update_yaxes(tickformat=",.0f", row=2, col=1)
fig.update_yaxes(tickformat=".1%", row=2, col=2)
fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False, tickformat="%b %y")
fig.update_layout(height=680, template="plotly_white", barmode="group", bargap=0.25, margin=dict(l=40, r=20, t=60, b=40),
                  legend=dict(orientation="h", y=-0.06, x=0), hovermode="x unified")
fig
```

## [18] [MARKDOWN] § Spend efficiency — header
_cell id `01a0c4f3-f5f0-72d1-8a41-3e2b4c623cd0` · static `01a0c4f3-f5f0-72d1-8a41-40e12f330eb7`_
## Spend efficiency
Blended performance and channel segments · monthly and weekly · targets: **blended 1.5×** (all spend), **paid 0.85×**

**Definitions** — *Blended* pairs cohort booked LTV (m35, the sheet basis) with ALL TW spend; *Forecasted* pairs trial-start forecasted LTV with spend capped at the last complete LTV day. *Paid* is attributed realised LTV ÷ paid spend (`bucketed_channel = 'Paid'`), both capped at today − 5.

**Maturity** — each series is cut at its own source's last valid day, and spend is capped to match, because `marketing_spend_daily` books committed contracts onto days that haven't happened yet. Cut dates are emitted as columns. Anything marked **MTD** is partial: read the ratio, not the bar height.

**Segments** — Paid app iOS / Paid app Android / Paid web split by campaign-name platform token (Apple Search Ads → iOS); Influencer, Branded search and Brand by `bucketed_channel`. Scope: Ongoing (`_ongoing_`), Promo (`promo_disc`), Brand (`brandmarketing`), Untagged. Segment LTV is realised attributed LTV (sheet basis).

## [19] [SQL] TW New LTV Booked + Spend + LTV/CAC (blended board)
_cell id `01a0c4f4-3a9b-763e-86d9-b3221fa79881` · static `01a0c4f4-3a9b-763e-86d9-b62e95e5964f`_
```sql
-- output: tw_new_ltv_booked_cac  (BigQuery)
-- TW New LTV Booked, Marketing Spend and LTV/CAC by cohort month (Blended board basis). Port of the US cell, TW, no freemium layer,
-- plus a PAID leg (attributed realised LTV vs paid spend, both capped at today-5) with its 0.85x target.
--   forecasted_ltv_booked (transaction_ltv_forecasted, trial-start anchored) capped at cap_complete = last COMPLETE LTV day
--     (a day is complete when its LTV >= 60% of the mean of the 14 days ending 2 days before it; the newest day is partially loaded).
--   blended_ltv_booked (cohort_ltv_marketing revenue_ltv @ m35, month grain, cannot be capped) paired with spend through cap_raw.
--   Spend = marketing_spend_daily, non-B2B-Paid, TW. On closed months the caps fall past month end and the columns coincide.
-- Blended line reconciles to the sheet: Jul 1.385 vs sheet 1.38; Aug 1.144 vs sheet 1.20 (sheet spend extract was cut 9/7).
-- Window: last 13 cohort months INCLUDING the current one (flagged MTD).
WITH ltv_daily AS (
  SELECT ds, SUM(forecasted_ltv) AS ltv
  FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted`
  WHERE country_group_marketing = 'Taiwan' AND ds >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 45 DAY)
  GROUP BY 1),
ltv_ref AS (SELECT ds, ltv, AVG(ltv) OVER (ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 2 PRECEDING) AS ref_ltv FROM ltv_daily),
bounds AS (
  SELECT (SELECT MAX(ds) FROM ltv_ref WHERE ref_ltv IS NULL OR ltv >= 0.6 * ref_ltv) AS cap_complete,
         (SELECT MAX(ds) FROM ltv_daily) AS cap_raw,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS attr_cap,
         DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH) AS this_month,
         DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH) AS start_month),
fcst AS (
  SELECT DATE_TRUNC(ds, MONTH) AS cohort_month, SUM(forecasted_ltv) AS forecasted_ltv_booked
  FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` CROSS JOIN bounds b
  WHERE country_group_marketing = 'Taiwan' AND ds BETWEEN b.start_month AND b.cap_complete GROUP BY 1),
blend AS (
  SELECT DATE_TRUNC(first_transaction_month, MONTH) AS cohort_month, SUM(revenue_ltv) AS blended_ltv_booked
  FROM `speak-v2-2a1f1.analytics.cohort_ltv_marketing` CROSS JOIN bounds b
  WHERE month_index = 35 AND country = 'Taiwan' AND first_transaction_month >= b.start_month GROUP BY 1),
spend AS (
  SELECT DATE(DATE_TRUNC(date_start, MONTH)) AS cohort_month,
    SUM(IF(CAST(date_start AS DATE) <= b.cap_complete, spend, 0)) AS marketing_spend,
    SUM(IF(CAST(date_start AS DATE) <= b.cap_raw, spend, 0)) AS marketing_spend_blended_basis,
    SUM(IF(CAST(date_start AS DATE) <= b.attr_cap AND m.bucketed_channel = 'Paid', spend, 0)) AS paid_spend_attr_basis
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` m CROSS JOIN bounds b
  WHERE m.bucketed_channel != 'B2B Paid' AND `speak-v2-2a1f1`.UDFs.country_group_marketing(m.country) = 'Taiwan'
    AND CAST(m.date_start AS DATE) BETWEEN b.start_month AND b.cap_raw
  GROUP BY 1),
paid AS (
  SELECT DATE_TRUNC(attribution_date, MONTH) AS cohort_month, SUM(ltv) AS paid_ltv_attributed
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` CROSS JOIN bounds b
  WHERE `speak-v2-2a1f1`.UDFs.country_group_marketing(country) = 'Taiwan' AND bucketed_channel = 'Paid'
    AND attribution_date BETWEEN b.start_month AND b.attr_cap GROUP BY 1)
SELECT f.cohort_month, b.cap_complete AS data_through, b.cap_raw AS data_through_blended, b.attr_cap AS data_through_attributed,
  IF(f.cohort_month = b.this_month, 'MTD', 'Complete') AS month_status,
  ROUND(f.forecasted_ltv_booked) AS forecasted_ltv_booked, ROUND(bl.blended_ltv_booked) AS blended_ltv_booked,
  ROUND(s.marketing_spend) AS marketing_spend, ROUND(s.marketing_spend_blended_basis) AS marketing_spend_blended_basis,
  SAFE_DIVIDE(f.forecasted_ltv_booked, s.marketing_spend) AS ltv_cac_forecasted,
  SAFE_DIVIDE(bl.blended_ltv_booked, s.marketing_spend_blended_basis) AS ltv_cac_blended,
  ROUND(s.paid_spend_attr_basis) AS paid_spend, ROUND(p.paid_ltv_attributed) AS paid_ltv_attributed,
  SAFE_DIVIDE(p.paid_ltv_attributed, s.paid_spend_attr_basis) AS paid_ltv_cac,
  1.5 AS target_blended, 0.85 AS target_paid
FROM fcst f CROSS JOIN bounds b
LEFT JOIN blend bl ON bl.cohort_month = f.cohort_month
LEFT JOIN spend s ON s.cohort_month = f.cohort_month
LEFT JOIN paid p ON p.cohort_month = f.cohort_month
ORDER BY f.cohort_month
```

## [20] [SQL] §1 · Attributed vs organic split (monthly)
_cell id `01a0c4f4-61fb-7373-bc36-0009e506a0bd` · static `01a0c4f4-61fb-7373-bc36-0551f803d5cf`_
```sql
-- output: tw_blended_attributed_split  (BigQuery)
-- Attributed vs organic share of forecasted LTV by cohort month (TW). Port of the US §1 cell. Both legs capped at today-5 so the
-- current month's SHARE is honest even though its absolute dollars are partial. Headline series = pct_organic.
-- APPROXIMATION: the legs use different cohort anchors (transaction date vs attribution date); directionally right, not exact.
WITH bounds AS (
  SELECT DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH) AS start_month,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS cap,
         DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH) AS this_month),
total AS (
  SELECT DATE_TRUNC(ds, MONTH) AS cohort_month, SUM(forecasted_ltv) AS total_ltv_booked
  FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` CROSS JOIN bounds b
  WHERE country_group_marketing = 'Taiwan' AND ds BETWEEN b.start_month AND b.cap GROUP BY 1),
attributed AS (
  SELECT DATE_TRUNC(attribution_date, MONTH) AS cohort_month, SUM(forecasted_ltv) AS attributed_ltv
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` CROSS JOIN bounds b
  WHERE `speak-v2-2a1f1`.UDFs.country_group_marketing(country) = 'Taiwan' AND attribution_date BETWEEN b.start_month AND b.cap GROUP BY 1)
SELECT t.cohort_month, IF(t.cohort_month = b.this_month, 'MTD', 'Complete') AS month_status,
  ROUND(t.total_ltv_booked) AS total_ltv_booked, ROUND(COALESCE(a.attributed_ltv, 0)) AS attributed_ltv,
  ROUND(t.total_ltv_booked - COALESCE(a.attributed_ltv, 0)) AS organic_ltv,
  ROUND(SAFE_DIVIDE(t.total_ltv_booked - COALESCE(a.attributed_ltv, 0), t.total_ltv_booked), 4) AS pct_organic,
  ROUND(SAFE_DIVIDE(COALESCE(a.attributed_ltv, 0), t.total_ltv_booked), 4) AS pct_attributed
FROM total t LEFT JOIN attributed a USING (cohort_month) CROSS JOIN bounds b ORDER BY cohort_month
```

## [21] [SQL] §2 · Segments — daily (attributed engine)
_cell id `01a0c4f4-b3c7-7667-9e73-f3d05b763d3d` · static `01a0c4f4-b3c7-7667-9e73-f701a8aeaa95`_
```sql
-- output: tw_seg_attributed_daily  (BigQuery)
-- ============================================================================
-- DATASET: tw_seg_attributed_daily  -- DAY x segment x scope, one attributed engine (TW)
-- Spend (marketing_spend_daily) and attributed outcomes (attribution table, realised ltv = sheet basis, forecasted alongside)
-- are aggregated SEPARATELY at day x campaign and classified on the canonical campaign name (marketing_campaign_mapping by
-- campaign_id, falling back to each table's own name), then unioned. No row-level join is needed at this grain.
-- SEGMENTS: Paid app iOS (_ios_ / TW_ASA_* / Apple Nonbrand Search) · Paid app Android (_android) · Paid web (_web_) · Paid other
--           · Influencer · Branded search · Brand   (non-paid segments by bucketed_channel).
-- SCOPE: Brand (brandmarketing) > Promo (promo_disc) > Ongoing (_ongoing_) > Untagged. TW never uses _test_; ASA is untagged.
-- Window: 13 months incl. current; capped at today-5 (attribution bakes ~4 days). Rolled to month/week by the Python combiner.
-- ============================================================================
WITH bounds AS (
  SELECT DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH) AS start_month,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 5 DAY) AS attr_cap
),
spd AS (
  SELECT CAST(s.date_start AS DATE) AS day, s.bucketed_channel AS bc, s.platform AS ch, COALESCE(CAST(s.campaign_id AS STRING), '') AS cid,
    LOWER(COALESCE(s.campaign, '')) AS cname, SUM(s.spend) AS spend
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` s CROSS JOIN bounds b
  WHERE `speak-v2-2a1f1`.UDFs.country_group_marketing(s.country) = 'Taiwan' AND COALESCE(s.spend, 0) > 0
    AND CAST(s.date_start AS DATE) BETWEEN b.start_month AND b.attr_cap
  GROUP BY 1, 2, 3, 4, 5),
att AS (
  SELECT a.attribution_date AS day, a.bucketed_channel AS bc, a.channel AS ch, COALESCE(a.campaign_id, '') AS cid,
    LOWER(COALESCE(a.campaign_name, '')) AS cname, SUM(a.ltv) AS ltv, SUM(a.forecasted_ltv) AS fltv,
    SUM(a.trial_converts_and_initial_purchases) AS conversions, SUM(a.installs) AS installs
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort` a CROSS JOIN bounds b
  WHERE `speak-v2-2a1f1`.UDFs.country_group_marketing(a.country) = 'Taiwan' AND a.attribution_date BETWEEN b.start_month AND b.attr_cap
  GROUP BY 1, 2, 3, 4, 5),
u AS (
  SELECT day, bc, ch, cid, cname, spend, 0.0 AS ltv, 0.0 AS fltv, 0.0 AS conversions, 0 AS installs FROM spd
  UNION ALL SELECT day, bc, ch, cid, cname, 0.0, ltv, fltv, conversions, installs FROM att),
named AS (
  SELECT u.*, LOWER(COALESCE(cm.campaign_name, u.cname, '')) AS cn
  FROM u LEFT JOIN `speak-v2-2a1f1.analytics.marketing_campaign_mapping` cm ON u.cid != '' AND LOWER(cm.campaign_id) = LOWER(u.cid)),
classified AS (
  SELECT day, spend, ltv, fltv, conversions, installs,
    CASE WHEN bc = 'Paid' AND (REGEXP_CONTAINS(cn, r'_ios_|_ios$|^tw_asa') OR ch LIKE 'Apple Nonbrand%') THEN 'Paid — App iOS'
         WHEN bc = 'Paid' AND REGEXP_CONTAINS(cn, r'_android') THEN 'Paid — App Android'
         WHEN bc = 'Paid' AND REGEXP_CONTAINS(cn, r'_web_') THEN 'Paid — Web'
         WHEN bc = 'Paid' THEN 'Paid — Other'
         WHEN bc = 'Influencer' THEN 'Influencer'
         WHEN bc = 'Paid Branded Search' THEN 'Branded search'
         WHEN bc = 'Brand' THEN 'Brand' END AS segment,
    CASE WHEN REGEXP_CONTAINS(cn, r'brandmarketing') THEN 'Brand'
         WHEN REGEXP_CONTAINS(cn, r'promo_disc') THEN 'Promo'
         WHEN REGEXP_CONTAINS(cn, r'_ongoing_|_ongoing$') THEN 'Ongoing'
         ELSE 'Untagged' END AS scope
  FROM named)
SELECT day, segment, scope,
  ROUND(SUM(spend)) AS media_spend, ROUND(SUM(conversions)) AS conversions, ROUND(SUM(ltv)) AS ltv, ROUND(SUM(fltv)) AS forecasted_ltv, SUM(installs) AS installs,
  (SELECT attr_cap FROM bounds) AS last_mature_date
FROM classified WHERE segment IS NOT NULL
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
```

## [22] [CODE] §2 · Segments combiner (monthly + weekly)
_cell id `01a0c4f4-e959-744a-ba0a-9d72e1c63c8e` · static `01a0c4f4-e959-744a-ba0a-a3a4b2593a65`_
```python
# ============================================================================
# CELL: tw_segments_monthly / tw_segments_weekly / tw_segments_monthly_all / tw_segments_weekly_all  (§2 combiner)
# Rolls tw_seg_attributed_daily up to month AND week from one frame. Ratios are SUM(num)/SUM(den) AFTER roll-up.
# *_all frames collapse scope (Ongoing + Promo + Brand + Untagged) per segment; the others keep segment x scope.
# Target: 0.85x for the Paid segments (Kevin 2026-09-21); other segments carry no target line.
# No BigQuery scan here by design.
# ============================================================================
import pandas as pd

_daily = tw_seg_attributed_daily.copy()
_daily["day"] = pd.to_datetime(_daily["day"])
_daily["spend"] = _daily["media_spend"].astype(float)
_MEAS = ["spend", "conversions", "ltv", "forecasted_ltv", "installs"]
_cut = pd.to_datetime(_daily["last_mature_date"]).max()
_PAID = {"Paid — App iOS", "Paid — App Android", "Paid — Web", "Paid — Other"}

def _roll(freq, label, status_col, collapse_scope):
    d = _daily.copy()
    d["period"] = d["day"].dt.to_period(freq).dt.start_time
    keys = ["period", "segment"] + ([] if collapse_scope else ["scope"])
    g = d.groupby(keys, as_index=False)[_MEAS].sum()
    if collapse_scope:
        g["scope"] = "All"
    end = g["period"].dt.to_period(freq).dt.end_time.dt.normalize()
    g[status_col] = ["Complete" if e <= _cut else "MTD" for e in end]
    g["cac"] = g["spend"] / g["conversions"].replace(0, float("nan"))
    g["cpi"] = g["spend"] / g["installs"].replace(0, float("nan"))
    g["ltv_cac"] = g["ltv"] / g["spend"].replace(0, float("nan"))
    g["ltv_cac_forecasted"] = g["forecasted_ltv"] / g["spend"].replace(0, float("nan"))
    g["series"] = g["segment"] + " · " + g["scope"]
    g["target"] = [0.85 if s in _PAID else float("nan") for s in g["segment"]]
    g = g.rename(columns={"period": label})
    return g.sort_values([label, "segment", "scope"]).reset_index(drop=True)

tw_segments_monthly = _roll("M", "month", "month_status", False)
tw_segments_monthly_all = _roll("M", "month", "month_status", True)
_w = _roll("W-SUN", "week", "week_status", False)
_wa = _roll("W-SUN", "week", "week_status", True)
_cutoff = _wa["week"].max() - pd.Timedelta(weeks=11)   # 12 weekly buckets inclusive (recent-trend lens)
tw_segments_weekly = _w[_w["week"] >= _cutoff].reset_index(drop=True)
tw_segments_weekly_all = _wa[_wa["week"] >= _cutoff].reset_index(drop=True)
tw_segments_monthly_all
```

## [23] [CODE] Charts — Blended: LTV booked vs spend, LTV/CAC vs targets, organic share
_cell id `01a0c4f6-d2e2-70bd-ae5a-70941650d3ab` · static `01a0c4f6-d2e2-70bd-ae5a-76d616591018`_
```python
# Blended performance charts (one axis per panel). Bars: forecasted LTV, blended LTV, spend. Lines: LTV/CAC blended / forecasted / paid vs targets. Share: organic vs attributed.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_m = tw_new_ltv_booked_cac.copy(); _m["cohort_month"] = pd.to_datetime(_m["cohort_month"])
_s = tw_blended_attributed_split.copy(); _s["cohort_month"] = pd.to_datetime(_s["cohort_month"])
_C1, _C2, _C3, _GREY = "#2a78d6", "#eb6834", "#1baf7a", "#52514e"

fig = make_subplots(rows=3, cols=1, subplot_titles=["New LTV booked vs marketing spend — by cohort month (MTD partial)",
                                                    "LTV/CAC — blended (target 1.5×), forecasted, paid (target 0.85×)",
                                                    "Organic vs attributed share of forecasted LTV"], vertical_spacing=0.1)
fig.add_trace(go.Bar(x=_m["cohort_month"], y=_m["forecasted_ltv_booked"], name="Forecasted LTV booked", marker_color=_C1, hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra>Forecasted LTV</extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=_m["cohort_month"], y=_m["blended_ltv_booked"], name="Blended LTV booked (cohort m35)", marker_color=_C3, hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra>Blended LTV</extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=_m["cohort_month"], y=_m["marketing_spend"], name="Marketing spend", marker_color=_C2, hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra>Spend</extra>"), row=1, col=1)
fig.add_trace(go.Scatter(x=_m["cohort_month"], y=_m["ltv_cac_blended"], mode="lines+markers", name="LTV/CAC blended", line=dict(color=_C3, width=2.5), marker=dict(size=8), hovertemplate="%{x|%b %Y}<br>%{y:.2f}x<extra>Blended</extra>"), row=2, col=1)
fig.add_trace(go.Scatter(x=_m["cohort_month"], y=_m["ltv_cac_forecasted"], mode="lines+markers", name="LTV/CAC forecasted", line=dict(color=_C1, width=2), marker=dict(size=8), hovertemplate="%{x|%b %Y}<br>%{y:.2f}x<extra>Forecasted</extra>"), row=2, col=1)
fig.add_trace(go.Scatter(x=_m["cohort_month"], y=_m["paid_ltv_cac"], mode="lines+markers", name="Paid LTV/CAC (attributed)", line=dict(color=_C2, width=2), marker=dict(size=8), hovertemplate="%{x|%b %Y}<br>%{y:.2f}x<extra>Paid</extra>"), row=2, col=1)
fig.add_trace(go.Scatter(x=_m["cohort_month"], y=_m["target_blended"], mode="lines", name="Blended target 1.5×", line=dict(color=_GREY, width=1.5, dash="dash"), hoverinfo="skip"), row=2, col=1)
fig.add_trace(go.Scatter(x=_m["cohort_month"], y=_m["target_paid"], mode="lines", name="Paid target 0.85×", line=dict(color=_GREY, width=1.5, dash="dot"), hoverinfo="skip"), row=2, col=1)
fig.add_trace(go.Bar(x=_s["cohort_month"], y=_s["pct_organic"], name="Organic share", marker_color=_C3, hovertemplate="%{x|%b %Y}<br>%{y:.1%}<extra>Organic</extra>"), row=3, col=1)
fig.add_trace(go.Bar(x=_s["cohort_month"], y=_s["pct_attributed"], name="Attributed share", marker_color=_C1, hovertemplate="%{x|%b %Y}<br>%{y:.1%}<extra>Attributed</extra>"), row=3, col=1)
fig.update_yaxes(tickprefix="$", tickformat=",.2s", row=1, col=1)
fig.update_yaxes(ticksuffix="x", tickformat=".2f", rangemode="tozero", row=2, col=1)
fig.update_yaxes(tickformat=".0%", range=[0, 1], row=3, col=1)
fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False, tickformat="%b %y")
fig.update_layout(height=980, template="plotly_white", barmode="group", bargap=0.25, margin=dict(l=40, r=20, t=60, b=40),
                  legend=dict(orientation="h", y=-0.04, x=0), hovermode="x unified")
fig.update_traces(selector=dict(name="Organic share"), offsetgroup="share")
fig.update_layout(barmode="group")
fig
```

## [24] [CODE] Charts — Segments: LTV/CAC monthly and weekly
_cell id `01a0c4f7-06ab-749c-916b-f97efca9c3fd` · static `01a0c4f7-06ab-749c-916b-fdfc58b6699e`_
```python
# Segment LTV/CAC (realised attributed LTV / spend), scope collapsed. Fixed hue order per segment (never cycled); 0.85x target for paid segments.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_ORDER = ["Paid — App iOS", "Paid — App Android", "Paid — Web", "Influencer", "Branded search", "Brand", "Paid — Other"]
_HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
_COL = dict(zip(_ORDER, _HUES))
_mo = tw_segments_monthly_all.copy(); _mo["month"] = pd.to_datetime(_mo["month"])
_wk = tw_segments_weekly_all.copy(); _wk["week"] = pd.to_datetime(_wk["week"])

fig = make_subplots(rows=2, cols=1, subplot_titles=["LTV/CAC by segment — monthly (13 months, current month MTD)", "LTV/CAC by segment — weekly (last 12 weeks)"], vertical_spacing=0.14)
for seg in _ORDER:
    d = _mo[_mo["segment"] == seg]
    if d.empty:
        continue
    fig.add_trace(go.Scatter(x=d["month"], y=d["ltv_cac"], mode="lines+markers", name=seg, legendgroup=seg, line=dict(color=_COL[seg], width=2), marker=dict(size=8),
                             customdata=d[["spend", "ltv", "conversions"]].values,
                             hovertemplate="%{x|%b %Y}<br>" + seg + ": %{y:.2f}x<br>spend $%{customdata[0]:,.0f} · LTV $%{customdata[1]:,.0f} · subs %{customdata[2]:,.0f}<extra></extra>"), row=1, col=1)
    w = _wk[_wk["segment"] == seg]
    fig.add_trace(go.Scatter(x=w["week"], y=w["ltv_cac"], mode="lines+markers", name=seg, legendgroup=seg, showlegend=False, line=dict(color=_COL[seg], width=2), marker=dict(size=7),
                             customdata=w[["spend", "ltv", "conversions"]].values,
                             hovertemplate="wk of %{x|%b %d}<br>" + seg + ": %{y:.2f}x<br>spend $%{customdata[0]:,.0f} · LTV $%{customdata[1]:,.0f} · subs %{customdata[2]:,.0f}<extra></extra>"), row=2, col=1)
for r, x in [(1, _mo["month"]), (2, _wk["week"])]:
    if len(x):
        fig.add_trace(go.Scatter(x=[x.min(), x.max()], y=[0.85, 0.85], mode="lines", name="Paid target 0.85×", showlegend=(r == 1), line=dict(color="#52514e", width=1.5, dash="dot"), hoverinfo="skip"), row=r, col=1)
fig.update_yaxes(ticksuffix="x", tickformat=".2f", rangemode="tozero", range=[0, 3], gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False)
fig.update_layout(height=760, template="plotly_white", margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.06, x=0), hovermode="x unified")
fig
```

## [25] [SQL] Cash CAC Payback by cohort month (blended board 1.c)
_cell id `01a0c4f7-54ff-7338-8ce4-1d65373a6002` · static `01a0c4f7-54ff-7338-8ce4-223e2927e5df`_
```sql
-- output: tw_cash_cac_payback_monthly  (BigQuery)
-- Cash CAC Payback — TW only (Blended board query 1.c, ported from the US cell). Months until a cohort's cumulative cash collections
-- cover that cohort's non-B2B-Paid marketing spend, linearly interpolated in the crossing month. Cash numerator, NOT LTV.
-- Spend denominator is capped at the last COMPLETE LTV day (no forward-dated committed spend).
-- DO NOT TRADE ON THE MTD ROW: a partial cohort's crossing point sits either side of the month-12 renewal step and swings by
-- months on a two-day change in the cut. Cohorts that never cross within 35 months show NULL.
WITH ltv_daily AS (
  SELECT ds, SUM(forecasted_ltv) AS ltv FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted`
  WHERE country_group_marketing = 'Taiwan' AND ds >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 45 DAY) GROUP BY 1),
ltv_ref AS (SELECT ds, ltv, AVG(ltv) OVER (ORDER BY ds ROWS BETWEEN 14 PRECEDING AND 2 PRECEDING) AS ref_ltv FROM ltv_daily),
bounds AS (SELECT (SELECT MAX(ds) FROM ltv_ref WHERE ref_ltv IS NULL OR ltv >= 0.6 * ref_ltv) AS cap, DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH) AS this_month),
final AS (
  SELECT first_transaction_month, month_index, country, SUM(revenue_initial) AS revenue_initial, SUM(revenue_ltv) AS revenue_ltv,
    SUM(initial_cash_bookings) AS initial_cash_bookings, SUM(cumulative_cash_bookings) AS cumulative_cash_bookings, SUM(users_initial) AS users_initial
  FROM `speak-v2-2a1f1.analytics.cohort_ltv_marketing` WHERE country = 'Taiwan' GROUP BY 1, 2, 3),
lm AS (SELECT *, LAG(cumulative_cash_bookings) OVER (PARTITION BY first_transaction_month, country ORDER BY month_index) AS cumulative_cash_bookings_last_month FROM final),
marketing_spend_monthly_by_country AS (
  SELECT DATE(DATE_TRUNC(date_start, MONTH)) AS day, `speak-v2-2a1f1`.UDFs.country_group_marketing(m.country) AS country, SUM(spend) AS marketing_spend_country
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily` m CROSS JOIN bounds b
  WHERE m.bucketed_channel != 'B2B Paid' AND CAST(m.date_start AS DATE) <= b.cap AND `speak-v2-2a1f1`.UDFs.country_group_marketing(m.country) = 'Taiwan'
  GROUP BY 1, 2),
cac AS (
  SELECT a.first_transaction_month, a.month_index, a.country, b.marketing_spend_country AS marketing_spend_total_month,
    CASE WHEN a.cumulative_cash_bookings / NULLIF(b.marketing_spend_country, 0) >= 1 AND a.cumulative_cash_bookings_last_month / NULLIF(b.marketing_spend_country, 0) IS NULL
           THEN 1 / (a.cumulative_cash_bookings / NULLIF(b.marketing_spend_country, 0))
         WHEN a.cumulative_cash_bookings / NULLIF(b.marketing_spend_country, 0) >= 1 AND a.cumulative_cash_bookings_last_month / NULLIF(b.marketing_spend_country, 0) < 1
           THEN a.month_index - (a.cumulative_cash_bookings / NULLIF(b.marketing_spend_country, 0) - 1)
                / (a.cumulative_cash_bookings / NULLIF(b.marketing_spend_country, 0) - a.cumulative_cash_bookings_last_month / NULLIF(b.marketing_spend_country, 0))
         ELSE NULL END AS cash_cac_payback
  FROM lm a LEFT JOIN marketing_spend_monthly_by_country b ON a.first_transaction_month = b.day AND a.country = b.country)
SELECT first_transaction_month AS cohort_month, ROUND(cash_cac_payback, 2) AS cash_cac_payback_months,
  IF(first_transaction_month = (SELECT this_month FROM bounds), 'MTD — unstable', 'Closed') AS cohort_status
FROM cac
WHERE (cash_cac_payback > 0 OR month_index = 35) AND country = 'Taiwan'
  AND first_transaction_month >= DATE_SUB(DATE(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH)), INTERVAL 11 MONTH)
QUALIFY ROW_NUMBER() OVER (PARTITION BY first_transaction_month, country ORDER BY month_index) = 1
ORDER BY cohort_month
```

## [26] [MARKDOWN] Section — Plan mix
_cell id `01a0c4f7-6141-7039-8a66-5f3db2a7c246` · static `01a0c4f7-6141-7039-8a66-63d3edaf0f7a`_
## Plan mix
New subscribers by plan duration and tier · monthly share and weekly volume · TW

_Subscriber = trial conversion ∪ initial purchase (`is_conversion`), dated at the event. Tier: regular → Premium, plus and unlimited → Premium Plus. Quarterly and semiannual are negligible in TW and fold into their own small buckets._

## [27] [SQL] tw_plan_mix_daily (dataset)
_cell id `01a0c4f7-a7ef-73f9-b6d1-5385f807a088` · static `01a0c4f7-a7ef-73f9-b6d1-56cb891f171f`_
```sql
-- output: tw_plan_mix_daily  (BigQuery)
-- ============================================================================
-- DATASET: tw_plan_mix_daily  -- TW plan-mix fact table (port of the US cell; no Runwayer funnel dimension in TW)
-- Grain: one row per (period_date, metric, platform_grp, plan_frequency, plan_tier, language_pair, language_level). user_id level, NO attribution.
-- Window: trailing 26 weeks (182d); cohort lookback +120d for trial->convert linkage. Source: canonical.transactions country = 'TW'.
-- DIMENSIONS platform_grp (app_store->iOS, play_store->Android, stripe/paddle->web); plan_frequency (annual = annual_single + annual_payment_plan);
--   plan_tier (regular->Premium, plus/unlimited->Premium Plus); language_pair/language_level (canonical.users).
-- METRICS trial_starts @ trial-start date; trial_conversions/initial_purchases/conversions_event @ event date; conversions_cohort @ COALESCE(trial_start_date, event_date).
-- MEASURES cnt, usd_gross (initial_gross), usd_net (initial_proceeds). Dates in Asia/Taipei.
-- ============================================================================
WITH ts_sub AS (
  SELECT subscription_id, MIN(DATE(created_at, 'Asia/Taipei')) AS trial_start_date
  FROM `speak-v2-2a1f1.canonical.transactions`
  WHERE is_trial_start AND country = 'TW' AND ds >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 302 DAY)
  GROUP BY 1
),
u AS (SELECT id AS user_id, language_pair, language_level_bucket AS language_level FROM `speak-v2-2a1f1.canonical.users`),
base AS (
  SELECT DATE(t.created_at, 'Asia/Taipei') AS event_date,
    COALESCE(ts_sub.trial_start_date, DATE(t.created_at, 'Asia/Taipei')) AS cohort_date,
    CASE t.platform WHEN 'app_store' THEN 'iOS' WHEN 'play_store' THEN 'Android' WHEN 'stripe' THEN 'web' WHEN 'paddle' THEN 'web' ELSE 'other' END AS platform_grp,
    CASE WHEN t.duration = 'monthly' THEN 'monthly' WHEN t.duration = 'quarterly' THEN 'quarterly' WHEN t.duration = 'semiannual' THEN 'semiannual'
         WHEN t.duration IN ('annual_single', 'annual_payment_plan') THEN 'annual' ELSE 'other' END AS plan_frequency,
    CASE t.tier WHEN 'regular' THEN 'Premium' WHEN 'plus' THEN 'Premium Plus' WHEN 'unlimited' THEN 'Premium Plus' ELSE 'Other' END AS plan_tier,
    COALESCE(u.language_pair, '(unknown)') AS language_pair, COALESCE(u.language_level, '(unknown)') AS language_level,
    t.is_trial_start, t.is_trial_conversion, t.is_initial_purchase, t.is_conversion,
    COALESCE(t.initial_gross, 0) AS ig, COALESCE(t.initial_proceeds, 0) AS ip
  FROM `speak-v2-2a1f1.canonical.transactions` t
  LEFT JOIN ts_sub USING (subscription_id)
  LEFT JOIN u USING (user_id)
  WHERE t.country = 'TW' AND t.ds >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 182 DAY) AND (t.is_trial_start OR t.is_conversion)
),
emitted AS (
  SELECT m.period_date, m.metric, b.platform_grp, b.plan_frequency, b.plan_tier, b.language_pair, b.language_level, m.usd_gross, m.usd_net
  FROM base b, UNNEST([
    IF(b.is_trial_start, STRUCT(b.event_date AS period_date, 'trial_starts' AS metric, 0.0 AS usd_gross, 0.0 AS usd_net), NULL),
    IF(b.is_conversion, STRUCT(b.event_date, 'conversions_event', b.ig, b.ip), NULL),
    IF(b.is_conversion, STRUCT(b.cohort_date, 'conversions_cohort', b.ig, b.ip), NULL),
    IF(b.is_trial_conversion, STRUCT(b.event_date, 'trial_conversions', b.ig, b.ip), NULL),
    IF(b.is_initial_purchase, STRUCT(b.event_date, 'initial_purchases', b.ig, b.ip), NULL)
  ]) m
  WHERE m IS NOT NULL
)
SELECT period_date, metric, platform_grp, plan_frequency, plan_tier, language_pair, language_level,
  CONCAT(plan_frequency, ' / ', plan_tier) AS plan_label,
  COUNT(*) AS cnt, ROUND(SUM(usd_gross), 2) AS usd_gross, ROUND(SUM(usd_net), 2) AS usd_net
FROM emitted
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
ORDER BY period_date, metric, platform_grp, plan_frequency, plan_tier
```

## [28] [CODE] Plan mix feeds + charts (duration / tier, monthly share + weekly volume)
_cell id `01a0c4f7-f367-77a4-8ce8-93954dc921c3` · static `01a0c4f7-f367-77a4-8ce8-9503cef1142f`_
```python
# Plan mix feeds (pm_newsubs_freq_share_mo, pm_newsubs_freq_wk, pm_newsubs_tier_share_mo, pm_newsubs_tier_wk) + 2x2 chart.
# Basis: conversions_event (trial conversion + initial purchase at event date). Shares = SUM/SUM per month.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_d = tw_plan_mix_daily[tw_plan_mix_daily["metric"] == "conversions_event"].copy()
_d["period_date"] = pd.to_datetime(_d["period_date"])
_d["month"] = _d["period_date"].dt.to_period("M").dt.start_time
_d["week"] = _d["period_date"].dt.to_period("W-SUN").dt.start_time

def _share(dim, per):
    g = _d.groupby([per, dim], as_index=False)["cnt"].sum()
    tot = g.groupby(per, as_index=False)["cnt"].sum().rename(columns={"cnt": "tot"})
    g = g.merge(tot, on=per)
    g["share_pct"] = (100 * g["cnt"] / g["tot"].replace(0, pd.NA)).astype(float).round(1)
    return g[[per, dim, "cnt", "share_pct"]]

pm_newsubs_freq_share_mo = _share("plan_frequency", "month")
pm_newsubs_tier_share_mo = _share("plan_tier", "month")
pm_newsubs_freq_wk = _d.groupby(["week", "plan_frequency"], as_index=False)["cnt"].sum().rename(columns={"cnt": "new_subs"})
pm_newsubs_tier_wk = _d.groupby(["week", "plan_tier"], as_index=False)["cnt"].sum().rename(columns={"cnt": "new_subs"})

_FREQ = ["annual", "monthly", "quarterly", "semiannual", "other"]
_TIER = ["Premium", "Premium Plus", "Other"]
_HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
fig = make_subplots(rows=2, cols=2, subplot_titles=["New subscribers by plan duration — monthly share %", "New subscribers by plan duration — weekly",
                                                    "New subscribers by plan tier — monthly share %", "New subscribers by plan tier — weekly"], vertical_spacing=0.16, horizontal_spacing=0.08)
for i, f in enumerate(_FREQ):
    a = pm_newsubs_freq_share_mo[pm_newsubs_freq_share_mo["plan_frequency"] == f]
    b = pm_newsubs_freq_wk[pm_newsubs_freq_wk["plan_frequency"] == f]
    if a.empty and b.empty:
        continue
    fig.add_trace(go.Bar(x=a["month"], y=a["share_pct"], name=f, legendgroup="f" + f, marker_color=_HUES[i], hovertemplate="%{x|%b %Y}<br>" + f + ": %{y:.1f}%<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=b["week"], y=b["new_subs"], name=f, legendgroup="f" + f, showlegend=False, marker_color=_HUES[i], hovertemplate="wk of %{x|%b %d}<br>" + f + ": %{y:,.0f}<extra></extra>"), row=1, col=2)
for i, t in enumerate(_TIER):
    a = pm_newsubs_tier_share_mo[pm_newsubs_tier_share_mo["plan_tier"] == t]
    b = pm_newsubs_tier_wk[pm_newsubs_tier_wk["plan_tier"] == t]
    if a.empty and b.empty:
        continue
    fig.add_trace(go.Bar(x=a["month"], y=a["share_pct"], name=t, legendgroup="t" + t, marker_color=_HUES[i], hovertemplate="%{x|%b %Y}<br>" + t + ": %{y:.1f}%<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Bar(x=b["week"], y=b["new_subs"], name=t, legendgroup="t" + t, showlegend=False, marker_color=_HUES[i], hovertemplate="wk of %{x|%b %d}<br>" + t + ": %{y:,.0f}<extra></extra>"), row=2, col=2)
fig.update_yaxes(ticksuffix="%", range=[0, 100], col=1)
fig.update_yaxes(tickformat=",.0f", col=2)
fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False)
fig.update_layout(height=680, template="plotly_white", barmode="stack", bargap=0.2, margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.06, x=0), hovermode="x unified")
fig
```

## [29] [MARKDOWN] CF · header + definitions
_cell id `01a0c4f8-0fd2-76da-ba67-afad3f5af85f` · static `01a0c4f8-0fd2-76da-ba67-b325f4952fc7`_
## Conversion funnel
Monthly cohort conversion by platform · iOS, Android and Web · TW

**Two cohort anchors, on purpose.** *Install charts* (install → sign up, install → trial start) are anchored on the install month, iOS / Android only (`analytics.first_installs`, TW). *Sign-up charts* (sign up → trial, sign up → subscriber, LTV / sign up, LTV / subscriber) are anchored on the sign-up month, iOS / Android / Web (`canonical.users` ⨝ transactions ⨝ forecasted LTV; TW has no Runwayer split, so Web is one series).

**Definitions.** Subscriber = trial convert ∪ initial purchase. The subscriber denominator is *blended*: realised converts where the trial window has closed plus the modelled conversion rate for trials still open, because the LTV numerator (`forecasted_ltv`) is booked in full at trial start. LTV = `forecasted_ltv`.

**Maturity.** A cohort is mature once ≥ 30 days old (`is_mature`). The newest month is a partial window: read the latest point as on-trend, not as a rise or fall. Rates are SUM/SUM at the month × platform grain, never averaged from daily ratios. Employees and B2B excluded. Rolling 13 months of cohorts.

## [30] [SQL] CF · Install cohort fact (iOS / Android)
_cell id `01a0c4f8-347e-71cf-a6e4-c2ec8c7c1d9b` · static `01a0c4f8-347e-71cf-a6e4-c442d8d207d1`_
```sql
-- output: tw_install_cohort_monthly  (BigQuery)
-- ============================================================================
-- DATASET: tw_install_cohort_monthly (Conversion Funnel, INSTALL-cohort grain, one row per install_month x platform). iOS / Android only.
-- Source: analytics.first_installs (device-level first install, country = 'Taiwan'), anchored on first_install_time (Asia/Taipei).
--   install -> signup = SUM(signed_up) / COUNT(*); install -> trial = distinct installers who ever started a trial / installs.
-- Window: rolling 13 months of INSTALL cohorts. iPadOS folded into iOS. is_mature = whole month's installs >= 30 days old.
-- RATES ARE NOT COMPUTED HERE (counts only); the Python builder does SUM(num)/SUM(den).
-- ============================================================================
WITH bounds AS (
  SELECT DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH) AS start_month,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 30 DAY) AS mature_cutoff
),
inst AS (
  SELECT DATE_TRUNC(DATE(fi.first_install_time, 'Asia/Taipei'), MONTH) AS cohort_month, DATE(fi.first_install_time, 'Asia/Taipei') AS install_date,
    CASE WHEN fi.os_name IN ('iOS', 'iPadOS') THEN 'iOS' WHEN fi.os_name = 'Android' THEN 'Android' END AS platform,
    fi.user_id, fi.signed_up
  FROM `speak-v2-2a1f1.analytics.first_installs` fi CROSS JOIN bounds b
  WHERE fi.country = 'Taiwan' AND fi.os_name IN ('iOS', 'iPadOS', 'Android')
    AND DATE(fi.first_install_time, 'Asia/Taipei') >= b.start_month AND DATE(fi.first_install_time, 'Asia/Taipei') <= CURRENT_DATE('Asia/Taipei')
),
ts AS (
  SELECT DISTINCT user_id FROM `speak-v2-2a1f1.canonical.transactions` CROSS JOIN bounds b
  WHERE is_trial_start AND ds >= b.start_month AND user_id IS NOT NULL
)
SELECT i.cohort_month, (MAX(i.install_date) <= (SELECT mature_cutoff FROM bounds)) AS is_mature, i.platform,
  COUNT(*) AS installs, SUM(i.signed_up) AS signups, COUNT(DISTINCT IF(t.user_id IS NOT NULL, i.user_id, NULL)) AS trial_starts
FROM inst i LEFT JOIN ts t ON t.user_id = i.user_id
GROUP BY i.cohort_month, i.platform ORDER BY i.cohort_month, i.platform
```

## [31] [SQL] CF · Signup cohort fact (wide, user-id level)
_cell id `01a0c4f8-8f22-762c-8dcb-8028dfd3abd2` · static `01a0c4f8-8f23-7519-841b-5ddf69c13e1a`_
```sql
-- output: tw_funnel_cohort_monthly  (BigQuery)
-- ============================================================================
-- DATASET: tw_funnel_cohort_monthly (Conversion Funnel, SIGNUP-cohort, wide grain). Port of the US cell; TW has no Runwayer split.
-- Basis: USER_ID LEVEL, NO ATTRIBUTION. canonical.users country = 'TW', is_employee = FALSE, organization_id IS NULL, Asia/Taipei dates.
-- Window: rolling 13 months of SIGNUP cohorts. Maturity: is_mature = cohort >= 30d old (immature months stay visible, flagged).
-- Dimensions (read one at a time, never crossed): platform (iOS / Android / Web), language_pair (top 12 + Other), motivation, level_bucket, activation.
-- Activation = distinct lesson_started days in the first 7 days (0 / 1 / 2-3 / 4+). A DIMENSION, not a funnel step.
-- SUBSCRIBER = trial converts + initial purchases. new_payers_blended adds the modelled top-up for still-open trial windows
--   (gate: NOT is_trial_window_complete AND NOT has_converted). RATES ARE NOT COMPUTED HERE; the Python builder does SUM/SUM.
-- ============================================================================
WITH bounds AS (
  SELECT DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH) AS start_month,
         DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 30 DAY) AS mature_cutoff
),
sign AS (
  SELECT u.id AS user_id, DATE_TRUNC(DATE(u.created_at, 'Asia/Taipei'), MONTH) AS cohort_month, DATE(u.created_at, 'Asia/Taipei') AS signup_date,
         CASE UPPER(u.signup_os) WHEN 'IOS' THEN 'iOS' WHEN 'ANDROID' THEN 'Android' WHEN 'WEB' THEN 'Web' ELSE 'other' END AS platform,
         COALESCE(u.language_pair, '(unknown)') AS language_pair,
         COALESCE(u.onboarding_results.motivations, '(none)') AS motivation,
         COALESCE(u.language_level_bucket, '(unknown)') AS level_bucket
  FROM `speak-v2-2a1f1.canonical.users` u CROSS JOIN bounds b
  WHERE u.country = 'TW' AND COALESCE(u.is_employee, FALSE) = FALSE AND u.organization_id IS NULL
    AND DATE(u.created_at, 'Asia/Taipei') >= b.start_month
),
tx AS (
  SELECT user_id, MAX(IF(is_trial_start, 1, 0)) AS has_ts, MAX(IF(is_trial_conversion, 1, 0)) AS has_tc, MAX(IF(is_initial_purchase, 1, 0)) AS has_ip
  FROM `speak-v2-2a1f1.canonical.transactions` CROSS JOIN bounds b WHERE ds >= b.start_month GROUP BY 1
),
act AS (
  SELECT l.user_id, COUNT(DISTINCT l.ds) AS active_days_7d
  FROM `speak-v2-2a1f1.analytics.lesson_started` l JOIN sign s ON s.user_id = l.user_id CROSS JOIN bounds b
  WHERE l.ds >= b.start_month AND l.ds BETWEEN s.signup_date AND DATE_ADD(s.signup_date, INTERVAL 6 DAY)
  GROUP BY 1
),
ltv AS (
  SELECT user_id, SUM(forecasted_ltv) AS f_ltv FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` CROSS JOIN bounds b WHERE ds >= b.start_month GROUP BY 1
),
model AS (
  SELECT user_id, MAX(IF(NOT COALESCE(is_trial_window_complete, TRUE) AND NOT COALESCE(has_converted, FALSE), COALESCE(estimated_conversion_rate, 0), 0)) AS open_trial_rate
  FROM `speak-v2-2a1f1.analytics.transaction_ltv_forecasted` CROSS JOIN bounds b WHERE ds >= b.start_month AND type = 'Trial Start' GROUP BY 1
),
lang_top AS (SELECT language_pair FROM sign GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 12),
base AS (
  SELECT s.cohort_month, (s.signup_date <= b.mature_cutoff) AS is_mature, s.platform,
    IF(lt.language_pair IS NULL, 'Other', s.language_pair) AS language_pair, s.motivation, s.level_bucket,
    CASE WHEN COALESCE(a.active_days_7d, 0) = 0 THEN '0 days' WHEN a.active_days_7d = 1 THEN '1 day' WHEN a.active_days_7d BETWEEN 2 AND 3 THEN '2-3 days' ELSE '4+ days' END AS activation,
    COALESCE(t.has_ts, 0) AS ts, COALESCE(t.has_tc, 0) AS tc, COALESCE(t.has_ip, 0) AS ip,
    IF(COALESCE(t.has_tc, 0) = 1 OR COALESCE(t.has_ip, 0) = 1, 1, 0) AS payer,
    IF(COALESCE(t.has_tc, 0) = 1 OR COALESCE(t.has_ip, 0) = 1, 1.0, COALESCE(m.open_trial_rate, 0)) AS payer_blended,
    IF(COALESCE(a.active_days_7d, 0) >= 1, 1, 0) AS activated, COALESCE(l.f_ltv, 0) AS f_ltv
  FROM sign s CROSS JOIN bounds b
  LEFT JOIN tx t ON t.user_id = s.user_id LEFT JOIN act a ON a.user_id = s.user_id LEFT JOIN ltv l ON l.user_id = s.user_id
  LEFT JOIN model m ON m.user_id = s.user_id LEFT JOIN lang_top lt ON lt.language_pair = s.language_pair
)
SELECT cohort_month, is_mature, platform, language_pair, motivation, level_bucket, activation,
  COUNT(*) AS signups, SUM(activated) AS activated, SUM(ts) AS trial_starts, SUM(tc) AS trial_converts, SUM(ip) AS initial_purchases,
  SUM(payer) AS new_payers, ROUND(SUM(payer_blended), 2) AS new_payers_blended, ROUND(SUM(f_ltv)) AS ltv_forecasted
FROM base GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY cohort_month, platform, signups DESC
```

## [32] [CODE] CF · Build chart frames + charts
_cell id `01a0c4f8-d66c-70c4-86e9-245444dc6390` · static `01a0c4f8-d66c-70c4-86e9-2afa0be0e7f1`_
```python
# Conversion funnel: six tidy frames (cf_install_to_signup, cf_install_to_trial, cf_signup_to_trial, cf_signup_to_sub, cf_ltv_per_signup, cf_ltv_per_sub)
# + a 2x3 chart. Rates are SUM(num)/SUM(den) at month x platform; immature cohorts drawn with hollow markers.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def _frame(df, num, den, platforms):
    out = df[df["platform"].isin(platforms)].copy()
    out["value"] = (out[num] / out[den].replace(0, float("nan"))).astype(float)
    out["numerator"] = out[num].astype(float); out["denominator"] = out[den].astype(float)
    return out[["cohort_month", "platform", "value", "is_mature", "numerator", "denominator"]].sort_values(["cohort_month", "platform"]).reset_index(drop=True)

_s = tw_funnel_cohort_monthly.copy()
_s = _s[_s["platform"].isin(["iOS", "Android", "Web"])]
_MEAS = ["signups", "trial_starts", "trial_converts", "initial_purchases", "new_payers", "new_payers_blended", "ltv_forecasted"]
_sg = _s.groupby(["cohort_month", "platform"], as_index=False).agg(**{**{m: (m, "sum") for m in _MEAS}, "is_mature": ("is_mature", "min")})
_ins = tw_install_cohort_monthly.copy()
_WEB3, _APP2 = ["iOS", "Android", "Web"], ["iOS", "Android"]
cf_install_to_signup = _frame(_ins, "signups", "installs", _APP2)
cf_install_to_trial = _frame(_ins, "trial_starts", "installs", _APP2)
cf_signup_to_trial = _frame(_sg, "trial_starts", "signups", _WEB3)
cf_signup_to_sub = _frame(_sg, "new_payers_blended", "signups", _WEB3)
cf_ltv_per_signup = _frame(_sg, "ltv_forecasted", "signups", _WEB3)
cf_ltv_per_sub = _frame(_sg, "ltv_forecasted", "new_payers_blended", _WEB3)

_PANELS = [("Install → sign up", cf_install_to_signup, ".0%"), ("Install → trial start", cf_install_to_trial, ".1%"), ("Sign up → trial start", cf_signup_to_trial, ".1%"),
           ("Sign up → subscriber (blended)", cf_signup_to_sub, ".1%"), ("LTV / sign up", cf_ltv_per_signup, "$,.2f"), ("LTV / subscriber (blended)", cf_ltv_per_sub, "$,.0f")]
_COL = {"iOS": "#2a78d6", "Android": "#eb6834", "Web": "#1baf7a"}
fig = make_subplots(rows=2, cols=3, subplot_titles=[p[0] for p in _PANELS], vertical_spacing=0.16, horizontal_spacing=0.07)
for i, (title, df, fmt) in enumerate(_PANELS):
    r, c = i // 3 + 1, i % 3 + 1
    d = df.copy(); d["cohort_month"] = pd.to_datetime(d["cohort_month"])
    for p in ["iOS", "Android", "Web"]:
        dp = d[d["platform"] == p]
        if dp.empty:
            continue
        sym = ["circle" if m else "circle-open" for m in dp["is_mature"]]
        fig.add_trace(go.Scatter(x=dp["cohort_month"], y=dp["value"], mode="lines+markers", name=p, legendgroup=p, showlegend=(i == 2),
                                 line=dict(color=_COL[p], width=2), marker=dict(size=8, symbol=sym, line=dict(width=2, color=_COL[p])),
                                 customdata=dp[["numerator", "denominator"]].values,
                                 hovertemplate="%{x|%b %Y}<br>" + p + ": %{y:" + fmt + "}<br>%{customdata[0]:,.0f} / %{customdata[1]:,.0f}<extra></extra>"), row=r, col=c)
    fig.update_yaxes(tickformat=(".0%" if "%" in fmt else "$,.0f"), rangemode="tozero", row=r, col=c)
fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False, tickformat="%b %y")
fig.update_layout(height=640, template="plotly_white", margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.08, x=0), hovermode="x unified",
                  title=dict(text="Hollow markers = cohort not yet mature (< 30 days)", font=dict(size=12)))
fig
```

## [33] [MARKDOWN] Section — Monitoring
_cell id `01a0c4f9-4623-76ad-af80-31e964c80d7f` · static `01a0c4f9-4623-76ad-af80-35884edf8603`_
## Monitoring
LTV multiplier drift · M12 revenue retention · media-budget mix · ARR reconciliation check

_Use this section to diagnose unexpected movement in headline metrics. Check these when a headline number looks off._

## [34] [SQL] LTV multiplier drift source
_cell id `01a0c4f9-6bfc-769a-bd62-ed0b7062cc1b` · static `01a0c4f9-6bfc-769a-bd62-f3084b403ad8`_
```sql
-- output: tw_ltv_multiplier_drift_source  (BigQuery)
-- LTV multiplier drift (TW): trailing-12-month cohort revenue_ltv @ m35 / (revenue_initial x 12), by window-end month. Port of the US cell.
-- No TW plan band exists yet (the US band 0.54-0.56 is US-specific and is NOT carried over). TW runs ~0.97-0.99 (annual-heavy mix).
WITH end_months AS (
    SELECT month_end FROM UNNEST(GENERATE_DATE_ARRAY(
        DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 12 MONTH),
        DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 1 MONTH), INTERVAL 1 MONTH)) AS month_end
),
multipliers AS (
    SELECT e.month_end, DATE_SUB(e.month_end, INTERVAL 11 MONTH) AS window_start_month, e.month_end AS window_end_month,
        SAFE_DIVIDE(SUM(c.revenue_ltv), SUM(c.revenue_initial) * 12) AS ltv_multiplier
    FROM end_months AS e
    LEFT JOIN `speak-v2-2a1f1.analytics.cohort_ltv_marketing` AS c
        ON c.first_transaction_month BETWEEN DATE_SUB(e.month_end, INTERVAL 11 MONTH) AND e.month_end AND c.country = 'Taiwan' AND c.month_index = 35
    GROUP BY e.month_end
)
SELECT month_end, window_start_month, window_end_month, ltv_multiplier, FORMAT_DATE('%b %Y', month_end) AS month_label FROM multipliers ORDER BY month_end
```

## [35] [CODE] M12 retention partition literals
_cell id `01a0c4f9-8862-7741-ba9d-9610cf3f92b2` · static `01a0c4f9-8862-7741-ba9d-988d77db4660`_
```python
# Builds the date literals the two M12 retention cells splice in via the sqlsafe filter (port of the US cell).
import datetime as dt
from dateutil.relativedelta import relativedelta

today = dt.date.today()

def last_day(d):
    return (d.replace(day=1) + relativedelta(months=1)) - dt.timedelta(days=1)

DAILY_DAYS = 120
anniv_start = today - dt.timedelta(days=DAILY_DAYS)
anniv_end = today - dt.timedelta(days=1)

m = (anniv_start - relativedelta(years=1)).replace(day=1)
base_ends = []
while m <= (anniv_end - relativedelta(years=1)):
    base_ends.append(last_day(m))
    m += relativedelta(months=1)

MOM_COHORTS = 13
latest = today.replace(day=1) - relativedelta(years=1)
while last_day(latest + relativedelta(years=1)) > today:
    latest -= relativedelta(months=1)

cohorts = [(latest - relativedelta(months=i)).replace(day=1) for i in range(MOM_COHORTS)][::-1]
coh_start, coh_end = cohorts[0], cohorts[-1]

parts = set()
for c in cohorts:
    parts.add(last_day(c))
    parts.add(last_day(c + relativedelta(years=1)))

base_month_ends_sql = ", ".join(f"DATE '{d.isoformat()}'" for d in base_ends)
cohort_partitions_sql = ", ".join(f"DATE '{d.isoformat()}'" for d in sorted(parts))
anniv_start_sql = f"DATE '{anniv_start.isoformat()}'"
anniv_end_sql = f"DATE '{anniv_end.isoformat()}'"
coh_start_sql = f"DATE '{coh_start.isoformat()}'"
coh_end_sql = f"DATE '{coh_end.isoformat()}'"
print(anniv_start_sql, anniv_end_sql, coh_start_sql, coh_end_sql)
```

## [36] [SQL] TW M12 retention daily snapshot + trailing 30d
_cell id `01a0c4f9-bc41-702f-b109-563b4c928f9d` · static `01a0c4f9-bc41-702f-b109-5af68e1d95ee`_
```sql
-- output: tw_m12_retention_daily  (BigQuery)
-- Daily M12 revenue retention on TW annual_single cohorts (Revenue Retention SoT basis: user_daily_arr standing ARR, gross less taxes less churn refund).
-- base = users whose first transaction was exactly one year before day d (M0 ARR at cohort month-end); anniv = their standing ARR on the anniversary.
-- Raw daily is noisy; the 30-day trailing ratio is the signal. Port of the US cell (US had a 21.7% anchor; TW carries no anchor yet).
WITH base AS (
    SELECT user_id, first_transaction_date, arr_usd_gross_less_taxes_less_churn_refund AS rev0
    FROM `speak-v2-2a1f1.analytics.user_daily_arr`
    WHERE first_duration = 'annual_single' AND country = 'Taiwan'
        AND first_transaction_date BETWEEN DATE_SUB({{ anniv_start_sql | sqlsafe }}, INTERVAL 1 YEAR) AND DATE_SUB({{ anniv_end_sql | sqlsafe }}, INTERVAL 1 YEAR)
        AND day = LAST_DAY(first_transaction_month)
        AND ds IN ({{ base_month_ends_sql | sqlsafe }})
),
anniv AS (
    SELECT user_id, arr_usd_gross_less_taxes_less_churn_refund AS rev12
    FROM `speak-v2-2a1f1.analytics.user_daily_arr`
    WHERE first_duration = 'annual_single' AND country = 'Taiwan'
        AND day = DATE_ADD(first_transaction_date, INTERVAL 1 YEAR)
        AND ds BETWEEN {{ anniv_start_sql | sqlsafe }} AND {{ anniv_end_sql | sqlsafe }}
),
daily AS (
    SELECT DATE_ADD(b.first_transaction_date, INTERVAL 1 YEAR) AS d, SUM(b.rev0) AS base_arr, SUM(a.rev12) AS surv_arr
    FROM base AS b LEFT JOIN anniv AS a ON b.user_id = a.user_id GROUP BY 1
),
spine AS (SELECT d FROM UNNEST(GENERATE_DATE_ARRAY({{ anniv_start_sql | sqlsafe }}, {{ anniv_end_sql | sqlsafe }})) AS d),
joined AS (
    SELECT s.d, COALESCE(daily.base_arr, 0) AS base_arr, COALESCE(daily.surv_arr, 0) AS surv_arr
    FROM spine AS s LEFT JOIN daily ON s.d = daily.d
)
SELECT d,
    ROUND(100 * SAFE_DIVIDE(surv_arr, NULLIF(base_arr, 0)), 2) AS m12_raw_pct,
    ROUND(100 * SAFE_DIVIDE(SUM(surv_arr) OVER trailing_30d, NULLIF(SUM(base_arr) OVER trailing_30d, 0)), 2) AS m12_trailing30_pct,
    ROUND(base_arr) AS base_arr, ROUND(surv_arr) AS retained_arr
FROM joined
WINDOW trailing_30d AS (ORDER BY d ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
ORDER BY d
```

## [37] [SQL] TW M12 retention by cohort month
_cell id `01a0c4f9-d56d-70fd-898e-59ce203724da` · static `01a0c4f9-d56d-70fd-898e-5e22bb476ecb`_
```sql
-- output: tw_m12_retention_cohort_month  (BigQuery)
-- Matured M12 revenue retention by cohort month (TW annual_single): standing ARR at M12 month-end / standing ARR at M0 month-end.
-- Latest 13 fully matured cohorts; the newest is flagged. Port of the US cell.
WITH s AS (
    SELECT first_transaction_month AS coh,
        SUM(IF(ds = LAST_DAY(first_transaction_month), arr_usd_gross_less_taxes_less_churn_refund, 0)) AS m0_arr,
        SUM(IF(ds = LAST_DAY(DATE_ADD(first_transaction_month, INTERVAL 1 YEAR)), arr_usd_gross_less_taxes_less_churn_refund, 0)) AS m12_arr,
        COUNT(DISTINCT IF(ds = LAST_DAY(first_transaction_month), user_id, NULL)) AS n_users
    FROM `speak-v2-2a1f1.analytics.user_daily_arr`
    WHERE first_duration = 'annual_single' AND country = 'Taiwan'
        AND first_transaction_month BETWEEN {{ coh_start_sql | sqlsafe }} AND {{ coh_end_sql | sqlsafe }}
        AND ds IN ({{ cohort_partitions_sql | sqlsafe }})
    GROUP BY 1
)
SELECT coh AS cohort_month, ROUND(100 * SAFE_DIVIDE(m12_arr, NULLIF(m0_arr, 0)), 2) AS m12_pct, n_users,
    ROUND(m0_arr) AS base_arr, ROUND(m12_arr) AS retained_arr, coh = MAX(coh) OVER () AS is_latest_matured_cohort
FROM s ORDER BY 1
```

## [38] [SQL] Media budget mix (weekly, by bucketed channel)
_cell id `01a0c4f9-e184-7459-be78-8c776fe1e9bc` · static `01a0c4f9-e184-7459-be78-90512402eabf`_
```sql
-- output: tw_media_budget_mix  (DuckDB dataframe SQL)
-- Weekly TW spend by bucketed_channel (Sunday weeks), from tw_channel_daily. Composition view for the Monitoring section.
SELECT (CAST(day AS DATE) - CAST(EXTRACT(dow FROM CAST(day AS DATE)) AS INTEGER))::DATE AS week, channel, SUM(spend) AS spend
FROM tw_channel_daily
GROUP BY 1, 2 ORDER BY 1, 2
```

## [39] [SQL] ARR KPI reconciliation check
_cell id `01a0c4f9-f072-767e-9d26-033f842b03c6` · static `01a0c4f9-f072-767e-9d26-067dfac04537`_
```sql
-- output: tw_arr_kpi_reconciliation_check  (DuckDB dataframe SQL)
-- Does net incremental ARR reconcile to the sum of its components? Residual should be ~0 every day.
SELECT COUNT(*) AS days_checked, MAX(ABS(arr_reconciliation_residual)) AS max_abs_daily_residual,
    AVG(ABS(arr_reconciliation_residual)) AS avg_abs_daily_residual, SUM(arr_reconciliation_residual) AS total_residual
FROM tw_arr_kpi_daily_base
```

## [40] [CODE] Charts — Monitoring (LTV multiplier drift, M12 retention, media mix)
_cell id `01a0c4fa-3a6a-731d-9ae6-189ba58872e3` · static `01a0c4fa-3a6a-731d-9ae6-1ec56378b363`_
```python
# Monitoring charts: LTV multiplier drift (T12M rolling), daily M12 retention raw vs 30d trailing, matured M12 by cohort month, weekly media mix.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_dr = tw_ltv_multiplier_drift_source.copy(); _dr["month_end"] = pd.to_datetime(_dr["month_end"])
_md = tw_m12_retention_daily.copy(); _md["d"] = pd.to_datetime(_md["d"])
_mc = tw_m12_retention_cohort_month.copy(); _mc["cohort_month"] = pd.to_datetime(_mc["cohort_month"])
_mm = tw_media_budget_mix.copy(); _mm["week"] = pd.to_datetime(_mm["week"])
_C1, _C2, _C3, _MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#9ec5f4"

fig = make_subplots(rows=2, cols=2, subplot_titles=["LTV multiplier — T12M rolling (revenue_ltv m35 / revenue_initial × 12)", "Daily M12 revenue retention — raw (light) vs 30-day trailing",
                                                    "Matured M12 revenue retention by cohort month (annual_single)", "Weekly spend by bucketed channel"], vertical_spacing=0.16, horizontal_spacing=0.08)
fig.add_trace(go.Scatter(x=_dr["month_end"], y=_dr["ltv_multiplier"], mode="lines+markers", name="LTV multiplier", line=dict(color=_C1, width=2), marker=dict(size=8), showlegend=False, hovertemplate="%{x|%b %Y}<br>%{y:.3f}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Scatter(x=_md["d"], y=_md["m12_raw_pct"], mode="lines", name="M12 raw (daily)", line=dict(color=_MUTED, width=1), hovertemplate="%{x|%b %d}<br>raw %{y:.1f}%<extra></extra>"), row=1, col=2)
fig.add_trace(go.Scatter(x=_md["d"], y=_md["m12_trailing30_pct"], mode="lines", name="M12 30-day trailing", line=dict(color=_C1, width=2.5), hovertemplate="%{x|%b %d}<br>trailing %{y:.1f}%<extra></extra>"), row=1, col=2)
_col = [_C2 if l else _C1 for l in _mc["is_latest_matured_cohort"]]
fig.add_trace(go.Bar(x=_mc["cohort_month"], y=_mc["m12_pct"], marker_color=_col, name="M12 % by cohort", showlegend=False, customdata=_mc[["n_users"]].values, hovertemplate="%{x|%b %Y} cohort<br>%{y:.1f}% · %{customdata[0]:,} users<extra></extra>"), row=2, col=1)
_ORDER = ["Paid", "Brand", "Influencer", "Paid Branded Search", "Agency Spend", "Referral", "Affiliate", "Public Relations", "Market Research & Analytics"]
_HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948", "#9ec5f4"]
_chs = [c for c in _ORDER if c in set(_mm["channel"])] + [c for c in sorted(set(_mm["channel"])) if c not in _ORDER]
for i, ch in enumerate(_chs):
    d = _mm[_mm["channel"] == ch]
    fig.add_trace(go.Bar(x=d["week"], y=d["spend"], name=ch, marker_color=_HUES[i % len(_HUES)], hovertemplate="wk of %{x|%b %d}<br>" + ch + ": $%{y:,.0f}<extra></extra>"), row=2, col=2)
fig.update_yaxes(tickformat=".2f", row=1, col=1)
fig.update_yaxes(ticksuffix="%", row=1, col=2)
fig.update_yaxes(ticksuffix="%", row=2, col=1)
fig.update_yaxes(tickprefix="$", tickformat=",.2s", row=2, col=2)
fig.update_yaxes(gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False)
fig.update_layout(height=720, template="plotly_white", barmode="stack", margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.06, x=0), hovermode="x unified")
fig
```

## [41] [MARKDOWN] Section — Churn forecasting
_cell id `01a0c4fb-076b-77fa-948c-738cb1c008b8` · static `01a0c4fb-076b-77fa-948c-773863d1a6ea`_
## Churn forecasting
Actual gross churn · per-plan retention curves · cohort-survival churn roll-forward · annual renewal cliff · TW

_Ported from the US model with `country_group = 'Taiwan'`. **Per Kevin (2026-09-21) the US per-plan settings are kept for now**: the annual M12 caps (app store ≤ 18%, play store ≥ 26%, paddle ≤ 38%) and the payment-plan / quarterly / semiannual anchors are US values. TW empirical M12 retention is higher (~26% / ~41% / ~31%), so the annual cliff here is conservative (over-forecasts churn) until the caps are re-fit for TW. The TW plan has no churn target, so there is no plan-vs-actual line; the closed-month reconciliation is the honesty check. The Exit ARR landing table is not carried over (no TW ARR plan)._

## [42] [SQL] TW monthly gross churn (actual)
_cell id `01a0c4fb-209e-703a-86a6-7dacaaf89486` · static `01a0c4fb-209e-703a-86a6-83e495ed8ae3`_
```sql
-- output: tw_monthly_gross_churn  (BigQuery)
-- TW monthly GROSS churn ($m) — actuals from user_daily_arr (churned_arr_less_taxes). Complete months only (excludes the current partial month).
SELECT DATE_TRUNC(day, MONTH) AS month, ROUND(ABS(SUM(COALESCE(churned_arr_less_taxes, 0))) / 1e6, 3) AS actual_gross_churn_m
FROM `speak-v2-2a1f1.analytics.user_daily_arr`
WHERE country_group = 'Taiwan' AND user_id IS NOT NULL AND day >= DATE '2026-01-01' AND ds >= DATE '2026-01-01'
  AND day < DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH)
GROUP BY month ORDER BY month
```

## [43] [SQL] TW per-plan retention curves (platform × duration × tier)
_cell id `01a0c4fb-6a0d-73eb-aaf7-fb56e48c1d9d` · static `01a0c4fb-6a0d-73eb-aaf7-ff80974e1423`_
```sql
-- output: tw_monthly_retention_curve  (BigQuery)
-- TW per-plan retention curves keyed by platform x duration x tier. Port of the US cell (US settings kept for now, Kevin 2026-09-21):
-- monthly and annual_single use observed month-end standing ARR (annual M12 with the US platform caps); payment-plan, quarterly and
-- semiannual use the US anchors. Re-fit for TW when the churn model becomes decision-grade.
WITH params AS (SELECT LAST_DAY(DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL 1 MONTH)) AS last_closed_month_end),
cohort_age AS (
  SELECT COALESCE(first_platform, 'unknown') AS first_platform, COALESCE(first_duration, 'unknown') AS first_duration, COALESCE(first_tier, 'unknown') AS first_tier,
    first_transaction_month AS cohort_month, DATE_DIFF(DATE_TRUNC(day, MONTH), first_transaction_month, MONTH) AS age, SUM(arr_usd_gross_less_taxes_less_churn_refund) AS standing_arr
  FROM `speak-v2-2a1f1.analytics.user_daily_arr`
  WHERE country_group = 'Taiwan' AND first_transaction_month BETWEEN DATE '2023-01-01' AND DATE '2025-12-01' AND ds = LAST_DAY(ds) AND day = ds
  GROUP BY 1, 2, 3, 4, 5),
m0 AS (SELECT first_platform, first_duration, first_tier, cohort_month, standing_arr AS m0_arr FROM cohort_age WHERE age = 0),
segments AS (SELECT DISTINCT first_platform, first_duration, first_tier FROM m0),
ages AS (SELECT age FROM UNNEST(GENERATE_ARRAY(0, 35)) AS age),
empirical AS (
  SELECT m.first_platform, m.first_duration, m.first_tier, a.age, SAFE_DIVIDE(SUM(COALESCE(c.standing_arr, 0)), SUM(m.m0_arr)) AS retention, COUNT(DISTINCT m.cohort_month) AS matured_cohorts
  FROM ages AS a CROSS JOIN params AS p
  JOIN m0 AS m ON LAST_DAY(DATE_ADD(m.cohort_month, INTERVAL a.age MONTH)) <= p.last_closed_month_end
  LEFT JOIN cohort_age AS c ON c.first_platform = m.first_platform AND c.first_duration = m.first_duration AND c.first_tier = m.first_tier AND c.cohort_month = m.cohort_month AND c.age = a.age
  GROUP BY 1, 2, 3, 4),
curve_base AS (
  SELECT s.first_platform, s.first_duration, s.first_tier, a.age, e.matured_cohorts,
    CASE
      WHEN s.first_duration = 'annual_payment_plan' THEN
        CASE WHEN a.age = 0 THEN 1.0
             WHEN MOD(a.age, 12) BETWEEN 1 AND 6 THEN POW(0.29, DIV(a.age, 12)) * (0.90 - (MOD(a.age, 12) - 1) * (0.90 - 0.66) / 5)
             WHEN MOD(a.age, 12) BETWEEN 7 AND 11 THEN POW(0.29, DIV(a.age, 12)) * (0.66 - (MOD(a.age, 12) - 6) * (0.66 - 0.54) / 5)
             ELSE POW(0.29, DIV(a.age, 12)) END
      WHEN s.first_duration = 'quarterly' THEN CASE WHEN a.age < 3 THEN 1.0 WHEN DIV(a.age, 3) = 1 THEN 0.836 ELSE 0.518 * POW(0.518 / 0.836, DIV(a.age, 3) - 2) END
      WHEN s.first_duration = 'semiannual' THEN POW(0.835, DIV(a.age, 6))
      WHEN s.first_duration = 'annual_single' AND a.age = 12 AND e.retention IS NOT NULL THEN
        CASE WHEN s.first_platform = 'app_store' THEN LEAST(e.retention, 0.18) WHEN s.first_platform = 'play_store' THEN GREATEST(e.retention, 0.26)
             WHEN s.first_platform = 'paddle' THEN LEAST(e.retention, 0.38) ELSE e.retention END
      WHEN s.first_duration = 'annual_single' AND e.retention IS NULL THEN
        POW(CASE WHEN s.first_platform = 'app_store' THEN 0.18 WHEN s.first_platform = 'play_store' THEN 0.28 WHEN s.first_platform IN ('paddle', 'stripe') THEN 0.36 ELSE 0.22 END, DIV(a.age, 12))
      ELSE COALESCE(e.retention, 0) END AS retention,
    s.first_platform IN ('paddle', 'stripe') AND a.age >= 12 AS low_maturity_web_m12
  FROM segments AS s CROSS JOIN ages AS a
  LEFT JOIN empirical AS e ON e.first_platform = s.first_platform AND e.first_duration = s.first_duration AND e.first_tier = s.first_tier AND e.age = a.age),
curve AS (
  SELECT *, GREATEST(COALESCE(LAG(retention) OVER (PARTITION BY first_platform, first_duration, first_tier ORDER BY age), retention) - retention, 0) AS incremental_loss
  FROM curve_base)
SELECT first_platform, first_duration, first_tier, age, retention, incremental_loss, matured_cohorts, low_maturity_web_m12
FROM curve ORDER BY first_duration, first_platform, first_tier, age
```

## [44] [SQL] Live TW plan cohorts M0 ARR by segment
_cell id `01a0c4fb-8334-76e9-860c-004c7fe0c880` · static `01a0c4fb-8334-76e9-860c-0706bd28c397`_
```sql
-- output: tw_monthly_cohort_m0_arr  (BigQuery)
-- Existing TW plan cohorts at platform x duration x tier grain. M0 = standing ARR at each cohort month end; the current incomplete month is excluded.
SELECT COALESCE(first_platform, 'unknown') AS first_platform, COALESCE(first_duration, 'unknown') AS first_duration, COALESCE(first_tier, 'unknown') AS first_tier,
  first_transaction_month AS cohort_month, SUM(arr_usd_gross_less_taxes_less_churn_refund) AS m0_arr, TRUE AS is_closed_cohort
FROM `speak-v2-2a1f1.analytics.user_daily_arr`
WHERE country_group = 'Taiwan'
  AND first_transaction_month BETWEEN DATE '2024-06-01' AND DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Taipei'), MONTH), INTERVAL 1 MONTH)
  AND ds = LAST_DAY(first_transaction_month) AND day = ds
GROUP BY 1, 2, 3, 4 ORDER BY cohort_month, first_duration, first_platform, first_tier
```

## [45] [SQL] Monthly new-ARR forecast (trailing-3 held flat)
_cell id `01a0c4fb-96d5-728c-875e-739520a0c6c7` · static `01a0c4fb-96d5-728c-875e-759bc5d62988`_
```sql
-- output: tw_monthly_new_arr_forecast  (DuckDB dataframe SQL)
-- Forecast seed for future monthly-plan cohorts: trailing-three closed monthly-cohort M0 ARR held flat through Jun 2027.
-- (The US version is an editable INPUT; this build cannot create input cells, so the default is used directly.)
WITH monthly_totals AS (
  SELECT CAST(cohort_month AS DATE) AS cohort_month, SUM(m0_arr) AS monthly_new_arr
  FROM tw_monthly_cohort_m0_arr
  WHERE is_closed_cohort AND first_duration LIKE 'month%' AND m0_arr IS NOT NULL
  GROUP BY 1),
trailing_three AS (
  SELECT AVG(monthly_new_arr) AS trailing_3m_monthly_new_arr
  FROM (SELECT monthly_new_arr FROM monthly_totals ORDER BY cohort_month DESC LIMIT 3)),
months AS (
  SELECT CAST(m AS DATE) AS month
  FROM generate_series(CAST(DATE_TRUNC('month', CURRENT_DATE) AS DATE), DATE '2027-06-01', INTERVAL '1 month') AS t(m))
SELECT month, ROUND(trailing_3m_monthly_new_arr, 2) AS monthly_new_arr
FROM months CROSS JOIN trailing_three ORDER BY month
```

## [46] [SQL] Monthly churn forecast (cohort survival)
_cell id `01a0c4fb-edf3-765e-95e2-51334323f0db` · static `01a0c4fb-edf3-765e-95e2-55423f78c88d`_
```sql
-- output: tw_monthly_plan_churn_forecast  (DuckDB dataframe SQL)
-- All-plan cohort-survival gross-churn roll-forward at platform x duration x tier grain (TW). Port of the US cell.
-- Future monthly-plan M0 ARR comes from tw_monthly_new_arr_forecast; other future plan cohorts hold their trailing-three-month segment run rate.
-- Annual cliff is included here exactly once.
WITH months AS (
  SELECT CAST(month AS DATE) AS month FROM generate_series(DATE '2026-01-01', DATE '2027-06-01', INTERVAL '1 month') AS t(month)),
actual_cohorts AS (
  SELECT CAST(first_platform AS VARCHAR) AS first_platform, CAST(first_duration AS VARCHAR) AS first_duration, CAST(first_tier AS VARCHAR) AS first_tier,
    CAST(cohort_month AS DATE) AS cohort_month, CAST(m0_arr AS DOUBLE) AS m0_arr, 'actual' AS cohort_source
  FROM tw_monthly_cohort_m0_arr WHERE m0_arr IS NOT NULL),
last_three AS (SELECT DISTINCT cohort_month FROM actual_cohorts ORDER BY cohort_month DESC LIMIT 3),
monthly_mix AS (
  SELECT first_platform, first_tier, SUM(m0_arr) / SUM(SUM(m0_arr)) OVER () AS segment_share
  FROM actual_cohorts WHERE first_duration LIKE 'month%' AND cohort_month IN (SELECT cohort_month FROM last_three)
  GROUP BY 1, 2),
forecast_monthly AS (
  SELECT mm.first_platform, 'monthly' AS first_duration, mm.first_tier, CAST(f.month AS DATE) AS cohort_month,
    CAST(f.monthly_new_arr AS DOUBLE) * mm.segment_share AS m0_arr, 'forecast_monthly' AS cohort_source
  FROM tw_monthly_new_arr_forecast AS f CROSS JOIN monthly_mix AS mm WHERE f.monthly_new_arr IS NOT NULL),
other_segment_defaults AS (
  SELECT first_platform, first_duration, first_tier, SUM(m0_arr) / 3.0 AS monthly_m0_arr
  FROM actual_cohorts WHERE first_duration NOT LIKE 'month%' AND cohort_month IN (SELECT cohort_month FROM last_three)
  GROUP BY 1, 2, 3),
forecast_other AS (
  SELECT d.first_platform, d.first_duration, d.first_tier, CAST(f.month AS DATE) AS cohort_month, d.monthly_m0_arr AS m0_arr, 'forecast_other_flat' AS cohort_source
  FROM (SELECT DISTINCT month FROM tw_monthly_new_arr_forecast) AS f CROSS JOIN other_segment_defaults AS d),
cohorts AS (SELECT * FROM actual_cohorts UNION ALL SELECT * FROM forecast_monthly UNION ALL SELECT * FROM forecast_other),
curve AS (
  SELECT CAST(first_platform AS VARCHAR) AS first_platform, CAST(first_duration AS VARCHAR) AS first_duration, CAST(first_tier AS VARCHAR) AS first_tier,
    CAST(age AS INTEGER) AS age, CAST(incremental_loss AS DOUBLE) AS incremental_loss, CAST(matured_cohorts AS INTEGER) AS matured_cohorts, CAST(low_maturity_web_m12 AS BOOLEAN) AS low_maturity_web_m12
  FROM tw_monthly_retention_curve),
cohort_months AS (
  SELECT m.month, c.*, DATE_DIFF('month', c.cohort_month, m.month) AS age FROM months AS m CROSS JOIN cohorts AS c WHERE c.cohort_month <= m.month),
losses AS (
  SELECT cm.month, cm.first_duration, cm.cohort_source, cm.age,
    cm.m0_arr * COALESCE(CASE WHEN cv.matured_cohorts >= 3 OR cm.first_duration IN ('annual_payment_plan', 'quarterly', 'semiannual') THEN cv.incremental_loss END, fb.incremental_loss, 0) AS churn_arr,
    COALESCE(cv.low_maturity_web_m12, fb.low_maturity_web_m12, FALSE) AS low_maturity_web_m12
  FROM cohort_months AS cm
  LEFT JOIN curve AS cv ON cv.first_platform = cm.first_platform AND cv.first_duration = cm.first_duration AND cv.first_tier = cm.first_tier AND cv.age = LEAST(cm.age, 35)
  LEFT JOIN curve AS fb ON fb.first_platform = CASE WHEN cm.first_platform IN ('paddle', 'stripe') THEN 'paddle' ELSE cm.first_platform END
    AND fb.first_duration = cm.first_duration AND fb.first_tier = 'plus' AND fb.age = LEAST(cm.age, 35)
  WHERE cm.age >= 1)
SELECT month,
  SUM(CASE WHEN first_duration LIKE 'month%' THEN churn_arr ELSE 0 END) AS monthly_churn,
  SUM(CASE WHEN first_duration = 'annual_single' THEN churn_arr ELSE 0 END) AS annual_cliff,
  SUM(CASE WHEN first_duration = 'annual_payment_plan' THEN churn_arr ELSE 0 END) AS payment_plan_churn,
  SUM(CASE WHEN first_duration = 'quarterly' THEN churn_arr ELSE 0 END) AS quarterly_churn,
  SUM(CASE WHEN first_duration = 'semiannual' THEN churn_arr ELSE 0 END) AS semiannual_churn,
  SUM(CASE WHEN first_duration NOT LIKE 'month%' AND first_duration NOT IN ('annual_single', 'annual_payment_plan', 'quarterly', 'semiannual') THEN churn_arr ELSE 0 END) AS other_churn,
  SUM(churn_arr) AS total_plan_churn,
  SUM(CASE WHEN cohort_source = 'actual' THEN churn_arr ELSE 0 END) AS existing_cohort_churn,
  SUM(CASE WHEN cohort_source <> 'actual' THEN churn_arr ELSE 0 END) AS forecast_cohort_churn,
  BOOL_OR(low_maturity_web_m12) AS has_low_maturity_web_m12
FROM losses GROUP BY month ORDER BY month
```

## [47] [SQL] Total expected churn by month + reconciliation vs actual
_cell id `01a0c4fc-0bfc-77d8-bcb6-76c7e2851727` · static `01a0c4fc-0bfc-77d8-bcb6-7852c4e0c90a`_
```sql
-- output: tw_total_expected_churn  (DuckDB dataframe SQL)
-- Bottoms-up total expected gross churn by month (annual cliff + monthly + other), with status and the closed-month reconciliation
-- against actual TW gross churn. Gaps are intentionally surfaced; no calibration factor is applied.
WITH forecast_start AS (SELECT MIN(CAST(month AS DATE)) AS current_month FROM tw_monthly_new_arr_forecast),
exp AS (
  SELECT CAST(p.month AS DATE) AS month, CAST(p.annual_cliff AS DOUBLE) AS annual_cliff, CAST(p.monthly_churn AS DOUBLE) AS monthly_churn,
    CAST(p.payment_plan_churn + p.quarterly_churn + p.semiannual_churn + p.other_churn AS DOUBLE) AS other,
    CAST(p.total_plan_churn AS DOUBLE) AS total_expected_churn, CAST(p.has_low_maturity_web_m12 AS BOOLEAN) AS low_maturity_web_m12,
    CASE WHEN CAST(p.month AS DATE) < f.current_month THEN 'closed month — compare to actual'
         WHEN CAST(p.month AS DATE) = f.current_month THEN 'forecast — current month' ELSE 'forecast' END AS status
  FROM tw_monthly_plan_churn_forecast AS p CROSS JOIN forecast_start AS f)
SELECT e.*, CAST(a.actual_gross_churn_m AS DOUBLE) * 1000000 AS actual_gross_churn,
  (e.total_expected_churn - CAST(a.actual_gross_churn_m AS DOUBLE) * 1000000) / NULLIF(CAST(a.actual_gross_churn_m AS DOUBLE) * 1000000, 0) AS gap_pct,
  ABS((e.total_expected_churn - CAST(a.actual_gross_churn_m AS DOUBLE) * 1000000) / NULLIF(CAST(a.actual_gross_churn_m AS DOUBLE) * 1000000, 0)) <= 0.10 AS within_10pct
FROM exp e LEFT JOIN tw_monthly_gross_churn a ON CAST(a.month AS DATE) = e.month
ORDER BY e.month
```

## [48] [SQL] Renewal cliff forecast source
_cell id `01a0c4fc-68ec-77cd-87c4-3ec1d532d741` · static `01a0c4fc-68ec-77cd-87c4-4387e30aa5d9`_
```sql
-- output: tw_renewal_cliff_forecast_source  (BigQuery)
-- TW annual_single renewal cliff, weighted by each cohort's actual platform x tier mix. Port of the US cell (US M12 caps kept for now).
-- Per cohort: forecast churn = pre-renewal (M11, else M0) standing ARR x (1 - m12 retention); actual churn = M11 -> M12 drop once the cohort matures.
-- annual_payment_plan is excluded: it is modeled as in-year decay in the total churn roll-forward.
WITH mature_snap AS (
  SELECT COALESCE(first_platform, 'unknown') AS first_platform, COALESCE(first_tier, 'unknown') AS first_tier, first_transaction_month AS cohort_month,
    DATE_DIFF(DATE_TRUNC(day, MONTH), first_transaction_month, MONTH) AS age, SUM(arr_usd_gross_less_taxes_less_churn_refund) AS arr
  FROM `speak-v2-2a1f1.analytics.user_daily_arr`
  WHERE country_group = 'Taiwan' AND first_duration = 'annual_single' AND first_transaction_month BETWEEN DATE '2024-01-01' AND DATE '2025-07-01' AND ds = LAST_DAY(ds) AND day = ds
  GROUP BY 1, 2, 3, 4),
platform_tier_retention AS (
  SELECT first_platform, first_tier,
    CASE WHEN first_platform = 'app_store' THEN LEAST(SAFE_DIVIDE(SUM(IF(age = 12, arr, 0)), SUM(IF(age = 0, arr, 0))), 0.18)
         WHEN first_platform = 'play_store' THEN GREATEST(SAFE_DIVIDE(SUM(IF(age = 12, arr, 0)), SUM(IF(age = 0, arr, 0))), 0.26)
         WHEN first_platform = 'paddle' THEN LEAST(SAFE_DIVIDE(SUM(IF(age = 12, arr, 0)), SUM(IF(age = 0, arr, 0))), 0.38)
         ELSE SAFE_DIVIDE(SUM(IF(age = 12, arr, 0)), SUM(IF(age = 0, arr, 0))) END AS m12_retention,
    COUNT(DISTINCT IF(age = 12, cohort_month, NULL)) AS matured_cohorts
  FROM mature_snap GROUP BY 1, 2),
snap AS (
  SELECT COALESCE(first_platform, 'unknown') AS first_platform, COALESCE(first_tier, 'unknown') AS first_tier, first_transaction_month AS cohort_month,
    DATE_DIFF(DATE_TRUNC(day, MONTH), first_transaction_month, MONTH) AS age, SUM(arr_usd_gross_less_taxes_less_churn_refund) AS arr
  FROM `speak-v2-2a1f1.analytics.user_daily_arr`
  WHERE country_group = 'Taiwan' AND first_duration = 'annual_single' AND first_transaction_month >= DATE '2025-01-01' AND ds = LAST_DAY(ds) AND day = ds
  GROUP BY 1, 2, 3, 4),
piv AS (
  SELECT first_platform, first_tier, cohort_month, DATE_ADD(cohort_month, INTERVAL 12 MONTH) AS renewal_month,
    MAX(IF(age = 0, arr, NULL)) AS m0, MAX(IF(age = 11, arr, NULL)) AS m11, MAX(IF(age = 12, arr, NULL)) AS m12
  FROM snap GROUP BY 1, 2, 3, 4),
per_segment AS (
  SELECT p.first_platform, p.first_tier, p.cohort_month, p.renewal_month, COALESCE(p.m11, p.m0) AS pre_renewal_arr,
    COALESCE(r.m12_retention, CASE WHEN p.first_platform = 'app_store' THEN 0.18 WHEN p.first_platform = 'play_store' THEN 0.28 WHEN p.first_platform IN ('paddle', 'stripe') THEN 0.36 ELSE 0.22 END) AS m12_retention,
    COALESCE(p.m11, p.m0) * (1 - COALESCE(r.m12_retention, CASE WHEN p.first_platform = 'app_store' THEN 0.18 WHEN p.first_platform = 'play_store' THEN 0.28 WHEN p.first_platform IN ('paddle', 'stripe') THEN 0.36 ELSE 0.22 END)) AS forecast_churn,
    p.m12 IS NOT NULL AS is_actual, IF(p.m12 IS NOT NULL, GREATEST(COALESCE(p.m11, p.m0) - p.m12, 0), NULL) AS actual_churn,
    r.matured_cohorts, p.first_platform IN ('paddle', 'stripe') AND COALESCE(r.matured_cohorts, 0) = 0 AS low_maturity_web_m12
  FROM piv AS p LEFT JOIN platform_tier_retention AS r USING (first_platform, first_tier)
  WHERE p.renewal_month BETWEEN DATE '2026-01-01' AND DATE '2027-06-30'),
per_cohort AS (
  SELECT cohort_month, renewal_month, SUM(pre_renewal_arr) AS pre_renewal_arr, SUM(forecast_churn) AS forecast_churn, SUM(actual_churn) AS actual_churn,
    LOGICAL_AND(is_actual) AS is_actual, LOGICAL_OR(low_maturity_web_m12) AS low_maturity_web_m12
  FROM per_segment GROUP BY 1, 2),
totals AS (SELECT renewal_month, SUM(IF(is_actual, actual_churn, forecast_churn)) AS month_churn, LOGICAL_AND(is_actual) AS month_is_actual FROM per_cohort GROUP BY renewal_month),
gross_churn AS (
  SELECT DATE_TRUNC(day, MONTH) AS month, ABS(SUM(COALESCE(churned_arr_less_taxes, 0))) AS actual_gross_churn
  FROM `speak-v2-2a1f1.analytics.user_daily_arr`
  WHERE country_group = 'Taiwan' AND user_id IS NOT NULL AND day >= DATE '2026-01-01' AND ds >= DATE '2026-01-01' GROUP BY month)
SELECT c.renewal_month, FORMAT_DATE('%b %Y', c.renewal_month) AS renewal_month_label, FORMAT_DATE('%b %Y cohort', c.cohort_month) AS cohort_month_label,
  c.is_actual, c.forecast_churn, c.actual_churn, IF(c.is_actual, c.actual_churn, c.forecast_churn) AS forecasted_cliff_churn,
  t.month_churn AS total_forecasted_cliff_churn, t.month_is_actual, c.low_maturity_web_m12, g.actual_gross_churn,
  t.month_churn = (SELECT MAX(month_churn) FROM totals) AS is_peak_month
FROM per_cohort AS c JOIN totals AS t USING (renewal_month) LEFT JOIN gross_churn AS g ON c.renewal_month = g.month
ORDER BY c.renewal_month, c.cohort_month
```

## [49] [CODE] Cliff monthly table + churn charts
_cell id `01a0c4fc-a978-746e-b01d-2f37c0f9efb7` · static `01a0c4fc-a978-746e-b01d-33f8ee05c0a6`_
```python
# Renewal-cliff monthly table (tw_cliff_monthly) + charts: expected gross churn by component vs actual (closed months), and the annual renewal cliff by month.
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_cf = tw_renewal_cliff_forecast_source.drop_duplicates("renewal_month").sort_values("renewal_month").copy()
_cf["renewal_month"] = pd.to_datetime(_cf["renewal_month"])
def _fk(v): return "—" if pd.isna(v) else f"${v/1e3:,.0f}K"
tw_cliff_monthly = pd.DataFrame({"Renewal month": _cf["renewal_month_label"].values,
                                 "Upcoming annual churn ARR": [_fk(v) for v in _cf["total_forecasted_cliff_churn"]],
                                 "Status": ["✅ actual" if a else "📊 forecast" for a in _cf["month_is_actual"]]})

_t = tw_total_expected_churn.copy(); _t["month"] = pd.to_datetime(_t["month"])
_C1, _C2, _C3, _GREY = "#2a78d6", "#eb6834", "#1baf7a", "#52514e"
fig = make_subplots(rows=2, cols=1, subplot_titles=["Expected gross churn by component (stacked) vs actual gross churn (closed months)", "Annual renewal cliff by renewal month (actual once matured, else forecast)"], vertical_spacing=0.16)
fig.add_trace(go.Bar(x=_t["month"], y=_t["annual_cliff"], name="Annual cliff", marker_color=_C1, hovertemplate="%{x|%b %Y}<br>annual cliff $%{y:,.0f}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=_t["month"], y=_t["monthly_churn"], name="Monthly-plan churn", marker_color=_C2, hovertemplate="%{x|%b %Y}<br>monthly $%{y:,.0f}<extra></extra>"), row=1, col=1)
fig.add_trace(go.Bar(x=_t["month"], y=_t["other"], name="Other plans", marker_color=_C3, hovertemplate="%{x|%b %Y}<br>other $%{y:,.0f}<extra></extra>"), row=1, col=1)
_a = _t.dropna(subset=["actual_gross_churn"])
fig.add_trace(go.Scatter(x=_a["month"], y=_a["actual_gross_churn"], mode="lines+markers", name="Actual gross churn", line=dict(color=_GREY, width=2.5), marker=dict(size=9, symbol="diamond"), hovertemplate="%{x|%b %Y}<br>actual $%{y:,.0f}<extra></extra>"), row=1, col=1)
_colc = [_C1 if a else "#9ec5f4" for a in _cf["month_is_actual"]]
fig.add_trace(go.Bar(x=_cf["renewal_month"], y=_cf["total_forecasted_cliff_churn"], name="Renewal cliff (dark = actual)", marker_color=_colc, hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>"), row=2, col=1)
fig.update_yaxes(tickprefix="$", tickformat=",.2s", gridcolor="#eeede9", zeroline=False)
fig.update_xaxes(showgrid=False, tickformat="%b %y")
fig.update_layout(height=720, template="plotly_white", barmode="stack", margin=dict(l=40, r=20, t=60, b=40), legend=dict(orientation="h", y=-0.06, x=0), hovermode="x unified")
fig.show()
tw_cliff_monthly
```
