import json
import os
import logging
import sys

from exerpy import ExergyAnalysis

# Get the log file path
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'parser_run.log'))

"""
Logging setup note:
- We avoid opening parser_run.log via FileHandler because shell redirection
    (e.g. `python tests/test_aspen_luftzerlegung.py > parser_run.log 2>&1`) already
    owns the file handle and causes PermissionError on Windows.
- Instead, emit logs to stdout only; the shell captures them into parser_run.log.
"""

# Reset existing handlers and configure stdout-only logging
for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

#model_path = r'C:\Users\Felin\Documents\Masterthesis\Code\Exerpy\exerpy\examples\asu_aspen\Doppelkolonne.bkp'
model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Doppelkolonne\Doppelkolonne_Simulation_Final.bkp"


ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)

# ===== MHeatX CONFIGURATION (spezProdukt mode - OPTIONAL) =====
# If you want to configure specific stream pairs for MHeatX components,
# define them here. Otherwise, leave empty {} for balance-mode only.
#
# Structure:
# {
#     "component_name": {
#         "part": "E_PH" | "E_T" | "E_M",  # exergy component to use
#         "hot_pairs": [("S_in", "S_out"), ...],      # streams giving up exergy (fuel-like)
#         "cold_pairs": [("S_in", "S_out"), ...],     # streams taking exergy (product-like)
#         "product_pairs": [("S_in", "S_out"), ...],  # which cold pairs are "product"
#         "fuel_pairs": [("S_in", "S_out"), ...],     # optional: override fuel base (default=hot_pairs)
#     }
# }
#
# Example (uncomment and customize as needed):
MHEATX_CFG = {
    # "MW": {
    #     "part": "E_PH",
    #     "hot_pairs": [("S11", "S12"), ("S19", "S20")],       # cooled streams
    #     "cold_pairs": [("S15", "S16"), ("S27", "S28"), ("S29", "S30")],  # heated streams
    #     "product_pairs": [("S15", "S16")],  # which of the cold streams are product
    # },
}

# Apply configuration to ExergyAnalysis
if MHEATX_CFG:
    ean.set_mheatx_config(MHEATX_CFG)

# Discover power connections in the parsed model and use them for the test.
# Some Aspen files name power flows differently, so we pick available 'power' connections dynamically.
power_conns = ean.list_connections_by_kind('power')
if len(power_conns) >= 4:
    fuel = {"inputs": power_conns[:3], "outputs": [power_conns[3]]}
else:
    # Fallback: use whatever power connections exist; if none, pick first material streams as a best-effort fallback.
    material_conns = ean.list_connections_by_kind('material')
    fuel = {"inputs": material_conns[:3], "outputs": material_conns[3:4]}

# Select product and loss streams from available material streams (fall back to specific names if present)
material_conns = ean.list_connections_by_kind('material')
product = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('32')][:1] or material_conns[31:32]}
loss = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('28') or c.endswith('25')][:2]}

ean.analyse(E_F=fuel, E_P=product, E_L=loss)

# Log calculated exergy results for all components
logging.info("\n" + "="*100)
logging.info("COMPONENT EXERGY RESULTS")
logging.info("="*100)
for comp_name, component in ean.components.items():
    if component.__class__.__name__ != "CycleCloser":
        E_F = getattr(component, 'E_F', None)
        E_P = getattr(component, 'E_P', None)
        E_D = getattr(component, 'E_D', None)
        epsilon = getattr(component, 'epsilon', None)
        
        epsilon_str = f"{epsilon:.4f}" if epsilon is not None else "N/A"
        
        result_msg = (
            f"Component results | {comp_name} ({component.__class__.__name__}) | "
            f"E_F={E_F:.2f} W | E_P={E_P:.2f} W | E_D={E_D:.2f} W | eps={epsilon_str}"
        )
        logging.info(result_msg)

logging.info("\n" + "="*100)
logging.info("OVERALL SYSTEM RESULTS")
logging.info("="*100)
logging.info(f"Total E_F = {ean.E_F:.2f} W")
logging.info(f"Total E_P = {ean.E_P:.2f} W")
logging.info(f"Total E_D = {ean.E_D:.2f} W")
logging.info(f"Total E_L = {ean.E_L:.2f} W")
epsilon_total = f"{ean.epsilon:.4f}" if ean.epsilon is not None else "N/A"
logging.info(f"System Efficiency eps = {epsilon_total}")
logging.info("="*100 + "\n")

# Export JSON in the same structure as examples/json_example/example.json
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung.json")
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
export_data = ean._serialize()
json_payload = {
    "components": export_data.get("components", {}),
    "connections": export_data.get("connections", {}),
    "ambient_conditions": export_data.get("ambient_conditions", {}),
}
with open(output_path, "w", encoding="utf-8") as json_file:
    json.dump(json_payload, json_file, indent=4)

# Export LaTeX table with all material stream data
def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for key, repl in replacements.items():
        value = value.replace(key, repl)
    return value


def _format_value(value):
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.6g}"
    return _latex_escape(str(value))


def _build_streams_latex_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("m", r"$\dot m$", "m_unit"),
        ("n", r"$\dot n$", "n_unit"),
        ("T", r"$T$", "T_unit"),
        ("p", r"$p$", "p_unit"),
        ("h", r"$h$", "h_unit"),
        ("s", r"$s$", "s_unit"),
        ("mfn2", r"$x_{N_2}$", "mfn2_unit"),
        ("mfo2", r"$x_{O_2}$", "mfo2_unit"),
        ("mfco", r"$x_{CO_2}$", "mfco_unit"),
        ("mfar", r"$x_{Ar}$", "mfar_unit"),
        ("mfho", r"$x_{H_2O}$", "mfho_unit"),
        ("lfrac", r"$l_{frac}$", "lfrac_unit"),
        ("vfrac_out", r"$v_{frac}$", "vfrac_out_unit"),
        ("e_PH", r"$e_{PH}$", "e_PH_unit"),
        ("e_CH", r"$e_{CH}$", "e_CH_unit"),
        ("e_T", r"$e_T$", "e_T_unit"),
        ("e_M", r"$e_M$", "e_M_unit"),
    ]

    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = conn.get("name", "")
        try:
            return (0, int(str(name)))
        except (ValueError, TypeError):
            return (1, str(name))

    material_streams.sort(key=_sort_key)

    unit_lookup = {}
    for key, _, unit_key in columns:
        if not unit_key:
            unit_lookup[key] = ""
            continue
        unit = None
        for conn in material_streams:
            unit = conn.get(unit_key)
            if unit:
                break
        unit_lookup[key] = unit or ""

    header = " & ".join(label for _, label, _ in columns) + " \\\\"
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\\"

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = conn.get(key)
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{tabular}",
    ]
    return "\n".join(lines)


def _collect_components(connections: dict, composition_key: str) -> list[str]:
    components = set()
    for conn in connections.values():
        if conn.get("kind") != "material":
            continue
        comp = conn.get(composition_key) or {}
        components.update(comp.keys())
    return sorted(components)

def _build_composition_table(connections: dict, composition_key: str, caption: str, label: str) -> str:
    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = conn.get("name", "")
        try:
            return (0, int(str(name)))
        except (ValueError, TypeError):
            return (1, str(name))

    material_streams.sort(key=_sort_key)
    components = _collect_components(connections, composition_key)

    if not components:
        return ""

        header = " & ".join(["Stream", *components]) + r" \\\\"
    rows = []
    for conn in material_streams:
        values = [conn.get("name", "-")]
        comp = conn.get(composition_key) or {}
        for comp_name in components:
            values.append(_format_value(comp.get(comp_name)))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * len(components)
    lines = [
        r"\\begin{table}[ht]",
        r"\\centering",
        rf"\\begin{{tabular}}{{{col_spec}}}",
        r"\\hline",
        header,
        r"\\hline",
        *rows,
        r"\\hline",
        r"\\end{tabular}",
        rf"\\caption{{{caption}}}",
        rf"\\label{{{label}}}",
        r"\\end{table}",
        "",
    ]
    return "\n".join(lines)


latex_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams.tex",
    )
)
os.makedirs(os.path.dirname(latex_output_path), exist_ok=True)
connections_data = json_payload.get("connections", {})
latex_table = _build_streams_latex_table(connections_data)
with open(latex_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(latex_table)
