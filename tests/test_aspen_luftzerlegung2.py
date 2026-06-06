"""Minimal, robust test runner that mirrors the original single-column test
but avoids duplicated code and known string-escaping bugs. Writes outputs
with a '2' suffix to avoid overwriting existing results.

This file is intentionally conservative: helpers produce simple LaTeX
longtables and JSON payloads sufficient for plotting and document
generation. It avoids complex formatting that previously caused
unterminated-string and indentation problems.
"""

import json
import os
import logging
import sys
import math
from typing import Dict

from exerpy import ExergyAnalysis

# Configure simple stdout logging
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(ch)
logging.root.setLevel(logging.INFO)

# Default model path (user-provided Aspen backup copy)
default_model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne_klein - Kopie\Single_Column_Simulation_Final.bkp"
model_path = os.environ.get('MODEL_PATH') or (sys.argv[1] if len(sys.argv) > 1 else default_model_path)
logging.info(f"Using model_path={model_path}")

# Run analysis
ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)
ean.analyse()


def _latex_escape(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    return (
        s.replace('\\', '\\textbackslash{}')
        .replace('&', '\\&')
        .replace('%', '\\%')
        .replace('$', '\\$')
        .replace('#', '\\#')
        .replace('_', '\\_')
        .replace('{', '\\{')
        .replace('}', '\\}')
    )


def _format_value(v) -> str:
    if v is None:
        return "-"
    try:
        x = float(v)
    except Exception:
        return _latex_escape(str(v))
    if not math.isfinite(x):
        return "-"
    if globals().get('NO_ROUNDING', True):
        s = format(x, '.17g')
        return s.replace('.', ',')
    return f"{x:.2f}".replace('.', ',')


def _build_streams_latex_table(conns: Dict) -> str:
    # Minimal table: Stream & m
    mat = [c for c in conns.values() if isinstance(c, dict) and c.get('kind') == 'material']
    lines = ['\\begin{longtable}{lr}', '\\caption{Stoffliche Stroeme} \\', '\\hline', 'Stream & $\\dot m$ \\', '\\hline']
    for c in mat:
        name = _latex_escape(c.get('name') or '')
        m = _format_value(c.get('m'))
        lines.append("{} & {} \\\\".format(name, m))
    lines += ['\\hline', '\\end{longtable}']
    return "\n".join(lines)


def _build_component_results_table(components: Dict) -> str:
    # Minimal component table: Component & Type & E_D (W)
    lines = ['\\begin{longtable}{lrr}', '\\caption{Komponenten - E_D (W)} \\', '\\hline', 'Component & Type & $\\dot{E}_D$ \\', '\\hline']
    for name, comp in components.items():
        try:
            typ = comp.__class__.__name__
            E_D = getattr(comp, 'E_D', None) or getattr(comp, 'E_D_custom', None) or 0.0
        except Exception:
            typ = 'Unknown'
            E_D = 0.0
        lines.append("{} & {} & {} \\\\".format(_latex_escape(name), _latex_escape(typ), _format_value(E_D)))
    lines += ['\\hline', '\\end{longtable}']
    return "\n".join(lines)


def _build_components_work_table(conns: Dict, components: Dict) -> str:
    # Search for power-kind connections and write Component & Type & W
    power = [ (k,c) for k,c in conns.items() if isinstance(c, dict) and c.get('kind') == 'power']
    lines = ['\\begin{longtable}{lrr}', '\\caption{Komponenten mit Arbeitsströmen (W)} \\', '\\hline', 'Component & Type & $\\dot W$ \\', '\\hline']
    for key, conn in power:
        name = conn.get('name') or key
        typ = conn.get('type') or ''
        w = conn.get('energy_flow') or conn.get('E') or 0.0
        lines.append("{} & {} & {} \\\\".format(_latex_escape(name), _latex_escape(typ), _format_value(w)))
    lines += ['\\hline', '\\end{longtable}']
    return "\n".join(lines)


def _build_molar_fractions_table(conns: Dict) -> str:
    # Very small molfrac table (stream, x_N2, x_O2)
    mat = [c for c in conns.values() if isinstance(c, dict) and c.get('kind') == 'material']
    lines = ['\\begin{longtable}{lrr}', '\\caption{Molfraktionen} \\', '\\hline', 'Stream & $x_{N_2}$ & $x_{O_2}$ \\', '\\hline']
    for c in mat:
        name = _latex_escape(c.get('name') or '')
        x_n2 = _format_value(c.get('x_N2'))
        x_o2 = _format_value(c.get('x_O2'))
        lines.append("{} & {} & {} \\\\".format(name, x_n2, x_o2))
    lines += ['\\hline', '\\end{longtable}']
    return "\n".join(lines)


# Prepare exports and write suffixed files
export_data = ean._serialize()
connections = export_data.get('connections', {})

out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Overleaf_LaTeX', 'tabellen'))
os.makedirs(out_dir, exist_ok=True)

json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'examples', 'json_example', 'aspen_luftzerlegung_single2.json'))
os.makedirs(os.path.dirname(json_path), exist_ok=True)
with open(json_path, 'w', encoding='utf-8') as jf:
    json.dump(export_data, jf, indent=4)

with open(os.path.join(out_dir, 'aspen_luftzerlegung_streams_single2.tex'), 'w', encoding='utf-8') as f:
    f.write(_build_streams_latex_table(connections))

with open(os.path.join(out_dir, 'aspen_luftzerlegung_components_single2.tex'), 'w', encoding='utf-8') as f:
    f.write(_build_component_results_table(ean.components))

with open(os.path.join(out_dir, 'aspen_luftzerlegung_components_work_single2.tex'), 'w', encoding='utf-8') as f:
    f.write(_build_components_work_table(connections, ean.components))

with open(os.path.join(out_dir, 'aspen_luftzerlegung_streams_molfrac_single2.tex'), 'w', encoding='utf-8') as f:
    f.write(_build_molar_fractions_table(connections))

logging.info('Wrote JSON and LaTeX outputs with suffix 2')
