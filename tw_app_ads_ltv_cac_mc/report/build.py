import json, pathlib
here = pathlib.Path(__file__).parent
res = json.load(open(here.parent / 'output' / 'results.json'))
html = (here / 'template.html').read_text().replace('__RESULTS_JSON__', json.dumps(res, separators=(',', ':')))
(here / 'index.html').write_text(html)
print('wrote', here / 'index.html', len(html) // 1024, 'KB')
