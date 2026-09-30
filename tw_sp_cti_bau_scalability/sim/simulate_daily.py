"""
Daily check-in simulation: every TW iOS Meta ad in the testing / winning / scaling campaigns, Jun 1 - Sep 29 2026,
re-scored on each day it delivered with its cumulative-to-date data, against three gates:

  SP   pass: SP (Option B, cumulative-to-date, benchmark = same group's placements to date) >= 2.0 and >= 10 installs
  CTI  pass: installs / link clicks >= 1% and >= 300 link clicks
  SP2  pass: EI >= 1 and EI x SI >= 2 and >= 10 installs
       EI = (K / CPI) / 0.8, K = $12.26 SSOT LTV per Meta install (tw_app_ads_ltv_cac_mc/sp2.py) -> CPI target $15.32
       SI = spend per active day / median of live ads in the same group that day, clipped [0.25, 4]
  Before the minimum data is reached the gate is 'pending'.

Ground truth (known at Sep 29): Winner = cumulative Meta trials >= 10 and CPFT <= $70.
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
WIN_TRIALS, WIN_CPR = 10, 70.0
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


def state(ok, enough):
    return np.where(~enough, 'pending', np.where(ok, 'pass', 'fail'))


df['st_sp'] = state(df.sp >= SP_BAR, df.cum_installs >= MIN_INST)
df['st_cti'] = state(df.cti >= CTI_BAR, df.cum_link >= MIN_LINK)
df['st_sp2'] = state((df.ei >= 1) & (df.sp2 >= SP2_BAR), df.cum_installs >= MIN_INST)
df = df.sort_values(['g', 'ad_id', 'off']).reset_index(drop=True)
df['n'] = df.active_days  # check-in number = lifetime active day # (ads live before Jun 1 start mid-life)

# ---- per-ad outcome ----
last = df.groupby(['g', 'ad_id']).tail(1).set_index(['g', 'ad_id'])
ads = last[['key', 'first_date', 'cum_spend', 'cum_trials', 'cum_installs', 'cpft', 'active_days']].copy()
ads['last_date'] = [BASE + timedelta(int(o)) for o in last.off]
ads['first_date'] = pd.to_datetime(ads.first_date).dt.date
ads['winner'] = (ads.cum_trials >= WIN_TRIALS) & (ads.cpft <= WIN_CPR)
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
                          k_ltv_per_install=K_LTV, cpi_target=CPI_TARGET, winner=f'trials>={WIN_TRIALS} & CPFT<=${WIN_CPR:.0f}',
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

# ---- motion-graphic payload ----
code = {'pending': 0, 'fail': 1, 'pass': 2}


def label(key):
    cr, co = key.split('|', 1) if '|' in key else ('', key)
    return co if cr in ('na', '') else f'{cr.rstrip("_")} · {co}'


out = []
for (g, ad_id), a in ads.iterrows():
    D = df[(df.g == g) & (df.ad_id == ad_id)]
    days = [[int(r.off), round(r.spend), round(r.cum_spend), round(r.sp, 2),
             None if not np.isfinite(r.cti) else round(r.cti * 100, 2),
             None if not np.isfinite(r.sp2) else round(r.sp2, 2),
             None if not np.isfinite(r.cpft) else round(r.cpft),
             code[r.st_sp] * 9 + code[r.st_cti] * 3 + code[r.st_sp2]] for r in D.itertuples()]
    out.append(dict(g=g, id=ad_id, name=label(a.key), f=(a.first_date - BASE).days, w=bool(a.winner), nw=bool(a.too_new),
                    s=round(a.cum_spend), t=int(a.cum_trials), c=None if not np.isfinite(a.cpft) else round(a.cpft), d=days))
(HERE / 'sim_ads.json').write_text(json.dumps(out, separators=(',', ':')))

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(ads.groupby(level='g').agg(n=('winner', 'size'), winners=('winner', 'sum'), too_new=('too_new', 'sum'), spend=('cum_spend', 'sum')))
print(sm.round(2).to_string(index=False))
for gname, blk in results['groups'].items():
    for gl, v in blk['gates'].items():
        print(gname, gl, 'early', {k: (e['n'], e['pending'], e['passed'], None if e['precision'] is None else round(e['precision'], 2), None if e['recall'] is None else round(e['recall'], 2)) for k, e in v['early'].items()},
              'killed3', v['policy']['3_consecutive_fails']['winners_killed'])
