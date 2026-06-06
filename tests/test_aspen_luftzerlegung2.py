import json
import os
import logging
import sys
import math

from exerpy import ExergyAnalysis

# When True, formatting helpers will avoid rounding and output full float precision.
NO_ROUNDING = True

# Get the log file path
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'parser_run_single.log'))

# Reset existing handlers and configure stdout-only logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

# When True, formatting helpers will avoid rounding and output full float precision.
NO_ROUNDING = True

# Allow overriding the model path via environment variable or first CLI argument.
# Fallback to the new model path provided by the user.
default_model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne_klein - Kopie\Single_Column_Simulation_Final.bkp"
model_path = os.environ.get('MODEL_PATH') or (sys.argv[1] if len(sys.argv) > 1 else default_model_path)

logging.info(f"Using model_path={model_path}")

ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)

# --- The body of this file mirrors test_aspen_luftzerlegung_single.py but
#     writes outputs suffixed with '2' to avoid overwriting existing files.

export_now = ean._serialize()
conns = export_now.get('connections', {})

power_keys = [k for k, c in conns.items() if isinstance(c, dict) and c.get('kind') == 'power' and (c.get('energy_flow') or c.get('E'))]
if power_keys:
    if len(power_keys) >= 4:
        fuel = {"inputs": power_keys[:3], "outputs": [power_keys[3]]}
    else:
        fuel = {"inputs": power_keys[:-1] or power_keys, "outputs": [power_keys[-1]]}
else:
    mat_keys = [k for k, c in conns.items() if isinstance(c, dict) and c.get('kind') == 'material']
    def _E_val(key):
        try:
            v = conns.get(key, {}).get('E')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    sorted_mat = sorted(mat_keys, key=_E_val, reverse=True)
    inputs = sorted_mat[:3]
    outputs = sorted_mat[3:4] or (sorted_mat[:1] if sorted_mat else [])
    fuel = {"inputs": inputs, "outputs": outputs}

material_conns = ean.list_connections_by_kind('material')
product = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('32')][:1] or material_conns[31:32]}
loss = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('28') or c.endswith('25')][:2]}

ean.analyse(E_F=fuel, E_P=product, E_L=loss)

# --- Reuse helper functions from the original test file ---
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
    if isinstance(value, str):
        sval = value.strip().lower()
        if sval in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infty"}:
            return "-"
    try:
        if isinstance(value, (int, float)) or hasattr(value, "__float__"):
            x_f = float(value)
            if not math.isfinite(x_f):
                return "-"
            if globals().get("NO_ROUNDING", False):
                s = format(x_f, ".17g")
                return s.replace(".", ",")
            x = round(x_f, 2)
            if abs(x) < 1e-9:
                return "0"
            text = f"{x:.2f}".rstrip("0").rstrip(".")
            return text.replace(".", ",") if text else "0"
    except Exception:
        return "-"
    sval = str(value).strip().lower()
    if sval in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infty"}:
        return "-"
    return _latex_escape(str(value))


def _format_molfrac_value(value):
    if value is None:
        return "-"
    if isinstance(value, str):
        sval = value.strip().lower()
        if sval in {"nan", "inf", "+inf", "-inf", "infty"}:
            return "-"
    if isinstance(value, (int, float)):
        x = float(value)
        if abs(x) < 1e-12:
            return "0"
        if globals().get("NO_ROUNDING", False):
            s = format(x, ".17g")
            return s.replace(".", ",")
        ax = abs(x)
        if ax >= 1e-2:
            text = f"{x:.4f}"
        elif ax >= 1e-4:
            text = f"{x:.6f}"
        else:
            return "<1e-6"
        if "e" not in text and "E" not in text:
            text = text.rstrip("0").rstrip(".")
            if text in {"", "-0"}:
                text = "0"
        return text.replace(".", ",")
    return _latex_escape(str(value))


def _format_value_fixed(value, ndigits: int):
    if value is None:
        return ""
    try:
        x = float(value)
        if not math.isfinite(x):
            return ""
        if globals().get("NO_ROUNDING", False):
            s = format(float(value), ".17g")
            if ndigits is not None:
                if "e" not in s and "E" not in s and "." in s:
                    intpart, frac = s.split('.', 1)
                    frac = (frac + '0' * ndigits)[:ndigits]
                    s = intpart + ('.' + frac if ndigits > 0 else '')
            return s.replace('.', ',')
        fmt = f"{x:.{ndigits}f}"
        if fmt.startswith("+"):
            fmt = fmt[1:]
        return fmt.replace('.', ',')
    except Exception:
        return ""


def _build_streams_latex_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("m", r"$\dot m$", "m_unit"),
        ("n", r"$\dot n$", "n_unit"),
        ("T", r"$T$", "T_unit"),
        ("p", r"$p$", "p_unit"),
        ("h", r"$h$", "h_unit"),
        ("s", r"$s$", "s_unit"),
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

    def _stream_value(conn: dict, key: str):
        val = conn.get(key)
        if key == "e_PH" and val is None:
            e_t = conn.get("e_T")
            e_m = conn.get("e_M")
            if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                return float(e_t) + float(e_m)
        return val

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

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
        if key == "e_PH" and not unit:
            for conn in material_streams:
                unit = conn.get("e_T_unit")
                if unit:
                    break
        unit_lookup[key] = unit or ""

    header = " & ".join(label for _, label, _ in columns) + " \\\""
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\""

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = _stream_value(conn, key)
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Thermodynamische und exergetische Kenngrößen der simulierten Prozessströme des Single-Kolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_components_work_table(connections: dict, components: dict) -> str:
    power_conns = [ (k, v) for k, v in connections.items() if isinstance(v, dict) and v.get("kind") == "power" ]
    comp_power = {}
    for name, conn in power_conns:
        val = conn.get("energy_flow") or conn.get("E")
        if not isinstance(val, (int, float)):
            continue
        comp = conn.get("source_component") or conn.get("target_component")
        if not comp:
            continue
        comp_power[comp] = comp_power.get(comp, 0.0) + float(val)

    rows = []
    for comp_name, w_val in sorted(comp_power.items()):
        if comp_name not in components and not any(str(k) == str(comp_name) for k in components.keys()):
            continue
        comp_obj = components.get(comp_name) or next((c for n, c in components.items() if str(n) == str(comp_name)), None)
        comp_type = comp_obj.__class__.__name__ if comp_obj is not None else ""
        if "turbine" in comp_type.lower() or str(comp_name).upper().startswith("T"):
            display_val = -abs(w_val)
        else:
            display_val = w_val
        rows.append(" & ".join([
            _latex_escape(str(comp_name)),
            _latex_escape(comp_type),
            _format_value(display_val),
        ]) + r" \\\")

    col_spec = "lrr"
    header = " & ".join(["Component", "Type", r"$\dot W$"]) + " " + r"\\"
    unit_row = " & ".join(["", "", "(W)"]) + " " + r"\\"
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        r"\caption{Komponenten mit Arbeitsströmen (W)} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_molar_fractions_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("mfn2", r"$x_{N_2}$", "mfn2_unit"),
        ("mfo2", r"$x_{O_2}$", "mfo2_unit"),
        ("mfco", r"$x_{CO_2}$", "mfco_unit"),
        ("mfar", r"$x_{Ar}$", "mfar_unit"),
        ("mfho", r"$x_{H_2O}$", "mfho_unit"),
    ]

    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

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

    header = " & ".join(label for _, label, _ in columns) + " \\\""
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\""

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = conn.get(key)
            values.append(_format_molfrac_value(val))
        rows.append(" & ".join(values) + r" \\\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Stoffliche Zusammensetzung der Prozessströme des Single-Kolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_component_results_table(components: dict) -> str:
    # reproduce core logic from original test to format component results
    def _power_stream_abs_inner(stream_name: str):
        conn = connections_now.get(stream_name)
        if not isinstance(conn, dict):
            return None
        val = conn.get("energy_flow")
        if isinstance(val, (int, float)):
            return abs(float(val))
        return None

    W1 = _power_stream_abs_inner("W1")
    W2 = _power_stream_abs_inner("W2")
    E_S1 = _stream_total_exergy_from_table("S1")
    if all(isinstance(v, (int, float)) for v in [W1, W2, E_S1]):
        E_F_tot = W1 + W2 + E_S1
    else:
        E_F_tot = getattr(ean, "E_F", None)

    display_items = []
    for comp_name, component in components.items():
        try:
            if component.__class__.__name__ in {"CycleCloser", "Splitter"}:
                continue
        except Exception:
            pass

        comp_class_name = component.__class__.__name__
        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        E_L = getattr(component, "E_L", None)
        epsilon = getattr(component, "epsilon", None)
        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        E_L_custom = getattr(component, "E_L_custom", None)
        epsilon_custom = getattr(component, "epsilon_custom", None)

        use_custom = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom))
        name_up = str(comp_name).strip().upper()
        if name_up == "MIX" and any(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom)):
            use_custom = True
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_epsilon = epsilon_custom if epsilon_custom is not None else ((display_E_P / display_E_F) if (display_E_F not in (None, 0)) else None)
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_epsilon = epsilon

        display_items.append((comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon))

    E_D_tot = sum(abs(v) for _, _, _, _, v, _ in display_items if isinstance(v, (int, float)))

    rows = []
    sum_E_D = 0.0
    for comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon in display_items:
        y_D_k = (display_E_D / E_F_tot) if (isinstance(display_E_D, (int, float)) and isinstance(E_F_tot, (int, float)) and E_F_tot != 0) else None
        y_D_k_star = (abs(display_E_D) / E_D_tot) if (isinstance(display_E_D, (int, float)) and E_D_tot and E_D_tot != 0) else None
        if isinstance(display_E_D, (int, float)):
            sum_E_D += display_E_D

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(str(comp_class_name)),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value_fixed(display_epsilon, 4) if display_epsilon is not None else "",
                _format_value_fixed(y_D_k, 4),
                _format_value_fixed(y_D_k_star, 4),
            ]) + " \\\")
        )

    sum_row_cells = [r"\textbf{Summe}", "", "", "", _format_value(sum_E_D), "", _format_value_fixed(None, 4), _format_value_fixed(None, 4)]

    col_spec = "l" + "l" + "r" * 6
    header = " & ".join([
        "Component",
        "Type",
        r"$\dot{E}_F$",
        r"$\dot{E}_P$",
        r"$\dot{E}_D$",
        r"$\varepsilon$",
        r"$y_{D,k}$",
        r"$y^*_{D,k}$",
    ]) + " \\\")
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)", "(-)", "(-)"]) + " \\\")

    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        "\\caption{Berechnete exergetische Kennzahlen der Komponenten des Single-Kolonnenmodells} " + r"\\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        " & ".join(sum_row_cells) + r" \\\",
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


# Minimal helpers used above that reference connection exports
def _find_conn_by_suffix(suffix: str):
    for key, conn in connections_now.items():
        name = str(conn.get("name", key))
        if name.endswith(str(suffix)) or str(key).endswith(str(suffix)):
            return conn
    return None


def _get_val(conn, key_name: str):
    if not conn:
        return None
    return conn.get(key_name)


def _get_eph_effective(conn):
    if not conn:
        return None
    eph = conn.get("e_PH")
    if eph is not None:
        return eph
    e_t = conn.get("e_T")
    e_m = conn.get("e_M")
    if e_t is not None and e_m is not None:
        return e_t + e_m
    return None


def _term_m_eph(conn):
    if not isinstance(conn, dict):
        return None
    m = conn.get("m")
    if not isinstance(m, (int, float)):
        return None
    eph = _get_eph_effective(conn)
    if isinstance(eph, (int, float)):
        return float(m) * float(eph)
    return None


def _safe_diff_mult(m, val_plus, val_minus):
    if not isinstance(m, (int, float)):
        return None
    a = float(val_plus) if isinstance(val_plus, (int, float)) else 0.0
    b = float(val_minus) if isinstance(val_minus, (int, float)) else 0.0
    return float(m) * (a - b)


def _total_from_permass(conn, key_permass: str, key_mass: str = "m"):
    if not conn:
        return None
    val_permass = conn.get(key_permass)
    mass = conn.get(key_mass)
    try:
        if val_permass is None or mass is None:
            return None
        return float(val_permass) * float(mass)
    except Exception:
        return None


def _stream_total_exergy_from_table(stream_name: str):
    conn = connections_now.get(stream_name)
    if not isinstance(conn, dict):
        for key, c in connections_now.items():
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", key))
            if name == stream_name or str(key) == stream_name:
                conn = c
                break
    if not isinstance(conn, dict):
        return None
    m_val = conn.get("m")
    e_ph = conn.get("e_PH")
    e_ch = conn.get("e_CH")
    e_ph_eff = None
    if isinstance(e_ph, (int, float)):
        e_ph_eff = float(e_ph)
    else:
        e_t = conn.get("e_T")
        e_m = conn.get("e_M")
        if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
            e_ph_eff = float(e_t) + float(e_m)
        elif isinstance(e_ch, (int, float)):
            e_ph_eff = 0.0

    if all(isinstance(v, (int, float)) for v in [m_val, e_ph_eff, e_ch]):
        return float(m_val) * (float(e_ph_eff) + float(e_ch))
    return None


# Prepare exports and call the helpers, writing suffixed files
export_data = ean._serialize()
connections_data = export_data.get("connections", {})
connections_now = connections_data

json_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung_single2.json")
)
os.makedirs(os.path.dirname(json_output_path), exist_ok=True)
json_payload = {
    "components": export_data.get("components", {}),
    "connections": export_data.get("connections", {}),
    "ambient_conditions": export_data.get("ambient_conditions", {}),
}
with open(json_output_path, "w", encoding="utf-8") as json_file:
    json.dump(json_payload, json_file, indent=4)

latex_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_streams_single2.tex")
)
os.makedirs(os.path.dirname(latex_output_path), exist_ok=True)
latex_table = _build_streams_latex_table(connections_data)
with open(latex_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(latex_table)

components_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_components_single2.tex")
)
components_table = _build_component_results_table(ean.components)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

components_work_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_components_work_single2.tex")
)
components_work_table = _build_components_work_table(connections_now, ean.components)
with open(components_work_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_work_table)

block_ed_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed_single2.tex")
)
# reuse simple block functions from single test by building minimal mapping
def _get_block_map_single() -> dict:
    return {
        "gekuehlte Luftverdichtung": ["ZK1", "LK2"],
        "Luftverdichtung": ["LK1", "ZK1", "LK2"],
        "Gasaufbereitung": ["ZK2", "GW1", "GW2"],
        "Verdichtungs- und Reinigungsblock": ["LK1", "ZK1", "LK2", "ZK2", "GW1", "GW2"],
        "Hauptwaermeuebertrager": ["MW"],
        "Rektifikation": ["KOL", "RC", "D1"],
        "Rest": ["T", "D2"],
    }


def _compute_block_ed_sums(components: dict, block_map: dict) -> dict:
    alias_map = {
        "MW": ["MW", "MH"],
        "MH": ["MH", "MW"],
        "RC": ["RC", "RECO"],
        "RC1": ["RC1", "RC", "RECO"],
        "T": ["T", "TURB"],
        "TURB": ["TURB", "T"],
    }

    def _display_ed(comp_name: str):
        candidates = alias_map.get(comp_name, [comp_name])
        component = None
        for cand in candidates:
            component = components.get(cand)
            if component is not None:
                break
        if component is None:
            return 0.0
        E_D = getattr(component, "E_D", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        if isinstance(E_D_custom, (int, float)):
            return float(E_D_custom)
        if isinstance(E_D, (int, float)):
            return float(E_D)
        return 0.0

    return {
        block_name: sum(_display_ed(name) for name in comp_list)
        for block_name, comp_list in block_map.items()
    }


block_ed_table = []
ed_sums = _compute_block_ed_sums(ean.components, _get_block_map_single())
lines = ["\\begin{longtable}{lr}", r"\\caption{Summierte Exergievernichtung der Funktionsbloecke des Single-Kolonnenmodells} \\", r"\\hline"]
for block_name in ed_sums.keys():
    lines.append(" & ".join([block_name, _format_value(ed_sums.get(block_name, 0.0))]) + r" \\\")
lines += [r"\\hline", r"\\end{longtable}"]
with open(block_ed_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write("\n".join(lines))

block_ed_comparison_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed_comparison2.tex")
)
double_block_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed.tex")
)

def _read_block_ed_table(tex_path: str) -> dict:
    result = {}
    if not os.path.exists(tex_path):
        return result
    with open(tex_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Block") or "&" not in line:
                continue
            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) != 2:
                continue
            block_name, val_raw = parts
            try:
                val_norm = val_raw.strip()
                if "," in val_norm and "." in val_norm:
                    val_norm = val_norm.replace(".", "").replace(",", ".")
                elif "," in val_norm:
                    val_norm = val_norm.replace(",", ".")
                result[block_name] = float(val_norm)
            except ValueError:
                result[block_name] = 0.0
    return result


single_sums = _compute_block_ed_sums(ean.components, _get_block_map_single())
double_sums = _read_block_ed_table(double_block_path)
rows = []
for block_name in _get_block_map_single().keys():
    s_val = single_sums.get(block_name, 0.0)
    d_val = double_sums.get(block_name, 0.0)
    rows.append(" & ".join([block_name, _format_value(s_val), _format_value(d_val)]) + r" \\\")
lines = [r"\\begin{longtable}{lrr}", r"\\caption{Summierte Exergievernichtung der Funktionsbloecke fuer Single- und Doppelkolonnenmodell} \\", r"\\hline", r"Block & Summe $\\dot{E}_D$ Single (W) & Summe $\\dot{E}_D$ Doppel (W) \\\", r"\\hline", *rows, r"\\hline", r"\\end{longtable}"]
with open(block_ed_comparison_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write("\n".join(lines))

molfractions_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_streams_molfrac_single2.tex")
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)

# End of file
import json
import os
import logging
import sys
import math

from exerpy import ExergyAnalysis

# When True, formatting helpers will avoid rounding and output full float precision.
NO_ROUNDING = True

# Get the log file path
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'parser_run_single.log'))

# Reset existing handlers and configure stdout-only logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

# When True, formatting helpers will avoid rounding and output full float precision.
NO_ROUNDING = True

# Allow overriding the model path via environment variable or first CLI argument.
# Fallback to the user-provided Aspen file.
default_model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne_klein - Kopie\Single_Column_Simulation_Final.bkp"
model_path = os.environ.get('MODEL_PATH') or (sys.argv[1] if len(sys.argv) > 1 else default_model_path)

logging.info(f"Using model_path={model_path}")

ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)

# Robust selection of E_F (fuel) connections:
# 1) Prefer explicit 'power' connections with numeric energy values
# 2) Otherwise fall back to material connections ordered by absolute exergy ('E')
export_now = ean._serialize()
conns = export_now.get('connections', {})

power_keys = [k for k, c in conns.items() if isinstance(c, dict) and c.get('kind') == 'power' and (c.get('energy_flow') or c.get('E'))]
if power_keys:
    if len(power_keys) >= 4:
        fuel = {"inputs": power_keys[:3], "outputs": [power_keys[3]]}
    else:
        fuel = {"inputs": power_keys[:-1] or power_keys, "outputs": [power_keys[-1]]}
else:
    mat_keys = [k for k, c in conns.items() if isinstance(c, dict) and c.get('kind') == 'material']
    def _E_val(key):
        try:
            v = conns.get(key, {}).get('E')
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    sorted_mat = sorted(mat_keys, key=_E_val, reverse=True)
    inputs = sorted_mat[:3]
    outputs = sorted_mat[3:4] or (sorted_mat[:1] if sorted_mat else [])
    fuel = {"inputs": inputs, "outputs": outputs}

# Select product and loss streams from available material streams (fall back to specific names if present)
material_conns = ean.list_connections_by_kind('material')
product = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('32')][:1] or material_conns[31:32]}
loss = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('28') or c.endswith('25')][:2]}

ean.analyse(E_F=fuel, E_P=product, E_L=loss)

# --- Explicit overall-system boundary check (E_F, E_P, E_L, E_D) ---
def _sum_boundary_exergy(flow_dict: dict, label: str):
    inputs = flow_dict.get("inputs", []) or []
    outputs = flow_dict.get("outputs", []) or []

    def _E(conn_name):
        conn = ean.connections.get(conn_name)
        return None if conn is None else conn.get("E")

    in_terms = [(name, _E(name)) for name in inputs]
    out_terms = [(name, _E(name)) for name in outputs]

    in_sum = sum(v for _, v in in_terms if isinstance(v, (int, float)))
    out_sum = sum(v for _, v in out_terms if isinstance(v, (int, float)))
    total = in_sum - out_sum

    logging.info(f"\n{label} boundary terms:")
    logging.info(f"  inputs : {[name for name, _ in in_terms]}")
    for name, val in in_terms:
        logging.info(f"    + {name}: E={val}")
    logging.info(f"  outputs: {[name for name, _ in out_terms]}")
    for name, val in out_terms:
        logging.info(f"    - {name}: E={val}")
    logging.info(f"  {label} = sum(inputs) - sum(outputs) = {in_sum} - {out_sum} = {total} W")
    return total


E_F_chk = _sum_boundary_exergy(fuel, "E_F")
E_P_chk = _sum_boundary_exergy(product, "E_P")
E_L_chk = _sum_boundary_exergy(loss, "E_L")
E_D_chk = None
if all(isinstance(v, (int, float)) for v in [E_F_chk, E_P_chk, E_L_chk]):
    E_D_chk = E_F_chk - E_P_chk - E_L_chk

logging.info("\nOVERALL SYSTEM CONSISTENCY CHECK:")
logging.info(f"  ean.E_F={ean.E_F}, recomputed={E_F_chk}, diff={None if E_F_chk is None else ean.E_F - E_F_chk}")
logging.info(f"  ean.E_P={ean.E_P}, recomputed={E_P_chk}, diff={None if E_P_chk is None else ean.E_P - E_P_chk}")
logging.info(f"  ean.E_L={ean.E_L}, recomputed={E_L_chk}, diff={None if E_L_chk is None else ean.E_L - E_L_chk}")
logging.info(f"  ean.E_D={ean.E_D}, recomputed={E_D_chk}, diff={None if E_D_chk is None else ean.E_D - E_D_chk}")

# --- Additional RC re-calculation and comparison (sanity check) ---
export_now = ean._serialize()
connections_now = export_now.get("connections", {})

def _power_stream_abs(stream_name: str):
    # Return absolute power/energy flow for a named power connection if present.
    conn = connections_now.get(stream_name) or ean.connections.get(stream_name)
    if not isinstance(conn, dict):
        return None
    val = conn.get("energy_flow") or conn.get("E") or conn.get("energy_flow_unit")
    if isinstance(val, (int, float)):
        return abs(float(val))
    return None

def _stream_total_exergy_from_table(stream_name: str):
    # Find connection by name/key in the exported connections and compute total exergy m*(e_PH+e_CH)
    conn = connections_now.get(stream_name)
    if not isinstance(conn, dict):
        for key, c in connections_now.items():
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", key))
            if name == stream_name or str(key) == stream_name:
                conn = c
                break
    if not isinstance(conn, dict):
        return None
    m_val = conn.get("m")
    e_ph = conn.get("e_PH")
    e_ch = conn.get("e_CH")
    e_ph_eff = None
    if isinstance(e_ph, (int, float)):
        e_ph_eff = float(e_ph)
    else:
        e_t = conn.get("e_T")
        e_m = conn.get("e_M")
        if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
            e_ph_eff = float(e_t) + float(e_m)
        elif isinstance(e_ch, (int, float)):
            e_ph_eff = 0.0

    if all(isinstance(v, (int, float)) for v in [m_val, e_ph_eff, e_ch]):
        return float(m_val) * (float(e_ph_eff) + float(e_ch))
    return None

def _find_conn_by_suffix(suffix: str):
    for key, conn in connections_now.items():
        name = str(conn.get("name", key))
        if name.endswith(str(suffix)) or str(key).endswith(str(suffix)):
            return conn
    return None

def _get_val(conn, key_name: str):
    if not conn:
        return None
    return conn.get(key_name)

def _get_eph_effective(conn):
    if not conn:
        return None
    eph = conn.get("e_PH")
    if eph is not None:
        return eph
    e_t = conn.get("e_T")
    e_m = conn.get("e_M")
    if e_t is not None and e_m is not None:
        return e_t + e_m
    return None


def _term_m_eph(conn):
    """Return total physical exergy term m * e_PH (with e_PH fallback), or None."""
    if not isinstance(conn, dict):
        return None
    m = conn.get("m")
    if not isinstance(m, (int, float)):
        return None
    eph = _get_eph_effective(conn)
    if isinstance(eph, (int, float)):
        return float(m) * float(eph)
    return None


def _safe_diff_mult(m, val_plus, val_minus):
    """Compute m*(val_plus - val_minus) using 0 for missing val_plus/val_minus if m exists.
    Returns None if mass m is missing."""
    if not isinstance(m, (int, float)):
        return None
    a = float(val_plus) if isinstance(val_plus, (int, float)) else 0.0
    b = float(val_minus) if isinstance(val_minus, (int, float)) else 0.0
    return float(m) * (a - b)

# Try to locate streams 33..36 by suffix (best-effort)
s33 = _find_conn_by_suffix("33")
s34 = _find_conn_by_suffix("34")
s35 = _find_conn_by_suffix("35")
s36 = _find_conn_by_suffix("36")

# If the model doesn't use numeric S-numbers 33..36 (single-column exports often
# use SZ25/SZ26/SZ27/SZ28), try mapping those to the 33..36 placeholders so the
# user's RC formula can still be evaluated from available streams.
if not any((s33, s34, s35, s36)):
    alt_s25 = _find_conn_by_suffix("SZ25")
    alt_s26 = _find_conn_by_suffix("SZ26")
    alt_s27 = _find_conn_by_suffix("SZ27")
    alt_s28 = _find_conn_by_suffix("SZ28")
    # map: s33 <- SZ25, s34 <- SZ26, s35 <- SZ27, s36 <- SZ28 (best-effort)
    if alt_s25 is not None and s33 is None:
        s33 = alt_s25
    if alt_s26 is not None and s34 is None:
        s34 = alt_s26
    if alt_s27 is not None and s35 is None:
        s35 = alt_s27
    if alt_s28 is not None and s36 is None:
        s36 = alt_s28

ep_calc = None
ef_calc = None
ed_calc = None
tol = 1e-6

if s34 and s35:
    et34 = _get_val(s34, "e_T") or 0.0
    et35 = _get_val(s35, "e_T") or 0.0
    ep_calc = et34 - et35

if s35 and s36 and s33 and s34:
    eph35 = _get_val(s35, "e_PH") or 0.0
    eph36 = _get_val(s36, "e_PH") or 0.0
    em33 = _get_val(s33, "e_M") or 0.0
    em34 = _get_val(s34, "e_M") or 0.0
    ef_calc = eph35 - eph36 + em33 - em34

if ep_calc is not None and ef_calc is not None:
    ed_calc = ef_calc - ep_calc

# Locate RC component (by name or prefix)
rc_comp = ean.components.get("RC") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC")), None)

E_P_comp = getattr(rc_comp, "E_P", None) if rc_comp else None
E_F_comp = getattr(rc_comp, "E_F", None) if rc_comp else None
E_D_comp = getattr(rc_comp, "E_D", None) if rc_comp else None
eps_comp = getattr(rc_comp, "epsilon", None) if rc_comp else None

logging.info("\nAdditional RC re-calculation check:")
logging.info(f"  Calculated -> Ep={ep_calc}, Ef={ef_calc}, Ed={ed_calc}")
logging.info(f"  Component  -> Ep={E_P_comp}, Ef={E_F_comp}, Ed={E_D_comp}")

def _cmp(a, b):
    if a is None or b is None:
        return False
    try:
        return abs(a - b) <= tol
    except Exception:
        return False

if E_P_comp is not None and ep_calc is not None:
    logging.info("  Ep match: " + ("YES" if _cmp(E_P_comp, ep_calc) else f"NO (diff={E_P_comp - ep_calc:.6g})"))
else:
    logging.info("  Ep match: N/A (missing values)")

if E_F_comp is not None and ef_calc is not None:
    logging.info("  Ef match: " + ("YES" if _cmp(E_F_comp, ef_calc) else f"NO (diff={E_F_comp - ef_calc:.6g})"))
else:
    logging.info("  Ef match: N/A (missing values)")

if E_D_comp is not None and ed_calc is not None:
    logging.info("  Ed match: " + ("YES" if _cmp(E_D_comp, ed_calc) else f"NO (diff={E_D_comp - ed_calc:.6g})"))
else:
    logging.info("  Ed match: N/A (missing values)")

# Compare epsilon if possible (epsilon = Ep / Ef if Ef != 0)
eps_calc = None
if ef_calc:
    try:
        eps_calc = ep_calc / ef_calc if ef_calc != 0 else None
    except Exception:
        eps_calc = None

logging.info(f"  epsilon -> comp={eps_comp}, calc={eps_calc}")
if eps_comp is not None and eps_calc is not None:
    logging.info("  epsilon match: " + ("YES" if _cmp(eps_comp, eps_calc) else f"NO (diff={eps_comp - eps_calc:.6g})"))
else:
    logging.info("  epsilon match: N/A (missing values)")

# --- Recompute using total flows (convert per-mass [J/kg] -> total [W] by multiplying with mass flow [kg/s])
def _total_from_permass(conn, key_permass: str, key_mass: str = "m"):
    if not conn:
        return None
    val_permass = conn.get(key_permass)
    mass = conn.get(key_mass)
    try:
        if val_permass is None or mass is None:
            return None
        return float(val_permass) * float(mass)
    except Exception:
        return None

et34_tot = _total_from_permass(s34, "e_T")
et35_tot = _total_from_permass(s35, "e_T")
eph35_tot = _total_from_permass(s35, "e_PH")
eph36_tot = _total_from_permass(s36, "e_PH")
em33_tot = _total_from_permass(s33, "e_M")
em34_tot = _total_from_permass(s34, "e_M")

ep_calc_tot = None
ef_calc_tot = None
ed_calc_tot = None

if et34_tot is not None and et35_tot is not None:
    ep_calc_tot = et34_tot - et35_tot

if eph35_tot is not None and eph36_tot is not None and em33_tot is not None and em34_tot is not None:
    ef_calc_tot = eph35_tot - eph36_tot + em33_tot - em34_tot

if ep_calc_tot is not None and ef_calc_tot is not None:
    ed_calc_tot = ef_calc_tot - ep_calc_tot

logging.info("\nRecomputed totals (J/kg * m [kg/s] -> W):")
logging.info(f"  Totals -> Ep={ep_calc_tot}, Ef={ef_calc_tot}, Ed={ed_calc_tot}")
if E_P_comp is not None and ep_calc_tot is not None:
    logging.info("  Ep (tot) match: " + ("YES" if _cmp(E_P_comp, ep_calc_tot) else f"NO (diff={E_P_comp - ep_calc_tot:.6g})"))
else:
    logging.info("  Ep (tot) match: N/A (missing values)")

if E_F_comp is not None and ef_calc_tot is not None:
    logging.info("  Ef (tot) match: " + ("YES" if _cmp(E_F_comp, ef_calc_tot) else f"NO (diff={E_F_comp - ef_calc_tot:.6g})"))
else:
    logging.info("  Ef (tot) match: N/A (missing values)")

if E_D_comp is not None and ed_calc_tot is not None:
    logging.info("  Ed (tot) match: " + ("YES" if _cmp(E_D_comp, ed_calc_tot) else f"NO (diff={E_D_comp - ed_calc_tot:.6g})"))
else:
    logging.info("  Ed (tot) match: N/A (missing values)")

eps_calc_tot = None
if ef_calc_tot:
    try:
        eps_calc_tot = ep_calc_tot / ef_calc_tot if ef_calc_tot != 0 else None
    except Exception:
        eps_calc_tot = None

logging.info(f"  epsilon -> comp={eps_comp}, calc_tot={eps_calc_tot}")
if eps_comp is not None and eps_calc_tot is not None:
    logging.info("  epsilon (tot) match: " + ("YES" if _cmp(eps_comp, eps_calc_tot) else f"NO (diff={eps_comp - eps_calc_tot:.6g})"))
else:
    logging.info("  epsilon (tot) match: N/A (missing values)")

# --- Condensation thermal exergy: Ep as difference of E_T totals for streams 33 and 34
# Use best-effort fallbacks: treat missing per-term totals as 0 when at least one term exists
et33_tot_raw = _total_from_permass(s33, "e_T")
et34_tot_raw = _total_from_permass(s34, "e_T")
ep_condens_tot = None
if et33_tot_raw is not None or et34_tot_raw is not None:
    et33_tot = float(et33_tot_raw or 0.0)
    et34_tot = float(et34_tot_raw or 0.0)
    # difference (non-negative): larger - smaller
    ep_condens_tot = abs(et33_tot - et34_tot)

logging.info("\nCondensation thermal exergy (E_T) comparison:")
# prepare display-friendly values (handle missing/raw vs computed)
display_et33 = None
display_et34 = None
if 'et33_tot' in locals():
    display_et33 = et33_tot
elif et33_tot_raw is not None:
    try:
        display_et33 = float(et33_tot_raw)
    except Exception:
        display_et33 = et33_tot_raw
if 'et34_tot' in locals():
    display_et34 = et34_tot
elif et34_tot_raw is not None:
    try:
        display_et34 = float(et34_tot_raw)
    except Exception:
        display_et34 = et34_tot_raw
logging.info(f"  E_T33 = {display_et33}, E_T34 = {display_et34}, Ep_condensation = {ep_condens_tot}")
if E_P_comp is not None and ep_condens_tot is not None:
    logging.info("  Ep_cond match: " + ("YES" if _cmp(E_P_comp, ep_condens_tot) else f"NO (diff={E_P_comp - ep_condens_tot:.6g})"))
else:
    logging.info("  Ep_cond match: N/A (missing values)")

# --- Ef per user's spec:
#  - physical exergy difference of reboiler streams 35 and 36 (non-negative)
#  - plus mechanical exergy difference of 33 and 34 (non-negative, represents pressure loss)
# Best-effort: compute available diffs treating missing terms as 0 if at least one term exists
eph35_tot_raw = _total_from_permass(s35, "e_PH")
eph36_tot_raw = _total_from_permass(s36, "e_PH")
em33_tot_raw = _total_from_permass(s33, "e_M")
em34_tot_raw = _total_from_permass(s34, "e_M")

phys_diff = None
mech_diff = None
ef_custom = None

if eph35_tot_raw is not None or eph36_tot_raw is not None:
    a = float(eph35_tot_raw or 0.0)
    b = float(eph36_tot_raw or 0.0)
    phys_diff = abs(a - b)

if em33_tot_raw is not None or em34_tot_raw is not None:
    a = float(em33_tot_raw or 0.0)
    b = float(em34_tot_raw or 0.0)
    mech_diff = abs(a - b)

# If at least one diff is available, use sum (missing part treated as 0)
if phys_diff is not None or mech_diff is not None:
    ef_custom = (phys_diff or 0.0) + (mech_diff or 0.0)

logging.info("\nEf (user formula) breakdown:")
logging.info(f"  phys | E_PH35 = {eph35_tot}, E_PH36 = {eph36_tot}, phys_diff = {phys_diff}")
logging.info(f"  mech | E_M33 = {em33_tot}, E_M34 = {em34_tot}, mech_diff = {mech_diff}")
logging.info(f"  Ef_custom = {ef_custom}")
if E_F_comp is not None and ef_custom is not None:
    logging.info("  Ef_custom match: " + ("YES" if _cmp(E_F_comp, ef_custom) else f"NO (diff={E_F_comp - ef_custom:.6g})"))
else:
    logging.info("  Ef_custom match: N/A (missing values)")

# --- Compute Ed from user's Ep/Ef and compare to RC.E_D
ed_custom = None
if ef_custom is not None and ep_condens_tot is not None:
    ed_custom = ef_custom - ep_condens_tot

logging.info("\nCUSTOM ED CHECK:")
logging.info(f"  Ep_cond = {ep_condens_tot}")
logging.info(f"  Ef_custom = {ef_custom}")
logging.info(f"  Ed_custom = {ed_custom}")
if E_D_comp is not None and ed_custom is not None:
    logging.info("  Ed match (component vs custom): " + ("YES" if _cmp(E_D_comp, ed_custom) else f"NO (diff={E_D_comp - ed_custom:.6g})"))
else:
    logging.info("  Ed match: N/A (missing values)")

# Attach custom values to RC component object (so tables/logs can access them)
if rc_comp is not None:
    try:
        rc_comp.E_P_custom = ep_condens_tot
        rc_comp.E_F_custom = ef_custom
        rc_comp.E_D_custom = ed_custom
        rc_comp.epsilon_custom = (ep_condens_tot / ef_custom) if (ef_custom and ef_custom != 0) else None
    except Exception:
        pass

# Helper: concise comparison log for a component and its custom values
def _log_component_custom_compare(name: str, comp):
    if comp is None:
        logging.info(f"{name}: component not found")
        return
    E_F = getattr(comp, 'E_F', None)
    E_P = getattr(comp, 'E_P', None)
    E_D = getattr(comp, 'E_D', None)
    E_L = getattr(comp, 'E_L', None)
    E_F_c = getattr(comp, 'E_F_custom', None)
    E_P_c = getattr(comp, 'E_P_custom', None)
    E_D_c = getattr(comp, 'E_D_custom', None)
    E_L_c = getattr(comp, 'E_L_custom', None)
    eps = getattr(comp, 'epsilon', None)
    eps_c = getattr(comp, 'epsilon_custom', None)

    logging.info("\n--- Compact comparison for %s ---" % name)
    logging.info(f"component | E_F={E_F} W | E_P={E_P} W | E_D={E_D} W | E_L={E_L} W | eps={eps}")
    logging.info(f"custom    | E_F={E_F_c} W | E_P={E_P_c} W | E_D={E_D_c} W | E_L={E_L_c} W | eps={eps_c}")
    if E_D is not None and E_D_c is not None:
        logging.info("Ed equal: " + ("YES" if _cmp(E_D, E_D_c) else f"NO (diff={E_D - E_D_c:.6g})"))
    else:
        logging.info("Ed equal: N/A")


# --- Formatting and LaTeX helpers (copied from original test)
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
    # Treat None as missing
    if value is None:
        return "-"

    # Normalize common textual non-numeric markers (e.g. 'nan', 'inf')
    if isinstance(value, str):
        sval = value.strip().lower()
        if sval in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infty"}:
            return "-"

    # If it's a numeric type, handle finiteness and formatting
    # Accept numpy numeric types and other number-like objects by coercing to float
    try:
        # Coerce to float where possible
        if isinstance(value, (int, float)) or hasattr(value, "__float__"):
            x_f = float(value)
            if not math.isfinite(x_f):
                return "-"
            # Allow optional full-precision output when requested
            if globals().get("NO_ROUNDING", False):
                s = format(x_f, ".17g")
                return s.replace(".", ",")
            # Thesis table formatting: no scientific notation and at most two decimals.
            x = round(x_f, 2)
            if abs(x) < 1e-9:
                return "0"
            text = f"{x:.2f}".rstrip("0").rstrip(".")
            return text.replace(".", ",") if text else "0"
    except Exception:
        return "-"

    # Fallback: if object is non-numeric, attempt to detect textual nan/inf inside its string form
    sval = str(value).strip().lower()
    if sval in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infty"}:
        return "-"
    return _latex_escape(str(value))


def _format_molfrac_value(value):
    if value is None:
        return "-"
    # Treat textual 'nan' or 'inf' as missing
    if isinstance(value, str):
        sval = value.strip().lower()
        if sval in {"nan", "inf", "+inf", "-inf", "infty"}:
            return "-"
    if isinstance(value, (int, float)):
        x = float(value)
        if abs(x) < 1e-12:
            return "0"
        if globals().get("NO_ROUNDING", False):
            s = format(x, ".17g")
            return s.replace(".", ",")
        # Composition formatting by magnitude for readable thesis tables.
        ax = abs(x)
        if ax >= 1e-2:
            text = f"{x:.4f}"
        elif ax >= 1e-4:
            text = f"{x:.6f}"
        else:
            return "<1e-6"

        # Remove trailing zeros for non-scientific notation.
        if "e" not in text and "E" not in text:
            text = text.rstrip("0").rstrip(".")
            if text in {"", "-0"}:
                text = "0"

        return text.replace(".", ",")
    return _latex_escape(str(value))


def _format_value_fixed(value, ndigits: int):
    """Format a numeric value with a fixed number of decimals (no scientific notation).

    Returns a string with a comma as decimal separator. Caller may pass None and
    should handle it if desired.
    """
    if value is None:
        return ""
    try:
        x = float(value)
        if not math.isfinite(x):
            return ""
        if globals().get("NO_ROUNDING", False):
            s = format(x, ".17g")
            # If caller expects fixed digits, honor ndigits for fractional part when possible
            if ndigits is not None:
                if "e" not in s and "E" not in s and "." in s:
                    intpart, frac = s.split('.', 1)
                    frac = (frac + '0' * ndigits)[:ndigits]
                    s = intpart + ('.' + frac if ndigits > 0 else '')
            return s.replace('.', ',')
        fmt = f"{x:.{ndigits}f}"
        # Remove leading + sign if any, keep negative sign
        if fmt.startswith("+"):
            fmt = fmt[1:]
        return fmt.replace('.', ',')
    except Exception:
        return ""


def _build_streams_latex_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("m", r"$\dot m$", "m_unit"),
        ("n", r"$\dot n$", "n_unit"),
        ("T", r"$T$", "T_unit"),
        ("p", r"$p$", "p_unit"),
        ("h", r"$h$", "h_unit"),
        ("s", r"$s$", "s_unit"),
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

    def _stream_value(conn: dict, key: str):
        # Aspen exports sometimes leave e_PH empty while e_T and e_M are available.
        # In this case, reconstruct e_PH = e_T + e_M for the LaTeX table output.
        val = conn.get(key)
        if key == "e_PH" and val is None:
            e_t = conn.get("e_T")
            e_m = conn.get("e_M")
            if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                return float(e_t) + float(e_m)
        return val

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

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
        if key == "e_PH" and not unit:
            for conn in material_streams:
                unit = conn.get("e_T_unit")
                if unit:
                    break
        unit_lookup[key] = unit or ""

    header = " & ".join(label for _, label, _ in columns) + " \\\""
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\""

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = _stream_value(conn, key)
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Thermodynamische und exergetische Kenngrößen der simulierten Prozessströme des Single-Kolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_components_work_table(connections: dict, components: dict) -> str:
    # Similar work-table builder for the single-column model
    power_conns = [ (k, v) for k, v in connections.items() if isinstance(v, dict) and v.get("kind") == "power" ]
    comp_power = {}
    for name, conn in power_conns:
        val = conn.get("energy_flow") or conn.get("E")
        if not isinstance(val, (int, float)):
            continue
        comp = conn.get("source_component") or conn.get("target_component")
        if not comp:
            continue
        comp_power[comp] = comp_power.get(comp, 0.0) + float(val)

    rows = []
    for comp_name, w_val in sorted(comp_power.items()):
        if comp_name not in components and not any(str(k) == str(comp_name) for k in components.keys()):
            continue
        comp_obj = components.get(comp_name) or next((c for n, c in components.items() if str(n) == str(comp_name)), None)
        comp_type = comp_obj.__class__.__name__ if comp_obj is not None else ""
        if "turbine" in comp_type.lower() or str(comp_name).upper().startswith("T"):
            display_val = -abs(w_val)
        else:
            display_val = w_val
        rows.append(" & ".join([
            _latex_escape(str(comp_name)),
            _latex_escape(comp_type),
            _format_value(display_val),
        ]) + r" \\\")

    col_spec = "lrr"
    header = " & ".join(["Component", "Type", r"$\dot W$"]) + " " + r"\\\"
    unit_row = " & ".join(["", "", "(W)"]) + " " + r"\\\"
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        r"\caption{Komponenten mit Arbeitsströmen (W)} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_molar_fractions_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("mfn2", r"$x_{N_2}$", "mfn2_unit"),
        ("mfo2", r"$x_{O_2}$", "mfo2_unit"),
        ("mfco", r"$x_{CO_2}$", "mfco_unit"),
        ("mfar", r"$x_{Ar}$", "mfar_unit"),
        ("mfho", r"$x_{H_2O}$", "mfho_unit"),
    ]

    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

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

    header = " & ".join(label for _, label, _ in columns) + " \\\""
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\""

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = conn.get(key)
            values.append(_format_molfrac_value(val))
        rows.append(" & ".join(values) + r" \\\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Stoffliche Zusammensetzung der Prozessströme des Single-Kolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_component_results_table(components: dict) -> str:
    # keep original column layout; we'll inject custom values into the standard columns
    # compute E_F_tot from available power/material streams for y calculation
    W1 = _power_stream_abs("W1")
    W2 = _power_stream_abs("W2")
    E_S1 = _stream_total_exergy_from_table("S1")
    if all(isinstance(v, (int, float)) for v in [W1, W2, E_S1]):
        E_F_tot = W1 + W2 + E_S1
    else:
        E_F_tot = getattr(ean, "E_F", None)

    rows = []
    # Header and units for component results table (E_L removed)
    header = " & ".join([
        "Component",
        "Type",
        r"$\dot{E}_F$",
        r"$\dot{E}_P$",
        r"$\dot{E}_D$",
        r"$\varepsilon$",
        r"$y_{D,k}$",
        r"$y^*_{D,k}$",
    ]) + " \\\""
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)", "(-)", "(-)"]) + " \\\""
    # Support two input formats:
    # - runtime component objects (component instances with attributes)
    # - exported component dicts (as produced by ean._serialize())
    # two-pass: collect display values first (need total absolute E_D for y* normalization)
    display_items = []
    for comp_name, component in components.items():
        # Skip CycleCloser/Splitter and RECON as before
        name_key = str(comp_name).strip()
        if name_key.upper() == "RECON":
            continue

        # Determine if this entry is an exported dict
        if isinstance(component, dict):
            comp_type = component.get("type") or component.get("__class__", "")
            ex = component.get("exergy_results", {}) or {}
            E_F = ex.get("E_F")
            E_P = ex.get("E_P")
            E_D = ex.get("E_D")
            epsilon = ex.get("epsilon")
            comp_class_name = comp_type
            # custom overrides (not present in exported dicts)
            E_F_custom = None
            E_P_custom = None
            E_D_custom = None
            E_L_custom = None
            epsilon_custom = None
        else:
            # runtime object path
            if component.__class__.__name__ in {"CycleCloser", "Splitter"}:
                continue
            comp_class_name = component.__class__.__name__
            E_F = getattr(component, "E_F", None)
            E_P = getattr(component, "E_P", None)
            E_D = getattr(component, "E_D", None)
            E_L = getattr(component, "E_L", None)
            epsilon = getattr(component, "epsilon", None)
            E_F_custom = getattr(component, "E_F_custom", None)
            E_P_custom = getattr(component, "E_P_custom", None)
            E_D_custom = getattr(component, "E_D_custom", None)
            E_L_custom = getattr(component, "E_L_custom", None)
            epsilon_custom = getattr(component, "epsilon_custom", None)

        # Use custom display values only when custom triplet is numeric and finite
        use_custom = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom))
        # Special-case: for MIX enforce use of custom values if any custom value was computed
        try:
            name_up = str(comp_name).strip().upper()
        except Exception:
            name_up = ""
        if name_up == "MIX" and any(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom)):
            use_custom = True
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_E_L = E_L_custom if E_L_custom is not None else 0.0
            if epsilon_custom is not None:
                display_epsilon = epsilon_custom
            else:
                display_epsilon = (display_E_P / display_E_F) if (display_E_F not in (None, 0)) else None
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_E_L = E_L if 'E_L' in locals() and E_L is not None else 0.0
            display_epsilon = epsilon

        # collect for second pass (E_L omitted)
        display_items.append((comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon))

    # compute total absolute E_D for y* normalization
    E_D_tot = sum(abs(v) for _, _, _, _, v, _ in display_items if isinstance(v, (int, float)))

    rows = []
    sum_E_D = 0.0
    sum_y = 0.0
    sum_y_star = 0.0
    for comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon in display_items:
        y_D_k = (display_E_D / E_F_tot) if (
            isinstance(display_E_D, (int, float)) and isinstance(E_F_tot, (int, float)) and E_F_tot != 0
        ) else None
        y_D_k_star = (abs(display_E_D) / E_D_tot) if (isinstance(display_E_D, (int, float)) and E_D_tot and E_D_tot != 0) else None

        if isinstance(display_E_D, (int, float)):
            sum_E_D += display_E_D
        # E_L column removed; no accumulation here
        if isinstance(y_D_k, (int, float)):
            sum_y += y_D_k
        if isinstance(y_D_k_star, (int, float)):
            sum_y_star += y_D_k_star

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(str(comp_class_name)),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value_fixed(display_epsilon, 4) if display_epsilon is not None else "",
                _format_value_fixed(y_D_k, 4),
                _format_value_fixed(y_D_k_star, 4),
            ]) + " \\\")
        )

    # sum row (only E_D, y_D_k, y*_D_k) — E_L removed
    sum_row_cells = [r"\textbf{Summe}", "", "", "", _format_value(sum_E_D), "", _format_value_fixed(sum_y, 4), _format_value_fixed(sum_y_star, 4)]

    col_spec = "l" + "l" + "r" * 6
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        "\\caption{Berechnete exergetische Kennzahlen der Komponenten des Single-Kolonnenmodells} " + r"\\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        " & ".join(sum_row_cells) + r" \\\",
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_global_check_table(components: dict) -> str:
    def _find_stream_conn(stream_name: str):
        conn_direct = ean.connections.get(stream_name)
        if isinstance(conn_direct, dict):
            return conn_direct
        for key, conn in ean.connections.items():
            if not isinstance(conn, dict):
                continue
            name = str(conn.get("name", key))
            if name == stream_name or str(key) == stream_name:
                return conn
        return None

    def _stream_total_exergy_from_table(stream_name: str):
        conn = _find_stream_conn(stream_name)
        if not isinstance(conn, dict):
            return None
        m_val = conn.get("m")
        e_ph = conn.get("e_PH")
        e_ch = conn.get("e_CH")
        e_ph_eff = None
        if isinstance(e_ph, (int, float)):
            e_ph_eff = float(e_ph)
        else:
            e_t = conn.get("e_T")
            e_m = conn.get("e_M")
            if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                e_ph_eff = float(e_t) + float(e_m)
            elif isinstance(e_ch, (int, float)):
                e_ph_eff = 0.0

        if all(isinstance(v, (int, float)) for v in [m_val, e_ph_eff, e_ch]):
            return float(m_val) * (float(e_ph_eff) + float(e_ch))
        return None

    display_by_name = {}
    for comp_name, component in components.items():
        if component.__class__.__name__ == "CycleCloser":
            continue
        if str(comp_name).strip().upper() == "RECON":
            continue

        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        E_L = getattr(component, "E_L", None)

        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        E_L_custom = getattr(component, "E_L_custom", None)

        use_custom = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom))
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_E_L = E_L_custom if E_L_custom is not None else 0.0
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            # Default: component attribute E_L if present
            display_E_L = E_L if E_L is not None else 0.0
            # But prefer system-exiting outlet streams for component E_L when available
            try:
                comp_name_str = str(comp_name)
                comp_exit_el = 0.0
                for sname, conn in connections_now.items():
                    if not isinstance(conn, dict):
                        continue
                    # check source component and target component fields (robust keys)
                    src = conn.get("source_component") or conn.get("source") or conn.get("from")
                    tgt = conn.get("target_component") or conn.get("target") or conn.get("to")
                    if src is None:
                        continue
                    try:
                        src_str = str(src).strip()
                    except Exception:
                        src_str = ""
                    # if this connection originates from this component and has no target -> system exit
                    if src_str == comp_name_str and not tgt:
                        # determine total exergy flow for this stream
                        val = conn.get("E") or conn.get("energy_flow")
                        if not isinstance(val, (int, float)):
                            m_val = conn.get("m")
                            e_ph = conn.get("e_PH")
                            e_ch = conn.get("e_CH")
                            e_ph_eff = None
                            if isinstance(e_ph, (int, float)):
                                e_ph_eff = float(e_ph)
                            else:
                                e_t = conn.get("e_T")
                                e_m = conn.get("e_M")
                                if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                                    e_ph_eff = float(e_t) + float(e_m)
                                elif isinstance(e_ch, (int, float)):
                                    e_ph_eff = 0.0
                            if all(isinstance(v, (int, float)) for v in [m_val, e_ph_eff, e_ch]):
                                val = float(m_val) * (float(e_ph_eff) + float(e_ch))
                        if isinstance(val, (int, float)):
                            comp_exit_el += float(val)
                if comp_exit_el > 0:
                    display_E_L = comp_exit_el
            except Exception:
                pass

        display_by_name[str(comp_name)] = {
            "E_F": display_E_F,
            "E_P": display_E_P,
            "E_D": display_E_D,
            "E_L": display_E_L,
        }

    sum_E_D_table = sum(
        data["E_D"] for data in display_by_name.values()
        if isinstance(data.get("E_D"), (int, float))
    )
    def _power_stream_abs(stream_name: str):
        conn = _find_stream_conn(stream_name)
        if not isinstance(conn, dict):
            return None
        val = conn.get("energy_flow")
        if isinstance(val, (int, float)):
            return abs(float(val))
        return None

    W1 = _power_stream_abs("W1")
    W2 = _power_stream_abs("W2")
    W3 = _power_stream_abs("W3")

    E_S1 = _stream_total_exergy_from_table("S1")

    product_stream = "S24"
    E_product = _stream_total_exergy_from_table(product_stream)

    W_T = W3
    if W_T is None:
        turb_comp = (
            components.get("TURB")
            or components.get("T")
            or next((c for n, c in components.items() if str(n).strip().upper() in {"TURB", "T"}), None)
        )
        if turb_comp is not None:
            P_val = getattr(turb_comp, "P", None)
            if isinstance(P_val, (int, float)):
                W_T = abs(P_val)
        if W_T is None:
            turb_data = display_by_name.get("TURB") or display_by_name.get("T") or {}
            W_T = turb_data.get("E_P")

    loss_streams = ["S7", "S9", "S10", "S21"]
    loss_terms = [(_name, _stream_total_exergy_from_table(_name)) for _name in loss_streams]
    sum_E_L_total = sum(v for _, v in loss_terms if isinstance(v, (int, float)))

    E_F_comp = None
    if isinstance(W1, (int, float)) and isinstance(W2, (int, float)):
        E_F_comp = W1 + W2

    E_in = None
    if isinstance(E_F_comp, (int, float)) and isinstance(E_S1, (int, float)):
        E_in = E_F_comp + E_S1

    sum_out = None
    if all(isinstance(v, (int, float)) for v in [E_product, W_T, sum_E_D_table, sum_E_L_total]):
        sum_out = E_product + W_T + sum_E_D_table + sum_E_L_total

    balance_diff = None
    if isinstance(E_in, (int, float)) and isinstance(sum_out, (int, float)):
        balance_diff = E_in - sum_out

    balance_diff_pct = None
    if isinstance(balance_diff, (int, float)) and isinstance(E_in, (int, float)) and E_in != 0:
        balance_diff_pct = 100.0 * balance_diff / E_in

    def _format_int_de(value):
        if not isinstance(value, (int, float)):
            return "-"
        try:
            if not math.isfinite(value):
                return "-"
            if globals().get("NO_ROUNDING", False):
                s = format(float(value), ".17g")
                return s.replace(".", ",")
            return f"{int(round(value)):,}"
        except Exception:
            return "-"

    def _format_pct_de(value):
        if not isinstance(value, (int, float)):
            return "-"
        if globals().get("NO_ROUNDING", False):
            s = format(float(value), ".17g")
            return s.replace(".", ",")
        return f"{value:.2f}".replace(".", ",")

    delta_text = "-"
    if isinstance(balance_diff, (int, float)) and isinstance(balance_diff_pct, (int, float)):
        delta_text = f"{_format_int_de(balance_diff)} ({_format_pct_de(balance_diff_pct)} \\%)"

    row_end = r"\\"
    lines = [
        r"\\begin{longtable}{llr | llr}",
        r"\caption{Exergetische Bilanz des Gesamtsystems des Single-Kolonnenmodells} " + row_end,
        r"\\hline",
        r"\\multicolumn{3}{l|}{\textbf{Exergetischer Aufwand ($E_{in}$)}} & \\multicolumn{3}{l}{\textbf{Exergetischer Verbleib}} " + row_end,
        r"\\hline",
        r"Posten & Quelle & Wert (W) & Posten & Typ & Wert (W) " + row_end,
        r"\\hline",
        f"Strom 1 & $\\dot{{E}}_{{S1}}$ & {_format_int_de(E_S1)} & Produkt N2 & $\\dot{{E}}_{{{product_stream}}}$ & {_format_int_de(E_product)} " + row_end,
        f"Verdichtung & $\\dot{{W}}_1 + \\dot{{W}}_2$ & {_format_int_de(E_F_comp)} & Turbinenarbeit & $\\dot{{W}}_3$ & {_format_int_de(W_T)} " + row_end,
        f" &  &  & Exerget. Vernichtung & $\\sum \\dot{{E}}_{{D,k}}$ & {_format_int_de(sum_E_D_table)} " + row_end,
        f" &  &  & Austrittsverluste & $\\dot{{E}}_{{S7}}+\\dot{{E}}_{{S9}}+\\dot{{E}}_{{S10}}+\\dot{{E}}_{{S21}}$ & {_format_int_de(sum_E_L_total)} " + row_end,
        r"\\hline",
        f"\\textbf{{Summe Ein}} &  & \\textbf{{{_format_int_de(E_in)}}} & \\textbf{{Summe Aus}} &  & \\textbf{{{_format_int_de(sum_out)}}} " + row_end,
        r"\\hline",
        f"\\multicolumn{{3}}{{l}}{{}} & \\textbf{{Differenz ($\\Delta$)}} &  & \\textbf{{{delta_text}}} " + row_end,
        r"\\hline",
        r"\\end{longtable}",
    ]
    return "\n".join(lines)


def _get_block_map_single() -> dict:
    return {
        "gekuehlte Luftverdichtung": ["ZK1", "LK2"],
        "Luftverdichtung": ["LK1", "ZK1", "LK2"],
        "Gasaufbereitung": ["ZK2", "GW1", "GW2"],
        "Verdichtungs- und Reinigungsblock": ["LK1", "ZK1", "LK2", "ZK2", "GW1", "GW2"],
        "Hauptwaermeuebertrager": ["MW"],
        "Rektifikation": ["KOL", "RC", "D1"],
        "Rest": ["T", "D2"],
    }


def _compute_block_ed_sums(components: dict, block_map: dict) -> dict:
    alias_map = {
        "MW": ["MW", "MH"],
        "MH": ["MH", "MW"],
        "RC": ["RC", "RECO"],
        "RC1": ["RC1", "RC", "RECO"],
        "T": ["T", "TURB"],
        "TURB": ["TURB", "T"],
    }

    def _display_ed(comp_name: str):
        candidates = alias_map.get(comp_name, [comp_name])

        component = None
        for cand in candidates:
            component = components.get(cand)
            if component is not None:
                break

        if component is None:
            return 0.0

        E_D = getattr(component, "E_D", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        if isinstance(E_D_custom, (int, float)):
            return float(E_D_custom)
        if isinstance(E_D, (int, float)):
            return float(E_D)
        return 0.0

    return {
        block_name: sum(_display_ed(name) for name in comp_list)
        for block_name, comp_list in block_map.items()
    }


def _build_block_ed_table(components: dict) -> str:
    block_map = _get_block_map_single()
    ed_sums = _compute_block_ed_sums(components, block_map)

    rows = []
    for block_name in block_map.keys():
        rows.append(" & ".join([block_name, _format_value(ed_sums.get(block_name, 0.0))]) + r" \\\")

    lines = [
        r"\\begin{longtable}{lr}",
        r"\\caption{Summierte Exergievernichtung der Funktionsbloecke des Single-Kolonnenmodells} \\",
        r"\\hline",
        r"Block & Summe $\\dot{E}_D$ (W) \\",
        r"\\hline",
        *rows,
        r"\\hline",
        r"\\end{longtable}",
    ]
    return "\n".join(lines)


def _read_block_ed_table(tex_path: str) -> dict:
    result = {}
    if not os.path.exists(tex_path):
        return result

    with open(tex_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Block") or "&" not in line:
                continue

            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) != 2:
                continue

            block_name, val_raw = parts
            try:
                val_norm = val_raw.strip()
                if "," in val_norm and "." in val_norm:
                    val_norm = val_norm.replace(".", "").replace(",", ".")
                elif "," in val_norm:
                    val_norm = val_norm.replace(",", ".")
                result[block_name] = float(val_norm)
            except ValueError:
                result[block_name] = 0.0

    return result


def _build_block_ed_comparison_table(single_sums: dict, double_sums: dict) -> str:
    ordered_blocks = list(_get_block_map_single().keys())
    rows = []
    for block_name in ordered_blocks:
        s_val = single_sums.get(block_name, 0.0)
        d_val = double_sums.get(block_name, 0.0)
        rows.append(" & ".join([block_name, _format_value(s_val), _format_value(d_val)]) + r" \\\")

    lines = [
        r"\\begin{longtable}{lrr}",
        r"\\caption{Summierte Exergievernichtung der Funktionsbloecke fuer Single- und Doppelkolonnenmodell} \\",
        r"\\hline",
        r"Block & Summe $\\dot{E}_D$ Single (W) & Summe $\\dot{E}_D$ Doppel (W) \\",
        r"\\hline",
        *rows,
        r"\\hline",
        r"\\end{longtable}",
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
        rows.append(" & ".join(values) + r" \\\")

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


# Export JSON in the same structure as examples/json_example/example.json (suffixed with 2)
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung_single2.json")
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
export_data = ean._serialize()
json_payload = {
    "components": export_data.get("components", {}),
    "connections": export_data.get("connections", {}),
    "ambient_conditions": export_data.get("ambient_conditions", {}),
}

# Inject custom exergy results (from test calculations) into JSON export for traceability
custom_exergy = {}
for comp_name, comp in ean.components.items():
    E_F_custom = getattr(comp, 'E_F_custom', None)
    E_P_custom = getattr(comp, 'E_P_custom', None)
    E_D_custom = getattr(comp, 'E_D_custom', None)
    E_L_custom = getattr(comp, 'E_L_custom', None)
    eps_custom = getattr(comp, 'epsilon_custom', None)
    if any(v is not None for v in (E_F_custom, E_P_custom, E_D_custom, E_L_custom, eps_custom)):
        custom_exergy[str(comp_name)] = {
            "E_F_custom": E_F_custom,
            "E_P_custom": E_P_custom,
            "E_D_custom": E_D_custom,
            "E_L_custom": E_L_custom,
            "epsilon_custom": eps_custom,
        }

if custom_exergy:
    json_payload["custom_exergy"] = custom_exergy
with open(output_path, "w", encoding="utf-8") as json_file:
    json.dump(json_payload, json_file, indent=4)

# LaTeX outputs (all suffixed with 2 to avoid overwriting)
latex_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_streams_single2.tex")
)
os.makedirs(os.path.dirname(latex_output_path), exist_ok=True)
connections_data = json_payload.get("connections", {})
latex_table = _build_streams_latex_table(connections_data)
with open(latex_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(latex_table)

components_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_components_single2.tex")
)
components_table = _build_component_results_table(ean.components)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

components_work_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_components_work_single2.tex")
)
components_work_table = _build_components_work_table(connections_now, ean.components)
with open(components_work_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_work_table)

block_ed_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed_single2.tex")
)
block_ed_table = _build_block_ed_table(ean.components)
with open(block_ed_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_table)

block_ed_comparison_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed_comparison2.tex")
)
double_block_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_blocks_ed.tex")
)
single_sums = _compute_block_ed_sums(ean.components, _get_block_map_single())
double_sums = _read_block_ed_table(double_block_path)
block_ed_comparison_table = _build_block_ed_comparison_table(single_sums, double_sums)
with open(block_ed_comparison_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_comparison_table)

molfractions_output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_streams_molfrac_single2.tex")
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)
