"""
Daily check-in simulation: every TW iOS Meta ad in the testing / winning / scaling campaigns, Jun 1 - Sep 29 2026,
re-scored on each day it delivered with its cumulative-to-date data, against three gates:

  SP   pass: SP (Option B, cumulative-to-date, benchmark = same group's placements to date) >= 2.0 and >= 10 installs
  CTI  pass: installs / link clicks >= 1% and >= 300 link clicks
  SP2  pass: EI >= 1 and EI x SI >= 2 and >= 10 installs
       EI = (K / CPI) / 0.8, K = $12.26 SSOT LTV per Meta install (tw_app_ads_ltv_cac_mc/sp2.py) -> CPI target $15.32
       SI = spend per active day / median of live ads in the same group that day, clipped [0.25, 4]
  Before the minimum data is reached the gate is 'pending'.

Ground truth (known at Sep 29): Winner = lifetime LTV/CAC >= 0.85 AND lifetime spend >= $1k (testing) / $5k (winning, scaling).
Ads still inside their first 14 days on Sep 29 are 'too new' and left out of the scoring (still animated).

Policy replay: pause an ad at its first check-in where the gate reads 'fail' (optionally only after 3 consecutive fails)
-> spend saved on non-winners vs winners that would have been killed (and the spend they went on to earn).

Inputs:  ../data/ad_daily_cum.txt (BigQuery), ../data/meta_ad_link_clicks.tsv (Meta Ads MCP)
Outputs: sim_results.json, sim_ads.json (per ad per day, consumed by the motion graphic), sim_summary.csv
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
K_LTV, TARGET = 12.255086110766943, 0.8
CPI_TARGET = K_LTV / TARGET
SP_BAR, CTI_BAR, SP2_BAR = 2.0, 0.01, 2.0
MIN_INST, MIN_LINK = 10, 300
WIN_LTVCAC = 0.85                                   # winner: lifetime LTV/CAC >= 0.85 ...
WIN_SPEND = {'T': 1000.0, 'W': 5000.0, 'S': 5000.0}  # ... and lifetime spend >= $1k (testing) / $5k (winning, scaling)
END, NEW_DAYS = date(2026, 9, 29), 14
BASE = date(2026, 1, 1)
GROUPS = {'T': 'Testing', 'W': 'Winning', 'S': 'Scaling'}

# ---- load ----
rows = []
for line in (HERE.parent / 'data/ad_daily_cum.txt').read_text().split('\n'):
    parts = line.split('|')
    g, ad_id, key, d0, days = parts[0], parts[1], '|'.join(parts[2:-2]), parts[-2], parts[-1]
    for d in days.split(';'):
        off, s, cs, ci, cc, cn, ct, cd, sp = d.split(':')
        rows.append((g, ad_id, key, d0, int(off), float(s), float(cs), int(ci), int(cc), int(cn), int(ct), int(cd), float(sp)))
df = pd.DataFrame(rows, columns=['g', 'ad_id', 'key', 'first_date', 'off', 'spend', 'cum_spend', 'cum_impr', 'cum_clicks',
                                 'cum_installs', 'cum_trials', 'active_days', 'sp'])
lc = pd.read_csv(HERE.parent / 'data/meta_ad_link_clicks.tsv', sep='\t', dtype={'ad_id': str})
share = (lc.link_clicks / lc.clicks_all.replace(0, np.nan)).clip(upper=1.05)
share = dict(zip(lc.ad_id, share))
df['link_share'] = df.ad_id.map(share)
df['link_share'] = df.link_share.fillna(df.groupby('g').link_share.transform('median'))

# ---- daily metrics ----
df['cum_link'] = df.cum_clicks * df.link_share
df['cti'] = np.where(df.cum_link > 0, df.cum_installs / df.cum_link, np.nan)
df['cpi'] = np.where(df.cum_installs > 0, df.cum_spend / df.cum_installs, np.nan)
df['ei'] = (K_LTV / df.cpi) / TARGET
df['spd'] = df.cum_spend / df.active_days
df['si'] = (df.spd / df.groupby(['g', 'off']).spd.transform('median')).clip(0.25, 4)
df['sp2'] = df.ei * df.si
df['cpft'] = np.where(df.cum_trials > 0, df.cum_spend / df.cum_trials, np.nan)

# ---- LTV/CAC to date: SSOT modelled LTV by attribution date, scaled up by the group-month share lost to 'No Ad ID' ----
cov = {(g, m): float(f) for g, m, f in (x.split('|') for x in (HERE.parent / 'data/ssot_ltv_coverage.txt').read_text().split(';'))}
lt = []
for line in (HERE.parent / 'data/ssot_ad_daily_ltv.txt').read_text().split('\n'):
    g, ad_id, days = line.split('|')
    for d in days.split(';'):
        off, v, _ = d.split(':')
        m = (BASE + timedelta(int(off))).strftime('%Y-%m')
        lt.append((g, ad_id, int(off), float(v) * cov.get((g, m), 1.2)))
lt = pd.DataFrame(lt, columns=['g', 'ad_id', 'off', 'ltv']).sort_values('off')
lt['cum_ltv'] = lt.groupby(['g', 'ad_id']).ltv.cumsum()
df = df.sort_values('off')
df = pd.merge_asof(df, lt[['g', 'ad_id', 'off', 'cum_ltv']], on='off', by=['g', 'ad_id'], direction='backward')
df['cum_ltv'] = df.cum_ltv.fillna(0.0)
df['ltv_cac'] = df.cum_ltv / df.cum_spend
LTVCAC_TARGET = WIN_LTVCAC


def state(ok, enough):
    return np.where(~enough, 'pending', np.where(ok, 'pass', 'fail'))


df['st_sp'] = state(df.sp >= SP_BAR, df.cum_installs >= MIN_INST)
df['st_cti'] = state(df.cti >= CTI_BAR, df.cum_link >= MIN_LINK)
df['st_sp2'] = state((df.ei >= 1) & (df.sp2 >= SP2_BAR), df.cum_installs >= MIN_INST)
df = df.sort_values(['g', 'ad_id', 'off']).reset_index(drop=True)
df['n'] = df.active_days  # check-in number = lifetime active day # (ads live before Jun 1 start mid-life)

# ---- per-ad outcome ----
last = df.groupby(['g', 'ad_id']).tail(1).set_index(['g', 'ad_id'])
ads = last[['key', 'first_date', 'cum_spend', 'cum_trials', 'cum_installs', 'cpft', 'active_days', 'cum_ltv', 'ltv_cac']].copy()
ads['last_date'] = [BASE + timedelta(int(o)) for o in last.off]
ads['first_date'] = pd.to_datetime(ads.first_date).dt.date
ads['winner'] = (ads.ltv_cac >= WIN_LTVCAC) & (ads.cum_spend >= [WIN_SPEND[g] for g in ads.index.get_level_values('g')])
ads['too_new'] = [(END - fd).days < NEW_DAYS for fd in ads.first_date]
ads['scored'] = ~ads.too_new
ad_keys = ads.index

GATES = {'sp': 'SP', 'cti': 'CTI', 'sp2': 'SP2'}


def first_where(mask):
    m = df[mask].groupby(['g', 'ad_id']).head(1).set_index(['g', 'ad_id'])
    return m


def consec_fail(col, k):
    f = (df[col] == 'fail').astype(int)
    run = f.groupby([df.g, df.ad_id, (f != f.shift()).cumsum()]).cumsum()
    return (run >= k) & (df[col] == 'fail')


results = {'params': dict(sp_bar=SP_BAR, cti_bar=CTI_BAR, sp2_bar=SP2_BAR, min_installs=MIN_INST, min_link_clicks=MIN_LINK,
                          k_ltv_per_install=K_LTV, cpi_target=CPI_TARGET, winner=f'lifetime LTV/CAC>={WIN_LTVCAC} & spend>=$1k (testing) / $5k (winning, scaling)',
                          too_new_days=NEW_DAYS, window='2026-06-01..2026-09-29'),
           'groups': {}}
summary = []
for g, gname in list(GROUPS.items()) + [('ALL', 'All')]:
    A = ads[ads.scored] if g == 'ALL' else ads[ads.scored & (ads.index.get_level_values('g') == g)]
    blk = dict(n_ads=int(len(A)), n_winners=int(A.winner.sum()), spend=float(A.cum_spend.sum()),
               winner_spend=float(A[A.winner].cum_spend.sum()), gates={})
    for c, gl in GATES.items():
        col = f'st_{c}'
        D = df[df.set_index(['g', 'ad_id']).index.isin(A.index)]
        fin = D.groupby(['g', 'ad_id']).tail(1).set_index(['g', 'ad_id'])[col].reindex(A.index)
        ever = D[D[col] == 'pass'].groupby(['g', 'ad_id']).head(1).set_index(['g', 'ad_id'])
        ever_pass = A.index.isin(ever.index)
        final_pass = (fin == 'pass').values
        w = A.winner.values

        def pr(pred):
            tp = int((pred & w).sum()); fp = int((pred & ~w).sum()); fn = int((~pred & w).sum())
            return dict(flagged=int(pred.sum()), tp=tp, fp=fp, fn=fn,
                        precision=tp / (tp + fp) if tp + fp else None, recall=tp / (tp + fn) if tp + fn else None)

        # early calls: state at check-in #k (ads that reached k check-ins)
        early = {}
        for kk in (3, 7, 14):
            s = D[D.n == kk].set_index(['g', 'ad_id'])[col]
            sub = A.loc[A.index.intersection(s.index)]
            st = s.reindex(sub.index)
            ww = sub.winner.values
            passed = (st == 'pass').values; pend = (st == 'pending').values
            tp = int((passed & ww).sum()); fp = int((passed & ~ww).sum())
            early[kk] = dict(n=int(len(sub)), pending=int(pend.sum()), passed=int(passed.sum()),
                             precision=tp / (tp + fp) if tp + fp else None,
                             recall=tp / int(ww.sum()) if ww.sum() else None, winners=int(ww.sum()))
        # speed for winners
        fw = ever.reindex(A[A.winner].index).dropna(subset=['n'])
        # flips
        flips = D[D[col] != 'pending'].groupby(['g', 'ad_id'])[col].apply(lambda x: int((x != x.shift()).sum() - 1)).reindex(A.index).fillna(0)
        # pause policy replay
        pol = {}
        for label, mask in (('first_fail', D[col] == 'fail'), ('3_consecutive_fails', consec_fail(col, 3).loc[D.index])):
            ff = D[mask].groupby(['g', 'ad_id']).head(1).set_index(['g', 'ad_id'])
            paused = A.index.isin(ff.index)
            spend_at_pause = ff.cum_spend.reindex(A.index)
            after = (A.cum_spend - spend_at_pause).where(paused, 0)
            pol[label] = dict(
                paused=int(paused.sum()), losers_paused=int((paused & ~w).sum()), winners_paused=int((paused & w).sum()),
                loser_spend_saved=float(after[~w].sum()), winner_spend_forgone=float(after[w].sum()),
                share_loser_spend_saved=float(after[~w].sum() / A[~A.winner].cum_spend.sum()) if (~w).any() else None,
                share_winner_spend_forgone=float(after[w].sum() / A[A.winner].cum_spend.sum()) if w.any() else None,
                winners_killed=[A.key[i].replace('|', ' · ') for i in A.index[paused & w]][:12])
        blk['gates'][gl] = dict(final=pr(final_pass), ever=pr(ever_pass), early=early,
                                winner_days_to_pass=float(fw.n.median()) if len(fw) else None,
                                winner_spend_to_pass=float(fw.cum_spend.median()) if len(fw) else None,
                                winners_never_pass=int(A.winner.sum() - len(fw)),
                                mean_flips=float(flips.mean()), policy=pol)
        summary.append(dict(group=gname, gate=gl, n=len(A), winners=int(A.winner.sum()),
                            final_precision=blk['gates'][gl]['final']['precision'], final_recall=blk['gates'][gl]['final']['recall'],
                            day7_precision=early[7]['precision'], day7_recall=early[7]['recall'], day7_pending=early[7]['pending'],
                            winner_days_to_pass=blk['gates'][gl]['winner_days_to_pass'], winner_spend_to_pass=blk['gates'][gl]['winner_spend_to_pass'],
                            mean_flips=blk['gates'][gl]['mean_flips'],
                            pause1_loser_saved=pol['first_fail']['share_loser_spend_saved'], pause1_winner_lost=pol['first_fail']['share_winner_spend_forgone'],
                            pause3_loser_saved=pol['3_consecutive_fails']['share_loser_spend_saved'], pause3_winner_lost=pol['3_consecutive_fails']['share_winner_spend_forgone'],
                            pause3_winners_killed=pol['3_consecutive_fails']['winners_paused']))
    results['groups'][gname] = blk

(HERE / 'sim_results.json').write_text(json.dumps(results, indent=1, default=float))
sm = pd.DataFrame(summary)
sm.to_csv(HERE / 'sim_summary.csv', index=False)

# ---- efficiency and spend: does a check-in metric tell you how efficient the ad will be and whether it can spend? ----
# At each ad's check-in #k (k = 3, 7, 14) we take the metric and gate state, then look FORWARD from that day:
#   future spend  = spend after check-in k (can it spend?)
#   forward LTV/CAC = LTV earned after k / spend after k (is the extra spend efficient?), ads with >= $200 forward spend
# plus the ad's final lifetime LTV/CAC for reference.
from scipy.stats import spearmanr
MCOL = {'SP': ('sp', 'st_sp'), 'CTI': ('cti', 'st_cti'), 'SP2': ('sp2', 'st_sp2')}
fin_ads = ads[ads.scored]
eff = {}
eff_rows = []
for g, gname in list(GROUPS.items()) + [('ALL', 'All')]:
    A = fin_ads if g == 'ALL' else fin_ads[fin_ads.index.get_level_values('g') == g]
    eff[gname] = {}
    for kk in (3, 7, 14):
        cp = df[df.n == kk].set_index(['g', 'ad_id'])
        cp = cp[cp.index.isin(A.index)]
        if not len(cp):
            continue
        fut_spend = A.cum_spend.reindex(cp.index) - cp.cum_spend
        fut_ltv = A.cum_ltv.reindex(cp.index) - cp.cum_ltv
        fwd = (fut_ltv / fut_spend).where(fut_spend >= 200)
        fin_lc = A.ltv_cac.reindex(cp.index)
        blk = {}
        for gl, (mc, sc) in MCOL.items():
            x = cp[mc].replace([np.inf, -np.inf], np.nan)

            def rho(y):
                m = x.notna() & y.notna()
                return (float(spearmanr(x[m], y[m])[0]), float(spearmanr(x[m], y[m])[1]), int(m.sum())) if m.sum() >= 8 else (None, None, int(m.sum()))
            r_fs, p_fs, n_fs = rho(fut_spend); r_fw, p_fw, n_fw = rho(fwd); r_fl, p_fl, n_fl = rho(fin_lc)
            ps, fl = cp[sc] == 'pass', cp[sc] == 'fail'

            def sw(mask):  # spend-weighted forward LTV/CAC of a set
                m = mask & fwd.notna()
                return float(fut_ltv[m].sum() / fut_spend[m].sum()) if fut_spend[m].sum() > 0 else None
            blk[gl] = dict(rho_future_spend=r_fs, p_future_spend=p_fs, n_future_spend=n_fs,
                           rho_fwd_ltvcac=r_fw, p_fwd_ltvcac=p_fw, n_fwd=n_fw,
                           rho_final_ltvcac=r_fl, p_final_ltvcac=p_fl,
                           pass_n=int(ps.sum()), fail_n=int(fl.sum()), pending_n=int((cp[sc] == 'pending').sum()),
                           pass_med_future_spend=float(fut_spend[ps].median()) if ps.any() else None,
                           fail_med_future_spend=float(fut_spend[fl].median()) if fl.any() else None,
                           pass_share_future_spend=float(fut_spend[ps].sum() / fut_spend.sum()) if fut_spend.sum() > 0 else None,
                           pass_fwd_ltvcac=sw(ps), fail_fwd_ltvcac=sw(fl))
            eff_rows.append(dict(group=gname, checkin=kk, metric=gl, n=len(cp), rho_future_spend=r_fs, p_fs=p_fs,
                                 rho_fwd_ltvcac=r_fw, p_fw=p_fw, n_fwd=n_fw, rho_final_ltvcac=r_fl,
                                 pass_fwd_ltvcac=blk[gl]['pass_fwd_ltvcac'], fail_fwd_ltvcac=blk[gl]['fail_fwd_ltvcac'],
                                 pass_med_fut_spend=blk[gl]['pass_med_future_spend'], fail_med_fut_spend=blk[gl]['fail_med_future_spend'],
                                 pass_share_fut_spend=blk[gl]['pass_share_future_spend']))
        eff[gname][kk] = dict(n=int(len(cp)), group_fwd_ltvcac=float(fut_ltv[fwd.notna()].sum() / fut_spend[fwd.notna()].sum()) if fwd.notna().any() else None, metrics=blk)
    # final quadrant: efficient (lifetime LTV/CAC >= 0.8) x spent (>= group spend bar)
    bar = WIN_SPEND.get(g, 5000.0)
    eff[gname]['quadrant'] = dict(spend_bar=bar, efficient_and_spent=int(((A.ltv_cac >= LTVCAC_TARGET) & (A.cum_spend >= bar)).sum()),
                                  efficient_small=int(((A.ltv_cac >= LTVCAC_TARGET) & (A.cum_spend < bar)).sum()),
                                  inefficient_spent=int(((A.ltv_cac < LTVCAC_TARGET) & (A.cum_spend >= bar)).sum()),
                                  inefficient_small=int(((A.ltv_cac < LTVCAC_TARGET) & (A.cum_spend < bar)).sum()),
                                  group_ltvcac=float(A.cum_ltv.sum() / A.cum_spend.sum()))
eff['All']['quadrant'] = {k: (sum(eff[x]['quadrant'][k] for x in ('Testing', 'Winning', 'Scaling')) if k not in ('spend_bar', 'group_ltvcac') else eff['All']['quadrant'][k])
                          for k in eff['All']['quadrant']}
eff['All']['quadrant']['spend_bar'] = 'Testing $1k, Winning/Scaling $5k'
results['efficiency'] = eff
results['params']['ltv_cac_target'] = LTVCAC_TARGET
results['params']['ltv_source'] = 'SSOT marketing_attribution_aggregate_attribution_date_cohort.ltv x group-month No-Ad-ID coverage factor'
(HERE / 'sim_results.json').write_text(json.dumps(results, indent=1, default=float))
er = pd.DataFrame(eff_rows)
er.to_csv(HERE / 'sim_efficiency.csv', index=False)

# ---- motion-graphic payload ----
code = {'pending': 0, 'fail': 1, 'pass': 2}


def label(key):
    cr, co = key.split('|', 1) if '|' in key else ('', key)
    return co if cr in ('na', '') else f'{cr.rstrip("_")} · {co}'


out = []
for (g, ad_id), a in ads.iterrows():
    D = df[(df.g == g) & (df.ad_id == ad_id)].sort_values('off')
    days = [[int(r.off), round(r.spend), round(r.cum_spend), round(r.sp, 2),
             None if not np.isfinite(r.cti) else round(r.cti * 100, 2),
             None if not np.isfinite(r.sp2) else round(r.sp2, 2),
             None if not np.isfinite(r.cpft) else round(r.cpft),
             code[r.st_sp] * 9 + code[r.st_cti] * 3 + code[r.st_sp2], round(r.ltv_cac, 2)] for r in D.itertuples()]
    out.append(dict(g=g, id=ad_id, name=label(a.key), f=(a.first_date - BASE).days, w=bool(a.winner), nw=bool(a.too_new),
                    s=round(a.cum_spend), t=int(a.cum_trials), c=None if not np.isfinite(a.cpft) else round(a.cpft),
                    l=round(float(a.ltv_cac), 2), d=days))
(HERE / 'sim_ads.json').write_text(json.dumps(out, separators=(',', ':')))

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(ads.groupby(level='g').agg(n=('winner', 'size'), winners=('winner', 'sum'), too_new=('too_new', 'sum'), spend=('cum_spend', 'sum')))
print(sm.round(2).to_string(index=False))
for gname, blk in results['groups'].items():
    for gl, v in blk['gates'].items():
        print(gname, gl, 'early', {k: (e['n'], e['pending'], e['passed'], None if e['precision'] is None else round(e['precision'], 2), None if e['recall'] is None else round(e['recall'], 2)) for k, e in v['early'].items()},
              'killed3', v['policy']['3_consecutive_fails']['winners_killed'])

print(er[er.checkin == 7].round(2).to_string(index=False))
for gname, e in eff.items(): print(gname, e['quadrant'])
