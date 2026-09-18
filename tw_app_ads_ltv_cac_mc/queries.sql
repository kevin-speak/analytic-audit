-- BigQuery project: speak-v2-2a1f1. Window: 2026-06-01 .. 2026-09-15. Market: Taiwan, iOS app campaigns (Speak ZH ad account).

-- 1) Meta ad x placement funnel  -> data/ad_placement.csv
SELECT ad_id, campaign_name, COALESCE(placement,'unknown') placement, ROUND(SUM(spend),2) spend, SUM(impressions) impressions,
       SUM(clicks) clicks, SUM(installs) installs, SUM(signups) signups, SUM(trial_starts) trials, ROUND(SUM(adj_trial_starts),2) adj_trials,
       SUM(trial_converts) trial_converts, SUM(initial_purchases) init_purch, ROUND(SUM(adj_initial_purchases),2) adj_init_purch,
       SUM(n_3_sec_video_views) v3s, SUM(video_view_throughs) thruplays
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date BETWEEN '2026-06-01' AND '2026-09-15' AND country='Taiwan' AND os='ios'
GROUP BY 1,2,3 HAVING spend>0 OR impressions>0;

-- 2) Meta ad attributes -> data/ads_meta.csv
SELECT ad_id, ANY_VALUE(ad_name) ad_name, ANY_VALUE(campaign_name) campaign_name, ANY_VALUE(creative_id) creative_id, ANY_VALUE(format) format,
       ANY_VALUE(content_type) content_type, ANY_VALUE(category) category, ANY_VALUE(concept) concept, ANY_VALUE(creator_name) creator_name,
       ANY_VALUE(ad_preview_link) preview, MIN(date) first_date, MAX(date) last_date, COUNT(DISTINCT date) active_days
FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
WHERE date BETWEEN '2026-06-01' AND '2026-09-15' AND country='Taiwan' AND os='ios' AND spend>0 GROUP BY 1;

-- 3) AppsFlyer SSOT per-ad events (plan mix) -> data/af_ads.csv
SELECT af_ad_id, ANY_VALUE(af_ad) af_ad, ANY_VALUE(campaign) campaign,
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
WHERE geo='TW' AND install_date BETWEEN '2026-06-01' AND '2026-09-15' AND media_source='facebook' AND app_id='id1286609883' AND conversion_type='install'
GROUP BY 1;

-- 4) Official attribution SSOT per ad (trial starts, modeled paid, LTV) -> data/ssot_ads.csv
SELECT ad_id, ANY_VALUE(campaign_name) campaign_name, SUM(installs) installs, ROUND(SUM(signups),1) signups,
 ROUND(SUM(trial_starts),1) trial_starts, ROUND(SUM(trial_starts_sa),1) trial_starts_sa, ROUND(SUM(trial_starts_ca),1) trial_starts_ca,
 ROUND(SUM(trial_converts),2) trial_converts, ROUND(SUM(trial_converts_sa),2) trial_converts_sa, ROUND(SUM(trial_converts_ca),2) trial_converts_ca,
 ROUND(SUM(initial_purchases),2) initial_purchases, ROUND(SUM(trial_converts_and_initial_purchases),2) paid,
 ROUND(SUM(ltv),1) ltv, ROUND(SUM(forecasted_ltv),1) forecasted_ltv, SUM(trial_or_purchase_sa) trial_or_purchase_sa
FROM `speak-v2-2a1f1.analytics.marketing_attribution_aggregate_attribution_date_cohort`
WHERE country='Taiwan' AND platform='ios' AND channel='Meta Ads' AND attribution_date BETWEEN '2026-06-01' AND '2026-09-15'
GROUP BY 1;

-- 5) LTV per paid user by plan, Meta-iOS-attributed Taiwan users paying in window (LTV_MU constants)
SELECT l.first_duration, l.first_tier, COUNT(*) users, ROUND(AVG(l.ltv),2) avg_ltv, APPROX_QUANTILES(ROUND(l.ltv,2), 20) q
FROM `speak-v2-2a1f1.analytics.user_attribution` ua
JOIN `speak-v2-2a1f1.analytics.user_ltv` l ON l.user_id=ua.user_id AND l.first_transaction_date BETWEEN '2026-06-01' AND '2026-09-17'
WHERE ua.country='Taiwan' AND ua.attribution_channel='Meta Ads' AND ua.attribution_platform='ios'
  AND DATE(ua.attribution_timestamp) BETWEEN '2026-06-01' AND '2026-09-15'
GROUP BY 1,2;
