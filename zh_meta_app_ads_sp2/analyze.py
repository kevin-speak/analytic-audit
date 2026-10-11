"""
SP2 vs LTV/CAC vs old SP (Option B) vs IPM for every iOS app ad in the Meta "Speak ZH" account (Taiwan + Hong Kong),
2026-06-01 .. 2026-10-07.

Inputs  (data/): ad_placement.csv, ads_meta.csv, ad_daily.csv, ssot_ads.csv, af_ads.csv, calibration.json
Outputs (output/): results.json (embedded into report/index.html by report/build.py), ads_scored.csv
Run: python3 analyze.py        (N_SIM=500 python3 analyze.py for a quick pass)

Model (same as tw_app_ads_ltv_cac_mc/simulate.py, run per market):
  LTV/CAC per ad is simulated N_SIM times from its SSOT trial starts, an uncertain trial-to-paid rate, Meta-observed
  purchases (re-allocating paid users across ads), the plan mix of its trialists and the LTV per paid user by plan.
  The same draws re-score old SP (CTR/CTI shrunk toward placement benchmarks), IPM, EI and SP2 (installs drawn from
  the ad's install rate), so correlations, AUCs and gate lifts carry 90% intervals.
"""
import json, os, re, time
import numpy as np, pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.metrics import roc_auc_score

t0 = time.time()
rng = np.random.default_rng(20261011)
N_SIM = int(os.environ.get('N_SIM', 10000))
SP_THRESHOLD, CPFT_TARGET, MIN_TRIALS, MIN_INSTALLS = 2.0, 55.0, 10, 10   # old SP phase rules (Taiwan targets, applied to HK too)
MIN_SPEND = 100.0                                                         # ads below this are listed but excluded from statistics
TARGET, SP2_BAR, SI_CLIP = 0.8, 2.0, (0.25, 4.0)                         # SP2: EI = 1 <=> projected LTV/CAC = 0.8x
PRIOR_STRENGTH, LTV_FORECAST_SD, P_CONV_SD = 20.0, 0.05, 0.03
KAPPA_CTR, KAPPA_CTI = 2000.0, 30.0
PLANS = ['annual_reg', 'annual_plus', 'monthly']
MARKETS = ['Taiwan', 'Hong Kong']; GEO = {'Taiwan': 'TW', 'Hong Kong': 'HK'}
STAGES = ['Testing', 'Winning', 'Scaling', 'Other']
MILESTONES = [50, 100, 150, 200, 300, 500, 750, 1000, 2000]
SIGNALS = [('sp2', 'SP2 (new)'), ('ei', 'Efficiency Index'), ('sp', 'SP (old)'), ('ipm', 'IPM')]
cal = json.load(open('data/calibration.json'))
ANALYSIS = os.environ.get('ANALYSIS', 'oct')          # 'oct' = October only (default); 'full' = 1 Jun - 7 Oct 2026
PRESETS = {
    'oct': dict(window=('2026-10-01', '2026-10-07'), label='1–7 Oct 2026', placement='data/ad_placement_oct.csv', ssot='data/ssot_ads_oct.csv', af='data/af_ads_oct.csv',
                mix_block='october', k_trailing=True,
                note='Ad-level inputs (spend, installs, placements, SSOT trial starts and LTV, AppsFlyer plan mix) are October only. A week of cohorts is too few to calibrate the market constants on, so trial-to-paid, LTV per paid user and K (LTV per install) are estimated on 1 Jun – 7 Oct 2026; the plan-mix prior uses October AppsFlyer trials.'),
    'full': dict(window=('2026-06-01', '2026-10-07'), label='1 Jun – 7 Oct 2026', placement='data/ad_placement.csv', ssot='data/ssot_ads.csv', af='data/af_ads.csv',
                 mix_block=None, k_trailing=False, note='All inputs and market constants are estimated on the same window, 1 Jun – 7 Oct 2026.'),
}
PRE = PRESETS[ANALYSIS]; W0, W1 = PRE['window']

def market_cal(m):
    c = cal['markets'][m]; s = c['ssot']; e = (cal[PRE['mix_block']][m]['af_events'] if PRE['mix_block'] else c['af_events'])
    typed = np.array([e['trial_started_annual_premium'], e['trial_started_annual_premium_plus'], e['trial_started_monthly_premium']], float)
    plans = {(r['duration'], r['tier']): r for r in c['ltv_by_plan']}
    def blend(rows):
        n = sum(r['users'] for r in rows); mu = sum(r['users'] * r['avg_ltv'] for r in rows) / n
        var = sum(r['users'] * (r['sd_ltv'] ** 2 + (r['avg_ltv'] - mu) ** 2) for r in rows) / n
        return mu, var ** 0.5
    mu_sd = [blend([plans[('annual_single', 'regular')]]), blend([plans[('annual_single', 'plus')]]), blend([plans[('monthly', 'regular')], plans[('monthly', 'plus')]])]
    return {'p_conv': s['paid'] / s['trial_starts'], 'mix': typed / typed.sum(), 'mu': np.array([x[0] for x in mu_sd]), 'sd': np.array([x[1] for x in mu_sd]),
            'ssot_installs': s['installs'], 'ssot_trials': s['trial_starts'], 'ssot_paid': s['paid'], 'ssot_ltv': s['ltv']}
CAL = {m: market_cal(m) for m in MARKETS}

def stage(c):
    c = c.lower()
    for s in ('testing', 'winning', 'scaling'):
        if s in c: return s.capitalize()
    return 'Other'
def clean_name(name):
    m = re.findall(r'c(\d+)[:\!]([^_c\s][^_]*?)(?=_c\d+[:\!]|$)', str(name).replace('__', '_'))
    if m:
        d = {int(k): v.strip('_').strip() for k, v in m}
        c3, c6, c7 = d.get(3, ''), d.get(6, ''), d.get(7, '')
        if c3 or c6 or c7: return f"{c3} – {c6} – {c7}".strip(' –')
    return str(name)[:80]
def extract_c1(name):
    m = re.search(r'c1[:\!](\w+)', str(name), re.IGNORECASE)
    return m.group(1) if m else 'Untagged'
def fl(x, d=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)
def q(a, qs=(5, 50, 95)):
    return np.nanpercentile(a, qs, axis=0)
def ql(a, d=3):
    return [fl(x, d) for x in q(a)]

# ---- load ----------------------------------------------------------------------------------
pl = pd.read_csv(PRE['placement'], dtype={'ad_id': str})
meta = pd.read_csv('data/ads_meta.csv', dtype={'ad_id': str})
dl = pd.read_csv('data/ad_daily.csv', dtype={'ad_id': str}); dl['date'] = pd.to_datetime(dl.date)
dl = dl[(dl.date >= W0) & (dl.date <= W1)].sort_values(['ad_id', 'date']).reset_index(drop=True)
ssot = pd.read_csv(PRE['ssot'], dtype={'ad_id': str}).rename(columns={'country': 'market'})
af = pd.read_csv(PRE['af'], dtype={'af_ad_id': str})
num = ['spend', 'impressions', 'clicks', 'installs', 'signups', 'trials', 'adj_trials', 'init_purch', 'trial_converts']
for c in num: pl[c] = pd.to_numeric(pl[c]).fillna(0)
for c in ['spend', 'impressions', 'clicks', 'installs', 'signups', 'trials', 'adj_trials']: dl[c] = pd.to_numeric(dl[c]).fillna(0)
for c in ssot.columns[3:]: ssot[c] = pd.to_numeric(ssot[c]).fillna(0)
for c in af.columns[4:]: af[c] = pd.to_numeric(af[c]).fillna(0)

ads = pl.groupby('ad_id').agg(**{c: (c, 'sum') for c in num}, campaign_name=('campaign_name', 'first'), market=('country', 'first')).reset_index()
ads = ads.merge(meta[['ad_id', 'ad_name', 'format', 'category', 'concept', 'creator_name', 'preview', 'first_date', 'last_date', 'active_days']], on='ad_id', how='left')
ads = ads[ads.spend > 0].reset_index(drop=True)
ads['stage'] = ads.campaign_name.map(stage)
ads['ad_name'] = ads.ad_name.fillna('ad ' + ads.ad_id)
ads['clean_name'] = ads.ad_name.map(clean_name); ads['c1'] = ads.ad_name.map(extract_c1)
ads['days'] = ads.ad_id.map(dl.groupby('ad_id').date.nunique()).fillna(1).astype(int)
ads['first_date'] = ads.ad_id.map(dl.groupby('ad_id').date.min().dt.strftime('%Y-%m-%d')).fillna(ads.first_date)
ads['last_date'] = ads.ad_id.map(dl.groupby('ad_id').date.max().dt.strftime('%Y-%m-%d')).fillna(ads.last_date); ads['active_days'] = ads.days
ads['signups_d'] = ads.ad_id.map(dl.groupby('ad_id').signups.sum()).fillna(0)
imp_nz = ads.impressions.replace(0, np.nan)
ads['ipm'] = (ads.installs / imp_nz * 1000).fillna(0); ads['tpi'] = (ads.trials / imp_nz * 1000).fillna(0); ads['ctr'] = (ads.clicks / imp_nz).fillna(0)
ads['cpft'] = ads.spend / ads.trials.replace(0, np.nan)
ads['meta_paid_obs'] = ads.init_purch + ads.trial_converts

# ---- SSOT trial base (per ad, matched on the ad's market) and AppsFlyer plan mix ----------------
ads = ads.merge(ssot[['ad_id', 'market', 'trial_starts', 'paid', 'ltv']].rename(columns={'trial_starts': 'ssot_trials', 'paid': 'ssot_paid', 'ltv': 'ssot_ltv'}), on=['ad_id', 'market'], how='left')
spill = ssot[ssot.ad_id.isin(ads.ad_id)].merge(ads[['ad_id', 'market']].rename(columns={'market': 'ad_market'}), on='ad_id'); spill = spill[spill.market != spill.ad_market]
ssot_fallback = {}
for m in MARKETS:
    mm = ads.market == m; has = mm & ads.ssot_trials.notna()
    ratio = ads.loc[has, 'ssot_trials'].sum() / max(ads.loc[has, 'adj_trials'].sum(), 1e-9)
    ads.loc[mm & ~has, 'ssot_trials'] = ads.loc[mm & ~has, 'adj_trials'] * ratio
    ssot_fallback[m] = {'ratio_ssot_to_adj_trials': fl(ratio), 'n_ads_without_ssot': int((mm & ~has).sum())}
ads[['ssot_paid', 'ssot_ltv']] = ads[['ssot_paid', 'ssot_ltv']].fillna(0)
af['market'] = af.geo.map({v: k for k, v in GEO.items()})
af_cols = ['af_installs', 'af_signups', 'af_trials', 'af_trials_annual_reg', 'af_trials_annual_plus', 'af_trials_monthly']
ads = ads.merge(af[['af_ad_id', 'market'] + af_cols].rename(columns={'af_ad_id': 'ad_id'}), on=['ad_id', 'market'], how='left')
ads[af_cols] = ads[af_cols].fillna(0)

n = len(ads)
mi = ads.market.map({m: i for i, m in enumerate(MARKETS)}).values
p_conv_m = np.array([CAL[m]['p_conv'] for m in MARKETS]); mix_m = np.array([CAL[m]['mix'] for m in MARKETS])
mu_m = np.array([CAL[m]['mu'] for m in MARKETS]); sd_m = np.array([CAL[m]['sd'] for m in MARKETS])
typed = ads[['af_trials_annual_reg', 'af_trials_annual_plus', 'af_trials_monthly']].values.astype(float); ts = typed.sum(1, keepdims=True)
mix = (typed + 10 * mix_m[mi]) / (ts + 10)                               # shrink each ad's plan mix toward its market mix (10 pseudo-trials)
trials_by_plan = ads.ssot_trials.values[:, None] * mix
expected_paid = trials_by_plan.sum(1) * p_conv_m[mi]
ratio_m = np.array([ads.meta_paid_obs.values[mi == i].sum() / max(expected_paid[mi == i].sum(), 1e-9) for i in range(len(MARKETS))])   # Meta-observed / modeled paid
E_meta = expected_paid * ratio_m[mi]
k_conv = p_conv_m * (1 - p_conv_m) / P_CONV_SD ** 2 - 1; conv_a, conv_b = p_conv_m * k_conv, (1 - p_conv_m) * k_conv
mu_ad, sd_ad = mu_m[mi], sd_m[mi]

# ---- old SP (Option B), benchmarks within the ad's market ------------------------------------------
blocks = []
for i, m in enumerate(MARKETS):
    idx = np.where(mi == i)[0]; ids = ads.ad_id.values[idx]; plm = pl[pl.ad_id.isin(ids)]
    plc = sorted(plm.placement.unique()); pidx = {p: j for j, p in enumerate(plc)}; aidx = {a: k for k, a in enumerate(ids)}
    S = np.zeros((len(idx), len(plc))); I = np.zeros_like(S); C = np.zeros_like(S); T = np.zeros_like(S)
    for r in plm.itertuples():
        k, j = aidx[r.ad_id], pidx[r.placement]; S[k, j] += r.spend; I[k, j] += r.impressions; C[k, j] += r.clicks; T[k, j] += r.trials
    tot = S.sum(1, keepdims=True); w = S / np.where(tot > 0, tot, 1)
    oI, oC = I.sum(0) - I, C.sum(0) - C
    bench_ctr = np.where(oI > 0, (C.sum(0) - C) / np.where(oI > 0, oI, 1), 0); bench_cti = np.where(oC > 0, (T.sum(0) - T) / np.where(oC > 0, oC, 1), 0)
    ctr = np.where(I > 0, C / np.where(I > 0, I, 1), 0); cti = np.where(C > 0, T / np.where(C > 0, C, 1), 0)
    blocks.append(dict(idx=idx, w=w, I=I, C=C, T=T, ctr=ctr, cti=cti, bench_ctr=bench_ctr, bench_cti=bench_cti, mI=I > 0, mC=C > 0,
                       bctr_p=np.where(bench_ctr > 0, bench_ctr, ctr[I > 0].mean()), bcti_p=np.where(bench_cti > 0, bench_cti, cti[C > 0].mean()), placements=plc))
def sp_from(b, ctr_, cti_):
    r1 = np.where(b['bench_ctr'] > 0, ctr_ / np.where(b['bench_ctr'] > 0, b['bench_ctr'], 1), 0)
    r2 = np.where(b['bench_cti'] > 0, cti_ / np.where(b['bench_cti'] > 0, b['bench_cti'], 1), 0)
    return (b['w'] * (r1 + r2)).sum(1)
sp = np.zeros(n)
for b in blocks: sp[b['idx']] = sp_from(b, b['ctr'], b['cti'])
ads['sp'] = sp
def phase(r):
    if r.sp >= SP_THRESHOLD:
        if r.trials >= MIN_TRIALS and r.cpft <= CPFT_TARGET: return 'Phase 2 Winner'
        if r.installs >= MIN_INSTALLS: return 'Phase 1 Winner'
    if 1.4 <= r.sp < SP_THRESHOLD: return 'Mid-Tier'
    return 'Pause'
ads['phase'] = ads.apply(phase, axis=1)
ads['p1_point'] = (ads.sp >= SP_THRESHOLD) & (ads.installs >= MIN_INSTALLS)
ads['p2_point'] = (ads.sp >= SP_THRESHOLD) & (ads.trials >= MIN_TRIALS) & (ads.cpft <= CPFT_TARGET)

# ---- SP2 = Efficiency Index x Scale Index ------------------------------------------------------------
K_in_window = np.array([ads.ssot_ltv.values[mi == i].sum() / max(ads.installs.values[mi == i].sum(), 1) for i in range(len(MARKETS))])   # SSOT LTV per Meta-reported install
if PRE['k_trailing']:   # K is a market constant refreshed monthly: take it from the trailing 1 Jun - 7 Oct window (data/ad_placement.csv + data/ssot_ads.csv)
    plf = pd.read_csv('data/ad_placement.csv', dtype={'ad_id': str}); ssf = pd.read_csv('data/ssot_ads.csv', dtype={'ad_id': str}).rename(columns={'country': 'market'})
    for c in ['spend', 'installs']: plf[c] = pd.to_numeric(plf[c]).fillna(0)
    ssf['ltv'] = pd.to_numeric(ssf.ltv).fillna(0)
    fw = plf.groupby('ad_id').agg(spend=('spend', 'sum'), installs=('installs', 'sum'), market=('country', 'first')).reset_index(); fw = fw[fw.spend > 0]
    fw = fw.merge(ssf[['ad_id', 'market', 'ltv']], on=['ad_id', 'market'], how='left'); fw['ltv'] = fw.ltv.fillna(0)
    K_m = np.array([fw.ltv[fw.market == m].sum() / max(fw.installs[fw.market == m].sum(), 1) for m in MARKETS])
else:
    K_m = K_in_window
ads['K'] = K_m[mi]
ads['cpi'] = ads.spend / ads.installs.replace(0, np.nan)
ads['EI'] = (ads.K / ads.cpi) / TARGET
ads.loc[(ads.installs == 0) & (ads.spend >= MIN_SPEND), 'EI'] = 0.0          # $100 with no install: the score is readable and it is zero
ads['spend_per_day'] = ads.spend / ads.days
ads['SI'] = (ads.spend_per_day / ads.groupby('campaign_name').spend_per_day.transform('median')).clip(*SI_CLIP)
ads['SP2'] = ads.EI * ads.SI
ads['sp2_winner'] = (ads.EI >= 1) & (ads.SP2 >= SP2_BAR)
ads['sp2_phase'] = np.select([ads.EI.isna(), ads.sp2_winner, ads.EI >= 1, ads.EI >= TARGET], ['No installs yet', 'Scalable winner', 'Efficient, unproven scale', 'Watch'], 'Pause')

# ---- Monte Carlo ----------------------------------------------------------------------------------
spend = ads.spend.values; imps = ads.impressions.values.astype(float); inst = ads.installs.values.astype(float); tri = ads.trials.values.astype(float)
obs = ads.meta_paid_obs.values; SI = ads.SI.values; K_ad = ads.K.values
LTVCAC = np.zeros((N_SIM, n)); PAID = np.zeros((N_SIM, n)); SP = np.zeros((N_SIM, n)); IPM = np.zeros((N_SIM, n)); TPI = np.zeros((N_SIM, n))
for s in range(N_SIM):
    p_k = rng.beta(conv_a, conv_b)[mi]
    theta = rng.gamma(PRIOR_STRENGTH + obs, 1.0 / (PRIOR_STRENGTH + E_meta))
    scale = np.bincount(mi, weights=E_meta, minlength=len(MARKETS)) / np.maximum(np.bincount(mi, weights=E_meta * theta, minlength=len(MARKETS)), 1e-9)
    theta *= scale[mi]                                   # Meta evidence re-allocates paid across ads; the market level stays at SSOT
    lam = trials_by_plan * (p_k * theta)[:, None]
    paid_k = rng.poisson(lam)
    ltv = (paid_k * mu_ad + np.sqrt(paid_k) * sd_ad * rng.standard_normal(paid_k.shape)).sum(1) * rng.normal(1.0, LTV_FORECAST_SD)
    PAID[s] = paid_k.sum(1); LTVCAC[s] = ltv / spend
    for b in blocks:
        ctr_s = np.where(b['mI'], rng.beta(b['C'] + KAPPA_CTR * b['bctr_p'] + 1e-3, np.maximum(b['I'] - b['C'], 0) + KAPPA_CTR * (1 - b['bctr_p']) + 1e-3), 0)
        cti_s = np.where(b['mC'], rng.beta(b['T'] + KAPPA_CTI * b['bcti_p'] + 1e-3, np.maximum(b['C'] - b['T'], 0) + KAPPA_CTI * (1 - b['bcti_p']) + 1e-3), 0)
        SP[s, b['idx']] = sp_from(b, ctr_s, cti_s)
    IPM[s] = rng.beta(inst + 0.5, np.maximum(imps - inst, 0) + 0.5) * 1000
    TPI[s] = rng.beta(tri + 0.5, np.maximum(imps - tri, 0) + 0.5) * 1000
EI_D = K_ad * (IPM / 1000 * imps) / spend / TARGET        # install draws -> CPI draws -> EI draws
SP2_D = EI_D * SI
print(f'simulated {N_SIM} draws for {n} ads in {time.time() - t0:.0f}s')
med = np.median(LTVCAC, axis=0); ads['ltv_cac'] = med
lo, hi = np.percentile(LTVCAC, [5, 95], axis=0); ads['ltv_cac_lo'] = lo; ads['ltv_cac_hi'] = hi
ads['on_target'] = ads.ltv_cac >= TARGET
analyzed = spend >= MIN_SPEND; ads['analyzed'] = analyzed
DRAWS = {'sp2': SP2_D, 'ei': EI_D, 'sp': SP, 'ipm': IPM}
POINT = {'sp2': ads.SP2.values, 'ei': ads.EI.values, 'sp': ads.sp.values, 'ipm': ads.ipm.values}
inst_ok = inst >= MIN_INSTALLS; tri_ok = tri >= MIN_TRIALS; cp_ok = np.nan_to_num(ads.cpft.values, nan=1e9) <= CPFT_TARGET
pool_ipm_m = {m: inst[mi == i].sum() / imps[mi == i].sum() * 1000 for i, m in enumerate(MARKETS)}; pool_ipm_ad = np.array([pool_ipm_m[m] for m in ads.market])
GATES = {   # name -> (point mask over all ads, draw mask over all ads)
    'SP2 winner (EI ≥ 1 & SP2 ≥ 2)': (ads.sp2_winner.values, (EI_D >= 1) & (SP2_D >= SP2_BAR)),
    'EI ≥ 1 (on target at any scale)': (ads.EI.values >= 1, EI_D >= 1),
    'P1 gate (SP ≥ 2 & ≥ 10 installs)': (ads.p1_point.values, (SP >= SP_THRESHOLD) & inst_ok[None, :]),
    'P2 gate (SP ≥ 2, ≥ 10 trials, CPFT ≤ $55)': (ads.p2_point.values, (SP >= SP_THRESHOLD) & (tri_ok & cp_ok)[None, :]),
    'IPM ≥ market average & ≥ 10 installs': ((ads.ipm.values >= pool_ipm_ad) & inst_ok, (IPM >= pool_ipm_ad[None, :]) & inst_ok[None, :]),
    'Not SP2 winner': (~ads.sp2_winner.values, ~((EI_D >= 1) & (SP2_D >= SP2_BAR))),
    'Not P1': (~ads.p1_point.values, ~((SP >= SP_THRESHOLD) & inst_ok[None, :])),
}

# ---- statistics helpers ----------------------------------------------------------------------------
def spearman_rows(X, Y):
    rx = rankdata(X, axis=1); ry = rankdata(Y, axis=1); rx = rx - rx.mean(1, keepdims=True); ry = ry - ry.mean(1, keepdims=True)
    d = np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1)); return np.where(d > 0, (rx * ry).sum(1) / np.where(d > 0, d, 1), np.nan)
def auc_rows(score, pos):
    r = rankdata(score, axis=1); npos = pos.sum(1); nneg = pos.shape[1] - npos
    with np.errstate(divide='ignore', invalid='ignore'):
        a = ((r * pos).sum(1) - npos * (npos + 1) / 2) / (npos * nneg)
    a[(npos == 0) | (nneg == 0)] = np.nan; return a
def gate_draws(G, X, sp_b):
    pos = X >= TARGET; gs = (G * sp_b).sum(1); ngs = ((~G) * sp_b).sum(1); ng = G.sum(1)
    with np.errstate(divide='ignore', invalid='ignore'):
        sw_in = np.where(gs > 0, (X * G * sp_b).sum(1) / np.where(gs > 0, gs, 1), np.nan)
        sw_out = np.where(ngs > 0, (X * (~G) * sp_b).sum(1) / np.where(ngs > 0, ngs, 1), np.nan)
        lift = sw_in / sw_out
        hit = np.where(ng > 0, (pos & G).sum(1) / np.maximum(ng, 1), np.nan)
        spend_pos = (pos * sp_b).sum(1); recall = np.where(spend_pos > 0, ((pos & G) * sp_b).sum(1) / np.where(spend_pos > 0, spend_pos, 1), np.nan)
    return {'sw_in': ql(sw_in), 'sw_out': ql(sw_out), 'lift': ql(lift), 'p_lift_gt1': fl(np.nanmean(lift > 1)), 'hit_rate': ql(hit), 'spend_recall': ql(recall),
            'n_mean': fl(ng.mean(), 1), 'spend_share': ql(gs / sp_b.sum())}
def gate_point(mask, g):
    gi = g[mask]; tot_ok = (g.spend * g.on_target).sum()
    return {'n': int(len(gi)), 'spend': fl(gi.spend.sum(), 2), 'sw_ltv_cac': fl((gi.ltv_cac * gi.spend).sum() / gi.spend.sum()) if len(gi) else None,
            'hit_rate': fl(gi.on_target.mean()) if len(gi) else None, 'hit_rate_1x': fl((gi.ltv_cac >= 1).mean()) if len(gi) else None,
            'spend_recall': fl((gi.spend * gi.on_target).sum() / tot_ok) if tot_ok else None, 'ssot_ltv_cac': fl(gi.ssot_ltv.sum() / gi.spend.sum()) if len(gi) and gi.spend.sum() else None}

# ---- milestone speed test (daily data) ----------------------------------------------------------------
cum = dl.groupby('ad_id')[['spend', 'impressions', 'clicks', 'installs', 'signups', 'trials']].cumsum(); cum['ad_id'] = dl.ad_id.values
cum['n'] = dl.groupby('ad_id').cumcount().values + 1
fin = ads.set_index('ad_id')
pool_ctr = {m: ads.clicks.values[mi == i].sum() / imps[mi == i].sum() for i, m in enumerate(MARKETS)}
pool_cti = {m: tri[mi == i].sum() / ads.clicks.values[mi == i].sum() for i, m in enumerate(MARKETS)}
def milestones(ids):
    rows = []
    for Sm in MILESTONES:
        f = cum[cum.spend >= Sm].groupby('ad_id').head(1).set_index('ad_id')
        f = f[f.index.isin(ids) & f.index.isin(fin.index[fin.spend >= 2 * Sm])].copy()
        row = {'spend': Sm, 'n': int(len(f))}
        if len(f) >= 8:
            f['ltv'] = fin.ltv_cac; f['market'] = fin.market; f['campaign'] = fin.campaign_name; f['K'] = fin.K
            f['ei'] = f.K * f.installs / f.spend / TARGET
            f['vel'] = f.spend / f.n; f['si'] = (f.vel / f.groupby('campaign').vel.transform('median')).clip(*SI_CLIP); f['sp2'] = f.ei * f.si
            f['ipm'] = f.installs / f.impressions * 1000; f['tpi'] = f.trials / f.impressions * 1000; f['cpft'] = -(f.spend / f.trials.replace(0, np.nan))
            f['spx'] = (f.clicks / f.impressions) / f.market.map(pool_ctr) + (f.trials / f.clicks.replace(0, np.nan)) / f.market.map(pool_cti)
            for x in ['sp2', 'ei', 'spx', 'ipm', 'tpi', 'cpft']:
                mm_ = f[[x, 'ltv']].replace([np.inf, -np.inf], np.nan).dropna()
                row['rho_' + x] = fl(spearmanr(mm_[x], mm_.ltv)[0]) if len(mm_) > 5 else None
                row['auc_' + x] = fl(roc_auc_score(mm_.ltv >= TARGET, mm_[x])) if (mm_.ltv >= TARGET).nunique() > 1 else None
            row['share_installs'] = fl((f.installs > 0).mean()); row['share_trials'] = fl((f.trials > 0).mean())
        rows.append(row)
    return rows
def scale_evidence(ids):
    coh = fin.index[(fin.days >= 14) & (fin.spend >= MIN_SPEND) & fin.index.isin(ids)]
    d = dl[dl.ad_id.isin(coh)].copy(); d['n'] = d.groupby('ad_id').cumcount() + 1
    v7 = d[d.n <= 7].groupby('ad_id').spend.sum() / 7; later = d[d.n > 7].groupby('ad_id').spend.sum()
    j = pd.concat([v7.rename('v'), later.rename('l')], axis=1).dropna()
    dd = d[d.installs > 0].copy(); dd['cpi'] = dd.spend / dd.installs
    w = [spearmanr(g.spend, g.cpi)[0] for _, g in dd.groupby('ad_id') if len(g) >= 10]
    return {'rho_velocity7_later_spend': fl(spearmanr(j.v, j.l)[0]) if len(j) > 5 else None, 'n': int(len(j)),
            'within_ad_rho_spend_cpi_median': fl(np.nanmedian(w)) if w else None, 'share_positive': fl(np.mean(np.array(w) > 0)) if w else None, 'n_ads': len(w)}

# ---- groups: market x stage ----------------------------------------------------------------------------
results = {'meta': {}, 'groups': {}, 'ads': [], 'campaigns': []}
SP2_PHASES = ['Scalable winner', 'Efficient, unproven scale', 'Watch', 'Pause', 'No installs yet']; OLD_PHASES = ['Phase 2 Winner', 'Phase 1 Winner', 'Mid-Tier', 'Pause']
for mk in ['All'] + MARKETS:
    for st in ['All'] + STAGES:
        bm = np.ones(n, bool) if mk == 'All' else (ads.market.values == mk)
        if st != 'All': bm = bm & (ads.stage.values == st)
        if bm.sum() == 0: continue
        am = bm & analyzed; idx = np.where(am)[0]; g = ads[am]; sp_b = spend[idx]; X = LTVCAC[:, idx]
        sw_full = (LTVCAC[:, bm] * spend[bm]).sum(1) / spend[bm].sum()
        G = {'n_ads': int(bm.sum()), 'n_analyzed': int(am.sum()), 'spend': fl(spend[bm].sum(), 2), 'impressions': fl(imps[bm].sum(), 0), 'installs': fl(inst[bm].sum(), 0),
             'meta_trials': fl(tri[bm].sum(), 0), 'ssot_trials': fl(ads.ssot_trials.values[bm].sum(), 1), 'ssot_ltv': fl(ads.ssot_ltv.values[bm].sum(), 1),
             'ssot_ltv_cac': fl(ads.ssot_ltv.values[bm].sum() / spend[bm].sum()), 'ltv_cac_sw': ql(sw_full), 'paid_est': ql(PAID[:, bm].sum(1), 1),
             'cac': ql(spend[bm].sum() / np.maximum(PAID[:, bm].sum(1), 1), 1), 'ipm': fl(inst[bm].sum() / imps[bm].sum() * 1000), 'cpi': fl(spend[bm].sum() / max(inst[bm].sum(), 1), 2),
             'cpft': fl(spend[bm].sum() / max(tri[bm].sum(), 1), 2), 'share_spend_on_target': fl(((LTVCAC[:, bm] >= TARGET).mean(0) * spend[bm]).sum() / spend[bm].sum()),
             'share_spend_ge1': fl(((LTVCAC[:, bm] >= 1).mean(0) * spend[bm]).sum() / spend[bm].sum()),
             'n_on_target': int(g.on_target.sum()), 'n_ge1': int((g.ltv_cac >= 1).sum()),
             'phase_counts': ads.loc[bm, 'phase'].value_counts().to_dict(), 'sp2_phase_counts': ads.loc[bm, 'sp2_phase'].value_counts().to_dict(),
             'phase_counts_analyzed': g.phase.value_counts().to_dict(), 'sp2_phase_counts_analyzed': g.sp2_phase.value_counts().to_dict(),
             'signals': {}, 'gates': {}, 'agreement': [], 'milestones': milestones(set(ads.ad_id.values[bm]))}
        if st == 'All': G['scale'] = scale_evidence(set(ads.ad_id.values[bm]))
        if len(idx) >= 8:
            pos08 = X >= TARGET; pos1 = X >= 1.0; medx = med[idx]
            for k, label in SIGNALS:
                pt = POINT[k][idx]; D = DRAWS[k][:, idx]; ok = ~np.isnan(pt)
                rho = spearman_rows(X, D); a08 = auc_rows(D, pos08); a1 = auc_rows(D, pos1)
                G['signals'][k] = {'label': label, 'n': int(ok.sum()), 'rho_point': fl(spearmanr(pt[ok], medx[ok])[0]) if ok.sum() > 5 else None,
                                   'rho': ql(rho), 'p_rho_gt0': fl(np.nanmean(rho > 0)), 'rho_hist': np.histogram(rho[~np.isnan(rho)], bins=np.linspace(-1, 1, 41))[0].tolist(),
                                   'auc08_point': fl(roc_auc_score(medx[ok] >= TARGET, pt[ok])) if ok.sum() > 5 and (medx[ok] >= TARGET).min() != (medx[ok] >= TARGET).max() else None,
                                   'auc08': ql(a08), 'auc1_point': fl(roc_auc_score(medx[ok] >= 1, pt[ok])) if ok.sum() > 5 and (medx[ok] >= 1).min() != (medx[ok] >= 1).max() else None, 'auc1': ql(a1)}
            for name, (pm, dm) in GATES.items():
                G['gates'][name] = {**gate_point(pm[idx], g), **gate_draws(dm[:, idx], X, sp_b)}
            for sp2p in SP2_PHASES:
                for oldp in OLD_PHASES:
                    c = g[(g.sp2_phase == sp2p) & (g.phase == oldp)]
                    if len(c): G['agreement'].append({'sp2_phase': sp2p, 'phase': oldp, 'n': int(len(c)), 'spend': fl(c.spend.sum(), 2), 'n_on_target': int(c.on_target.sum()),
                                                      'sw_ltv_cac': fl((c.ltv_cac * c.spend).sum() / c.spend.sum()), 'median_ltv_cac': fl(c.ltv_cac.median())})
        results['groups'][f'{mk}|{st}'] = G
print(f'group statistics done in {time.time() - t0:.0f}s')

# ---- campaigns, per-ad rows, meta --------------------------------------------------------------------
for c, g in ads.groupby('campaign_name'):
    bm = (ads.campaign_name == c).values
    results['campaigns'].append({'campaign': c, 'market': g.market.iloc[0], 'stage': g.stage.iloc[0], 'n_ads': int(bm.sum()), 'spend': fl(spend[bm].sum(), 2),
        'ltv_cac_sw': ql((LTVCAC[:, bm] * spend[bm]).sum(1) / spend[bm].sum()), 'ssot_ltv_cac': fl(ads.ssot_ltv.values[bm].sum() / spend[bm].sum()),
        'installs': fl(inst[bm].sum(), 0), 'cpi': fl(spend[bm].sum() / max(inst[bm].sum(), 1), 2), 'meta_trials': fl(tri[bm].sum(), 0),
        'median_spend_per_day': fl(g.spend_per_day.median(), 2), 'n_sp2_winner': int(g.sp2_winner.sum()), 'n_p1': int(g.p1_point.sum()), 'n_p2': int(g.p2_point.sum()),
        'first_date': str(g.first_date.min()), 'last_date': str(g.last_date.max())})
sq5, sq95 = np.percentile(SP, [5, 95], axis=0); s2q5, s2q95 = np.nanpercentile(SP2_D, [5, 95], axis=0); pq = q(PAID)
cac_arr = np.where(PAID > 0, spend / np.maximum(PAID, 1), np.nan)
P1D = (SP >= SP_THRESHOLD) & inst_ok[None, :]; W2D = (EI_D >= 1) & (SP2_D >= SP2_BAR)
for i, r in ads.iterrows():
    results['ads'].append({
        'ad_id': r.ad_id, 'name': r.clean_name, 'raw_name': r.ad_name, 'c1': r.c1, 'format': r.format if isinstance(r.format, str) else '', 'category': r.category if isinstance(r.category, str) else '',
        'creator': r.creator_name if isinstance(r.creator_name, str) else '', 'preview': r.preview if isinstance(r.preview, str) else '',
        'campaign': r.campaign_name, 'market': r.market, 'stage': r.stage, 'first_date': str(r.first_date), 'last_date': str(r.last_date), 'days': int(r.days),
        'spend': fl(r.spend, 2), 'impressions': int(r.impressions), 'clicks': int(r.clicks), 'installs': int(r.installs), 'signups': int(r.signups), 'trials': int(r.trials),
        'ssot_trials': fl(r.ssot_trials, 1), 'ssot_ltv': fl(r.ssot_ltv, 1), 'ssot_ltv_cac': fl(r.ssot_ltv / r.spend), 'meta_paid_obs': int(r.meta_paid_obs),
        'ipm': fl(r.ipm), 'tpi': fl(r.tpi, 4), 'cpft': fl(r.cpft, 2), 'ctr': fl(r.ctr, 5), 'cpi': fl(r.cpi, 2), 'spend_per_day': fl(r.spend_per_day, 2),
        'sp': fl(r.sp), 'sp_ci': [fl(sq5[i]), fl(sq95[i])], 'phase': r.phase, 'p_p1': fl(P1D[:, i].mean()),
        'EI': fl(r.EI), 'SI': fl(r.SI), 'SP2': fl(r.SP2), 'sp2_ci': [fl(s2q5[i]), fl(s2q95[i])], 'sp2_phase': r.sp2_phase, 'p_sp2_winner': fl(W2D[:, i].mean()),
        'ltv_cac': fl(r.ltv_cac), 'ltv_cac_ci': [fl(r.ltv_cac_lo), fl(r.ltv_cac_hi)], 'p_on_target': fl((LTVCAC[:, i] >= TARGET).mean()), 'p_ge1': fl((LTVCAC[:, i] >= 1).mean()),
        'paid': fl(pq[1][i], 1), 'paid_ci': [fl(pq[0][i], 1), fl(pq[2][i], 1)], 'cac': fl(np.nanmedian(cac_arr[:, i]), 1), 'analyzed': bool(r.analyzed)})
results['meta'] = {
    'window': f"{W0} .. {W1}", 'window_label': PRE['label'], 'analysis': ANALYSIS, 'calibration_window': f"{cal['window']['start']} .. {cal['window']['end']}", 'calibration_note': PRE['note'],
    'k_source': 'trailing window 1 Jun – 7 Oct 2026' if PRE['k_trailing'] else 'analysis window', 'account': 'Meta ad account "Speak ZH" (act 1148917790153640)', 'markets': MARKETS, 'n_sim': N_SIM,
    'ads_total': int(n), 'ads_analyzed': int(analyzed.sum()), 'min_spend_analyzed': MIN_SPEND, 'spend_total': fl(spend.sum(), 2),
    'meta_installs_total': fl(inst.sum(), 0), 'meta_trials_total': fl(tri.sum(), 0), 'target': TARGET, 'sp2_bar': SP2_BAR, 'si_clip': list(SI_CLIP),
    'sp_threshold': SP_THRESHOLD, 'cpft_target': CPFT_TARGET, 'min_installs': MIN_INSTALLS, 'min_trials': MIN_TRIALS,
    'prior_strength': PRIOR_STRENGTH, 'ltv_forecast_sd': LTV_FORECAST_SD, 'p_conv_sd': P_CONV_SD, 'kappa_ctr': KAPPA_CTR, 'kappa_cti': KAPPA_CTI,
    'ssot_spillover': {'n_ad_market_rows': int(len(spill)), 'ltv': fl(spill.ltv.sum(), 1), 'trial_starts': fl(spill.trial_starts.sum(), 1)},
    'market_params': {m: {'K_per_install': fl(K_m[i], 2), 'K_per_install_in_window': fl(K_in_window[i], 2), 'cpi_target': fl(K_m[i] / TARGET, 2), 'p_conv': fl(CAL[m]['p_conv'], 4), 'plan_mix': dict(zip(PLANS, [fl(x) for x in CAL[m]['mix']])),
                          'window_ssot': (cal[PRE['mix_block']][m]['ssot'] if PRE['mix_block'] else cal['markets'][m]['ssot']),
                          'ltv_mu': dict(zip(PLANS, [fl(x, 2) for x in CAL[m]['mu']])), 'ltv_sd': dict(zip(PLANS, [fl(x, 2) for x in CAL[m]['sd']])), 'meta_report_ratio': fl(ratio_m[i]),
                          'ssot_trials': CAL[m]['ssot_trials'], 'ssot_paid': CAL[m]['ssot_paid'], 'ssot_ltv': CAL[m]['ssot_ltv'], 'ssot_installs': CAL[m]['ssot_installs'],
                          'ssot_trials_matched': fl(ads.ssot_trials.values[mi == i].sum(), 1), 'ssot_ltv_matched': fl(ads.ssot_ltv.values[mi == i].sum(), 1),
                          'pool_ipm': fl(pool_ipm_m[m]), 'pool_cpi': fl(spend[mi == i].sum() / max(inst[mi == i].sum(), 1), 2), 'n_ads': int((mi == i).sum()),
                          'spend': fl(spend[mi == i].sum(), 2), 'placements': blocks[i]['placements'], **ssot_fallback[m]} for i, m in enumerate(MARKETS)},
}
os.makedirs('output', exist_ok=True)
json.dump(results, open('output/results.json', 'w'), indent=1)
ads.to_csv('output/ads_scored.csv', index=False)
print(json.dumps(results['meta']['market_params'], indent=1))
for k, G in results['groups'].items():
    if '|All' in k or k.startswith('All|'):
        print(k, G['n_ads'], G['n_analyzed'], round(G['spend']), 'LTV/CAC', G['ltv_cac_sw'], 'on target', G['n_on_target'], '/', G['n_analyzed'])
        for s_, v in G['signals'].items(): print('   ', s_, 'rho', v['rho_point'], v['rho'], 'AUC0.8', v['auc08_point'], v['auc08'])
        for g_, v in G['gates'].items(): print('   ', g_, v['n'], v['spend'], v['sw_ltv_cac'], v['hit_rate'], v['spend_recall'], 'lift', v['lift'])
print(ads.sp2_phase.value_counts().to_dict()); print(ads.phase.value_counts().to_dict()); print(f'done in {time.time() - t0:.0f}s')
