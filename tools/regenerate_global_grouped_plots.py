from pathlib import Path
import sys
from pathlib import Path as P
# Ensure project root is on sys.path so `tools` package imports work when running as script
proj_root = P(__file__).resolve().parents[1]
sys.path.insert(0, str(proj_root))

from tools.plot_exergy_results import (
    parse_global_vergleich_txt,
    parse_stream_mass_flows,
    plot_grouped_system_metrics,
    plot_grouped_specific_system_metrics,
    TAB_DIR, OUT_DIR, STREAMS_SINGLE, STREAMS_DOUBLE
)

gv_s, gv_d = parse_global_vergleich_txt(TAB_DIR / 'Global_Vergleich.txt')
print('gv_s parsed:', gv_s)
stream_mdot_single = parse_stream_mass_flows(STREAMS_SINGLE)
stream_mdot_double = parse_stream_mass_flows(STREAMS_DOUBLE)
# attempt normalized keys
mdot_single = stream_mdot_single.get('S24') or stream_mdot_single.get('S24,00') or stream_mdot_single.get('S24,0')
mdot_double = stream_mdot_double.get('S32') or stream_mdot_double.get('S32,00') or stream_mdot_double.get('S32,0')
print('mdot_single, mdot_double:', mdot_single, mdot_double)
if isinstance(gv_s, dict) and isinstance(gv_d, dict):
    plot_grouped_system_metrics(gv_d, gv_s, OUT_DIR / 'vergleich_global_kennzahlen_grouped.png')
    # Build specific metrics directly from parsed gv dicts to avoid key-format mismatches
    metrics_single_spec = {}
    metrics_double_spec = {}
    for k, v in (gv_s or {}).items():
        metrics_single_spec[k] = (v * 1000.0 / mdot_single) if (isinstance(v, (int, float)) and mdot_single) else None
    for k, v in (gv_d or {}).items():
        metrics_double_spec[k] = (v * 1000.0 / mdot_double) if (isinstance(v, (int, float)) and mdot_double) else None
    print('metrics_single_spec:', metrics_single_spec)
    print('metrics_double_spec:', metrics_double_spec)
    plot_grouped_specific_system_metrics(metrics_double_spec, metrics_single_spec, OUT_DIR / 'vergleich_global_kennzahlen_grouped_spezifisch.png')
    print('Generated grouped plots in', OUT_DIR)
else:
    print('Failed to parse Global_Vergleich.txt')
