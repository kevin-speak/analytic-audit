import json, pathlib
here = pathlib.Path(__file__).parent
res = json.load(open(here.parent / 'output' / 'results.json'))
payload = json.dumps(res, separators=(',', ':')).replace('<', '\\u003c')
html = (here / 'template.html').read_text().replace('__RESULTS_JSON__', payload)
(here / 'index.html').write_text(html)
print('wrote', here / 'index.html', len(html) // 1024, 'KB')
