"""
Python-Skript zur automatisierten Erstellung von globalen Exergiebilanz-Tabellen
aus LaTeX-Rohdaten.

Speichert: Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_single.tex
         Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_double.tex

Hinweis: Das Skript arbeitet mit voller Genauigkeit intern und rundet nicht bei
der Ausgabe. Es ersetzt numerische Platzhalter in den Ziel-.tex-Dateien mittels
Regex. Das Skript ist modular: die Parsers geben Dictionaries zurück.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

BASE = Path(__file__).resolve().parents[1]
TAB_DIR = BASE / "Overleaf_LaTeX" / "tabellen"
SCRIPTS_DIR = BASE / "Scripts"

# Input files (single / double)
STREAMS_SINGLE = TAB_DIR / "aspen_luftzerlegung_streams_single.tex"
STREAMS_DOUBLE = TAB_DIR / "aspen_luftzerlegung_streams.tex"
COMP_SINGLE = TAB_DIR / "aspen_luftzerlegung_components_single.tex"
COMP_DOUBLE = TAB_DIR / "aspen_luftzerlegung_components_preview.tex"
WORK_SINGLE = TAB_DIR / "aspen_luftzerlegung_components_work_single.tex"
WORK_DOUBLE = TAB_DIR / "aspen_luftzerlegung_components_work.tex"

# Output canonical global files (targets)
GLOBAL_SINGLE = TAB_DIR / "aspen_luftzerlegung_global_single.tex"
GLOBAL_DOUBLE = TAB_DIR / "aspen_luftzerlegung_global_double.tex"

NUMBER_RE = re.compile(r"-?\d[\d\.,eE+\-]*")

# --- Helpers -----------------------------------------------------------------

def _latex_number_to_float(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    s = str(text).strip()
    if s == "" or s == "-":
        return None
    # remove LaTeX markup
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = s.replace("$", "").replace("\\%", "").replace("%", "")
    s = s.replace("{", "").replace("}", "")
    # Handle German decimal comma and possible thousands dots
    # If string contains both '.' and ',' assume '.' thousand separator, ',' decimal
    if "." in s and "," in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        # If contains comma only -> decimal comma
        if "," in s and not "." in s:
            s = s.replace(',', '.')
        # else leave as-is (may be plain dot decimal or scientific notation)
    try:
        return float(s)
    except Exception:
        return None


def _format_w_no_round(value: Optional[float]) -> str:
    """Return full-precision representation with decimal comma and no rounding."""
    if value is None:
        return "-"
    # Use repr to keep full precision, then replace decimal point with comma
    txt = repr(float(value))
    # repr may produce scientific notation with 'e'; keep it but change decimal point
    if 'e' in txt or 'E' in txt:
        # ensure decimal comma before exponent
        parts = re.split(r"([eE].*)", txt)
        parts[0] = parts[0].replace('.', ',')
        return ''.join(parts)
    return txt.replace('.', ',')


# --- Parsers -----------------------------------------------------------------

def parse_stream_table(path: Path) -> Dict[str, Dict[str, float]]:
    """Parse a LaTeX stream table and extract numeric values for streams.

    Returns mapping: stream_id -> {"m_dot": float, "e_ph": float, "e_ch": float, ...}

    The parser is tolerant: it finds the first line containing the stream id and
    extracts all numeric tokens from that line. Heuristics assign values by
    position: first numeric token -> m_dot (mass flow), last 1 or 2 numeric tokens
    expected to be e_ph and e_ch (physical, chemical exergy). If values are
    missing they will be None.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    streams: Dict[str, Dict[str, float]] = {}
    # find stream ids like S1, S24, S32 etc in the file
    for ln in lines:
        m = re.match(r"\s*(S\d+)\b", ln)
        if not m:
            # also handle lines where stream id is first column inside LaTeX table
            m2 = re.search(r"\\\\?\s*(S\d+)\b", ln)
            if m2:
                sid = m2.group(1)
            else:
                continue
        else:
            sid = m.group(1)
        # Prefer to split the LaTeX table row by '&' so we don't accidentally
        # match digits inside stream labels like 'S1'. Extract numeric tokens
        # per cell and use positional column heuristics.
        parts = [p.strip() for p in ln.split('&')]
        m_dot = None
        e_ph = None
        e_ch = None
        # mass flow is typically in the second column (parts[1])
        if len(parts) >= 2:
            nums_cell = NUMBER_RE.findall(parts[1])
            if nums_cell:
                m_dot = _latex_number_to_float(nums_cell[0])
        # try to read e_ph and e_ch from the last columns (4th-last, 3rd-last)
        if len(parts) >= 4:
            # last numeric columns may be in the last 4th and 3rd cells
            cell_ph = parts[-4]
            cell_ch = parts[-3]
            nums_ph = NUMBER_RE.findall(cell_ph)
            nums_ch = NUMBER_RE.findall(cell_ch)
            if nums_ph:
                e_ph = _latex_number_to_float(nums_ph[-1])
            if nums_ch:
                e_ch = _latex_number_to_float(nums_ch[-1])
        # fallback: collect all numeric tokens from the line and pick by position
        if e_ph is None or e_ch is None or m_dot is None:
            nums = NUMBER_RE.findall(ln)
            nums_f = [_latex_number_to_float(n) for n in nums]
            # skip leading numeric token that may come from the 'S1' label
            if nums_f and nums_f[0] == 1.0 and len(nums_f) > 1:
                nums_f = nums_f[1:]
            if m_dot is None and len(nums_f) >= 1:
                m_dot = nums_f[0]
            if (e_ph is None or e_ch is None) and len(nums_f) >= 4:
                e_ph = nums_f[-4]
                e_ch = nums_f[-3]
            elif (e_ph is None or e_ch is None) and len(nums_f) >= 2:
                e_ph = nums_f[-2]
                e_ch = nums_f[-1]
        # compute E_dot = m_dot * (e_ph + e_ch)
        e_ph_eff = e_ph or 0.0
        e_ch_eff = e_ch or 0.0
        E_W = None
        if m_dot is not None:
            try:
                E_W = float(m_dot) * float(e_ph_eff + e_ch_eff)
            except Exception:
                E_W = None
        streams[sid] = {"m_dot": m_dot, "e_ph": e_ph, "e_ch": e_ch, "E_W": E_W}
    return streams


def parse_components_work(path: Path) -> Dict[str, float]:
    """Parse a components work table and return mapping component -> W (Watt).

    Accepts German decimal comma and different column arrangements.
    """
    text = path.read_text(encoding="utf-8")
    out: Dict[str, float] = {}
    for ln in text.splitlines():
        # typical line: LK1 & Compressor & 5291702,3099999996 \\\n        parts = [p.strip() for p in ln.split('&')]
        parts = []
        try:
            parts = [p.strip() for p in ln.split('&')]
        except Exception:
            parts = []
        if len(parts) < 2:
            continue
        comp = parts[0]
        # numeric token in line
        nums = NUMBER_RE.findall(ln)
        if not nums:
            continue
        val = _latex_number_to_float(nums[-1])
        if val is not None:
            out[comp] = float(val)
    return out


def parse_components_exergy_sum(path: Path) -> Optional[float]:
    """Parse a components exergy table and return the numeric value from the
    line labeled 'Summe' (column with E_D). Returns None if not found."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # first, try to detect header and find the index of the E_D column
    ed_col_idx = None
    for ln in lines:
        if 'E_D' in ln or '\\dot{E}_{D' in ln or 'E_{D' in ln or 'E_D' in ln:
            parts = [p.strip() for p in ln.split('&')]
            for i, p in enumerate(parts):
                if 'E_D' in p or '\\dot{E}_{D' in p or 'E_{D' in p or 'E_D' in p:
                    ed_col_idx = i
                    break
            if ed_col_idx is not None:
                break

    # find the Summe line and parse the E_D column if possible
    for ln in lines:
        if 'Summe' in ln or 'Summe:' in ln or ln.strip().startswith('\\textbf{Summe}') or ln.strip().startswith('Summe'):
            parts = [p.strip() for p in ln.split('&')]
            if ed_col_idx is not None and ed_col_idx < len(parts):
                nums = NUMBER_RE.findall(parts[ed_col_idx])
                if nums:
                    return _latex_number_to_float(nums[-1])
            # fallback to token scan (pick a reasonable token: 1st numeric after possible label)
            nums = NUMBER_RE.findall(ln)
            if nums:
                # try to pick the numeric that looks like a large W-value (more than 1e3)
                for tok in reversed(nums):
                    val = _latex_number_to_float(tok)
                    if val is not None and abs(val) > 1e3:
                        return val
                return _latex_number_to_float(nums[-1])

    # fallback: try to find a line with 'Gesamt' or 'Total'
    for ln in lines:
        if 'Gesamt' in ln or 'Total' in ln:
            nums = NUMBER_RE.findall(ln)
            if nums:
                return _latex_number_to_float(nums[-1])
    return None


# --- Computations -----------------------------------------------------------

def compute_model_metrics(
    streams: Dict[str, Dict[str, float]],
    works: Dict[str, float],
    components_exergy_sum: Optional[float],
    model: str = 'single',
) -> Dict[str, Optional[float]]:
    """Compute all requested metrics for a given model.

    model: 'single' or 'double' determines which stream ids to pick for product/rest.
    """
    if model == 'single':
        ids = {
            'feed': 'S1',
            'product': 'S24',
            'rest': 'S21',
            'purges': ['S7', 'S9', 'S10'],
        }
    else:
        ids = {
            'feed': 'S1',
            'product': 'S32',
            'rest': 'S28',
            'purges': ['S7', 'S9', 'S10'],
        }

    E_feed = streams.get(ids['feed'], {}).get('E_W')
    E_prod = streams.get(ids['product'], {}).get('E_W')
    E_rest = streams.get(ids['rest'], {}).get('E_W')

    # purge losses: compute individual purge stream exergies and their sum
    purge_sum = 0.0
    purge_found = False
    purge_values: Dict[str, Optional[float]] = {}
    for p in ids['purges']:
        v = streams.get(p, {}).get('E_W')
        purge_values[p] = v
        if v is not None:
            purge_sum += v
            purge_found = True
    L_tot = purge_sum if purge_found else None

    # log purge breakdown for debugging
    if purge_values:
        for k, vv in purge_values.items():
            print(f"Purge stream {k}: {vv}")
        if L_tot is not None:
            print(f"Purge total L_tot: {L_tot}")
    # include purge_values in returned metrics for later injection
    metrics_extra = {'purge_values': purge_values}

    # compressors sum: look for known keys and also any component with name starting with LK or PK or type=Compressor
    comp_sum = 0.0
    comp_found = False
    # Prefer explicit sums from the components work table when available
    if model == 'single':
        prefer_keys = ['LK1', 'LK2']
    else:
        prefer_keys = ['LK1', 'LK2', 'PK1']
    explicit_sum = 0.0
    explicit_found = False
    for k in prefer_keys:
        if k in works:
            explicit_sum += works[k]
            explicit_found = True
    if explicit_found:
        comp_sum = explicit_sum
        comp_found = True
    else:
        for k, v in works.items():
            if k.upper().startswith(('LK', 'PK')) or 'compressor' in k.lower():
                comp_sum += v
                comp_found = True
    E_comp_sum = comp_sum if comp_found else None

    # turbine: prefer explicit turbine entries from the components work table
    turbine_val = None
    prefer_turbine_keys = ('T', 'TURB', 'Turbine', 'WT', 'W_T', 'W_Turbine')
    for key in prefer_turbine_keys:
        if key in works:
            turbine_val = abs(works[key])
            break
    # fallback: look for any component name containing 'turb' or 'turbin'
    if turbine_val is None:
        for k, v in works.items():
            if 'turb' in k.lower() or 'turbin' in k.lower():
                turbine_val = abs(v)
                break
    # last resort: take first negative work value (assumed turbine output)
    if turbine_val is None:
        for k, v in works.items():
            if v is not None and v < 0:
                turbine_val = abs(v)
                break
    if turbine_val is not None:
        print(f"Using turbine work from components table: {turbine_val}")

    # Sum input
    sum_input = None
    if E_feed is not None:
        if E_comp_sum is not None:
            sum_input = E_feed + E_comp_sum
        else:
            sum_input = E_feed

    # Sum of material outputs (only stoffliche Ausgänge): product + rest + purge losses
    sum_out_stoff = None
    out_stoff_parts = []
    if E_prod is not None:
        out_stoff_parts.append(E_prod)
    if E_rest is not None:
        out_stoff_parts.append(E_rest)
    if L_tot is not None:
        out_stoff_parts.append(L_tot)
    if out_stoff_parts:
        sum_out_stoff = sum(out_stoff_parts)

    # Sum output (for legacy display) still kept as product + turbine + rest + purge
    sum_output = None
    out_parts = []
    if E_prod is not None:
        out_parts.append(E_prod)
    if turbine_val is not None:
        out_parts.append(turbine_val)
    if E_rest is not None:
        out_parts.append(E_rest)
    if L_tot is not None:
        out_parts.append(L_tot)
    if out_parts:
        sum_output = sum(out_parts)

    # Thermodynamic destruction (from components table)
    E_D_thermo = components_exergy_sum

    # Mechanical destruction: as requested compute for compressors (W) and turbine (E_P - |W|)
    E_D_mech = 0.0
    mech_found = False
    # compressors: sum of compressor works (assumed dissipated mechanically here)
    if E_comp_sum is not None:
        E_D_mech += E_comp_sum
        mech_found = True
    # turbine contribution
    if E_prod is not None and turbine_val is not None:
        E_D_mech += (E_prod - turbine_val)
        mech_found = True
    E_D_mech_val = E_D_mech if mech_found else None

    # Total exergy destruction
    E_D_total = None
    if E_D_thermo is not None and E_D_mech_val is not None:
        E_D_total = E_D_thermo + E_D_mech_val
    elif E_D_thermo is not None:
        E_D_total = E_D_thermo
    elif E_D_mech_val is not None:
        E_D_total = E_D_mech_val

    # Residuum & balance errors
    residuum = None
    abs_dev = None
    rel_err_pct = None
    # New balance: losses consist of stoffliche Outputs + technical turbine work + internal destructions
    sum_losses = None
    if sum_out_stoff is not None and turbine_val is not None and E_D_total is not None:
        sum_losses = sum_out_stoff + turbine_val + E_D_total
    else:
        # if some parts are missing, try partial sum where sensible
        parts_losses = []
        if sum_out_stoff is not None:
            parts_losses.append(sum_out_stoff)
        if turbine_val is not None:
            parts_losses.append(turbine_val)
        if E_D_total is not None:
            parts_losses.append(E_D_total)
        if parts_losses:
            sum_losses = sum(parts_losses)

    if sum_input is not None and sum_losses is not None:
        residuum = sum_input - sum_losses
        # Absolute bilanzabweichung: absolute difference between input and losses
        abs_dev = abs(residuum)
        # Relativer Bilanzfehler (bezogen auf Input) in Prozent
        if sum_input != 0:
            rel_err_pct = abs_dev / sum_input * 100.0
        # also compute deviation vs destruction for diagnostics
        # (kept under a different name if needed)
        # abs_dev_vs_E_D = None
        # if E_D_total is not None:
        #     abs_dev_vs_E_D = abs(residuum - E_D_total)

    return {
        'E_feed': E_feed,
        'E_prod': E_prod,
        'E_rest': E_rest,
        'L_tot': L_tot,
        'E_comp_sum': E_comp_sum,
        'turbine': turbine_val,
        'sum_input': sum_input,
        'sum_output': sum_output,
        'sum_out_stoff': sum_out_stoff,
        'sum_losses': sum_losses,
        'E_D_thermo': E_D_thermo,
        'E_D_mech': E_D_mech_val,
        'E_D_total': E_D_total,
        'residuum': residuum,
        'abs_dev': abs_dev,
        'rel_err_pct': rel_err_pct,
        'purge_values': purge_values,
    }


# --- File update / regex injection ------------------------------------------

def _inject_values_into_global(tex_path: Path, replacements: Dict[str, str]):
    """Replace values in the target LaTeX file for the given stream symbols.

    replacements: mapping of stream symbol (e.g. 'S1' or LaTeX symbol '\\dot{E}_{S1}')
    to the replacement string (e.g. '188365,39599999788 W').
    """
    txt = tex_path.read_text(encoding='utf-8')
    for key, val_str in replacements.items():
        # Prefer replacing the whole table cell up to the line break so unit and
        # formatting are controlled. Match both math-wrapped symbol and plain id.
        pat_math = re.compile(rf"(\$\\dot\{{E\}}_\{{{re.escape(key)}\}}\$\s*&\s*)(.*?)(\\\\)" , re.DOTALL)
        txt, n = pat_math.subn(lambda m: m.group(1) + val_str + ' ' + m.group(3), txt)
        if n == 0:
            pat_plain = re.compile(rf"(\b{re.escape(key)}\b\s*&\s*)(.*?)(\\\\)", re.DOTALL)
            txt, n2 = pat_plain.subn(lambda m: m.group(1) + val_str + ' ' + m.group(3), txt)
            if n2 == 0:
                # last resort simple replacements for common placeholders
                txt = txt.replace(f"$\\dot{{E}}_{{{key}}}$ & 0 W", f"$\\dot{{E}}_{{{key}}}$ & {val_str} W")
                txt = txt.replace(f"{key} & 0 W", f"{key} & {val_str} W")
    tex_path.write_text(txt, encoding='utf-8')


def _replace_label_value(tex_path: Path, label_substr: str, value_str: str, bold: bool = False, unit: str = ' W'):
    """Replace a numeric cell in the line that contains label_substr with value_str.

    If bold=True, wrap the value in \textbf{...}.
    """
    txt = tex_path.read_text(encoding='utf-8')
    lines = txt.splitlines()
    changed = False
    for i, ln in enumerate(lines):
        if label_substr in ln:
            parts = [p.strip() for p in ln.split('&')]
            if len(parts) >= 2:
                # last cell is the value; construct replacement
                val = value_str + unit
                if bold:
                    val = r"\textbf{" + value_str + unit + r"}"
                # preserve original indentation for the line
                prefix = ' & '.join(parts[:-1])
                new_ln = prefix + ' & ' + val + ' \\\\'
                lines[i] = new_ln
                changed = True
            break
    if changed:
        tex_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _insert_purge_breakdown(tex_path: Path, purge_values: Dict[str, Optional[float]]):
    """Insert individual purge stream lines (S7,S9,S10) before the total purge line."""
    if not purge_values:
        return
    txt = tex_path.read_text(encoding='utf-8')
    # avoid inserting if purge lines already present
    if '$\\dot{E}_{S7}$' in txt or '$\\dot{E}_{S9}$' in txt or '$\\dot{E}_{S10}$' in txt:
        # also clean duplicate occurrences: keep only first appearance of each purge line
        lines = txt.splitlines()
        seen = set()
        out_lines = []
        for ln in lines:
            if 'Purge-Stream S7' in ln or 'Purge-Stream S9' in ln or 'Purge-Stream S10' in ln:
                if ln in seen:
                    continue
                seen.add(ln)
            out_lines.append(ln)
        tex_path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
        return

    lines = txt.splitlines()
    for i, ln in enumerate(lines):
        if 'Purge / Flash-Verluste' in ln or 'Purge / Flash' in ln:
            insert_lines = []
            for k in ('S7', 'S9', 'S10'):
                v = purge_values.get(k)
                if v is not None:
                    vs = _format_w_no_round(v) + ' W'
                    insert_lines.append(' & Purge-Stream ' + k + ' & $\\dot{E}_{' + k + '}$ & ' + vs + ' \\\\')
            # insert before the total purge line
            lines[i:i] = insert_lines
            break
    tex_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _insert_summe_verluste(tex_path: Path, value: Optional[float]):
    """Insert a 'Summe der Verluste' row near the Bilanzabgleich section.

    Avoid duplicate insertion if the label already exists.
    """
    if value is None:
        return
    txt = tex_path.read_text(encoding='utf-8')
    if 'Summe der Verluste' in txt:
        # already inserted
        # but still update the numeric value if present
        _replace_label_value(tex_path, 'Summe der Verluste', _format_w_no_round(value), bold=True)
        return
    lines = txt.splitlines()
    insert_idx = None
    # find the Bilanzabgleich header and insert the losses row before it
    for i, ln in enumerate(lines):
        if '\\textbf{Bilanzabgleich}' in ln or 'Bilanzabgleich' in ln:
            insert_idx = i
            break
    if insert_idx is None:
        # fallback: insert before the first occurrence of '\\hline' near file end
        for i in range(len(lines)-1, -1, -1):
            if '\\hline' in lines[i]:
                insert_idx = i
                break
    if insert_idx is None:
        return
    val_str = _format_w_no_round(value) + ' W'
    # create a table row with four columns (first column empty)
    new_line = ' & \textbf{Summe der Verluste} & $\\sum \\dot{E}_{verluste}$ & ' + val_str + ' \\\\'
    lines.insert(insert_idx, new_line)
    tex_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# --- Main -------------------------------------------------------------------

def run_update():
    # parse both models
    streams_single = parse_stream_table(STREAMS_SINGLE) if STREAMS_SINGLE.exists() else {}
    streams_double = parse_stream_table(STREAMS_DOUBLE) if STREAMS_DOUBLE.exists() else {}

    works_single = parse_components_work(WORK_SINGLE) if WORK_SINGLE.exists() else {}
    works_double = parse_components_work(WORK_DOUBLE) if WORK_DOUBLE.exists() else {}

    comp_exergy_single = parse_components_exergy_sum(COMP_SINGLE) if COMP_SINGLE.exists() else None
    comp_exergy_double = parse_components_exergy_sum(COMP_DOUBLE) if COMP_DOUBLE.exists() else None

    metrics_single = compute_model_metrics(streams_single, works_single, comp_exergy_single, model='single')
    metrics_double = compute_model_metrics(streams_double, works_double, comp_exergy_double, model='double')

    # prepare replacements: format full-precision strings with decimal comma + ' W'
    repl_single = {}
    repl_double = {}

    # single: prefer feed E_W from streams table (full precision), fallback to metrics
    for sym, key in [('S1', 'E_feed'), ('S24', 'E_prod'), ('S21', 'E_rest')]:
        val = None
        # prefer exact stream energy E_W when available
        if streams_single and isinstance(streams_single.get(sym, {}), dict):
            ew = streams_single.get(sym, {}).get('E_W')
            if isinstance(ew, (int, float)):
                val = ew
                print(f"Using stream-derived E_W for single {sym}: {val}")
        # fallback to computed metric
        if val is None:
            val = metrics_single.get(key)
        if val is not None:
            repl_single[sym] = _format_w_no_round(val) + ' W'

    # write canonical single global
    if GLOBAL_SINGLE.exists():
        _inject_values_into_global(GLOBAL_SINGLE, repl_single)
        # update Summe Input/Output and thermodynamic destruction
        if metrics_single.get('sum_input') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\sum \dot{E}_{in}", _format_w_no_round(metrics_single['sum_input']), bold=True)
        if metrics_single.get('sum_output') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\sum \dot{E}_{out}", _format_w_no_round(metrics_single['sum_output']), bold=True)
        if metrics_single.get('E_D_thermo') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\sum \dot{E}_{D,k}", _format_w_no_round(metrics_single['E_D_thermo']), bold=True)
        if metrics_single.get('residuum') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\sum \dot{E}_{in} - \sum \dot{E}_{out}", _format_w_no_round(metrics_single['residuum']), bold=True)
        # compressors (aggregate), turbine, purge losses
        if metrics_single.get('E_comp_sum') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\dot{W}_{LK1} + \dot{W}_{LK2}", _format_w_no_round(metrics_single['E_comp_sum']), bold=False)
        if metrics_single.get('turbine') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\dot{W}_T", _format_w_no_round(metrics_single['turbine']), bold=False)
        if metrics_single.get('L_tot') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\dot{E}_{L,tot}", _format_w_no_round(metrics_single['L_tot']), bold=False)
        # mechanical and total destruction
        if metrics_single.get('E_D_mech') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\dot{E}_{D,mech}", _format_w_no_round(metrics_single['E_D_mech']), bold=False)
        if metrics_single.get('E_D_total') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\dot{E}_{D,tot}", _format_w_no_round(metrics_single['E_D_total']), bold=True)
        # absolute deviation and relative error (percent)
        if metrics_single.get('abs_dev') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\Delta \dot{E}", _format_w_no_round(metrics_single['abs_dev']), bold=True)
        if metrics_single.get('rel_err_pct') is not None:
            _replace_label_value(GLOBAL_SINGLE, r"\frac{\Delta \dot{E}}{\sum \dot{E}_{in}}", _format_w_no_round(metrics_single['rel_err_pct']), bold=True, unit=r' \%')
        # insert purge breakdown lines
        _insert_purge_breakdown(GLOBAL_SINGLE, metrics_single.get('purge_values', {}))
        # insert Summe der Verluste and update its value
        _insert_summe_verluste(GLOBAL_SINGLE, metrics_single.get('sum_losses'))

    # double: prefer feed E_W from streams table (full precision), fallback to metrics
    for sym, key in [('S1', 'E_feed'), ('S32', 'E_prod'), ('S28', 'E_rest')]:
        val = None
        if streams_double and isinstance(streams_double.get(sym, {}), dict):
            ew = streams_double.get(sym, {}).get('E_W')
            if isinstance(ew, (int, float)):
                val = ew
                print(f"Using stream-derived E_W for double {sym}: {val}")
        if val is None:
            val = metrics_double.get(key)
        if val is not None:
            repl_double[sym] = _format_w_no_round(val) + ' W'

    if GLOBAL_DOUBLE.exists():
        _inject_values_into_global(GLOBAL_DOUBLE, repl_double)
        # update sums and destruction entries
        if metrics_double.get('sum_input') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\sum \dot{E}_{in}", _format_w_no_round(metrics_double['sum_input']), bold=True)
        if metrics_double.get('sum_output') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\sum \dot{E}_{out}", _format_w_no_round(metrics_double['sum_output']), bold=True)
        if metrics_double.get('E_D_thermo') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\sum \dot{E}_{D,k}", _format_w_no_round(metrics_double['E_D_thermo']), bold=True)
        if metrics_double.get('E_D_total') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\dot{E}_{D,tot}", _format_w_no_round(metrics_double['E_D_total']), bold=True)
        if metrics_double.get('residuum') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\sum \dot{E}_{in} - \sum \dot{E}_{out}", _format_w_no_round(metrics_double['residuum']), bold=True)
        # compressors (aggregate), turbine, purge losses
        if metrics_double.get('E_comp_sum') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\dot{W}_{in}", _format_w_no_round(metrics_double['E_comp_sum']), bold=False)
        if metrics_double.get('turbine') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\dot{W}_{out}", _format_w_no_round(metrics_double['turbine']), bold=False)
        if metrics_double.get('L_tot') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\dot{E}_{L,tot}", _format_w_no_round(metrics_double['L_tot']), bold=False)
        # mechanical destruction
        if metrics_double.get('E_D_mech') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\dot{E}_{D,mech}", _format_w_no_round(metrics_double['E_D_mech']), bold=False)
        # absolute deviation and relative error (percent)
        if metrics_double.get('abs_dev') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\Delta \dot{E}", _format_w_no_round(metrics_double['abs_dev']), bold=True)
        if metrics_double.get('rel_err_pct') is not None:
            _replace_label_value(GLOBAL_DOUBLE, r"\frac{\Delta \dot{E}}{\sum \dot{E}_{in}}", _format_w_no_round(metrics_double['rel_err_pct']), bold=True, unit=r' \%')
        # insert purge breakdown lines
        _insert_purge_breakdown(GLOBAL_DOUBLE, metrics_double.get('purge_values', {}))
        # insert Summe der Verluste and update its value
        _insert_summe_verluste(GLOBAL_DOUBLE, metrics_double.get('sum_losses'))

    # Optionally: print a short summary for verification
    print('Single model metrics:')
    for k, v in metrics_single.items():
        print(f'  {k}:', v)
    print('\nDouble model metrics:')
    for k, v in metrics_double.items():
        print(f'  {k}:', v)


if __name__ == '__main__':
    run_update()
