"""Convert a saved BigQuery MCP result file ({rows:[{f:[{v:..}]}], schema:{fields:[{name}]}}) to CSV."""
import csv, json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
cols = [f['name'] for f in d['schema']['fields']]
rows = d.get('rows', [])
def val(x):
    v = x['v']
    if isinstance(v, list): return ';'.join(str(i['v']) for i in v)
    return '' if v is None else v
with open(dst, 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(cols)
    for r in rows: w.writerow([val(x) for x in r['f']])
print(f'{dst}: {len(rows)} rows, jobComplete={d.get("jobComplete")}, cols={cols}')
