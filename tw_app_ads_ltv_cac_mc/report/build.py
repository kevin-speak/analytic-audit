import json, pathlib
here = pathlib.Path(__file__).parent
res = json.load(open(here.parent / 'output' / 'results.json'))
sp2 = json.load(open(here.parent / 'output' / 'sp2.json'))
bt = json.load(open(here.parent / 'output' / 'sp2_backtest.json'))
html = (here / 'template.html').read_text().replace('__RESULTS_JSON__', json.dumps(res, separators=(',', ':'))).replace('__SP2_JSON__', json.dumps(sp2, separators=(',', ':'))).replace('__BACKTEST_JSON__', json.dumps(bt, separators=(',', ':')))
(here / 'index.html').write_text(html)
print('wrote', here / 'index.html', len(html) // 1024, 'KB')
