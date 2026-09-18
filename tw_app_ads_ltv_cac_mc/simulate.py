"""
Monte Carlo analysis: LTV/CAC vs creative signals for Speak ZH (Taiwan) iOS app ads,
2026-06-01 .. 2026-09-15.

Inputs (data/):
  ad_placement.csv  Meta ad x placement funnel (BigQuery analytics.meta_ads_creative_report_funnel)
  ads_meta.csv      Meta ad attributes (name, format, category, first/last date)
  af_ads.csv        AppsFlyer SSOT per-ad installs / trial starts by plan (analytics.marketing_ssot_aggregate)

Calibration constants come from BigQuery queries documented in queries.sql.
Output: output/results.json consumed by report/index.html
"""
import json, re, numpy as np, pandas as pd
from scipy.stats import rankdata

rng = np.random.default_rng(20260918)
N_SIM = 10000
N_SIM_REF = 4000            # first N_SIM_REF draws are re-summarised to show Monte Carlo stability
SP_THRESHOLD, CPFT_TARGET, MIN_TRIALS, MIN_INSTALLS = 2.0, 55.0, 10, 10
MIN_SPEND_ANALYZED = 100.0
PRIOR_STRENGTH = 20.0          # Gamma prior on per-ad conversion multiplier (mean 1, CV ~22%)
LTV_FORECAST_SD = 0.05         # global LTV forecast error (realized vs forecast for Mar-May cohorts ~ +/-10%)

# ---- calibration (Taiwan, Meta iOS, window) ----------------------------------------
# Official SSOT (analytics.marketing_attribution_aggregate_attribution_date_cohort, country=Taiwan, platform=ios,
# channel='Meta Ads', attribution_date in window): 9,224 trial starts -> 3,580.6 modeled paid -> $368.5K LTV
SSOT_TRIALS_TOTAL, SSOT_PAID_TOTAL, SSOT_LTV_TOTAL = 9224.0, 3580.6, 368542.0
P_CONV_MEAN = SSOT_PAID_TOTAL / SSOT_TRIALS_TOTAL          # 0.388 modeled trial->paid
P_CONV_SD = 0.03                                            # uncertainty on that level (user-level view implies ~0.31)
AF_TRIALS_TYPED = {'annual_reg': 9747, 'annual_plus': 1775, 'monthly': 638}   # AppsFlyer trial starts by plan (plan mix)
# LTV per paid user (analytics.user_ltv, 36-month) for Meta-iOS-attributed Taiwan users paying in window
LTV_MU = {'annual_reg': 93.47, 'annual_plus': 163.36, 'monthly': (250 * 54.51 + 59 * 88.80) / 309}
LTV_SD = {'annual_reg': 6.0, 'annual_plus': 25.0, 'monthly': 20.0}
PLANS = list(AF_TRIALS_TYPED)

def bucket(c):
    c = c.lower()
    if 'testing' in c: return 'Testing'
    if 'winning' in c: return 'Winning'
    if 'scaling' in c: return 'Scaling'
    return 'Other'

def clean_name(name):
    m = re.findall(r'c(\d+)[:\!]([^_c\s][^_]*?)(?=_c\d+[:\!]|$)', str(name).replace('__', '_'))
    if m:
        d = {int(k): v.strip('_').strip() for k, v in m}
        c3, c6, c7 = d.get(3, ''), d.get(6, ''), d.get(7, '')
        if c3 or c6 or c7:
            return f"{c3} – {c6} – {c7}".strip(' –')
    return str(name)[:80]

def extract_c1(name):
    m = re.search(r'c1[:\!](\w+)', str(name), re.IGNORECASE)
    return m.group(1) if m else 'Untagged'

# ---- load ---------------------------------------------------------------------------
pl = pd.read_csv('data/ad_placement.csv', dtype={'ad_id': str})
meta = pd.read_csv('data/ads_meta.csv', dtype={'ad_id': str})
af = pd.read_csv('data/af_ads.csv', dtype={'af_ad_id': str})
ssot = pd.read_csv('data/ssot_ads.csv', dtype={'ad_id': str})
for c in ssot.columns[2:]:
    ssot[c] = pd.to_numeric(ssot[c]).fillna(0)
for c in af.columns[3:]:
    af[c] = pd.to_numeric(af[c]).fillna(0)
num = ['spend', 'impressions', 'clicks', 'installs', 'trials', 'adj_trials', 'init_purch', 'trial_converts']
pl[num] = pl[num].fillna(0)

ads = pl.groupby('ad_id').agg(**{c: (c, 'sum') for c in num}, campaign_name=('campaign_name', 'first')).reset_index()
ads = ads.merge(meta[['ad_id', 'ad_name', 'format', 'category', 'concept', 'creator_name', 'first_date', 'last_date', 'active_days']], on='ad_id', how='left')
ads['bucket'] = ads.campaign_name.map(bucket)
ads['ad_name'] = ads.ad_name.fillna('ad ' + ads.ad_id)
ads['clean_name'] = ads.ad_name.map(clean_name)
ads['c1'] = ads.ad_name.map(extract_c1)
ads = ads[ads.spend > 0].reset_index(drop=True)
ads['ipm'] = ads.installs / ads.impressions * 1000
ads['tpi'] = ads.trials / ads.impressions * 1000
ads['cpft'] = np.where(ads.trials > 0, ads.spend / ads.trials, np.nan)
ads['ctr'] = ads.clicks / ads.impressions
ads['meta_paid_obs'] = ads.init_purch + ads.trial_converts

# ---- trial base per ad (SSOT), plan mix per ad (AppsFlyer) -----------------------------
ads = ads.merge(ssot[['ad_id', 'trial_starts', 'paid', 'ltv']].rename(columns={'trial_starts': 'ssot_trials', 'paid': 'ssot_paid', 'ltv': 'ssot_ltv'}), on='ad_id', how='left')
has_ssot = ads.ssot_trials.notna()
ratio_ssot_adj = ads.loc[has_ssot, 'ssot_trials'].sum() / ads.loc[has_ssot, 'adj_trials'].sum()
ads.loc[~has_ssot, 'ssot_trials'] = ads.loc[~has_ssot, 'adj_trials'] * ratio_ssot_adj   # 4 tiny ads w/o SSOT row
ads[['ssot_paid', 'ssot_ltv']] = ads[['ssot_paid', 'ssot_ltv']].fillna(0)
af_cols = ['af_installs', 'af_trials', 'af_trials_annual_reg', 'af_trials_annual_plus', 'af_trials_monthly']
ads = ads.merge(af[['af_ad_id'] + af_cols], left_on='ad_id', right_on='af_ad_id', how='left').drop(columns='af_ad_id')
ads[af_cols] = ads[af_cols].fillna(0)
global_mix = np.array([AF_TRIALS_TYPED[k] for k in PLANS], float); global_mix /= global_mix.sum()
typed = ads[['af_trials_annual_reg', 'af_trials_annual_plus', 'af_trials_monthly']].values.astype(float)
typed_sum = typed.sum(1, keepdims=True)
# shrink each ad's plan mix toward the global mix (pseudo-count 10 trials)
mix = (typed + 10 * global_mix) / (typed_sum + 10)
trials_by_plan = ads.ssot_trials.values[:, None] * mix                          # (n_ads, 3)

k_conv = P_CONV_MEAN * (1 - P_CONV_MEAN) / P_CONV_SD ** 2 - 1
conv_a, conv_b = P_CONV_MEAN * k_conv, (1 - P_CONV_MEAN) * k_conv
expected_paid = trials_by_plan.sum(1) * P_CONV_MEAN
meta_report_ratio = ads.meta_paid_obs.sum() / expected_paid.sum()               # Meta-observed / modeled paid (SKAN under-reporting)
E_meta = expected_paid * meta_report_ratio
mu = np.array([LTV_MU[k] for k in PLANS]); sd = np.array([LTV_SD[k] for k in PLANS])

# ---- SP score (Option B) on Meta ad x placement ----------------------------------------
pl = pl[pl.ad_id.isin(ads.ad_id)].copy()
ad_idx = {a: i for i, a in enumerate(ads.ad_id)}
plc = sorted(pl.placement.unique()); pl_idx = {p: j for j, p in enumerate(plc)}
n, m = len(ads), len(plc)
S = np.zeros((n, m)); I = np.zeros((n, m)); C = np.zeros((n, m)); T = np.zeros((n, m))
for r in pl.itertuples():
    i, j = ad_idx[r.ad_id], pl_idx[r.placement]
    S[i, j] += r.spend; I[i, j] += r.impressions; C[i, j] += r.clicks; T[i, j] += r.trials
w = S / np.where(S.sum(1, keepdims=True) > 0, S.sum(1, keepdims=True), 1)
tot_I, tot_C, tot_T = I.sum(0), C.sum(0), T.sum(0)
bench_ctr = np.where((tot_I - I) > 0, (tot_C - C) / np.where((tot_I - I) > 0, tot_I - I, 1), 0)
bench_cti = np.where((tot_C - C) > 0, (tot_T - T) / np.where((tot_C - C) > 0, tot_C - C, 1), 0)
ctr = np.where(I > 0, C / np.where(I > 0, I, 1), 0); cti = np.where(C > 0, T / np.where(C > 0, C, 1), 0)
def sp_from(ctr_, cti_):
    r1 = np.where(bench_ctr > 0, ctr_ / np.where(bench_ctr > 0, bench_ctr, 1), 0)
    r2 = np.where(bench_cti > 0, cti_ / np.where(bench_cti > 0, bench_cti, 1), 0)
    return (w * (r1 + r2)).sum(1)
ads['sp'] = sp_from(ctr, cti)
def phase(row):
    if row.sp >= SP_THRESHOLD:
        if row.trials >= MIN_TRIALS and row.cpft <= CPFT_TARGET: return 'Phase 2 Winner'
        if row.installs >= MIN_INSTALLS: return 'Phase 1 Winner'
    if 1.4 <= row.sp < SP_THRESHOLD: return 'Mid-Tier'
    return 'Pause'
ads['phase'] = ads.apply(phase, axis=1)
ads['p1_point'] = (ads.sp >= SP_THRESHOLD) & (ads.installs >= MIN_INSTALLS)
ads['p2_point'] = (ads.sp >= SP_THRESHOLD) & (ads.trials >= MIN_TRIALS) & (ads.cpft <= CPFT_TARGET)

# ---- Monte Carlo ---------------------------------------------------------------------
spend = ads.spend.values; imps = ads.impressions.values; inst = ads.installs.values; tri = ads.trials.values
obs = ads.meta_paid_obs.values
LTVCAC = np.zeros((N_SIM, n)); PAID = np.zeros((N_SIM, n)); SP = np.zeros((N_SIM, n))
IPM = np.zeros((N_SIM, n)); TPI = np.zeros((N_SIM, n))
mask_I = I > 0; mask_C = C > 0
for s in range(N_SIM):
    p_k = rng.beta(conv_a, conv_b)
    theta = rng.gamma(PRIOR_STRENGTH + obs, 1.0 / (PRIOR_STRENGTH + E_meta))
    theta *= E_meta.sum() / (E_meta * theta).sum()      # Meta evidence re-allocates paid across ads; level stays at SSOT
    lam = trials_by_plan * p_k * theta[:, None]
    paid_k = rng.poisson(lam)
    ltv_mult = rng.normal(1.0, LTV_FORECAST_SD)
    ltv = (paid_k * mu + np.sqrt(paid_k) * sd * rng.standard_normal(paid_k.shape)).sum(1) * ltv_mult
    PAID[s] = paid_k.sum(1); LTVCAC[s] = ltv / spend
    ctr_s = np.where(mask_I, rng.beta(C + 0.5, np.maximum(I - C, 0) + 0.5), 0)
    cti_s = np.where(mask_C, rng.beta(T + 0.5, np.maximum(C - T, 0) + 0.5), 0)
    SP[s] = sp_from(ctr_s, cti_s)
    IPM[s] = rng.beta(inst + 0.5, np.maximum(imps - inst, 0) + 0.5) * 1000
    TPI[s] = rng.beta(tri + 0.5, np.maximum(imps - tri, 0) + 0.5) * 1000
P1 = (SP >= SP_THRESHOLD) & (inst >= MIN_INSTALLS)[None, :]
P2 = (SP >= SP_THRESHOLD) & ((tri >= MIN_TRIALS) & (np.nan_to_num(ads.cpft.values, nan=1e9) <= CPFT_TARGET))[None, :]

def q(a, qs=(5, 50, 95)): return np.nanpercentile(a, qs, axis=0)
def spearman_rows(X, Y):
    rx = np.apply_along_axis(rankdata, 1, X); ry = np.apply_along_axis(rankdata, 1, Y)
    rx -= rx.mean(1, keepdims=True); ry -= ry.mean(1, keepdims=True)
    return (rx * ry).sum(1) / np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))

analyzed = spend >= MIN_SPEND_ANALYZED
buckets = {'Overall': np.ones(n, bool), 'Testing': ads.bucket.values == 'Testing',
           'Winning': ads.bucket.values == 'Winning', 'Scaling': ads.bucket.values == 'Scaling'}
results = {'meta': {
    'window': '2026-06-01 .. 2026-09-15', 'market': 'Taiwan (Speak ZH ad account), iOS app campaigns', 'n_sim': N_SIM,
    'ads_total': int(n), 'ads_analyzed': int(analyzed.sum()), 'min_spend_analyzed': MIN_SPEND_ANALYZED,
    'spend_total': float(spend.sum()), 'meta_trials_total': float(tri.sum()), 'meta_installs_total': float(inst.sum()),
    'ssot_trials_total': SSOT_TRIALS_TOTAL, 'ssot_paid_total': SSOT_PAID_TOTAL, 'ssot_ltv_total': SSOT_LTV_TOTAL,
    'ssot_trials_matched': float(ads.ssot_trials.sum()), 'ssot_ltv_matched': float(ads.ssot_ltv.sum()),
    'p_conv_mean': P_CONV_MEAN, 'p_conv_sd': P_CONV_SD, 'ltv_mu': {k: float(LTV_MU[k]) for k in PLANS}, 'plan_mix': {k: float(v) for k, v in zip(PLANS, global_mix)},
    'meta_report_ratio': float(meta_report_ratio), 'sp_threshold': SP_THRESHOLD, 'cpft_target': CPFT_TARGET,
    'prior_strength': PRIOR_STRENGTH, 'ltv_forecast_sd': LTV_FORECAST_SD,
}, 'buckets': {}, 'ads': [], 'campaigns': []}

for b, bm in buckets.items():
    am = bm & analyzed
    idx = np.where(am)[0]
    X = LTVCAC[:, idx]
    rho_sp = spearman_rows(X, SP[:, idx]); rho_ipm = spearman_rows(X, IPM[:, idx]); rho_tpi = spearman_rows(X, TPI[:, idx])
    def winner_stats(W):
        Wb = W[:, idx]; sp_b = spend[idx]
        med_w = np.array([np.median(X[s, Wb[s]]) if Wb[s].any() else np.nan for s in range(N_SIM)])
        med_n = np.array([np.median(X[s, ~Wb[s]]) if (~Wb[s]).any() else np.nan for s in range(N_SIM)])
        sw_w = np.array([(X[s, Wb[s]] * sp_b[Wb[s]]).sum() / sp_b[Wb[s]].sum() if Wb[s].any() else np.nan for s in range(N_SIM)])
        sw_n = np.array([(X[s, ~Wb[s]] * sp_b[~Wb[s]]).sum() / sp_b[~Wb[s]].sum() if (~Wb[s]).any() else np.nan for s in range(N_SIM)])
        lift = sw_w / sw_n
        return {'median_winner': q(med_w).tolist(), 'median_non': q(med_n).tolist(),
                'sw_winner': q(sw_w).tolist(), 'sw_non': q(sw_n).tolist(), 'lift': q(lift).tolist(),
                'p_lift_gt1': float(np.nanmean(lift > 1)), 'n_winner_mean': float(Wb.sum(1).mean()), 'n_non_mean': float((~Wb).sum(1).mean()),
                'n_winner_point': int(Wb.mean(0).round().sum())}
    sw_all = (X * spend[idx]).sum(1) / spend[idx].sum()
    full = LTVCAC[:, bm]; sw_full = (full * spend[bm]).sum(1) / spend[bm].sum()
    results['buckets'][b] = {
        'n_ads': int(bm.sum()), 'n_analyzed': int(am.sum()), 'spend': float(spend[bm].sum()),
        'impressions': float(imps[bm].sum()), 'installs': float(inst[bm].sum()), 'meta_trials': float(tri[bm].sum()),
        'ssot_trials': float(ads.ssot_trials.values[bm].sum()), 'ssot_ltv_cac': float(ads.ssot_ltv.values[bm].sum() / spend[bm].sum()), 'paid_est': q(PAID[:, bm].sum(1)).tolist(),
        'ltv_cac_sw': q(sw_full).tolist(), 'cac': q(spend[bm].sum() / PAID[:, bm].sum(1)).tolist(),
        'ipm': float(inst[bm].sum() / imps[bm].sum() * 1000), 'tpi': float(tri[bm].sum() / imps[bm].sum() * 1000),
        'cpft': float(spend[bm].sum() / max(tri[bm].sum(), 1)),
        'share_spend_ltvcac_ge1': float(((LTVCAC[:, bm] >= 1).mean(0) * spend[bm]).sum() / spend[bm].sum()),
        'rho_sp': q(rho_sp).tolist(), 'p_rho_sp_gt0': float((rho_sp > 0).mean()),
        'rho_ipm': q(rho_ipm).tolist(), 'p_rho_ipm_gt0': float((rho_ipm > 0).mean()),
        'rho_tpi': q(rho_tpi).tolist(), 'p_rho_tpi_gt0': float((rho_tpi > 0).mean()),
        'p1': winner_stats(P1), 'p2': winner_stats(P2),
        'phase_counts': ads.loc[bm, 'phase'].value_counts().to_dict(),
        'rho_sp_hist': np.histogram(rho_sp, bins=np.linspace(-1, 1, 41))[0].tolist(),
        'rho_ipm_hist': np.histogram(rho_ipm, bins=np.linspace(-1, 1, 41))[0].tolist(),
        'rho_tpi_hist': np.histogram(rho_tpi, bins=np.linspace(-1, 1, 41))[0].tolist(),
    }


# ---- gate analysis: does the SP >= 2 bar (P1 gate) predict LTV/CAC? ----------------------
THRESHOLDS = [round(1.0 + 0.25 * i, 2) for i in range(13)]            # 1.0 .. 4.0
pool_tpi = tri.sum() / imps.sum() * 1000; pool_ipm = inst.sum() / imps.sum() * 1000
cpft_arr = np.nan_to_num(ads.cpft.values, nan=1e9)
def gate_stats(G, X, sp_b, nsim):
    """G, X: (nsim, n_idx) bool / float. Returns dict of median + 5/95 summaries."""
    pos = X >= 1.0
    sw_in = np.array([(X[s, G[s]] * sp_b[G[s]]).sum() / sp_b[G[s]].sum() if G[s].any() else np.nan for s in range(nsim)])
    sw_out = np.array([(X[s, ~G[s]] * sp_b[~G[s]]).sum() / sp_b[~G[s]].sum() if (~G[s]).any() else np.nan for s in range(nsim)])
    with np.errstate(divide='ignore', invalid='ignore'):
        lift = sw_in / sw_out
        prec = np.array([pos[s, G[s]].mean() if G[s].any() else np.nan for s in range(nsim)])
        prec_out = np.array([pos[s, ~G[s]].mean() if (~G[s]).any() else np.nan for s in range(nsim)])
        spend_pos = (pos * sp_b).sum(1)
        recall = np.where(spend_pos > 0, ((pos & G) * sp_b).sum(1) / np.where(spend_pos > 0, spend_pos, 1), np.nan)
        spend_share = (G * sp_b).sum(1) / sp_b.sum()
    return {'lift': q(lift).tolist(), 'p_lift_gt1': float(np.nanmean(lift > 1)), 'sw_in': q(sw_in).tolist(), 'sw_out': q(sw_out).tolist(),
            'hit_rate_in': q(prec).tolist(), 'hit_rate_out': q(prec_out).tolist(), 'spend_recall': q(recall).tolist(),
            'spend_share': q(spend_share).tolist(), 'n_in_mean': float(G.sum(1).mean()), 'n_in_point': int(round(G.mean(0).sum()))}
def auc_rows(score, X, nsim):
    pos = X >= 1.0; out = np.full(nsim, np.nan)
    for s in range(nsim):
        p = pos[s]; npos, nneg = p.sum(), (~p).sum()
        if npos == 0 or nneg == 0: continue
        r = rankdata(score[s]); out[s] = (r[p].sum() - npos * (npos + 1) / 2) / (npos * nneg)
    return out
results['gates'] = {}
for b, bm in buckets.items():
    idx = np.where(bm & analyzed)[0]; X = LTVCAC[:, idx]; sp_b = spend[idx]
    SPb, IPMb, TPIb = SP[:, idx], IPM[:, idx], TPI[:, idx]
    inst_ok = (inst[idx] >= MIN_INSTALLS)[None, :]; tri_ok = (tri[idx] >= MIN_TRIALS)[None, :]; cp_ok = (cpft_arr[idx] <= CPFT_TARGET)[None, :]
    g = {}
    g['sweep'] = [{'t': t, **gate_stats((SPb >= t) & inst_ok, X, sp_b, N_SIM)} for t in THRESHOLDS]
    g['gates'] = {
        'P1 gate (SP ≥ 2 & ≥10 installs)': gate_stats((SPb >= 2) & inst_ok, X, sp_b, N_SIM),
        'SP ≥ 2 alone': gate_stats(SPb >= 2, X, sp_b, N_SIM),
        '≥ 10 installs alone': gate_stats(np.broadcast_to(inst_ok, X.shape), X, sp_b, N_SIM),
        'CPFT ≤ $55 & ≥10 trials': gate_stats(np.broadcast_to(tri_ok & cp_ok, X.shape), X, sp_b, N_SIM),
        'P2 gate (P1 & CPFT ≤ $55)': gate_stats((SPb >= 2) & tri_ok & cp_ok, X, sp_b, N_SIM),
        'TPI ≥ pool average': gate_stats((TPIb >= pool_tpi) & inst_ok, X, sp_b, N_SIM),
        'IPM ≥ pool average': gate_stats((IPMb >= pool_ipm) & inst_ok, X, sp_b, N_SIM),
    }
    g['quad'] = {
        'SP ≥ 2, ≥10 installs': gate_stats((SPb >= 2) & inst_ok, X, sp_b, N_SIM),
        'SP ≥ 2, <10 installs': gate_stats((SPb >= 2) & ~inst_ok, X, sp_b, N_SIM),
        'SP < 2, ≥10 installs': gate_stats((SPb < 2) & inst_ok, X, sp_b, N_SIM),
        'SP < 2, <10 installs': gate_stats((SPb < 2) & ~inst_ok, X, sp_b, N_SIM),
    }
    g['auc'] = {'SP score': q(auc_rows(SPb, X, N_SIM)).tolist(), 'IPM': q(auc_rows(IPMb, X, N_SIM)).tolist(),
                'Trial per impression': q(auc_rows(TPIb, X, N_SIM)).tolist(), 'CPFT (lower is better)': q(auc_rows(-np.broadcast_to(cpft_arr[idx], X.shape), X, N_SIM)).tolist()}
    # among P1 winners only: does a higher SP still track LTV/CAC?
    rin = np.full(N_SIM, np.nan)
    for s_ in range(N_SIM):
        Gs = (SPb[s_] >= 2) & inst_ok[0]
        if Gs.sum() >= 8:
            rx, ry = rankdata(SPb[s_, Gs]), rankdata(X[s_, Gs]); rx -= rx.mean(); ry -= ry.mean()
            d = np.sqrt((rx ** 2).sum() * (ry ** 2).sum()); rin[s_] = (rx * ry).sum() / d if d > 0 else np.nan
    g['rho_sp_within_p1'] = q(rin).tolist() if np.isfinite(rin).any() else [None, None, None]
    g['p_rho_within_gt0'] = float(np.nanmean(rin > 0)) if np.isfinite(rin).any() else None
    g['pool_tpi'] = float(pool_tpi); g['pool_ipm'] = float(pool_ipm)
    results['gates'][b] = g

# ---- Monte Carlo stability: first N_SIM_REF draws vs all ------------------------------------
stab = {}
for b, bm in buckets.items():
    idx = np.where(bm & analyzed)[0]; row = {}
    for label, ns in (('ref', N_SIM_REF), ('full', N_SIM)):
        X = LTVCAC[:ns, idx]; sw = (LTVCAC[:ns, bm] * spend[bm]).sum(1) / spend[bm].sum()
        G = (SP[:ns, idx] >= 2) & (inst[idx] >= MIN_INSTALLS)[None, :]
        gs = gate_stats(G, X, spend[idx], ns)
        row[label] = {'n_sim': ns, 'ltv_cac_sw': q(sw).tolist(), 'rho_sp': q(spearman_rows(X, SP[:ns, idx])).tolist(),
                      'rho_ipm': q(spearman_rows(X, IPM[:ns, idx])).tolist(), 'rho_tpi': q(spearman_rows(X, TPI[:ns, idx])).tolist(), 'p1_lift': gs['lift']}
    stab[b] = row
results['stability'] = stab

for c, g in ads.groupby('campaign_name'):
    bm = (ads.campaign_name == c).values
    results['campaigns'].append({'campaign': c, 'bucket': bucket(c), 'n_ads': int(bm.sum()), 'spend': float(spend[bm].sum()),
        'ltv_cac_sw': q((LTVCAC[:, bm] * spend[bm]).sum(1) / spend[bm].sum()).tolist(), 'ssot_ltv_cac': float(ads.ssot_ltv.values[bm].sum() / spend[bm].sum()),
        'paid_est': q(PAID[:, bm].sum(1)).tolist(), 'installs': float(inst[bm].sum()), 'meta_trials': float(tri[bm].sum())})

lq, lmed, lhq = q(LTVCAC); sq, smed, shq = q(SP); pq = q(PAID)
cac_arr = np.where(PAID > 0, spend / np.maximum(PAID, 1), np.nan)
for i, r in ads.iterrows():
    results['ads'].append({
        'ad_id': r.ad_id, 'name': r.clean_name, 'raw_name': r.ad_name, 'c1': r.c1, 'format': r.format if isinstance(r.format, str) else '',
        'category': r.category if isinstance(r.category, str) else '', 'campaign': r.campaign_name, 'bucket': r.bucket,
        'spend': round(float(r.spend), 2), 'impressions': int(r.impressions), 'clicks': int(r.clicks), 'installs': int(r.installs),
        'trials': int(r.trials), 'adj_trials': round(float(r.adj_trials), 1), 'ssot_trials': round(float(r.ssot_trials), 1), 'ssot_ltv_cac': round(float(r.ssot_ltv / r.spend), 3), 'meta_paid_obs': int(r.meta_paid_obs),
        'ipm': round(float(r.ipm), 3), 'tpi': round(float(r.tpi), 4), 'cpft': None if np.isnan(r.cpft) else round(float(r.cpft), 2),
        'ctr': round(float(r.ctr), 5), 'sp': round(float(r.sp), 3), 'sp_ci': [round(float(sq[i]), 3), round(float(shq[i]), 3)],
        'phase': r.phase, 'p_sp_ge2': round(float((SP[:, i] >= 2).mean()), 3), 'p_p1': round(float(P1[:, i].mean()), 3), 'p_p2': round(float(P2[:, i].mean()), 3),
        'ltv_cac': round(float(lmed[i]), 3), 'ltv_cac_ci': [round(float(lq[i]), 3), round(float(lhq[i]), 3)],
        'p_ltv_cac_ge1': round(float((LTVCAC[:, i] >= 1).mean()), 3),
        'paid': round(float(pq[1][i]), 1), 'paid_ci': [round(float(pq[0][i]), 1), round(float(pq[2][i]), 1)],
        'cac': None if np.isnan(np.nanmedian(cac_arr[:, i])) else round(float(np.nanmedian(cac_arr[:, i])), 1),
        'analyzed': bool(analyzed[i]), 'first_date': r.first_date, 'last_date': r.last_date, 'active_days': int(r.active_days) if not np.isnan(r.active_days) else 0,
    })
json.dump(results, open('output/results.json', 'w'), indent=1)
ads.to_csv('output/ads_scored.csv', index=False)
print(json.dumps(results['meta'], indent=1))
for b, v in results['buckets'].items():
    print(b, v['n_ads'], v['n_analyzed'], round(v['spend']), 'LTV/CAC sw', [round(x, 2) for x in v['ltv_cac_sw']], 'CAC', [round(x) for x in v['cac']], 'paid', [round(x) for x in v['paid_est']])
    print('  rho sp', [round(x, 2) for x in v['rho_sp']], 'ipm', [round(x, 2) for x in v['rho_ipm']], 'tpi', [round(x, 2) for x in v['rho_tpi']])
    print('  P1 lift', [round(x, 2) for x in v['p1']['lift']], v['p1']['p_lift_gt1'], 'n', v['p1']['n_winner_point'], '| P2 lift', [round(x, 2) for x in v['p2']['lift']], v['p2']['p_lift_gt1'], 'n', v['p2']['n_winner_point'])
    print('  phases', v['phase_counts'])
print(ads.phase.value_counts())
