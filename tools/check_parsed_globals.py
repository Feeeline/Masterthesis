import sys
from pathlib import Path as P
proj_root = P(__file__).resolve().parents[1]
sys.path.insert(0, str(proj_root))
from tools.plot_exergy_results import parse_global_vergleich_txt, parse_stream_mass_flows, TAB_DIR, STREAMS_SINGLE, STREAMS_DOUBLE

s,d = parse_global_vergleich_txt(TAB_DIR / 'Global_Vergleich.txt')
print('parsed single:', s)
print('parsed double:', d)
# Dump raw csv rows for debugging
import csv
with open(TAB_DIR / 'Global_Vergleich.txt', 'r', encoding='utf-8') as f:
	reader = csv.reader(f, delimiter=',', quotechar='"')
	rows = list(reader)
	print('raw rows:')
	for r in rows:
		print(r)
with open(TAB_DIR / 'Global_Vergleich.txt', 'rb') as f:
	b = f.read()
	print('raw bytes repr:')
	print(repr(b[:400]))
mds = parse_stream_mass_flows(STREAMS_SINGLE).get('S24') or parse_stream_mass_flows(STREAMS_SINGLE).get('S24,00')
mdd = parse_stream_mass_flows(STREAMS_DOUBLE).get('S32') or parse_stream_mass_flows(STREAMS_DOUBLE).get('S32,00')
print('mdot S24, S32:', mds, mdd)
# compute specific kJ/kg
spec_s = {k: (v*1000.0/mds) if (v is not None and mds) else None for k,v in (s or {}).items()}
spec_d = {k: (v*1000.0/mdd) if (v is not None and mdd) else None for k,v in (d or {}).items()}
print('specific single kJ/kg:', spec_s)
print('specific double kJ/kg:', spec_d)
