"""Embed sim_ads.json + sim_results.json into motion_template.html -> motion.html (the motion graphic)."""
from pathlib import Path
H = Path(__file__).parent
t = (H / 'motion_template.html').read_text()
t = t.replace('/*ADS*/[]', (H / 'sim_ads.json').read_text()).replace('/*RES*/{}', (H / 'sim_results.json').read_text())
(H / 'motion.html').write_text(t)
print('motion.html', len(t))
