"""Speak TW Google Android pulse-up geo test (Sep 2026): side-by-side campaign comparison and
test-vs-control difference-in-differences on Taiwan Android KPIs. Reads data/*.csv, writes
output/results.json and prints the tables used in README.md. No external dependencies."""
import csv, json, math, datetime as dt, collections, os
HERE = os.path.dirname(os.path.abspath(__file__))
TEST_REGIONS = ['New Taipei City', 'Taoyuan', 'Hsinchu County', 'Pingtung']
CONTROL_ID, TEST_ID = '23639420764', '24190362603'
D = dt.date.fromisoformat
def rows(name):
    with open(os.path.join(HERE, 'data', name), newline='') as f:
        return list(csv.DictReader(f))
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0
def ratio_ci(t0, c0, t1, c1):
    """Control-adjusted lift of test in period 1 vs period 0 with a Poisson log-ratio 95% CI."""
    if min(t0, c0, t1, c1) <= 0: return None
    lr = math.log((t1 / c1) / (t0 / c0)); se = math.sqrt(1/t0 + 1/c0 + 1/t1 + 1/c1)
    return dict(lift=math.exp(lr)-1, lo=math.exp(lr-1.96*se)-1, hi=math.exp(lr+1.96*se)-1,
                counterfactual=c1*t0/c0, incremental=t1-c1*t0/c0)
out = {}

# ---- 1. Campaign side by side, September 1-30 ----------------------------------------------
camp = collections.defaultdict(lambda: collections.defaultdict(float))
for r in rows('campaign_daily.csv'):
    d = D(r['date'])
    per = 'aug' if d < D('2026-09-01') else ('sep' if d <= D('2026-09-30') else 'oct')
    for k in ['spend', 'impressions', 'clicks', 'installs', 'signups', 'trial_starts', 'paid', 'ltv', 'forecasted_ltv']:
        camp[(r['campaign_id'], per)][k] += num(r[k])
    camp[(r['campaign_id'], per)]['days'] += 1 if num(r['spend']) > 0 else 0
def derived(m):
    s = m['spend']
    return dict(m, cpm=1000*s/m['impressions'] if m['impressions'] else None, ctr=m['clicks']/m['impressions'] if m['impressions'] else None,
                cpi=s/m['installs'] if m['installs'] else None, install_to_signup=m['signups']/m['installs'] if m['installs'] else None,
                signup_to_trial=m['trial_starts']/m['signups'] if m['signups'] else None, cpt=s/m['trial_starts'] if m['trial_starts'] else None,
                cpa=s/m['paid'] if m['paid'] else None, trial_to_paid=m['paid']/m['trial_starts'] if m['trial_starts'] else None,
                ltv_cac=m['forecasted_ltv']/s if s else None, spend_per_day=s/m['days'] if m['days'] else None)
out['campaigns'] = {f'{cid}_{per}': derived(m) for (cid, per), m in camp.items()}
print('== September 1-30, side by side')
hdr = ['spend', 'spend_per_day', 'impressions', 'cpm', 'ctr', 'clicks', 'installs', 'cpi', 'signups', 'install_to_signup', 'trial_starts', 'signup_to_trial', 'cpt', 'paid', 'cpa', 'forecasted_ltv', 'ltv_cac']
for cid, label in [(CONTROL_ID, 'tROAS (control)'), (TEST_ID, 'pulseup (test)')]:
    m = out['campaigns'][f'{cid}_sep']
    print(label, {k: (round(m[k], 3) if isinstance(m[k], float) else m[k]) for k in hdr})

# ---- 2. Did the geo split hold? attributed sign-ups by cell, Aug vs Sep --------------------
split = collections.defaultdict(lambda: collections.defaultdict(int))
for r in rows('campaign_signups_by_region.csv'):
    for k in ['signups', 'trials', 'conversions']:
        split[(r['campaign_id'], r['period'], r['cell'])][k] += int(r[k])
        split[(r['campaign_id'], r['period'], r['region'])][k] += int(r[k])
out['geo_split'] = {f'{k[0]}_{k[1]}_{k[2]}': dict(v) for k, v in split.items()}
print('\n== Attributed sign-ups by cell (IP region at sign-up)')
for cid, label in [(CONTROL_ID, 'tROAS (control)'), (TEST_ID, 'pulseup (test)')]:
    for per in ['aug', 'sep']:
        t, c, u = (split[(cid, per, x)]['signups'] for x in ['test', 'control', 'unknown'])
        if t + c: print(f'{label:16s} {per}: test {t:5d}  control {c:5d}  unknown {u:4d}  test share {t/(t+c):.3f}')

# ---- 3. Difference in differences on Taiwan Android (and iOS placebo) KPIs ----------------
daily = rows('tw_daily_by_cell.csv')
metrics = ['signups', 'trial_starts', 'conversions', 'purch_plus_trials']
periods = {'pre_JunJul': (D('2026-06-01'), D('2026-07-31')), 'pre_Aug': (D('2026-08-01'), D('2026-08-31')),
           'test_Sep': (D('2026-09-01'), D('2026-09-30')), 'post_Oct1-11': (D('2026-10-01'), D('2026-10-11'))}
def tot(os_, cell, m, a, b):
    return sum(int(r[m]) for r in daily if r['os'] == os_ and r['cell'] == cell and a <= D(r['d']) <= b)
out['did'] = {}
print('\n== Test vs control regions, per day, and DiD (Sep vs Jun-Jul baseline)')
for os_ in ['android', 'ios']:
    for m in metrics:
        row = {}
        for p, (a, b) in periods.items():
            n = (b - a).days + 1; t = tot(os_, 'test', m, a, b); c = tot(os_, 'control', m, a, b)
            row[p] = dict(days=n, test=t, control=c, test_per_day=t/n, control_per_day=c/n, test_share=t/(t+c) if t+c else None)
        row['did_sep_vs_junjul'] = ratio_ci(row['pre_JunJul']['test'], row['pre_JunJul']['control'], row['test_Sep']['test'], row['test_Sep']['control'])
        row['did_sep_vs_aug'] = ratio_ci(row['pre_Aug']['test'], row['pre_Aug']['control'], row['test_Sep']['test'], row['test_Sep']['control'])
        out['did'][f'{os_}_{m}'] = row
        d = row['did_sep_vs_junjul']
        print(f"{os_:7s} {m:17s} test/day pre {row['pre_JunJul']['test_per_day']:6.1f} sep {row['test_Sep']['test_per_day']:6.1f} | ctrl/day pre {row['pre_JunJul']['control_per_day']:6.1f} sep {row['test_Sep']['control_per_day']:6.1f} | lift {d['lift']:+.1%} [{d['lo']:+.1%}, {d['hi']:+.1%}] incremental {d['incremental']:+.0f}")

# ---- 4. Per-region lift, Android, weeks of Aug 31 - Sep 28 vs Jun 1 - Jul 27 ---------------
wk = rows('tw_android_weekly_by_region.csv')
pre, sep = (D('2026-06-01'), D('2026-07-27')), (D('2026-08-31'), D('2026-09-28'))
def wtot(metric, flt, a, b):
    return sum(int(r['n']) for r in wk if r['metric'] == metric and a <= D(r['wk']) <= b and flt(r['region']))
out['regions'] = {}
print('\n== Per-region control-adjusted lift (Android), Sep weeks vs Jun-Jul weeks')
for metric in ['signup', 'google_signup', 'trial_start', 'conversion']:
    ctrl = lambda reg: reg not in ('', 'None') and reg not in TEST_REGIONS
    c0, c1 = wtot(metric, ctrl, *pre), wtot(metric, ctrl, *sep)
    for reg in TEST_REGIONS + ['ALL_TEST', 'Taipei City', 'Taichung City', 'Kaohsiung', 'Tainan', 'Hsinchu City']:
        flt = (lambda r: r in TEST_REGIONS) if reg == 'ALL_TEST' else (lambda r, reg=reg: r == reg)
        t0, t1 = wtot(metric, flt, *pre), wtot(metric, flt, *sep)
        res = ratio_ci(t0, c0, t1, c1)
        out['regions'][f'{metric}_{reg}'] = dict(pre=t0, sep=t1, pre_per_week=t0/9, sep_per_week=t1/5, **(res or {}))
        if res: print(f"{metric:14s} {reg:15s} pre/wk {t0/9:6.1f} sep/wk {t1/5:6.1f} lift {res['lift']:+7.1%} [{res['lo']:+7.1%}, {res['hi']:+7.1%}]")
    out['regions'][f'{metric}_CONTROL_TOTAL'] = dict(pre=c0, sep=c1, pre_per_week=c0/9, sep_per_week=c1/5)

os.makedirs(os.path.join(HERE, 'output'), exist_ok=True)
json.dump(out, open(os.path.join(HERE, 'output', 'results.json'), 'w'), indent=1, default=lambda x: None if x != x else x)
print('\nwrote output/results.json')
