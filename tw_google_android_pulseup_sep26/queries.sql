-- BigQuery project: speak-v2-2a1f1. Speak TW Google Android pulse-up geo test, September 2026.
-- Campaigns: 23639420764 = tw_google_app_android_tw-en_pros_install_ongoing_no-disc_tROAS (control, BAU)
--            24190362603 = tw_google_app_android_tw-en_pros_install_ongoing_no-disc_pulseup (test cell)
-- Test regions (Paramark design, Notion "[Paid] Google Android Pulse Up - 2609"): Hsinchu County, New Taipei City, Pingtung, Taoyuan.
-- Region = user_details.country_subdivision (IP geography at sign-up). Google Ads geo spend is not in the warehouse.

-- 1) Campaign x day: spend (marketing_spend_daily) joined to attribution SSOT (attribution-date cohort) -> data/campaign_daily.csv
WITH sp AS (
  SELECT DATE(date_start) d, campaign_id, ROUND(SUM(spend),2) spend, SUM(impressions) impressions, SUM(clicks) clicks
  FROM `speak-v2-2a1f1.analytics.marketing_spend_daily`
  WHERE campaign_id IN ('23639420764','24190362603') AND DATE(date_start) BETWEEN '2026-08-01' AND '2026-10-11' GROUP BY 1,2),
att AS (
  SELECT attribution_date d, campaign_id, SUM(installs) installs, ROUND(SUM(signups),1) signups, ROUND(SUM(trial_starts),1) trial_starts,
         ROUND(SUM(trial_converts_and_initial_purchases),2) paid, ROUND(SUM(ltv),1) ltv, ROUND(SUM(forecasted_ltv),1) forecasted_ltv
  FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
  WHERE country='Taiwan' AND platform='android' AND campaign_id IN ('23639420764','24190362603')
    AND attribution_date BETWEEN '2026-08-01' AND '2026-10-11' GROUP BY 1,2)
SELECT COALESCE(sp.d,att.d) date, COALESCE(sp.campaign_id,att.campaign_id) campaign_id,
       CASE COALESCE(sp.campaign_id,att.campaign_id) WHEN '23639420764' THEN 'tROAS (control)' ELSE 'pulseup (test)' END campaign,
       spend, impressions, clicks, installs, signups, trial_starts, paid, ltv, forecasted_ltv
FROM sp FULL OUTER JOIN att ON sp.d=att.d AND sp.campaign_id=att.campaign_id ORDER BY 2,1;

-- 2) Taiwan users (all acquisition sources) by OS x test/control cell x event day -> data/tw_daily_by_cell.csv
--    purch_plus_trials = trial starts + initial purchases without a trial (Paramark's target metric)
WITH u AS (
  SELECT CASE WHEN LOWER(os_name) LIKE '%android%' THEN 'android' WHEN LOWER(os_name) IN ('ios','ipados') THEN 'ios' ELSE 'other' END os,
         CASE WHEN country_subdivision IN ('Hsinchu County','New Taipei City','Pingtung','Taoyuan') THEN 'test'
              WHEN country_subdivision IS NULL THEN 'unknown' ELSE 'control' END cell,
         DATE(sign_up_time) su, DATE(trial_start_time) ts, DATE(conversion_time) cv, DATE(initial_purchase_time) ip
  FROM `speak-v2-2a1f1.analytics.user_details` WHERE country='Taiwan' AND sign_up_time >= '2026-04-01')
SELECT os, cell, d, SUM(signups) signups, SUM(trial_starts) trial_starts, SUM(conversions) conversions, SUM(purch_plus_trials) purch_plus_trials FROM (
  SELECT os, cell, su d, COUNT(*) signups, 0 trial_starts, 0 conversions, 0 purch_plus_trials FROM u WHERE su BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
  UNION ALL SELECT os, cell, ts, 0, COUNT(*), 0, COUNT(*) FROM u WHERE ts BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
  UNION ALL SELECT os, cell, cv, 0, 0, COUNT(*), 0 FROM u WHERE cv BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
  UNION ALL SELECT os, cell, ip, 0, 0, 0, COUNT(*) FROM u WHERE ip BETWEEN '2026-06-01' AND '2026-10-11' AND (ts IS NULL OR ts<>ip) GROUP BY 1,2,3
) WHERE os IN ('android','ios') AND cell IN ('test','control') GROUP BY 1,2,3 ORDER BY 1,2,3;

-- 3) Taiwan Android users by region x ISO week (Monday) -> data/tw_android_weekly_by_region.csv
WITH u AS (
  SELECT user_id, country_subdivision region, sign_up_time, trial_start_time, conversion_time, sign_up_source
  FROM `speak-v2-2a1f1.analytics.user_details` WHERE country='Taiwan' AND LOWER(os_name) LIKE '%android%' AND sign_up_time >= '2026-05-01')
SELECT 'signup' metric, DATE_TRUNC(DATE(sign_up_time),WEEK(MONDAY)) wk, region, COUNT(*) n FROM u WHERE DATE(sign_up_time) BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
UNION ALL SELECT 'trial_start', DATE_TRUNC(DATE(trial_start_time),WEEK(MONDAY)), region, COUNT(*) FROM u WHERE DATE(trial_start_time) BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
UNION ALL SELECT 'conversion', DATE_TRUNC(DATE(conversion_time),WEEK(MONDAY)), region, COUNT(*) FROM u WHERE DATE(conversion_time) BETWEEN '2026-06-01' AND '2026-10-11' GROUP BY 1,2,3
UNION ALL SELECT 'google_signup', DATE_TRUNC(DATE(sign_up_time),WEEK(MONDAY)), region, COUNT(*) FROM u WHERE DATE(sign_up_time) BETWEEN '2026-06-01' AND '2026-10-11' AND LOWER(sign_up_source) LIKE '%google%' GROUP BY 1,2,3
ORDER BY 1,2,3;

-- 4) Attributed sign-ups per campaign by region and month (did the geo split hold?) -> data/campaign_signups_by_region.csv
SELECT sign_up_attribution_campaign_id campaign_id,
       CASE sign_up_attribution_campaign_id WHEN '23639420764' THEN 'tROAS (control)' ELSE 'pulseup (test)' END campaign,
       CASE WHEN DATE(sign_up_time) < '2026-09-01' THEN 'aug' ELSE 'sep' END period, COALESCE(country_subdivision,'(unknown)') region,
       CASE WHEN country_subdivision IN ('Hsinchu County','New Taipei City','Pingtung','Taoyuan') THEN 'test' WHEN country_subdivision IS NULL THEN 'unknown' ELSE 'control' END cell,
       COUNT(*) signups, COUNTIF(trial_started=1) trials, COUNTIF(conversion_time IS NOT NULL) conversions
FROM `speak-v2-2a1f1.analytics.user_details`
WHERE sign_up_attribution_campaign_id IN ('23639420764','24190362603') AND DATE(sign_up_time) BETWEEN '2026-08-01' AND '2026-09-30' AND country='Taiwan'
GROUP BY 1,2,3,4,5 ORDER BY 1,3,signups DESC;
