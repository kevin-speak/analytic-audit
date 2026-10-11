-- BigQuery project: speak-v2-2a1f1. Window: 2026-06-01 .. 2026-10-07 (attribution SSOT lags the Meta funnel by ~2 days; both cut at 10-07).
-- Scope: Meta ad account "Speak ZH" (act 1148917790153640) = Taiwan + Hong Kong campaigns. iOS app campaigns only: web campaigns have no
-- install event, so the install-based SP2 cannot score them. Results were pulled through the BigQuery MCP tool and converted with bqjson2csv.py.

-- 1) Meta ad x placement funnel -> data/ad_placement.csv (run once per country, concatenated)
SELECT ad_id, 'Taiwan' country, campaign_name, COALESCE(placement,'unknown') placement, ROUND(SUM(spend),2) spend, SUM(impressions) impressions,
       SUM(clicks) clicks, SUM(installs) installs, SUM(signups) signups, SUM(trial_starts) trials, ROUND(SUM(adj_trial_starts),2) adj_trials,
       SUM(trial_converts) trial_converts, SUM(initial_purchases) init_purch, ROUND(SUM(adj_initial_purchases),2) adj_init_purch,
       SUM(n_3_sec_video_views) v3s, SUM(video_view_throughs) thruplays
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date BETWEEN '2026-06-01' AND '2026-10-07' AND country='Taiwan' AND os='ios'      -- and country='Hong Kong'
GROUP BY 1,2,3,4 HAVING spend>0 OR impressions>0;

-- 2) Meta ad attributes -> data/ads_meta.csv
SELECT ad_id, ANY_VALUE(ad_name) ad_name, ANY_VALUE(country) country, ANY_VALUE(campaign_name) campaign_name, ANY_VALUE(campaign_id) campaign_id,
       ANY_VALUE(creative_id) creative_id, ANY_VALUE(format) format, ANY_VALUE(content_type) content_type, ANY_VALUE(category) category,
       ANY_VALUE(concept) concept, ANY_VALUE(creator_name) creator_name, ANY_VALUE(ad_preview_link) preview,
       MIN(date) first_date, MAX(date) last_date, COUNT(DISTINCT date) active_days
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date BETWEEN '2026-06-01' AND '2026-10-07' AND country IN ('Taiwan','Hong Kong') AND os='ios' AND spend>0 GROUP BY 1;

-- 3) Meta ad x day -> data/ad_daily.csv (run once per country, concatenated)
SELECT date, ad_id, ROUND(SUM(spend),2) spend, SUM(impressions) impressions, SUM(clicks) clicks, SUM(installs) installs, SUM(signups) signups,
       SUM(trial_starts) trials, ROUND(SUM(adj_trial_starts),2) adj_trials, SUM(n_3_sec_video_views) v3s, SUM(video_view_throughs) thruplays
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date BETWEEN '2026-06-01' AND '2026-10-07' AND country='Taiwan' AND os='ios' GROUP BY 1,2 HAVING spend>0;

-- 4) Official attribution SSOT per ad -> data/ssot_ads.csv
SELECT ad_id, ANY_VALUE(country) country, ANY_VALUE(campaign_name) campaign_name, SUM(installs) installs, ROUND(SUM(signups),1) signups,
 ROUND(SUM(trial_starts),1) trial_starts, ROUND(SUM(trial_starts_sa),1) trial_starts_sa, ROUND(SUM(trial_starts_ca),1) trial_starts_ca,
 ROUND(SUM(trial_converts),2) trial_converts, ROUND(SUM(trial_converts_sa),2) trial_converts_sa, ROUND(SUM(trial_converts_ca),2) trial_converts_ca,
 ROUND(SUM(initial_purchases),2) initial_purchases, ROUND(SUM(trial_converts_and_initial_purchases),2) paid,
 ROUND(SUM(ltv),1) ltv, ROUND(SUM(forecasted_ltv),1) forecasted_ltv, SUM(trial_or_purchase_sa) trial_or_purchase_sa
FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
WHERE country IN ('Taiwan','Hong Kong') AND platform='ios' AND channel='Meta Ads' AND attribution_date BETWEEN '2026-06-01' AND '2026-10-07' GROUP BY 1;

-- 5) AppsFlyer SSOT per ad (plan mix) -> data/af_ads.csv
SELECT af_ad_id, ANY_VALUE(geo) geo, ANY_VALUE(af_ad) af_ad, ANY_VALUE(campaign) campaign,
 SUM(CASE WHEN event_name='Application Installed' THEN unique_users END) af_installs,
 SUM(CASE WHEN event_name='signedUp' THEN unique_users END) af_signups,
 SUM(CASE WHEN event_name='trial_started_event' THEN unique_users END) af_trials,
 SUM(CASE WHEN event_name='trial_started_annual_premium' THEN unique_users END) af_trials_annual_reg,
 SUM(CASE WHEN event_name='trial_started_annual_premium_plus' THEN unique_users END) af_trials_annual_plus,
 SUM(CASE WHEN event_name='trial_started_monthly_premium' THEN unique_users END) af_trials_monthly,
 SUM(CASE WHEN event_name='trial_cancelled_event' THEN unique_users END) af_trial_cancelled,
 SUM(CASE WHEN event_name='rcPurchaseCompleted' THEN unique_users END) af_rc_purchase,
 SUM(CASE WHEN event_name='trial_or_purchase' THEN unique_users END) af_trial_or_purchase,
 ROUND(SUM(CASE WHEN event_name='trial_or_purchase' THEN revenue_usd END),0) af_top_rev
FROM `speak-v2-2a1f1.analytics.marketing_ssot_aggregate`
WHERE geo IN ('TW','HK') AND install_date BETWEEN '2026-06-01' AND '2026-10-07' AND media_source='facebook' AND app_id='id1286609883' AND conversion_type='install'
GROUP BY 1;

-- 6) Market calibration: SSOT totals (data/calibration.json -> markets.*.ssot)
SELECT country, SUM(installs) installs, ROUND(SUM(signups),1) signups, ROUND(SUM(trial_starts),1) trial_starts,
       ROUND(SUM(trial_converts_and_initial_purchases),2) paid, ROUND(SUM(ltv),1) ltv, ROUND(SUM(forecasted_ltv),1) forecasted_ltv, COUNT(DISTINCT ad_id) ads
FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
WHERE country IN ('Taiwan','Hong Kong') AND platform='ios' AND channel='Meta Ads' AND attribution_date BETWEEN '2026-06-01' AND '2026-10-07' GROUP BY 1;

-- 7) Market calibration: AppsFlyer trial starts by plan (data/calibration.json -> markets.*.af_events)
SELECT geo, event_name, SUM(unique_users) users, ROUND(SUM(revenue_usd)) rev
FROM `speak-v2-2a1f1.analytics.marketing_ssot_aggregate`
WHERE geo IN ('TW','HK') AND install_date BETWEEN '2026-06-01' AND '2026-10-07' AND media_source='facebook' AND app_id='id1286609883' AND conversion_type='install'
  AND event_name IN ('Application Installed','signedUp','trial_started_event','trial_started_annual_premium','trial_started_annual_premium_plus','trial_started_monthly_premium','trial_cancelled_event','rcPurchaseCompleted','trial_or_purchase')
GROUP BY 1,2;

-- 8) Market calibration: 36-month LTV per paid user by plan (data/calibration.json -> markets.*.ltv_by_plan)
SELECT ua.country, l.first_duration, l.first_tier, COUNT(*) users, ROUND(AVG(l.ltv),2) avg_ltv, ROUND(STDDEV(l.ltv),2) sd_ltv
FROM `speak-v2-2a1f1.analytics.user_attribution` ua
JOIN `speak-v2-2a1f1.analytics.user_ltv` l ON l.user_id=ua.user_id AND l.first_transaction_date BETWEEN '2026-06-01' AND '2026-10-09'
WHERE ua.country IN ('Taiwan','Hong Kong') AND ua.attribution_channel='Meta Ads' AND ua.attribution_platform='ios'
  AND DATE(ua.attribution_timestamp) BETWEEN '2026-06-01' AND '2026-10-07'
GROUP BY 1,2,3;

-- 9) October-only run (ANALYSIS=oct, the default): one joined extract at ad x placement for 2026-10-01..07 with the ad's October
--    attribution SSOT (by market) and AppsFlyer plan mix (by geo) -> split by analyze.py's loader into data/ad_placement_oct.csv,
--    data/ssot_ads_oct.csv, data/af_ads_oct.csv. Daily data comes from data/ad_daily.csv filtered to the window.
WITH f AS (
  SELECT ad_id, country, ANY_VALUE(ad_name) ad_name, campaign_name, COALESCE(placement,'unknown') placement,
         ROUND(SUM(spend),2) spend, SUM(impressions) impressions, SUM(clicks) clicks, SUM(installs) installs, SUM(signups) signups,
         SUM(trial_starts) trials, ROUND(SUM(adj_trial_starts),2) adj_trials, SUM(trial_converts) trial_converts, SUM(initial_purchases) init_purch,
         ROUND(SUM(adj_initial_purchases),2) adj_init_purch, SUM(n_3_sec_video_views) v3s, SUM(video_view_throughs) thruplays
  FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
  WHERE date BETWEEN '2026-10-01' AND '2026-10-07' AND country IN ('Taiwan','Hong Kong') AND os='ios'
  GROUP BY ad_id, country, campaign_name, placement HAVING spend>0 OR impressions>0),
s AS (
  SELECT ad_id, country, SUM(installs) ssot_installs, ROUND(SUM(signups),1) ssot_signups, ROUND(SUM(trial_starts),1) ssot_trial_starts,
         ROUND(SUM(trial_converts_and_initial_purchases),2) ssot_paid, ROUND(SUM(ltv),1) ssot_ltv, ROUND(SUM(forecasted_ltv),1) ssot_forecasted_ltv
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
  WHERE country IN ('Taiwan','Hong Kong') AND platform='ios' AND channel='Meta Ads' AND attribution_date BETWEEN '2026-10-01' AND '2026-10-07' GROUP BY 1,2),
a AS (
  SELECT af_ad_id ad_id, CASE geo WHEN 'TW' THEN 'Taiwan' WHEN 'HK' THEN 'Hong Kong' END country,
   SUM(CASE WHEN event_name='Application Installed' THEN unique_users END) af_installs, SUM(CASE WHEN event_name='signedUp' THEN unique_users END) af_signups,
   SUM(CASE WHEN event_name='trial_started_event' THEN unique_users END) af_trials, SUM(CASE WHEN event_name='trial_started_annual_premium' THEN unique_users END) af_trials_annual_reg,
   SUM(CASE WHEN event_name='trial_started_annual_premium_plus' THEN unique_users END) af_trials_annual_plus, SUM(CASE WHEN event_name='trial_started_monthly_premium' THEN unique_users END) af_trials_monthly
  FROM `speak-v2-2a1f1.analytics.marketing_ssot_aggregate`
  WHERE geo IN ('TW','HK') AND install_date BETWEEN '2026-10-01' AND '2026-10-07' AND media_source='facebook' AND app_id='id1286609883' AND conversion_type='install' GROUP BY 1,2)
SELECT f.*, s.ssot_installs, s.ssot_signups, s.ssot_trial_starts, s.ssot_paid, s.ssot_ltv, s.ssot_forecasted_ltv,
       a.af_installs, a.af_signups, a.af_trials, a.af_trials_annual_reg, a.af_trials_annual_plus, a.af_trials_monthly
FROM f LEFT JOIN s ON s.ad_id=f.ad_id AND s.country=f.country LEFT JOIN a ON a.ad_id=f.ad_id AND a.country=f.country;
-- October market totals (data/calibration.json -> october): SSOT by attribution_date 2026-10-01..07 and AppsFlyer events by install_date >= 2026-10-01, same filters as sections 6-7.
