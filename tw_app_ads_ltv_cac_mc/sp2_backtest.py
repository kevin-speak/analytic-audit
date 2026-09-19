"""
Backtest of the proposed SP2 (sp2.py) against the current P1 rule (SP >= 2 & >= 10 installs), Speak ZH Taiwan iOS,
2026-06-01 .. 2026-09-15. Three questions:
  Q1  Speed: when does each rule first give a verdict?  P1 needs 10 installs; SP2 reads at 20 installs or $100, whichever first.
  Q2  Same date: at each ad's 10-install date, which score better captures the ads that end at >= 0.85x LTV/CAC?
  Q3  Scaling campaign: how well does each score rank the scaled ads, full window and at the 10-install date?
Inputs: data/ad_daily.csv, data/ad_placement.csv, data/ad_placement_milestones.csv (placement funnel cumulative to the
        10-install date 'i10' and to the SP2 read date 'read'), output/ads_sp2.csv, output/sp2.json, output/results.json
Output: output/sp2_backtest.json (consumed by the report, section 8), output/ads_backtest.csv
"""
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
rng = np.random.default_rng(7)
TARGET85, TARGET80, SI_CLIP, MIN_SPEND = 0.85, 0.8, (0.25, 4.0), 100.0
P = json.load(open('output/sp2.json'))['params']; K, TARGET = P['K_per_install'], P['target']
sim = {a['ad_id']: a for a in json.load(open('output/results.json'))['ads']}
ads = pd.read_csv('output/ads_sp2.csv', dtype={'ad_id': str}).set_index('ad_id')
ads['p85'] = pd.Series({k: v.get('p_ltv_cac_ge085', np.nan) for k, v in sim.items()}); ads['p80'] = pd.Series({k: v.get('p_ltv_cac_ge08', np.nan) for k, v in sim.items()})
ads['name'] = pd.Series({k: v['name'] for k, v in sim.items()})
dl = pd.read_csv('data/ad_daily.csv', dtype={'ad_id': str}); dl['date'] = pd.to_datetime(dl.date); dl = dl[dl.ad_id.isin(ads.index)].sort_values(['ad_id', 'date'])
dl['day'] = dl.groupby('ad_id').cumcount() + 1
for c in ['spend', 'installs', 'trials', 'clicks', 'impressions']: dl['cum_' + c] = dl.groupby('ad_id')[c].cumsum()

# ---------- Q1: time to verdict ----------------------------------------------------------------------------
def first(mask):
    f = dl[mask].groupby('ad_id').head(1).set_index('ad_id'); return f[['day', 'date', 'cum_spend', 'cum_installs', 'cum_trials']]
f10 = first(dl.cum_installs >= 10); f20 = first(dl.cum_installs >= 20); f100 = first(dl.cum_spend >= 100)
fread = pd.concat([f20, f100]).sort_values(['day', 'date']).groupby(level=0).head(1)      # earlier of the two
for k, f in (('i10', f10), ('read', fread)):
    ads[f'{k}_day'] = f.day; ads[f'{k}_date'] = f.date; ads[f'{k}_spend'] = f.cum_spend; ads[f'{k}_installs'] = f.cum_installs; ads[f'{k}_trials'] = f.cum_trials
ads['last_day'] = dl.groupby('ad_id').day.max()
def speed(df):
    both = df.dropna(subset=['i10_day', 'read_day']); never10 = df[df.i10_day.isna()]
    gap_day = (both.i10_day - both.read_day); gap_spend = (both.i10_spend - both.read_spend)
    r = {'n': int(len(df)), 'spend': float(df.spend.sum()),
         'p1': {'share_verdict': float(df.i10_day.notna().mean()), 'n_verdict': int(df.i10_day.notna().sum()), 'median_day': float(df.i10_day.median()) if df.i10_day.notna().any() else None,
                'median_spend': float(df.i10_spend.median()) if df.i10_spend.notna().any() else None, 'p75_day': float(df.i10_day.quantile(.75)) if df.i10_day.notna().any() else None},
         'sp2': {'share_verdict': float(df.read_day.notna().mean()), 'n_verdict': int(df.read_day.notna().sum()), 'median_day': float(df.read_day.median()) if df.read_day.notna().any() else None,
                 'median_spend': float(df.read_spend.median()) if df.read_spend.notna().any() else None, 'p75_day': float(df.read_day.quantile(.75)) if df.read_day.notna().any() else None,
                 'median_installs_at_read': float(df.read_installs.median()) if df.read_installs.notna().any() else None},
         'paired': {'n': int(len(both)), 'sp2_earlier': float((gap_day > 0).mean()) if len(both) else None, 'same_day': float((gap_day == 0).mean()) if len(both) else None,
                    'sp2_later': float((gap_day < 0).mean()) if len(both) else None, 'median_day_gap': float(gap_day.median()) if len(both) else None, 'mean_day_gap': float(gap_day.mean()) if len(both) else None,
                    'median_spend_gap': float(gap_spend.median()) if len(both) else None, 'spend_gap_total': float(gap_spend.sum()) if len(both) else None},
         'never10': {'n': int(len(never10)), 'spend': float(never10.spend.sum()), 'n_sp2_read': int(never10.read_day.notna().sum()), 'spend_sp2_read': float(never10[never10.read_day.notna()].spend.sum()),
                     'spend_after_read': float((never10.spend - never10.read_spend).clip(lower=0).sum())}}
    return r
# day-by-day share of ads with a verdict (all ads with spend > 0)
curve = {b: [{'day': d, 'p1': float((df.i10_day <= d).mean()), 'sp2': float((df.read_day <= d).mean())} for d in range(1, 31)]
         for b, df in [('Overall', ads)] + [(b, ads[ads.bucket == b]) for b in ['Testing', 'Winning', 'Scaling']]}

# ---------- SP (Option B) at a milestone, using the pool placement benchmarks -------------------------------
pl = pd.read_csv('data/ad_placement.csv', dtype={'ad_id': str}); pl = pl[pl.ad_id.isin(ads.index)]
plc = sorted(pl.placement.unique()); pj = {p: j for j, p in enumerate(plc)}; ai = {a: i for i, a in enumerate(ads.index)}
n, m = len(ads), len(plc); If, Cf, Tf = np.zeros((n, m)), np.zeros((n, m)), np.zeros((n, m))
for r in pl.itertuples(): If[ai[r.ad_id], pj[r.placement]] += r.impressions; Cf[ai[r.ad_id], pj[r.placement]] += r.clicks; Tf[ai[r.ad_id], pj[r.placement]] += r.trials
tI, tC, tT = If.sum(0), Cf.sum(0), Tf.sum(0)
def sp_option_b(rows):
    """rows: DataFrame ad_id x placement with spend, impressions, clicks, trials at the milestone. Leave-one-out pool benchmark."""
    out = {}
    for a, g in rows.groupby('ad_id'):
        i = ai[a]; w = g.spend.values / g.spend.sum() if g.spend.sum() > 0 else np.zeros(len(g)); s = 0.0
        for wj, r in zip(w, g.itertuples()):
            j = pj.get(r.placement)
            if j is None or wj == 0: continue
            bI, bC, bT = tI[j] - If[i, j], tC[j] - Cf[i, j], tT[j] - Tf[i, j]
            bctr = bC / bI if bI > 0 else 0; bcti = bT / bC if bC > 0 else 0
            ctr = r.clicks / r.impressions if r.impressions > 0 else 0; cti = r.trials / r.clicks if r.clicks > 0 else 0
            s += wj * ((ctr / bctr if bctr > 0 else 0) + (cti / bcti if bcti > 0 else 0))
        out[a] = s
    return pd.Series(out)
ms = pd.read_csv('data/ad_placement_milestones.csv', dtype={'ad_id': str}); ms = ms[ms.ad_id.isin(ads.index)]
ads['sp_i10'] = sp_option_b(ms[ms.milestone == 'i10']); ads['sp_read'] = sp_option_b(ms[ms.milestone == 'read'])
# SP2 at the milestones (ad-level): EI from cumulative CPI, SI vs the campaign median of spend/day at the same milestone
for k in ('i10', 'read'):
    ads[f'ei_{k}'] = (K / (ads[f'{k}_spend'] / ads[f'{k}_installs'].replace(0, np.nan))) / TARGET
    spd = ads[f'{k}_spend'] / ads[f'{k}_day']
    ads[f'si_{k}'] = (spd / spd.groupby(ads.campaign_name).transform('median')).clip(*SI_CLIP)
    ads[f'sp2_{k}'] = ads[f'ei_{k}'] * ads[f'si_{k}']
ads['on85'] = ads.ltv_cac >= TARGET85; ads['on80'] = ads.ltv_cac >= TARGET80
# verdict stability: early call vs the same rule on full-window data
def agree(a, b): m_ = a.notna() & b.notna(); return float((a[m_] == b[m_]).mean()) if m_.any() else None
A = ads[ads.spend >= MIN_SPEND]
stability = {'p1_early_vs_final': agree(A.sp_i10 >= 2, A.sp >= 2), 'ei_early_vs_final': agree(A.ei_read >= 1, A.EI >= 1), 'sp2w_early_vs_final': agree((A.ei_read >= 1) & (A.sp2_read >= 2), A.sp2_winner),
             'p1_early_vs_on85': agree(A.sp_i10 >= 2, A.on85), 'ei_early_vs_on85': agree(A.ei_read >= 1, A.on85), 'n_p1': int(A.sp_i10.notna().sum()), 'n_read': int(A.ei_read.notna().sum())}

# ---------- Q2: same 10-install date --------------------------------------------------------------------------
def gate_row(df, mask, label, target='on85'):
    g = df[mask]; pos = df[target]; tp = (mask & pos).sum(); spend_pos = (df.spend * pos).sum()
    prec = tp / mask.sum() if mask.sum() else None; rec = tp / pos.sum() if pos.sum() else None
    return {'gate': label, 'n': int(mask.sum()), 'spend': float(g.spend.sum()), 'hits': int(tp), 'hit_rate': None if prec is None else float(prec), 'recall': None if rec is None else float(rec),
            'spend_recall': float((g.spend * g[target]).sum() / spend_pos) if spend_pos else None,
            'f1': float(2 * prec * rec / (prec + rec)) if prec and rec else 0.0,
            'sw_ltv_cac': float((g.ltv_cac * g.spend).sum() / g.spend.sum()) if len(g) else None,
            'sw_ltv_cac_out': float((df[~mask].ltv_cac * df[~mask].spend).sum() / df[~mask].spend.sum()) if (~mask).any() else None,
            'exp_hit_rate': float(g.p85.mean()) if len(g) and g.p85.notna().any() else None}
def score_stats(df, col, target='on85'):
    d = df[[col, 'ltv_cac', target, 'spend']].replace([np.inf, -np.inf], np.nan).dropna()
    return {'n': int(len(d)), 'rho': float(spearmanr(d[col], d.ltv_cac)[0]) if len(d) > 5 else None,
            'auc': float(roc_auc_score(d[target], d[col])) if d[target].nunique() > 1 else None}
def boot_auc_diff(df, a, b, target='on85', B=4000):
    d = df[[a, b, target]].replace([np.inf, -np.inf], np.nan).dropna(); y = d[target].values
    if y.sum() < 2 or (~y).sum() < 2: return None
    diffs = []
    for _ in range(B):
        idx = rng.integers(0, len(d), len(d)); yy = y[idx]
        if yy.sum() == 0 or yy.sum() == len(yy): continue
        diffs.append(roc_auc_score(yy, d[a].values[idx]) - roc_auc_score(yy, d[b].values[idx]))
    diffs = np.array(diffs); return {'diff': float(np.median(diffs)), 'ci': [float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95))], 'p_gt0': float((diffs > 0).mean())}
def boot_rho_diff(df, a, b, B=4000):
    d = df[[a, b, 'ltv_cac']].replace([np.inf, -np.inf], np.nan).dropna(); diffs = []
    for _ in range(B):
        idx = rng.integers(0, len(d), len(d)); s = d.iloc[idx]
        diffs.append(spearmanr(s[a], s.ltv_cac)[0] - spearmanr(s[b], s.ltv_cac)[0])
    diffs = np.array(diffs); return {'diff': float(np.nanmedian(diffs)), 'ci': [float(np.nanpercentile(diffs, 5)), float(np.nanpercentile(diffs, 95))], 'p_gt0': float(np.nanmean(diffs > 0))}
T = A.dropna(subset=['i10_day']).copy()             # analyzed ads that reached 10 installs
EI85 = TARGET85 / TARGET                              # EI equivalent of the 0.85x target
q2 = {}
for b in ['Overall', 'Testing', 'Winning', 'Scaling']:
    df = T if b == 'Overall' else T[T.bucket == b]
    rows = [gate_row(df, df.sp_i10 >= 2, 'P1: SP ≥ 2 at 10 installs'),
            gate_row(df, (df.ei_i10 >= 1) & (df.sp2_i10 >= 2), 'SP2 winner: EI ≥ 1 & SP2 ≥ 2'),
            gate_row(df, df.ei_i10 >= 1, 'EI ≥ 1 (projected ≥ 0.8×)'),
            gate_row(df, df.ei_i10 >= EI85, f'EI ≥ {EI85:.3f} (projected ≥ 0.85×)'),
            gate_row(df, df.ei_i10 >= 0.8, 'EI ≥ 0.8 (not paused by SP2)'),
            gate_row(df, (df.sp_i10 >= 2) & (df.ei_i10 >= 1), 'Both: SP ≥ 2 and EI ≥ 1')]
    sweep_sp = [{'t': t, **{k: v for k, v in gate_row(df, df.sp_i10 >= t, '').items() if k in ('n', 'hit_rate', 'recall', 'f1', 'sw_ltv_cac')}} for t in np.arange(1.0, 3.01, 0.25)]
    sweep_ei = [{'t': round(t, 2), **{k: v for k, v in gate_row(df, df.ei_i10 >= t, '').items() if k in ('n', 'hit_rate', 'recall', 'f1', 'sw_ltv_cac')}} for t in np.arange(0.5, 1.61, 0.1)]
    q2[b] = {'n': int(len(df)), 'n_on85': int(df.on85.sum()), 'n_on80': int(df.on80.sum()), 'spend': float(df.spend.sum()), 'median_i10_trials': float(df.i10_trials.median()) if len(df) else None,
             'median_i10_spend': float(df.i10_spend.median()) if len(df) else None, 'median_i10_day': float(df.i10_day.median()) if len(df) else None,
             'rows': rows, 'sweep_sp': sweep_sp, 'sweep_ei': sweep_ei,
             'scores': {'sp': score_stats(df, 'sp_i10'), 'ei': score_stats(df, 'ei_i10'), 'sp2': score_stats(df, 'sp2_i10'), 'si': score_stats(df, 'si_i10')},
             'scores80': {'sp': score_stats(df, 'sp_i10', 'on80'), 'ei': score_stats(df, 'ei_i10', 'on80'), 'sp2': score_stats(df, 'sp2_i10', 'on80')},
             'boot_auc_ei_minus_sp': boot_auc_diff(df, 'ei_i10', 'sp_i10') if len(df) > 10 else None,
             'boot_rho_ei_minus_sp': boot_rho_diff(df, 'ei_i10', 'sp_i10') if len(df) > 10 else None}

# ---------- Q3: scaling campaign -------------------------------------------------------------------------------
S = A[A.bucket == 'Scaling'].copy()
Kt = ads.ssot_ltv.sum() / ads.trials.sum()                                 # SSOT LTV per Meta-reported trial (pool)
S['cpft'] = S.spend / S.trials.replace(0, np.nan); S['ei_trial'] = (Kt / S.cpft) / TARGET; S['sp2_trial'] = S.ei_trial * S.SI
S['inst_to_trial'] = S.trials / S.installs.replace(0, np.nan)
def rank_block(df, col):
    d = df[[col, 'ltv_cac', 'spend']].replace([np.inf, -np.inf], np.nan).dropna().sort_values(col, ascending=False)
    if len(d) < 6: return None
    k = max(3, len(d) // 3); top, bot = d.head(k), d.tail(k); half = d.head(len(d) // 2)
    return {'n': int(len(d)), 'rho': float(spearmanr(d[col], d.ltv_cac)[0]), 'auc_above_median': float(roc_auc_score(d.ltv_cac >= d.ltv_cac.median(), d[col])),
            'top_third_sw': float((top.ltv_cac * top.spend).sum() / top.spend.sum()), 'bottom_third_sw': float((bot.ltv_cac * bot.spend).sum() / bot.spend.sum()),
            'top_half_sw': float((half.ltv_cac * half.spend).sum() / half.spend.sum()), 'top_third_spend': float(top.spend.sum()), 'k': int(k)}
q3 = {'n': int(len(S)), 'spend': float(S.spend.sum()), 'actual_sw': float((S.ltv_cac * S.spend).sum() / S.spend.sum()), 'n_on85': int(S.on85.sum()), 'n_on80': int(S.on80.sum()),
      'K_per_trial': float(Kt), 'cpft_target': float(Kt / TARGET),
      'full': {'SP (current)': rank_block(S, 'sp'), 'EI (CPI)': rank_block(S, 'EI'), 'SP2 = EI × SI': rank_block(S, 'SP2'), 'SI alone': rank_block(S, 'SI'),
               'EI on cost per trial': rank_block(S, 'ei_trial'), 'SP2 on cost per trial': rank_block(S, 'sp2_trial')},
      'i10': {'SP at 10 installs': rank_block(S, 'sp_i10'), 'EI at 10 installs': rank_block(S, 'ei_i10'), 'SP2 at 10 installs': rank_block(S, 'sp2_i10')},
      'boot_rho_sp_minus_ei_full': boot_rho_diff(S, 'sp', 'EI'), 'boot_rho_sp_minus_sp2_full': boot_rho_diff(S, 'sp', 'SP2'), 'boot_rho_eit_minus_ei_full': boot_rho_diff(S, 'ei_trial', 'EI'),
      'boot_rho_sp_minus_ei_i10': boot_rho_diff(S, 'sp_i10', 'ei_i10'),
      'diag': {'rho_inst_to_trial': float(spearmanr(S.inst_to_trial, S.ltv_cac, nan_policy='omit')[0]), 'rho_cpi': float(spearmanr(-S.cpi, S.ltv_cac, nan_policy='omit')[0]),
               'rho_cpft': float(spearmanr(-S.cpft, S.ltv_cac, nan_policy='omit')[0]), 'rho_ipm': float(spearmanr(S.ipm, S.ltv_cac)[0]), 'rho_tpi': float(spearmanr(S.tpi, S.ltv_cac)[0]),
               'cv_cpi': float(S.cpi.std() / S.cpi.mean()), 'cv_inst_to_trial': float(S.inst_to_trial.std() / S.inst_to_trial.mean()),
               'median_i10_day_scaling': float(S.i10_day.median()) if S.i10_day.notna().any() else None},
      'gates_full': [gate_row(S, S.p1, 'P1 gate (SP ≥ 2 & ≥ 10 installs)', 'on80'), gate_row(S, S.sp2_winner, 'SP2 winner (EI ≥ 1 & SP2 ≥ 2)', 'on80'), gate_row(S, S.EI >= 1, 'EI ≥ 1', 'on80'),
                     gate_row(S, S.ei_trial >= 1, f'EI on cost per trial ≥ 1 (CPFT ≤ ${Kt / TARGET:.0f})', 'on80')],
      'ads': [{'ad_id': i, 'name': r.name, 'spend': round(float(r.spend), 2), 'sp': round(float(r.sp), 2), 'EI': None if np.isnan(r.EI) else round(float(r.EI), 2), 'SP2': None if np.isnan(r.SP2) else round(float(r.SP2), 2),
               'ei_trial': None if np.isnan(r.ei_trial) else round(float(r.ei_trial), 2), 'ltv_cac': round(float(r.ltv_cac), 3), 'ltv_cac_ci': [round(float(r.ltv_cac_lo), 3), round(float(r.ltv_cac_hi), 3)]} for i, r in S.iterrows()]}

out = {'params': {'target85': TARGET85, 'target80': TARGET80, 'K_per_install': float(K), 'K_per_trial': float(Kt), 'ei85': float(EI85), 'min_spend': MIN_SPEND, 'read_rule': '20 installs or $100 spend, whichever first'},
       'speed': {b: speed(ads if b == 'Overall' else ads[ads.bucket == b]) for b in ['Overall', 'Testing', 'Winning', 'Scaling']},
       'speed_analyzed': {b: speed(A if b == 'Overall' else A[A.bucket == b]) for b in ['Overall', 'Testing', 'Winning', 'Scaling']},
       'curve': curve, 'stability': stability, 'q2': q2, 'q3': q3,
       'ads': [{'ad_id': i, 'bucket': r.bucket, 'spend': round(float(r.spend), 2), 'analyzed': bool(r.spend >= MIN_SPEND), 'ltv_cac': round(float(r.ltv_cac), 3), 'on85': bool(r.on85),
                'i10_day': None if pd.isna(r.i10_day) else int(r.i10_day), 'i10_spend': None if pd.isna(r.i10_spend) else round(float(r.i10_spend), 2), 'i10_trials': None if pd.isna(r.i10_trials) else int(r.i10_trials),
                'read_day': None if pd.isna(r.read_day) else int(r.read_day), 'read_spend': None if pd.isna(r.read_spend) else round(float(r.read_spend), 2), 'read_installs': None if pd.isna(r.read_installs) else int(r.read_installs),
                'sp_i10': None if pd.isna(r.sp_i10) else round(float(r.sp_i10), 3), 'ei_i10': None if pd.isna(r.ei_i10) else round(float(r.ei_i10), 3), 'sp2_i10': None if pd.isna(r.sp2_i10) else round(float(r.sp2_i10), 3),
                'ei_read': None if pd.isna(r.ei_read) else round(float(r.ei_read), 3)} for i, r in ads.iterrows()]}
json.dump(out, open('output/sp2_backtest.json', 'w'), indent=1); ads.to_csv('output/ads_backtest.csv')

# ---------- console summary ----------
def f(x, d=2): return '–' if x is None or (isinstance(x, float) and np.isnan(x)) else (f'{x:.{d}f}' if isinstance(x, float) else str(x))
print('K/install', f(K), 'K/trial', f(Kt), '\n== Q1 speed (all ads with spend)')
for b, s in out['speed'].items():
    print(f"{b:8s} n={s['n']} | P1 verdict {f(s['p1']['share_verdict'])} med day {f(s['p1']['median_day'],1)} med $ {f(s['p1']['median_spend'],0)} | SP2 verdict {f(s['sp2']['share_verdict'])} med day {f(s['sp2']['median_day'],1)} med $ {f(s['sp2']['median_spend'],0)} installs@read {f(s['sp2']['median_installs_at_read'],0)} | paired n={s['paired']['n']} SP2 earlier {f(s['paired']['sp2_earlier'])} same {f(s['paired']['same_day'])} gap med {f(s['paired']['median_day_gap'],1)}d ${f(s['paired']['median_spend_gap'],0)} | never10 n={s['never10']['n']} ${f(s['never10']['spend'],0)} SP2 read {s['never10']['n_sp2_read']} $after {f(s['never10']['spend_after_read'],0)}")
print('stability', {k: f(v) for k, v in stability.items()})
print('== Q2 at 10-install date (analyzed ads), target 0.85x')
for b, g in q2.items():
    print(f"{b:8s} n={g['n']} on85={g['n_on85']} on80={g['n_on80']} med trials@i10 {f(g['median_i10_trials'],0)} | AUC sp {f(g['scores']['sp']['auc'])} ei {f(g['scores']['ei']['auc'])} sp2 {f(g['scores']['sp2']['auc'])} | rho sp {f(g['scores']['sp']['rho'])} ei {f(g['scores']['ei']['rho'])} sp2 {f(g['scores']['sp2']['rho'])} | boot AUC ei-sp {g['boot_auc_ei_minus_sp']}")
    for r in g['rows']: print(f"    {r['gate']:42s} n={r['n']:3d} hits={r['hits']:2d} prec {f(r['hit_rate'])} rec {f(r['recall'])} $rec {f(r['spend_recall'])} F1 {f(r['f1'])} swLTV/CAC {f(r['sw_ltv_cac'])} out {f(r['sw_ltv_cac_out'])} E[hit] {f(r['exp_hit_rate'])}")
print('== Q3 scaling', q3['n'], 'ads', f(q3['spend'], 0), 'actual sw', f(q3['actual_sw']), 'on85', q3['n_on85'], 'on80', q3['n_on80'], 'diag', {k: f(v) for k, v in q3['diag'].items()})
for grp in ('full', 'i10'):
    for k, v in q3[grp].items():
        if v: print(f"  {grp:4s} {k:24s} rho {f(v['rho'])} AUC>med {f(v['auc_above_median'])} top3rd {f(v['top_third_sw'])} bot3rd {f(v['bottom_third_sw'])} tophalf {f(v['top_half_sw'])}")
for k in ('boot_rho_sp_minus_ei_full', 'boot_rho_sp_minus_sp2_full', 'boot_rho_eit_minus_ei_full', 'boot_rho_sp_minus_ei_i10'): print(' ', k, q3[k])
for r in q3['gates_full']: print(f"    {r['gate']:42s} n={r['n']:3d} hits={r['hits']} prec {f(r['hit_rate'])} swLTV/CAC {f(r['sw_ltv_cac'])} out {f(r['sw_ltv_cac_out'])}")
