-- BigQuery project speak-v2-2a1f1. Campaign 120216508762540167 (tw_meta_standard_ios_tw-en_pros_trial_ongoing_winning), 2026-09-01 .. latest (2026-10-06 at time of pull).

-- 1) Meta funnel per ad -> data/meta_funnel.csv
SELECT ad_id, ANY_VALUE(ad_name) ad_name, ANY_VALUE(adset_name) adset_name, ANY_VALUE(ad_preview_link) preview,
       MIN(date) first_date, MAX(date) last_date, COUNT(DISTINCT CASE WHEN spend>0 THEN date END) active_days,
       ROUND(SUM(spend),2) spend, SUM(impressions) impressions, SUM(clicks) clicks, SUM(installs) installs, SUM(signups) signups,
       SUM(trial_starts) trials, ROUND(SUM(adj_trial_starts),2) adj_trials, SUM(trial_converts) trial_converts, SUM(initial_purchases) init_purch,
       SUM(n_3_sec_video_views) v3s, SUM(video_view_throughs) thruplays
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date >= '2026-09-01' AND campaign_id='120216508762540167' GROUP BY 1 ORDER BY spend DESC;

-- 2) Attribution SSOT per ad (installs, trial starts, modeled paid, LTV) -> data/ssot_ads.csv
SELECT ad_id, SUM(installs) installs, ROUND(SUM(signups),1) signups, ROUND(SUM(trial_starts),1) trial_starts,
       ROUND(SUM(trial_converts),2) trial_converts, ROUND(SUM(initial_purchases),2) initial_purchases,
       ROUND(SUM(trial_converts_and_initial_purchases),2) paid, ROUND(SUM(ltv),1) ltv, ROUND(SUM(forecasted_ltv),1) forecasted_ltv,
       SUM(trial_or_purchase_sa) trial_or_purchase_sa, MIN(attribution_date) first_d, MAX(attribution_date) last_d
FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
WHERE campaign_id='120216508762540167' AND attribution_date >= '2026-09-01' GROUP BY 1 ORDER BY ltv DESC;

-- 3) Weekly trend (both tables, same filters, DATE_TRUNC(.., WEEK(MONDAY))) for the six largest ads + 'No Ad ID'.

-- Ad status (effective_status, updated_time) comes from the Meta Marketing API (Speak ZH ad account 1148917790153640), pulled 2026-10-08.
