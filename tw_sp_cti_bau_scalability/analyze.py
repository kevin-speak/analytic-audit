"""
TW SP score & CTI vs Meta iOS BAU scalability (replicates the JP analysis for Taiwan).

Question: among creatives that made it from the TW iOS testing campaign into the BAU campaigns
(winning / winning3 / scaling2), does the testing-phase SP score or CTI (click-to-install) better
predict which ones actually scale?

Inputs (see queries.sql):
  data/creatives.tsv            BigQuery: per BAU creative, first BAU date, weekly BAU spend/trials,
                                matched testing ads and their testing-phase funnel + SP (Option B)
  data/meta_test_link_clicks.tsv Meta Ads MCP: link clicks / installs / trials of those testing ads
Outputs: output/creatives_scored.csv, output/results.json, output/quadrant.png
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, spearmanr

ROOT = Path(__file__).parent
SP_BENCH, CTI_BENCH = 2.0, 0.05
WK1_SPEND_SCALED, CPR_SCALED, MIN_WEEK_SPEND, BORDERLINE_SPEND = 1500.0, 70.0, 1000.0, 5000.0
CTI_TW = 0.01  # TW-calibrated CTI cut (testing-campaign average installs/link click = 0.80%)
WINDOW = ('2026-06-01', '2026-09-22')  # first BAU launch; need a complete first week by 2026-09-29

cr = pd.read_csv(ROOT / 'data/creatives.tsv', sep='\t', dtype={'test_ad_ids': str})
lc = pd.read_csv(ROOT / 'data/meta_test_link_clicks.tsv', sep='\t', dtype={'ad_id': str}).set_index('ad_id')


def weekly(s):
    rows = [tuple(map(float, x.split(':'))) for x in s.split(';')]
    return pd.DataFrame(rows, columns=['w', 'spend', 'trials']).astype({'w': int})


RENAME = {'harryspeaks|og-video': 'harryspeaks · 26Q3 og-video', 'harryspeaks_|og-video': 'harryspeaks · og-video'}


def label(key):
    creator, concept = key.split('|')
    return RENAME.get(key) or (concept if creator == 'na' else f'{creator.rstrip("_")} · {concept}')


out = []
for r in cr.itertuples():
    wk = weekly(r.bau_weekly)
    w1 = wk[wk.w == 0]
    wk1_spend, wk1_trials = float(w1.spend.sum()), float(w1.trials.sum())
    big = wk[wk.spend >= MIN_WEEK_SPEND]
    best_cpr = (big.spend / big.trials.replace(0, np.nan)).min() if len(big) else np.nan
    ids = r.test_ad_ids.split(',') if isinstance(r.test_ad_ids, str) else []
    link = float(lc.loc[ids, 'link_clicks'].sum()) if ids else np.nan
    excl = None
    if not ids:
        excl = 'no testing-campaign ad'
    elif not (WINDOW[0] <= r.bau_first_date <= WINDOW[1]):
        excl = 'outside launch window'
    scaled = wk1_spend > WK1_SPEND_SCALED and best_cpr <= CPR_SCALED
    borderline = (not scaled) and r.bau_spend >= BORDERLINE_SPEND
    out.append(dict(
        key=r.key, creative=label(r.key), bau_first_date=r.bau_first_date, excluded=excl,
        test_ad_ids=r.test_ad_ids, test_spend=r.test_spend, test_impr=r.test_impr,
        test_clicks_all=r.test_clicks_all, test_link_clicks=link, test_installs=r.test_installs,
        test_trials=r.test_trials, sp=r.test_sp if r.test_sp >= 0 else np.nan,
        ctr=r.test_clicks_all / r.test_impr if r.test_impr else np.nan,
        cti=r.test_installs / link if link else np.nan,
        cti_all_clicks=r.test_installs / r.test_clicks_all if r.test_clicks_all else np.nan,
        cvr=r.test_trials / r.test_installs if r.test_installs else np.nan,
        test_cpft=r.test_spend / r.test_trials if r.test_trials else np.nan,
        wk1_spend=wk1_spend, wk1_trials=wk1_trials,
        wk1_cpr=wk1_spend / wk1_trials if wk1_trials else np.nan,
        best_week_cpr=best_cpr, bau_spend=float(r.bau_spend), bau_trials=float(r.bau_trials),
        bau_cpr=r.bau_spend / r.bau_trials if r.bau_trials else np.inf,
        weekly=';'.join(f'w{int(x.w)+1}:${x.spend:,.0f}/{int(x.trials)}' for x in wk.itertuples()),
        status='Scaled' if scaled else ('Borderline' if borderline else 'Not scaled'),
    ))
df = pd.DataFrame(out)
df.to_csv(ROOT / 'output/creatives_scored.csv', index=False)
a = df[df.excluded.isna()].copy()
a['hi_sp'] = a.sp >= SP_BENCH
a['hi_cti'] = a.cti >= CTI_BENCH
a['hi_cti_tw'] = a.cti >= CTI_TW
a['hi_cti_25'] = a.cti >= 0.025
a['hi_sp3'] = a.sp >= 3.0
a['is_scaled'] = a.status == 'Scaled'


def grp(mask):
    g = a[mask]
    return dict(n=int(len(g)), scaled=int(g.is_scaled.sum()), borderline=int((g.status == 'Borderline').sum()),
                rate=float(g.is_scaled.mean()) if len(g) else None,
                med_wk1_spend=float(g.wk1_spend.median()) if len(g) else None,
                med_wk1_cpr=float(g.wk1_cpr.median()) if g.wk1_cpr.notna().any() else None,
                creatives=[f"{'✅' if s == 'Scaled' else 'B' if s == 'Borderline' else '❌'} {c}"
                           for c, s in g.sort_values(['status', 'bau_spend'], ascending=[False, False])[['creative', 'status']].values])


def fisher(col):
    t = pd.crosstab(a[col], a.is_scaled).reindex(index=[True, False], columns=[True, False], fill_value=0)
    return dict(table=t.values.tolist(), p=float(fisher_exact(t.values)[1]))


def spear(x, y):
    m = a[x].notna() & a[y].notna()
    rho, p = spearmanr(a.loc[m, x], a.loc[m, y])
    return dict(rho=float(rho), p=float(p), n=int(m.sum()))


res = dict(
    n=int(len(a)), n_scaled=int(a.is_scaled.sum()), n_borderline=int((a.status == 'Borderline').sum()),
    excluded=df[df.excluded.notna()][['creative', 'bau_first_date', 'excluded']].to_dict('records'),
    benchmarks={
        'CTI >= 5%': grp(a.hi_cti), 'CTI < 5%': grp(~a.hi_cti),
        'CTI >= 1% (TW)': grp(a.hi_cti_tw), 'CTI < 1% (TW)': grp(~a.hi_cti_tw),
        'CTI >= 2.5%': grp(a.hi_cti_25), 'CTI < 2.5%': grp(~a.hi_cti_25),
        'SP >= 2.0': grp(a.hi_sp), 'SP < 2.0': grp(~a.hi_sp),
        'SP >= 3.0': grp(a.hi_sp3), 'SP < 3.0': grp(~a.hi_sp3),
    },
    quadrants_tw={
        'High SP x high CTI': grp(a.hi_sp3 & a.hi_cti_tw), 'High SP x low CTI': grp(a.hi_sp3 & ~a.hi_cti_tw),
        'Low SP x high CTI': grp(~a.hi_sp3 & a.hi_cti_tw), 'Low SP x low CTI': grp(~a.hi_sp3 & ~a.hi_cti_tw),
    },
    quadrants={
        'High SP x high CTI': grp(a.hi_sp & a.hi_cti), 'High SP x low CTI': grp(a.hi_sp & ~a.hi_cti),
        'Low SP x high CTI': grp(~a.hi_sp & a.hi_cti), 'Low SP x low CTI': grp(~a.hi_sp & ~a.hi_cti),
    },
    fisher={'CTI>=5%': fisher('hi_cti'), 'CTI>=1%': fisher('hi_cti_tw'), 'CTI>=2.5%': fisher('hi_cti_25'), 'SP>=2.0': fisher('hi_sp'), 'SP>=3.0': fisher('hi_sp3')},
    spearman={
        'CTI vs BAU CPR': spear('cti', 'bau_cpr'), 'SP vs BAU CPR': spear('sp', 'bau_cpr'),
        'CTI vs BAU spend': spear('cti', 'bau_spend'), 'SP vs BAU spend': spear('sp', 'bau_spend'),
        'CTI vs wk1 CPR': spear('cti', 'wk1_cpr'), 'SP vs wk1 CPR': spear('sp', 'wk1_cpr'),
        'CTR vs BAU CPR': spear('ctr', 'bau_cpr'), 'CVR vs BAU CPR': spear('cvr', 'bau_cpr'),
        'test CPFT vs BAU CPR': spear('test_cpft', 'bau_cpr'),
    },
    cti_sweep=[dict(cut=c, **{k: v for k, v in grp(a.cti >= c).items() if k != 'creatives'},
                    below_scaled=int(a[a.cti < c].is_scaled.sum()), below_n=int((a.cti < c).sum()),
                    p=float(fisher_exact(pd.crosstab(a.cti >= c, a.is_scaled).reindex(index=[True, False], columns=[True, False], fill_value=0).values)[1]))
               for c in [0.01, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.06]],
    sp_sweep=[dict(cut=c, **{k: v for k, v in grp(a.sp >= c).items() if k != 'creatives'})
              for c in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]],
    top_sp=a.sort_values('sp', ascending=False).head(8)[['creative', 'sp', 'cti', 'status']].to_dict('records'),
    scaled_sp_range=[float(a[a.is_scaled].sp.min()), float(a[a.is_scaled].sp.max())],
    scaled_cti_range=[float(a[a.is_scaled].cti.min()), float(a[a.is_scaled].cti.max())],
    cti_bench_testing_campaign=None,
)
(ROOT / 'output/results.json').write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))

# ---- console summary ----
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_colwidth', 45)
cols = ['creative', 'bau_first_date', 'sp', 'ctr', 'cti', 'cti_all_clicks', 'cvr', 'test_cpft', 'test_spend', 'wk1_spend', 'wk1_cpr', 'best_week_cpr', 'bau_spend', 'bau_cpr', 'status']
print(a.sort_values('bau_spend', ascending=False)[cols].round(3).to_string(index=False))
print(json.dumps({k: res[k] for k in ['n', 'n_scaled', 'n_borderline', 'fisher', 'spearman', 'scaled_sp_range', 'scaled_cti_range']}, indent=1, default=float))
for name, blk in [('benchmarks', res['benchmarks']), ('quadrants', res['quadrants']), ('quadrants_tw', res['quadrants_tw'])]:
    print('==', name)
    for k, v in blk.items():
        print(f"{k:22s} n={v['n']:2d} scaled={v['scaled']} B={v['borderline']} rate={v['rate'] or 0:.0%} wk1$={v['med_wk1_spend'] or 0:,.0f} wk1CPR={v['med_wk1_cpr'] or 0:,.0f}  {', '.join(v['creatives'])}")
print(pd.DataFrame(res['cti_sweep']).round(3).to_string(index=False))
print(pd.DataFrame(res['sp_sweep']).round(3).to_string(index=False))

# ---- quadrant chart ----
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(11, 7))
colors = {'Scaled': '#2e9e5b', 'Borderline': '#f08c00', 'Not scaled': '#9aa0a6'}
for st, g in a.groupby('status'):
    ax.scatter(g.sp, g.cti * 100, s=np.clip(g.bau_spend / 60, 25, 900), c=colors[st], alpha=.75,
               marker='D' if st == 'Borderline' else 'o', edgecolors='white', linewidths=.8, label=st)
NOTABLE = {'comic-engmeeting', 'mip-kellyyangdes · pineapple-cutting', 'harryspeaks · 26Q3 og-video', 'thedodomen · og-video',
           'havefunytchannel · vschatgpt-short', 'qing · doesaienglishlearningwork_2humantutor', 'hua · 2026resolutionenglish5m_3invest',
           'mip-emily_life · learning-technique-sharing', 'na · connor-keyskillsintheaiera-2cut', 'connor-keyskillsintheaiera-2cut'}
for r in a.itertuples():
    if r.status == 'Not scaled' and r.creative not in NOTABLE:
        continue
    lab = r.creative.split(' · ')[-1] if ' · ' in r.creative else r.creative
    lab = (r.creative.split(' · ')[0] + ' · ' + lab[:22]) if ' · ' in r.creative else lab[:28]
    ax.annotate(f'{lab} (${r.test_cpft:,.0f})' if np.isfinite(r.test_cpft) else lab, (r.sp, r.cti * 100),
                fontsize=6.5, xytext=(5, 3), textcoords='offset points', color='#222' if r.status != 'Not scaled' else '#777')
ax.axvline(SP_BENCH, ls='--', c='#555', lw=1); ax.axhline(CTI_BENCH * 100, ls='--', c='#555', lw=1)
ax.axhline(CTI_TW * 100, ls=':', c='#c0392b', lw=1); ax.axvline(3.0, ls=':', c='#c0392b', lw=1)
ax.text(9.9, CTI_BENCH * 100 + .1, 'JP CTI 5%', ha='right', fontsize=7); ax.text(9.9, CTI_TW * 100 + .1, 'TW CTI 1%', ha='right', fontsize=7, color='#c0392b')
ax.set_yscale('symlog', linthresh=1); ax.set_yticks([0, .5, 1, 2, 3, 5, 10]); ax.set_yticklabels(['0', '0.5', '1', '2', '3', '5', '10'])
ax.set_xlabel('Testing-phase SP score (Option B)'); ax.set_ylabel('Testing-phase CTI = installs / link clicks (%)')
ax.set_title('TW Meta iOS: testing SP × CTI vs BAU scaling (BAU launch Jun 1 – Sep 22, 2026)\n'
             'bubble = BAU cumulative spend · ($) = testing CPFT · green = scaled, orange diamond = borderline, grey = not scaled (only notable greys labelled)', fontsize=10)
ax.legend(loc='lower right', markerscale=.5, fontsize=8); ax.set_xlim(0.5, 10.6); ax.set_ylim(-0.05, 14)
ax.grid(alpha=.25)
fig.tight_layout(); fig.savefig(ROOT / 'output/quadrant.png', dpi=160)
