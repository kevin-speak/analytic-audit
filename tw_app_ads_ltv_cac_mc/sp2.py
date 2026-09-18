"""
Proposed SP2 = Efficiency Index (EI) x Scale Index (SI), computed from install-stage data only.
  EI = (K / CPI) / TARGET        K = SSOT LTV per Meta install for the market (refreshed monthly), TARGET = 0.8x LTV/CAC
  SI = spend per active day / median spend per active day of ads in the same campaign, clipped to [0.25, 4]
Validation against the simulated LTV/CAC (output/results.json) and speed by spend milestone (data/ad_daily.csv).
Output: output/sp2.json (consumed by the report).
"""
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
TARGET, SP2_BAR, SI_CLIP = 0.8, 2.0, (0.25, 4.0)
dl = pd.read_csv('data/ad_daily.csv', dtype={'ad_id': str}); dl['date'] = pd.to_datetime(dl.date); dl = dl.sort_values(['ad_id', 'date'])
ads = pd.read_csv('output/ads_scored.csv', dtype={'ad_id': str})
sim = {a['ad_id']: a for a in json.load(open('output/results.json'))['ads']}
ads['ltv_cac'] = ads.ad_id.map(lambda i: sim[i]['ltv_cac']); ads['ltv_cac_lo'] = ads.ad_id.map(lambda i: sim[i]['ltv_cac_ci'][0]); ads['ltv_cac_hi'] = ads.ad_id.map(lambda i: sim[i]['ltv_cac_ci'][1])
ads['days'] = ads.ad_id.map(dl.groupby('ad_id').date.nunique())
ads['signups'] = ads.ad_id.map(dl.groupby('ad_id').signups.sum())
K = ads.ssot_ltv.sum() / ads.installs.sum()                     # LTV per install
Ks = ads.ssot_ltv.sum() / ads.signups.sum()                     # LTV per signup (alternative)
CPI_TARGET = K / TARGET
ads['cpi'] = ads.spend / ads.installs.replace(0, np.nan); ads['cps'] = ads.spend / ads.signups.replace(0, np.nan)
ads['EI'] = (K / ads.cpi) / TARGET
ads['spend_per_day'] = ads.spend / ads.days
ads['SI'] = (ads.spend_per_day / ads.groupby('campaign_name').spend_per_day.transform('median')).clip(*SI_CLIP)
ads['SP2'] = ads.EI * ads.SI
ads['on_target'] = ads.ltv_cac >= TARGET
ads['p1'] = (ads.sp >= 2) & (ads.installs >= 10)
ads['sp2_winner'] = (ads.EI >= 1) & (ads.SP2 >= SP2_BAR)
ads['sp2_phase'] = np.select([ads.EI.isna(), ads.sp2_winner, ads.EI >= 1, ads.EI >= 0.8], ['No installs yet', 'Scalable winner', 'Efficient, unproven scale', 'Watch'], 'Pause')
A = ads[ads.spend >= 100].copy()
def gate(mask, label, df=A):
    g = df[mask]; tot_ok = (df.spend * df.on_target).sum()
    return {'gate': label, 'n': int(len(g)), 'spend': float(g.spend.sum()), 'sw_ltv_cac': float((g.ltv_cac * g.spend).sum() / g.spend.sum()) if len(g) else None,
            'hit_rate': float(g.on_target.mean()) if len(g) else None, 'spend_recall': float((g.spend * g.on_target).sum() / tot_ok) if tot_ok else None}
out = {'params': {'target': TARGET, 'sp2_bar': SP2_BAR, 'si_clip': SI_CLIP, 'K_per_install': float(K), 'K_per_signup': float(Ks), 'cpi_target': float(CPI_TARGET),
                  'cps_target': float(Ks / TARGET), 'pool_cpi': float(ads.spend.sum() / ads.installs.sum()), 'pool_cps': float(ads.spend.sum() / ads.signups.sum())},
       'gates': {}, 'milestones': [], 'ads': []}
for b in ['Overall', 'Testing', 'Winning', 'Scaling']:
    df = A if b == 'Overall' else A[A.bucket == b]
    e = df.dropna(subset=['EI'])
    out['gates'][b] = {'rows': [gate(df.p1, 'P1 gate (SP ≥ 2 & ≥ 10 installs)', df), gate(df.EI >= 1, f'EI ≥ 1 (CPI ≤ ${CPI_TARGET:.0f})', df), gate(df.sp2_winner, 'SP2 winner (EI ≥ 1 & SP2 ≥ 2)', df),
                               gate(~df.p1, 'Not P1', df), gate(~df.sp2_winner, 'Not SP2 winner', df)],
                       'rho_ei': float(spearmanr(e.EI, e.ltv_cac)[0]) if len(e) > 5 else None, 'rho_sp': float(spearmanr(df.sp, df.ltv_cac)[0]) if len(df) > 5 else None,
                       'rho_sp2': float(spearmanr(e.SP2, e.ltv_cac)[0]) if len(e) > 5 else None,
                       'auc_ei': float(roc_auc_score(e.on_target, e.EI)) if e.on_target.nunique() > 1 else None, 'auc_sp': float(roc_auc_score(df.on_target, df.sp)) if df.on_target.nunique() > 1 else None,
                       'n_on_target': int(df.on_target.sum()), 'n': int(len(df))}
# speed by cumulative-spend milestone
pool_ctr = ads.clicks.sum() / ads.impressions.sum(); pool_cti = ads.trials.sum() / ads.clicks.sum()
cum = dl.groupby('ad_id')[['spend', 'impressions', 'clicks', 'installs', 'signups', 'trials']].cumsum(); cum['ad_id'] = dl.ad_id.values
fin = ads.set_index('ad_id')
for S in [50, 100, 150, 200, 300, 500, 750, 1000, 2000]:
    f = cum[cum.spend >= S].groupby('ad_id').head(1).set_index('ad_id'); f = f[f.index.isin(fin.index[fin.spend >= 2 * S])].copy(); f['ltv'] = fin.ltv_cac
    f['ei'] = (K / (f.spend / f.installs.replace(0, np.nan))) / TARGET; f['tpi'] = f.trials / f.impressions * 1000; f['cpft'] = -(f.spend / f.trials.replace(0, np.nan))
    f['spx'] = (f.clicks / f.impressions) / pool_ctr + (f.trials / f.clicks.replace(0, np.nan)) / pool_cti; f['ipm'] = f.installs / f.impressions * 1000
    def r(x): m = f[[x, 'ltv']].replace([np.inf, -np.inf], np.nan).dropna(); return float(spearmanr(m[x], m.ltv)[0]) if len(m) > 5 else None
    def auc(x): m = f[[x, 'ltv']].replace([np.inf, -np.inf], np.nan).dropna(); return float(roc_auc_score(m.ltv >= TARGET, m[x])) if (m.ltv >= TARGET).nunique() > 1 else None
    out['milestones'].append({'spend': S, 'n': int(len(f)), 'rho_ei': r('ei'), 'rho_ipm': r('ipm'), 'rho_tpi': r('tpi'), 'rho_cpft': r('cpft'), 'rho_sp': r('spx'),
                              'auc_ei': auc('ei'), 'auc_tpi': auc('tpi'), 'auc_sp': auc('spx'), 'share_installs': float((f.installs > 0).mean()), 'share_trials': float((f.trials > 0).mean())})
# scale evidence
dl['n'] = dl.groupby('ad_id').cumcount() + 1
coh = fin.index[(fin.days >= 14) & (fin.spend >= 100)]
v7 = dl[dl.n <= 7].groupby('ad_id').spend.sum() / 7; later = dl[dl.n > 7].groupby('ad_id').spend.sum()
j = pd.concat([v7.rename('v'), later.rename('l')], axis=1).dropna(); j = j[j.index.isin(coh)]
dd = dl[dl.installs > 0].copy(); dd['cpi'] = dd.spend / dd.installs
w = [spearmanr(g.spend, g.cpi)[0] for _, g in dd.groupby('ad_id') if len(g) >= 10]
out['scale'] = {'rho_velocity7_later_spend': float(spearmanr(j.v, j.l)[0]), 'n': int(len(j)), 'within_ad_rho_spend_cpi_median': float(np.nanmedian(w)), 'share_positive': float(np.mean(np.array(w) > 0)), 'n_ads': len(w)}
for _, r_ in ads.iterrows():
    out['ads'].append({'ad_id': r_.ad_id, 'name': sim[r_.ad_id]['name'], 'bucket': r_.bucket, 'spend': round(float(r_.spend), 2), 'installs': int(r_.installs), 'cpi': None if np.isnan(r_.cpi) else round(float(r_.cpi), 2),
                       'EI': None if np.isnan(r_.EI) else round(float(r_.EI), 3), 'SI': round(float(r_.SI), 3), 'SP2': None if np.isnan(r_.SP2) else round(float(r_.SP2), 3), 'sp2_phase': r_.sp2_phase,
                       'sp': round(float(r_.sp), 3), 'phase': r_.phase, 'ltv_cac': round(float(r_.ltv_cac), 3), 'ltv_cac_ci': [round(float(r_.ltv_cac_lo), 3), round(float(r_.ltv_cac_hi), 3)], 'analyzed': bool(r_.spend >= 100)})
json.dump(out, open('output/sp2.json', 'w'), indent=1); ads.to_csv('output/ads_sp2.csv', index=False)
print(json.dumps(out['params'], indent=1)); print(json.dumps(out['scale'], indent=1))
for b, g in out['gates'].items():
    print(b, 'rho EI/SP/SP2', [None if x is None else round(x, 2) for x in (g['rho_ei'], g['rho_sp'], g['rho_sp2'])], 'AUC EI/SP', [None if x is None else round(x, 2) for x in (g['auc_ei'], g['auc_sp'])], 'on target', g['n_on_target'], '/', g['n'])
    for r_ in g['rows']: print('   ', r_['gate'], r_['n'], round(r_['spend']), None if r_['sw_ltv_cac'] is None else round(r_['sw_ltv_cac'], 2), None if r_['hit_rate'] is None else round(r_['hit_rate'], 2), None if r_['spend_recall'] is None else round(r_['spend_recall'], 2))
for m in out['milestones']: print(m['spend'], m['n'], {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items() if k not in ('spend', 'n')})
print(ads.sp2_phase.value_counts())
