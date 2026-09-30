"""
Extension: SP / CTI measured on the BAU ads themselves (winning / winning3 / scaling2), not only in testing.

For every creative first launched in a TW iOS BAU campaign Jun 1 - Sep 22 (incl. the ones with no testing ad):
  wk1 SP  = Option B on the creative's first 7 BAU days, benchmark = all other BAU ads on that placement (Jun 1 - Sep 29)
  wk1 CTI = wk1 installs / wk1 link clicks (BigQuery all-clicks x the ads' Meta link-click share)
Outcome is measured AFTER week 1 so predictor and outcome don't overlap:
  sustained = week-2-onward BAU spend >= $5k; also Spearman vs week-2+ spend and week-2+ CPR.
Only creatives launched by 2026-08-25 (>= 5 weeks of BAU history) enter the outcome tests.
Run after analyze.py (reuses output/creatives_scored.csv for testing-phase SP / CTI and JP 'scaled' labels).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu, spearmanr

ROOT = Path(__file__).parent
SUSTAINED_SPEND, OUTCOME_CUTOFF = 5000.0, '2026-08-25'

w = pd.read_csv(ROOT / 'data/bau_wk1.tsv', sep='\t', dtype={'wk1_ad_ids': str})
lc = pd.read_csv(ROOT / 'data/meta_bau_link_clicks.tsv', sep='\t', dtype={'ad_id': str}).set_index('ad_id')
sc = pd.read_csv(ROOT / 'output/creatives_scored.csv')


def link_share(ids):
    x = lc.loc[ids.split(',')]
    return x.link_clicks.sum() / x.clicks_all.sum()


w['link_share'] = w.wk1_ad_ids.map(link_share)
w['wk1_link_clicks'] = w.wk1_clicks_all * w.link_share
w['bau_wk1_cti'] = np.where(w.wk1_link_clicks > 0, w.wk1_installs / w.wk1_link_clicks, np.nan)
w['bau_wk1_ctr'] = w.wk1_clicks_all / w.wk1_impr
w['bau_wk1_sp'] = w.wk1_sp
w['bau_wk1_cpr'] = np.where(w.wk1_trials > 0, w.wk1_spend / w.wk1_trials, np.nan)
w['post_cpr'] = np.where(w.post_trials > 0, w.post_spend / w.post_trials, np.inf)
w['has_test'] = w.key.isin(sc[sc.excluded.isna()].key)
w = w.merge(sc[['key', 'creative', 'sp', 'cti', 'status', 'bau_spend']].rename(columns={'sp': 'test_sp', 'cti': 'test_cti', 'status': 'jp_status'}),
            on='key', how='left')
w['creative'] = w.creative.fillna(w.key.str.replace('|', ' · ', regex=False))
w['jp_status'] = w.jp_status.fillna('n/a')
w['sustained'] = w.post_spend >= SUSTAINED_SPEND
w.to_csv(ROOT / 'output/bau_wk1_scored.csv', index=False)

o = w[w.bau_first_date <= OUTCOME_CUTOFF].copy()
PRED = {'test_sp': 'Testing SP', 'test_cti': 'Testing CTI', 'bau_wk1_sp': 'BAU wk1 SP', 'bau_wk1_cti': 'BAU wk1 CTI',
        'bau_wk1_cpr': 'BAU wk1 CPR (lower=better)', 'bau_wk1_ctr': 'BAU wk1 CTR'}


def auc(col):
    d = o[[col, 'sustained']].dropna()
    pos, neg = d[d.sustained][col], d[~d.sustained][col]
    if not len(pos) or not len(neg):
        return np.nan, np.nan, len(d)
    u, p = mannwhitneyu(pos, neg, alternative='two-sided')
    a = u / (len(pos) * len(neg))
    return (1 - a if col == 'bau_wk1_cpr' else a), p, len(d)


def rho(col, y):
    d = o[[col, y]].replace([np.inf], np.nan if y != 'post_cpr' else 1e9).dropna()
    r, p = spearmanr(d[col], d[y])
    return r, p


rows = []
for c, name in PRED.items():
    a, ap, n = auc(c)
    r1, p1 = rho(c, 'post_spend'); r2, p2 = rho(c, 'post_cpr')
    rows.append(dict(predictor=name, n=n, auc_sustained=a, p_auc=ap, rho_post_spend=r1, p_spend=p1, rho_post_cpr=r2, p_cpr=p2))
pred = pd.DataFrame(rows)


def gate(mask, label):
    g = o[mask]; b = o[~mask]
    t = [[int(g.sustained.sum()), int((~g.sustained).sum())], [int(b.sustained.sum()), int((~b.sustained).sum())]]
    return dict(gate=label, n_pass=len(g), sustained_pass=t[0][0], rate_pass=g.sustained.mean() if len(g) else np.nan,
                n_fail=len(b), sustained_fail=t[1][0], rate_fail=b.sustained.mean() if len(b) else np.nan, p=fisher_exact(t)[1],
                sustained_missed=', '.join(b[b.sustained].creative))


gates = pd.DataFrame([
    gate(o.test_cti >= 0.01, 'Testing CTI >= 1%'), gate(o.test_cti >= 0.025, 'Testing CTI >= 2.5%'),
    gate(o.test_sp >= 2.0, 'Testing SP >= 2.0'), gate(o.test_sp >= 3.0, 'Testing SP >= 3.0'),
    gate(o.bau_wk1_cti >= 0.01, 'BAU wk1 CTI >= 1%'), gate(o.bau_wk1_cti >= 0.02, 'BAU wk1 CTI >= 2%'),
    gate(o.bau_wk1_cti >= 0.025, 'BAU wk1 CTI >= 2.5%'),
    gate(o.bau_wk1_sp >= 2.0, 'BAU wk1 SP >= 2.0'), gate(o.bau_wk1_sp >= 2.5, 'BAU wk1 SP >= 2.5'),
    gate(o.bau_wk1_cpr <= 90, 'BAU wk1 CPR <= $90'),
])

# testing-vs-BAU consistency: does a creative's CTI hold up once it hits BAU?
both = w[w.test_cti.notna() & w.bau_wk1_cti.notna()]
consistency = dict(
    rho_cti=spearmanr(both.test_cti, both.bau_wk1_cti)[0], rho_sp=spearmanr(both.test_sp, both.bau_wk1_sp)[0],
    median_test_cti=both.test_cti.median(), median_bau_wk1_cti=both.bau_wk1_cti.median(),
    median_test_sp=both.test_sp.median(), median_bau_wk1_sp=both.bau_wk1_sp.median(), n=len(both))

(ROOT / 'output/bau_results.json').write_text(json.dumps(dict(
    n_all=len(w), n_no_test=int((~w.has_test).sum()), n_outcome=len(o), n_sustained=int(o.sustained.sum()),
    predictors=pred.to_dict('records'), gates=gates.to_dict('records'), consistency=consistency), indent=1, default=float))

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 60)
print(f'all BAU creatives {len(w)} (no testing ad: {(~w.has_test).sum()}), outcome set {len(o)}, sustained {o.sustained.sum()}')
cols = ['creative', 'bau_first_date', 'campaigns', 'test_sp', 'test_cti', 'bau_wk1_sp', 'bau_wk1_ctr', 'bau_wk1_cti', 'wk1_spend', 'bau_wk1_cpr', 'post_spend', 'post_cpr', 'jp_status', 'sustained']
print(w.sort_values('post_spend', ascending=False)[cols].round(3).to_string(index=False))
print(pred.round(3).to_string(index=False))
print(gates.drop(columns='sustained_missed').round(3).to_string(index=False))
print(gates[['gate', 'sustained_missed']].to_string(index=False))
print(json.dumps(consistency, indent=1, default=float))
