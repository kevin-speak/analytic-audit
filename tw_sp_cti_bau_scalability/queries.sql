-- BigQuery project: speak-v2-2a1f1. Market: Taiwan, iOS app campaigns (Speak ZH ad account 1148917790153640).
-- Testing campaign: tw_meta_standard_ios_tw-en_pros_purchase_ongoing_no-disc_testing
-- BAU campaigns:    tw_meta_standard_ios_tw-en_pros_trial_ongoing_winning / _winning3 / _scaling2
-- Output of this query -> data/creatives.tsv (one row per BAU creative).
--
-- Creative key = c6 (creator) | c8 (concept) from the ad name, lower-cased, with campaign suffixes
-- (_scaling, -winning, _c9!app, _retest, " - copy", -1080x1080 sizes) stripped. A testing ad matches a BAU
-- creative if the key matches OR it uses the same video id, and it started testing on/before the BAU launch.
-- SP = Option B (sp-dashboard skill): per ad x placement, spend-weighted (CTR/bench_CTR + trials-per-click/bench),
-- benchmarks = all other testing-campaign ads on that placement (Apr 1 - Sep 29 2026). Creative SP = spend-weighted
-- mean over its matched testing ads.
CREATE TEMP FUNCTION k(n STRING) AS (
  CONCAT(LOWER(TRIM(IFNULL(REGEXP_EXTRACT(n, r'c6[!:_](.*?)_c7'),''))), '|',
  REGEXP_REPLACE(REGEXP_REPLACE(REGEXP_REPLACE(LOWER(TRIM(IFNULL(REGEXP_EXTRACT(n, r'c8[!:_](.*?)(?:_c9.*)?$'), n))),
     r'( - copy| \(1\))$',''), r'[\s_-]*(scaling|winning|winner|cpr|testing|app-scaling|app|retest)([\s_-].*)?$',''), r'-\d+x\d+-?$','')));
WITH f AS (
  SELECT *, k(ad_name) key, REGEXP_EXTRACT(ad_creative_video_permalink_url, r'/(\d{6,})/?$') vid, COALESCE(placement,'unknown') p,
    CASE WHEN campaign_name LIKE 'tw_meta_standard_ios_tw-en_pros_purchase_ongoing_no-disc_testing' THEN 'T'
         WHEN campaign_name IN ('tw_meta_standard_ios_tw-en_pros_trial_ongoing_winning','tw_meta_standard_ios_tw-en_pros_trial_ongoing_winning3','tw_meta_standard_ios_tw-en_pros_trial_ongoing_scaling2') THEN 'B' END grp
  FROM `speak-v2-2a1f1.analytics.meta_ads_creative_report_funnel`
  WHERE date BETWEEN '2026-01-01' AND '2026-09-29' AND country='Taiwan' AND os='ios'),
ap AS (SELECT ad_id, p, SUM(spend) s, SUM(impressions) i, SUM(clicks) c, SUM(trial_starts) t FROM f WHERE grp='T' AND date>='2026-04-01' GROUP BY 1,2),
pt AS (SELECT p, SUM(i) ti, SUM(c) tc, SUM(t) tt FROM ap GROUP BY 1),
adt AS (SELECT ad_id, SUM(s) ts FROM ap GROUP BY 1),
sp AS (SELECT ap.ad_id, SUM(SAFE_DIVIDE(ap.s, adt.ts) * (
     IFNULL(SAFE_DIVIDE(SAFE_DIVIDE(ap.c, ap.i), SAFE_DIVIDE(pt.tc-ap.c, pt.ti-ap.i)),0) +
     IFNULL(SAFE_DIVIDE(SAFE_DIVIDE(ap.t, ap.c), SAFE_DIVIDE(pt.tt-ap.t, pt.tc-ap.c)),0))) sp
  FROM ap JOIN pt USING(p) JOIN adt USING(ad_id) WHERE adt.ts>0 GROUP BY 1),
t AS (SELECT ad_id, ANY_VALUE(key) key, ANY_VALUE(vid) vid, MIN(IF(spend>0,date,NULL)) t0, SUM(spend) s, SUM(impressions) i, SUM(clicks) c, SUM(installs) n, SUM(trial_starts) tr
      FROM f WHERE grp='T' GROUP BY 1 HAVING s>0),
bk AS (SELECT key, MIN(IF(spend>0,date,NULL)) b0, ARRAY_AGG(DISTINCT IFNULL(vid,'-')) vids, SUM(spend) bs, SUM(trial_starts) bt FROM f WHERE grp='B' GROUP BY 1 HAVING bs>0),
m AS (SELECT DISTINCT bk.key, t.ad_id FROM bk JOIN t ON (t.key=bk.key OR t.vid IN UNNEST(bk.vids)) AND t.t0 <= bk.b0),
tm AS (SELECT m.key, STRING_AGG(DISTINCT CAST(t.ad_id AS STRING)) tads, SUM(t.s) ts, SUM(t.i) ti, SUM(t.c) tc, SUM(t.n) tn, SUM(t.tr) ttr, SAFE_DIVIDE(SUM(sp.sp*t.s), SUM(t.s)) tsp
      FROM m JOIN t USING(ad_id) LEFT JOIN sp USING(ad_id) GROUP BY 1),
wk AS (SELECT f.key, DIV(DATE_DIFF(f.date, bk.b0, DAY), 7) w, SUM(spend) s, SUM(trial_starts) tr FROM f JOIN bk USING(key) WHERE grp='B' GROUP BY 1,2),
ws AS (SELECT key, STRING_AGG(FORMAT('%d:%.0f:%d', w, s, tr), ';' ORDER BY w) series FROM wk WHERE s>0 GROUP BY 1)
SELECT bk.key, bk.b0 bau_first_date, ROUND(bk.bs) bau_spend, bk.bt bau_trials, tads test_ad_ids, ROUND(ts,1) test_spend, ti test_impr, tc test_clicks_all,
       tn test_installs, ttr test_trials, ROUND(tsp,3) test_sp, series bau_weekly
FROM bk LEFT JOIN tm USING(key) LEFT JOIN ws USING(key) WHERE bk.b0 BETWEEN '2026-06-01' AND '2026-09-29'
ORDER BY bk.b0;

-- Link clicks (not in BigQuery) -> data/meta_test_link_clicks.tsv, from Meta Ads MCP:
--   ads_get_ad_entities(ad_account_id=1148917790153640, level=ad, object_ids=<test_ad_ids>,
--     fields=[link_click, mobile_app_install, results], time_range=2026-04-01..2026-09-29)
-- BigQuery spend / clicks(all) / installs reconcile exactly with Meta for these ads; trials differ by <=2 on 3 ads.
