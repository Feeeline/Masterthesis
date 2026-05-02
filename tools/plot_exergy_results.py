import os
import re
import json
from pathlib import Path
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(r"C:/Users/Felin/Documents/Masterthesis/Simulation_Code/GIT")
TABLE_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components.tex"
TABLE_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex"
TABLE_DOUBLE_KLEIN = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_klein.tex"
TABLE_SINGLE_KLEIN = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single_klein.tex"
JSON_DOUBLE = BASE_DIR / "examples/json_example/aspen_luftzerlegung.json"
JSON_DOUBLE_KLEIN = BASE_DIR / "examples/json_example/aspen_luftzerlegung_klein.json"
JSON_SINGLE = BASE_DIR / "examples/json_example/aspen_luftzerlegung_single.json"
JSON_SINGLE_KLEIN = BASE_DIR / "examples/json_example/aspen_luftzerlegung_single_klein.json"
MOLFRAC_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac.tex"
MOLFRAC_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac_single.tex"
STREAMS_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams.tex"
STREAMS_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_single.tex"
GLOBAL_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check.tex"
GLOBAL_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check_single.tex"
OUT_DIR = BASE_DIR / "Overleaf_LaTeX/bilder"
TAB_DIR = BASE_DIR / "Overleaf_LaTeX/tabellen"
WERTE_TEX = BASE_DIR / "Overleaf_LaTeX/werte.tex"
COLOR_SINGLE = "#55A868"
COLOR_DOUBLE = "#4C72B0"
PLOT_THEME = {
    "font.family": "serif",
    "mathtext.fontset": "stix",
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
}

# Global flag: when True, formatting helpers return full-precision numbers
# and rounding/rounding-pass functions are disabled.
NO_ROUNDING = True


def _apply_plot_theme(style: str = "seaborn-v0_8-whitegrid"):
    plt.style.use(style)
    plt.rcParams.update(PLOT_THEME)


def _style_axis(ax, grid_axis: str = "y"):
    ax.grid(axis=grid_axis, linestyle="--", alpha=0.35)
    # Apply decimal-comma formatting only to the likely numeric axis.
    # This keeps categorical axes (e.g., component names) unchanged.
    if grid_axis == "x":
        ax.xaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    elif grid_axis == "y":
        ax.yaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    else:
        ax.xaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
        ax.yaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)


def _style_bottom_legend(ax, ncol: int = 2):
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=ncol,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )


def _to_float(value: str):
    return _to_float_latex_number(value)


def _format_decimal_comma(value, decimals: int = 3, trim: bool = False):
    if value is None or not isinstance(value, (int, float)):
        return "-"
    x = float(value)
    text = f"{x:.{decimals}f}"
    if trim:
        text = text.rstrip("0").rstrip(".")
        if text in {"", "-0"}:
            text = "0"
    return text.replace(".", ",")


def _tick_formatter_decimal_comma(x, _pos):
    if not isinstance(x, (int, float)):
        return ""
    ax = abs(float(x))
    if ax >= 100:
        text = f"{x:.0f}"
    elif ax >= 1:
        text = f"{x:.2f}".rstrip("0").rstrip(".")
    else:
        text = f"{x:.4f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return text.replace(".", ",")


def _to_float_latex_number(value: str):
    if value is None:
        return None
    value = str(value)
    value = re.sub(r"\\textbf\{([^}]*)\}", r"\1", value)
    value = value.replace("$", "").replace("\\%", "").replace("%", "")
    value = value.replace("\\", "").replace("{", "").replace("}", "").strip()
    # Treat empty or dash-like entries as zero for plotting calculations
    if not value:
        return 0.0
    if value in {"-", "—", "–"}:
        return 0.0

    # Threshold notation from tables, e.g. <1e-6: use 0.0 for plotting.
    if value.startswith("<"):
        return 0.0
    # Normalize common LaTeX/European numeric formats into Python float-friendly form.
    # Strategy:
    # - If both '.' and ',' present assume German thousands ('.') and decimal comma (',')
    #   -> remove thousands dots and convert comma to dot.
    # - Else if only ',' present -> treat as decimal comma and replace with dot.
    # - Else leave as-is (may already be english-format or scientific with dot).
    s = value.replace(" ", "")
    if "." in s and "," in s:
        s = s.replace('.', '').replace(',', '.')
    elif "," in s and "." not in s:
        s = s.replace(',', '.')

    # Remove stray braces/backslashes left (defensive)
    s = s.strip()

    # Try direct float conversion (handles scientific notation like 4.62e+26)
    try:
        return float(s)
    except ValueError:
        pass

    # Fallback: handle English-style thousand separators (commas)
    if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", value):
        try:
            return float(value.replace(',', ''))
        except Exception:
            return None

    # If still failing, attempt a final cleanup: strip non-numeric chars and try
    candidate = re.sub(r"[^0-9eE+\-.,]", "", value)
    candidate = candidate.replace(',', '.')
    try:
        return float(candidate)
    except Exception:
        return None


def parse_component_table(tex_path: Path) -> pd.DataFrame:
    rows = []
    # Normalize old component names to their current canonical names so plots
    # remain correct even if .tex files still contain legacy names.
    name_map = {
        "MH": "MW",
        "RECO": "RC",
        "RECON": "RC",
        "TURB": "T",
    }

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("\\"):
                continue
            if raw.startswith("Component") or raw.startswith("&"):
                continue

            # split on '&' and strip parts; remove trailing LaTeX backslashes
            parts = [p.strip() for p in re.split(r"&", raw)]
            if not parts:
                continue
            # remove trailing \\ from last part
            parts[-1] = re.sub(r"\\\\$", "", parts[-1]).strip()

            # need at least 6 columns: Component, Type, E_F, E_P, E_D, ...
            if len(parts) < 6:
                continue

            component = parts[0]
            if component in name_map:
                component = name_map[component]

            # E_D is expected in column index 4 (0-based)
            e_d = _to_float(parts[4]) if len(parts) > 4 else None

            # prefer last column as y_D_k (y* may be present as last); if last looks like share, use it
            y_dk_raw = parts[-1] if parts else None
            y_dk = _to_float(y_dk_raw)

            if e_d is None or y_dk is None:
                continue

            rows.append({
                "Component": component,
                "E_D_W": e_d,
                "E_D_MW": e_d / 1e6,
                "y_D_k": y_dk,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Keine verwertbaren Daten in {tex_path}")

    # Recompute y_D_k from parsed E_D values so shares sum to 1 per model
    total = df["E_D_W"].abs().sum()
    if total > 0:
        df["y_D_k"] = df["E_D_W"].abs() / total
    else:
        df["y_D_k"] = 0.0

    return df.sort_values("E_D_W", ascending=False).reset_index(drop=True)


def parse_component_ed_map(tex_path: Path) -> dict:
    rows = {}
    name_map = {
        "MH": "MW",
        "RECO": "RC",
        "RECON": "RC",
        "TURB": "T",
    }

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("\\"):
                continue
            if raw.startswith("Component") or raw.startswith("&"):
                continue

            parts = [p.strip() for p in re.split(r"&", raw)]
            if not parts or len(parts) < 5:
                continue
            parts[-1] = re.sub(r"\\\\$", "", parts[-1]).strip()

            comp = parts[0]
            if comp in name_map:
                comp = name_map[comp]
            try:
                ed = _to_float(parts[4])
            except Exception:
                ed = None
            if comp and isinstance(ed, (int, float)):
                rows[comp] = float(ed)

    if not rows:
        raise ValueError(f"Keine verwertbaren Komponenten-E_D-Daten in {tex_path}")
    return rows


def parse_molfrac_table(tex_path: Path) -> pd.DataFrame:
    rows = []
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^\\]+)\\\\")

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Stream") or line.startswith("&"):
                continue

            m = pattern.match(line)
            if not m:
                continue

            stream = m.group(1).strip()
            x_n2 = _to_float(m.group(2))
            x_o2 = _to_float(m.group(3))
            x_ar = _to_float(m.group(5))
            if x_n2 is None or x_o2 is None:
                continue

            rows.append({"Stream": stream, "x_N2": x_n2, "x_O2": x_o2, "x_AR": x_ar if x_ar is not None else 0.0})

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Keine verwertbaren Molfraktionsdaten in {tex_path}")
    return df


def parse_stream_mass_flows(tex_path: Path) -> dict:
    rows = {}

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Stream") or line.startswith("&"):
                continue

            parts = [part.strip() for part in line.replace("\\\\", "").split("&")]
            if len(parts) < 2:
                continue

            stream = parts[0]
            mass_flow = _to_float(parts[1])
            if stream and isinstance(mass_flow, (int, float)):
                # Normalize stream names: LaTeX tables often use labels like 'S32,00'.
                # Accept both the raw string and a normalized form without
                # trailing ',xx' formatting so lookups like 'S32' succeed.
                rows[stream] = float(mass_flow)
                # Create a normalized key by stripping a trailing comma+digits suffix
                norm = re.sub(r",\d{1,3}$", "", stream).strip()
                if norm and norm != stream and norm not in rows:
                    rows[norm] = float(mass_flow)

    if not rows:
        raise ValueError(f"Keine verwertbaren Massenstromdaten in {tex_path}")
    return rows


def parse_stream_data_from_json(json_path: Path, stream_names: list[str]) -> dict:
    raise RuntimeError(
        "JSON input is disabled for result calculations. Use the LaTeX tables under Overleaf_LaTeX/tabellen/ as authoritative sources."
    )


def parse_component_work_table(tex_path: Path) -> dict:
    """Parse a components_work LaTeX table and return mapping component->W (float).

    Expected simple longtable with 3 columns: Component & Type & W
    """
    rows = {}
    with tex_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("\\"):
                continue
            parts = [p.strip() for p in re.split(r"&", line)]
            if len(parts) < 3:
                continue
            # remove trailing \\ from last part
            parts[-1] = re.sub(r"\\\\$", "", parts[-1]).strip()
            comp = parts[0]
            try:
                val = _to_float(parts[2])
            except Exception:
                val = None
            if comp and isinstance(val, (int, float)):
                rows[comp] = float(val)
    if not rows:
        raise ValueError(f"Keine verwertbaren Arbeitsstromdaten in {tex_path}")
    return rows


def parse_stream_thermo_data(tex_path: Path) -> dict:
    """Return dict: stream -> {'m_dot': float, 'T': float, 'p_Pa': float}"""
    data = {}
    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\") or line.startswith("Stream") or line.startswith("&"):
                continue
            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) < 5:
                continue
            stream = parts[0]
            m_dot = _to_float(parts[1])
            # parts[2] contains molar flow (mol/s) in the stream tables
            n_mol_s = _to_float(parts[2])
            T = _to_float(parts[3])
            p_Pa = _to_float(parts[4])
            # attempt to read specific exergy columns if present: e_PH,e_CH,e_T,e_M
            e_ph = None
            e_ch = None
            e_t = None
            e_m = None
            # indices: 0=stream,1=m_dot,2=n_mol_s,3=T,4=p,5=h,6=s,7=l_frac,8=v_frac,9=e_PH,10=e_CH,11=e_T,12=e_M
            try:
                if len(parts) > 9:
                    e_ph = _to_float(parts[9])
                if len(parts) > 10:
                    e_ch = _to_float(parts[10])
                if len(parts) > 11:
                    e_t = _to_float(parts[11])
                if len(parts) > 12:
                    e_m = _to_float(parts[12])
            except Exception:
                e_ph = e_ch = e_t = e_m = None

            E_W = None
            if isinstance(m_dot, (int, float)):
                # Compute total specific physical exergy: prefer e_PH; otherwise try e_T + e_M
                e_ph_eff = None
                if isinstance(e_ph, (int, float)):
                    e_ph_eff = float(e_ph)
                else:
                    if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                        e_ph_eff = float(e_t) + float(e_m)

                # chemical exergy (may be present or None)
                e_ch_eff = float(e_ch) if isinstance(e_ch, (int, float)) else 0.0

                if e_ph_eff is not None:
                    # total specific exergy = physical + chemical
                    E_W = float(m_dot) * (e_ph_eff + e_ch_eff)

            if stream and m_dot is not None and T is not None and p_Pa is not None:
                        entry = {"m_dot": m_dot, "n_mol_s": n_mol_s, "T": T, "p_Pa": p_Pa, "e_ph": e_ph, "e_ch": e_ch, "e_t": e_t, "e_m": e_m, "E_W": E_W}
                        data[stream] = entry
                        # Create a normalized key without trailing comma+decimals (e.g. 'S1,00' -> 'S1')
                        norm = re.sub(r",\d{1,3}$", "", stream).strip()
                        if norm and norm != stream and norm not in data:
                            data[norm] = entry
    return data


def compute_global_metrics_from_tables(df_components: pd.DataFrame, streams_thermo: dict, product_stream: str | None, model_label: str) -> dict:
    """Compute global metrics (W) from component and stream LaTeX tables.

    Returns dict with keys: E_F, E_P, E_D, E_L, E_in_sum, product_stream_name
    """
    # E_D total from components
    E_D_tot = None
    try:
        if isinstance(df_components, pd.DataFrame) and "E_D_W" in df_components.columns:
            E_D_tot = float(df_components["E_D_W"].abs().sum())
    except Exception:
        E_D_tot = None

    # Product stream exergy from streams table
    E_prod = None
    prod_name = product_stream or ("S24" if "Einzel" in model_label or "Single" in model_label else "S32")
    p = streams_thermo.get(prod_name)
    if isinstance(p, dict):
        E_prod = p.get("E_W")

    # Loss streams (Austrittsverluste) sum over S7,S9,S10,S21 if available
    loss_streams = ["S7", "S9", "S10", "S21"]
    E_loss = 0.0
    found_loss = False
    for s in loss_streams:
        v = streams_thermo.get(s, {}).get("E_W") if streams_thermo.get(s) else None
        if isinstance(v, (int, float)):
            E_loss += float(v)
            found_loss = True
    if not found_loss:
        E_loss = None

    # E_P_tot: take E_prod (product stream exergy)
    # sum right side (product + E_D + E_L)
    sum_right = None
    try:
        parts = []
        if isinstance(E_prod, (int, float)):
            parts.append(float(E_prod))
        if isinstance(E_D_tot, (int, float)):
            parts.append(float(E_D_tot))
        if isinstance(E_loss, (int, float)):
            parts.append(float(E_loss))
        if parts:
            sum_right = sum(parts)
    except Exception:
        sum_right = None

    # E_in_sum: use sum_right when available
    E_in_sum = sum_right

    return {
        "E_F": E_in_sum,
        "E_P": E_prod,
        "E_D": E_D_tot,
        "E_L": E_loss,
        "E_in_sum": E_in_sum,
        "product_stream": prod_name,
    }


def _inject_streams_into_canonical(tex_path: Path, streams_thermo: dict, stream_keys: dict):
    """Inject unrounded Watt strings from streams_thermo into an existing canonical LaTeX file.

    Matches occurrences of the LaTeX symbol $\dot{E}_{Sxx}$ followed by an ampersand and a numeric value,
    replacing the numeric entry with the full-precision Watt string (decimal comma) produced by
    `_format_w_no_round_tex` plus ' W'. Falls back to a simple replace for common ' & 0 W' patterns.
    """
    if not tex_path.exists():
        return
    text = tex_path.read_text(encoding="utf-8")
    for label, stream_id in stream_keys.items():
        val = streams_thermo.get(stream_id, {}).get("E_W") if streams_thermo.get(stream_id) else None
        rep = _format_w_no_round_tex(val) + " W" if val is not None else "-"
        # pattern: $\dot{E}_{Sxx}$ & <value> \\\\  (value may contain spaces, dots, commas, minus, e notation)
        pattern = re.compile(rf"(\$\\dot\{{E\}}_\{{{re.escape(stream_id)}\}}\$\s*&\s*)([-0-9.,eE+\s]+)(\\\\\\\\)")
        def _repl(m):
            return m.group(1) + rep + m.group(3)
        text, n = pattern.subn(_repl, text)
        if n == 0:
            # fallback simple replace
            text = text.replace(f"$\\dot{{E}}_{{{stream_id}}}$ & 0 W", f"$\\dot{{E}}_{{{stream_id}}}$ & {rep}")
    tex_path.write_text(text, encoding="utf-8")


def parse_compressor_power_from_json(json_path: Path) -> float | None:
    """Read JSON results and sum compressor electrical power `P` (W).

    Returns total compressor power (W) or None if not available.
    """
    if not json_path.exists():
        return None
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    total = 0.0
    found = False
    # JSON layout: components -> category -> {name: {..P..}}
    comps = data.get("components") if isinstance(data, dict) else None
    if not isinstance(comps, dict):
        return None

    for cat, cat_dict in comps.items():
        if not isinstance(cat_dict, dict):
            continue
        for key, entry in cat_dict.items():
            try:
                typ = entry.get("type") if isinstance(entry, dict) else None
                p = entry.get("P") if isinstance(entry, dict) else None
                # Accept type == 'Compressor' or names that include 'LK'/'PK'
                if (isinstance(typ, str) and typ.lower().startswith("comp")) or (isinstance(key, str) and (key.upper().startswith("LK") or key.upper().startswith("PK") or "COMP" in key.upper())):
                    if isinstance(p, (int, float)):
                        total += float(p)
                        found = True
            except Exception:
                continue

    if not found:
        return None
    return total


def compute_yd_percent_from_ed_map(ed_map: dict, allowed_components: set[str] | None = None) -> dict:
    """Compute percent shares of E_D per component from an ed_map (component->E_D).

    Returns mapping component -> percent of total E_D (0..100).
    """
    e_map = {}
    for name, val in ed_map.items():
        if allowed_components is not None and name not in allowed_components:
            continue
        try:
            e_map[name] = abs(float(val))
        except Exception:
            continue

    total = sum(e_map.values())
    if total <= 0:
        return {k: 0.0 for k in e_map.keys()}
    return {k: (v / total) * 100.0 for k, v in e_map.items()}


def plot_grouped_product_purity(df_double_mol: pd.DataFrame, df_single_mol: pd.DataFrame, out_path: Path):
    # Requested product stream mapping.
    stream_map = {
        "single": {"n2": "S24", "o2": "S21"},
        "double": {"n2": "S32", "o2": "S28"},
    }

    def _pick(df: pd.DataFrame, stream: str, key: str):
        hit = df.loc[df["Stream"] == stream, key]
        if hit.empty:
            raise ValueError(f"Stream {stream} nicht in Molfraktions-Tabelle gefunden.")
        return float(hit.iloc[0])

    single_n2 = _pick(df_single_mol, stream_map["single"]["n2"], "x_N2")
    single_o2 = _pick(df_single_mol, stream_map["single"]["o2"], "x_O2")
    double_n2 = _pick(df_double_mol, stream_map["double"]["n2"], "x_N2")
    double_o2 = _pick(df_double_mol, stream_map["double"]["o2"], "x_O2")

    _apply_plot_theme()

    fig, ax_left = plt.subplots(figsize=(7.2, 5.4))
    ax_right = ax_left.twinx()

    categories = ["Stickstoff-Produktstrom", "Sauerstoffreststrom"]
    x = [0.0, 0.6]
    width = 0.12  # slight gap avoids visual seam between adjacent bars
    dx = 0.07

    # Colors requested to match existing style.
    color_single = COLOR_SINGLE
    color_double = COLOR_DOUBLE

    # Nitrogen product category on left axis.
    b_single_n2 = ax_left.bar(
        x[0] - dx,
        single_n2,
        width=width,
        color=color_single,
        edgecolor="none",
        linewidth=0,
        label="Einkolonnen-Modell",
    )
    b_double_n2 = ax_left.bar(
        x[0] + dx,
        double_n2,
        width=width,
        color=color_double,
        edgecolor="none",
        linewidth=0,
        label="Doppelkolonnen-Modell",
    )

    # Oxygen category on right axis (0..1).
    b_single_o2 = ax_right.bar(
        x[1] - dx,
        single_o2,
        width=width,
        color=color_single,
        edgecolor="none",
        linewidth=0,
    )
    b_double_o2 = ax_right.bar(
        x[1] + dx,
        double_o2,
        width=width,
        color=color_double,
        edgecolor="none",
        linewidth=0,
    )

    ax_left.set_xticks(x)
    ax_left.set_xticklabels(categories)
    ax_left.set_ylabel(r"Molare Zusammensetzung, $x_i$ (kmol/kmol)")

    # Left axis for high-purity N2 visibility.
    ax_left.set_ylim(0.9999, 1.00)
    ax_left.set_yticks([0.9999 + 0.00002 * i for i in range(int((1.00 - 0.9999) / 0.00002) + 1)])

    # Right axis for O2 full range.
    ax_right.set_ylim(0.0, 1.0)
    ax_right.set_yticks([0.1 * i for i in range(11)])
    ax_left.set_xlim(-0.28, 0.88)

    # Remove all vertical axis lines and tick marks for cleaner look.
    ax_left.spines["left"].set_visible(False)
    ax_left.spines["right"].set_visible(False)
    ax_right.spines["left"].set_visible(False)
    ax_right.spines["right"].set_visible(False)
    ax_left.spines["top"].set_visible(False)
    ax_right.spines["top"].set_visible(False)
    ax_left.tick_params(axis="y", length=0)
    ax_right.tick_params(axis="y", length=0)

    ax_left.grid(axis="y", linestyle="--", alpha=0.35)
    ax_right.grid(False)

    # Value labels for transparency.
    for bars, axis in ((b_single_o2, ax_right), (b_double_o2, ax_right), (b_single_n2, ax_left), (b_double_n2, ax_left)):
        y_max = axis.get_ylim()[1]
        offset = y_max * 0.01
        for bar in bars:
            v = bar.get_height()
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                v + offset,
                _format_decimal_comma(v, decimals=4, trim=False),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    # Legend below the plot.
    handles = [b_single_o2[0], b_double_o2[0]]
    labels = ["Einkolonnen-Modell", "Doppelkolonnen-Modell"]
    ax_left.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )

    fig.subplots_adjust(left=0.16, right=0.90, bottom=0.22, top=0.97)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def _component_sum(ed_map: dict, components: list[str]) -> float:
    return float(sum(float(ed_map.get(c, 0.0)) for c in components))


def _compute_block_yd_payload(ed_map: dict, model: str):
    # Cooled-compression is not shown as a separate point,
    # but its components remain included inside the V+G block.
    ignored = set()

    if model == "single":
        comp_only = ["LK1", "ZK1", "LK2"]
        gas_only = ["ZK2", "GW1", "GW2"]
        # move RC from heat transfer into the column block per user request
        heat_transfer = ["MW"]
        column_block = ["KOL", "D1", "RC"]
    else:
        comp_only = ["LK1", "ZK1", "LK2", "PK1"]
        gas_only = ["ZK2", "GW1", "GW2"]
        # move RC and RC2 from heat transfer into the column block per user request
        heat_transfer = ["MW"]
        column_block = ["KOLHP", "KOLLP", "D1", "D2", "D3", "RC", "RC2"]

    named_sets = {
        "comp_only": set(comp_only),
        "gas_only": set(gas_only),
        "combined": set(comp_only) | set(gas_only),
        "heat": set(heat_transfer),
        "column": set(column_block),
    }

    all_components = set(ed_map.keys())
    used = set()
    for s in named_sets.values():
        used |= set(s)
    used -= ignored
    rest_components = sorted((all_components - used) - ignored)

    # Normalize by all considered components (excluding explicitly ignored ones),
    # so combined + heat + column + rest sums to 100%.
    considered_components = sorted(all_components - ignored)
    total_ed = _component_sum(ed_map, considered_components)
    if total_ed <= 0:
        total_ed = 1.0

    sums = {
        "combined": _component_sum(ed_map, sorted(named_sets["combined"] - ignored)),
        "comp_only": _component_sum(ed_map, sorted(named_sets["comp_only"] - ignored)),
        "gas_only": _component_sum(ed_map, sorted(named_sets["gas_only"] - ignored)),
        "heat": _component_sum(ed_map, sorted(named_sets["heat"] - ignored)),
        "column": _component_sum(ed_map, sorted(named_sets["column"] - ignored)),
        "rest": _component_sum(ed_map, rest_components),
    }

    y_percent = {k: 100.0 * v / total_ed for k, v in sums.items()}
    return {"total_ed": total_ed, "sums": sums, "y": y_percent}


def plot_block_yd_comparison(ed_single: dict, ed_double: dict, out_path: Path):
    payload_single = _compute_block_yd_payload(ed_single, "single")
    payload_double = _compute_block_yd_payload(ed_double, "double")

    cats = ["V+G Block", "Wärmeübertrager", "Kolonnenblock", "Rest"]
    x = [0, 1, 2, 3]

    y_s = [
        payload_single["y"]["combined"],
        payload_single["y"]["heat"],
        payload_single["y"]["column"],
        payload_single["y"]["rest"],
    ]
    y_d = [
        payload_double["y"]["combined"],
        payload_double["y"]["heat"],
        payload_double["y"]["column"],
        payload_double["y"]["rest"],
    ]

    s_sub = [payload_single["y"]["comp_only"], payload_single["y"]["gas_only"]]
    d_sub = [payload_double["y"]["comp_only"], payload_double["y"]["gas_only"]]

    _apply_plot_theme()

    fig, ax = plt.subplots(figsize=(8.0, 5.8))

    c_single = COLOR_SINGLE
    c_double = COLOR_DOUBLE

    dx = 0.12
    x_single = [xi - dx for xi in x]
    x_double = [xi + dx for xi in x]

    ax.scatter(x_single, y_s, marker="s", s=62, color=c_single, edgecolors="black", linewidths=0.6, label="Singlekolonne", zorder=4)
    ax.scatter(x_double, y_d, marker="^", s=68, color=c_double, edgecolors="black", linewidths=0.6, label="Doppelkolonne", zorder=4)

    # Sub-points only for the combined compression+gas-treatment block.
    x0s = x_single[0]
    x0d = x_double[0]
    # first sub-point = Kompression, second = Reinigung
    ax.scatter([x0s], [s_sub[0]], marker="o", s=34, color=c_single, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0s], [s_sub[1]], marker="D", s=34, color=c_single, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0d], [d_sub[0]], marker="o", s=34, color=c_double, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0d], [d_sub[1]], marker="D", s=34, color=c_double, edgecolors="black", linewidths=0.5, zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel(r"$y_{D,b}$ [%]")
    ax.set_ylim(0, max(y_s + y_d + s_sub + d_sub) * 1.2)
    _style_axis(ax, grid_axis="y")

    model_handles, model_labels = ax.get_legend_handles_labels()
    extra_handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", markersize=6, linestyle="None"),
        Line2D([0], [0], marker="D", color="black", markerfacecolor="black", markersize=6, linestyle="None"),
    ]
    extra_labels = ["Unterpunkt Kompression", "Unterpunkt Reinigung"]
    ax.legend(
        model_handles + extra_handles,
        model_labels + extra_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.22, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_component_work_side_by_side(single_tex: Path, double_tex: Path, out_path: Path):
    """Create a side-by-side component work bar plot.

    Left: Singlekolonne components (green). Right: Doppelkolonne components (blue).
    Uses the same visual style as other plots.
    """
    # determine whether these are work tables (contain 'work' in filename)
    if "work" in single_tex.name.lower() or "work" in double_tex.name.lower():
        vals_map_s = parse_component_work_table(single_tex)
        vals_map_d = parse_component_work_table(double_tex)
    else:
        vals_map_s = parse_component_ed_map(single_tex)
        vals_map_d = parse_component_ed_map(double_tex)

    comps_s = list(vals_map_s.keys())
    vals_s = [vals_map_s[c] for c in comps_s]

    comps_d = list(vals_map_d.keys())
    vals_d = [vals_map_d[c] for c in comps_d]

    _apply_plot_theme()
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.0, 6.0), sharey=True)

    # Left: Single
    x_s = list(range(len(comps_s)))
    bar_width = 0.40
    bars_s = axL.bar(x_s, vals_s, width=bar_width, color=COLOR_SINGLE, edgecolor="none")
    axL.set_xticks(x_s)
    axL.set_xticklabels(comps_s, rotation=45, ha="right")
    axL.set_title("Singlekolonne")
    axL.set_ylabel(r"$\dot{E}$ [W]")
    _style_axis(axL, grid_axis="y")

    # Right: Double
    x_d = list(range(len(comps_d)))
    bars_d = axR.bar(x_d, vals_d, width=bar_width, color=COLOR_DOUBLE, edgecolor="none")
    axR.set_xticks(x_d)
    axR.set_xticklabels(comps_d, rotation=45, ha="right")
    axR.set_title("Doppelkolonne")
    _style_axis(axR, grid_axis="y")

    # Shared Y formatting: use same ticks on both axes
    # determine nice y-limits based on global max
    max_val = max([abs(v) for v in vals_s + vals_d] or [1.0])
    # allow negative values (e.g., turbine work)
    min_val = min([v for v in vals_s + vals_d] or [0.0])
    lower = min(0.0, min_val * 1.08)
    axL.set_ylim(lower, max_val * 1.08)

    # small legend centered below
    from matplotlib.lines import Line2D

    legend_handles = [Line2D([0], [0], color=COLOR_SINGLE, marker='s', markersize=8, linestyle='None'), Line2D([0], [0], color=COLOR_DOUBLE, marker='s', markersize=8, linestyle='None')]
    legend_labels = ["Singlekolonne", "Doppelkolonne"]
    fig.legend(legend_handles, legend_labels, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2, frameon=True, fancybox=False, edgecolor="black")

    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.22, top=0.92, wspace=0.22)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def parse_global_master_table(tex_path: Path):
    E_s1 = None
    E_comp = None
    E_prod = None
    W_turb = None
    E_dest = None
    E_loss = None
    E_in_sum = None
    product_stream = None

    with tex_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if "&" not in line or line.startswith("\\"):
                continue
            if line.startswith("Posten"):
                continue

            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) != 6:
                continue

            left_label = parts[0]
            left_value = _to_float_latex_number(parts[2])
            right_label = parts[3]
            right_value = _to_float_latex_number(parts[5])

            # tolerate multiple possible wording variants (German/modified)
            if "Strom 1" in left_label or "Feed" in left_label or "Feed-Strom" in left_label:
                E_s1 = left_value
            elif "Verdichtung" in left_label or "Verdichter" in left_label or "Verdichterleistung" in left_label:
                E_comp = left_value
            elif "Summe Ein" in left_label or "Summe Aufwand" in left_label or "Gesamtaufwand" in left_label:
                E_in_sum = left_value

            # right-hand labels: accept multiple variants
            if "Produkt" in right_label:
                E_prod = right_value
                m = re.search(r"\{(S[A-Z]*\d+)\}", parts[4])
                if m:
                    product_stream = m.group(1)
            elif "Turbine" in right_label or "Turbinen" in right_label or "Turbinenleistung" in right_label:
                W_turb = right_value
            elif "Vernichtung" in right_label or "Exergievernichtung" in right_label or "Exergievernichtung" in right_label:
                E_dest = right_value
            elif "Austritt" in right_label or "Austrittsverluste" in right_label or "Exergieverlust" in right_label:
                E_loss = right_value

    total_input = E_in_sum
    if total_input is None and isinstance(E_s1, (int, float)) and isinstance(E_comp, (int, float)):
        total_input = E_s1 + E_comp

    product_total = None
    if isinstance(E_prod, (int, float)) and isinstance(W_turb, (int, float)):
        product_total = E_prod + W_turb

    metrics_w = {
        r"$\dot{E}_{F,tot}$": total_input,
        r"$\dot{E}_{P,tot}$": product_total,
        r"$\dot{E}_{D,tot}$": E_dest,
        r"$\dot{E}_{L,tot}$": E_loss,
    }
    metrics_mw = {k: (v / 1e6 if isinstance(v, (int, float)) else None) for k, v in metrics_w.items()}
    raw = {
        "E_s1": E_s1,
        "E_comp": E_comp,
        "E_prod": E_prod,
        "W_turb": W_turb,
        "E_dest": E_dest,
        "E_loss": E_loss,
        "E_in_sum": E_in_sum,
    }
    return metrics_w, metrics_mw, product_stream, raw


def parse_global_vergleich_txt(txt_path: Path):
    """Parse Overleaf_LaTeX/tabellen/Global_Vergleich.txt (CSV-like) and
    return two dicts (metrics_single_mw, metrics_double_mw) with keys
    matching the plot labels: $\dot{E}_{F,tot}$, $\dot{E}_{P,tot}$,
    $\dot{E}_{D,tot}$, $\dot{E}_{L,tot}$. Values returned in MW.
    """
    if not txt_path.exists():
        return None, None

    def _parse_num_de(s: str) -> float | None:
        if s is None:
            return None
        s = s.strip().strip('"')
        if s == '':
            return None
        # remove thousand dots and convert decimal comma to dot
        s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None

    single = {}
    double = {}
    # mapping keywords to plot labels
    key_map = {
        'gesamtaufwand': r"$\dot{E}_{F,tot}$",
        'gesamtnutzen': r"$\dot{E}_{P,tot}$",
        'systemverluste': r"$\dot{E}_{L,tot}$",
        'exergievernichtung': r"$\dot{E}_{D,tot}$",
    }

    import csv
    try:
        with txt_path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=',', quotechar='"')
            # skip header if present
            first = next(reader, None)
            if first is None:
                return None, None
            # detect header: if first cell contains 'bilanz' or 'bilanzg', treat as header
            header_lower = str(first[0]).lower() if len(first) > 0 else ''
            if 'bilanz' in header_lower or 'bilanzgr' in header_lower or 'bilanzgr' in header_lower:
                pass  # already consumed header
            else:
                # first row is data, process it
                rows = [first]
                rows.extend(list(reader))
                reader = iter(rows)

            for parts in reader:
                if not parts:
                    continue
                label = parts[0].strip().strip('"').lower()
                # try to find numeric columns for single and double (last two columns)
                if len(parts) >= 3:
                    val_s = _parse_num_de(parts[-2])
                    val_d = _parse_num_de(parts[-1])
                else:
                    continue
                for k, out_key in key_map.items():
                    if k in label:
                        single[out_key] = (val_s / 1e6) if isinstance(val_s, (int, float)) else None
                        double[out_key] = (val_d / 1e6) if isinstance(val_d, (int, float)) else None
                        break
    except Exception:
        return None, None

    return single, double


def compute_specific_metrics(metrics_w: dict, product_mass_flow: float) -> dict:
    if not isinstance(product_mass_flow, (int, float)) or product_mass_flow <= 0:
        raise ValueError("Produktmassenstrom muss positiv sein.")

    specific_metrics = {}
    for key, value in metrics_w.items():
        if isinstance(value, (int, float)):
            specific_metrics[key] = value / product_mass_flow / 1e3
        else:
            specific_metrics[key] = None
    return specific_metrics


def _format_w_tex(value: float) -> str:
    """Format Watt values for LaTeX table: thousand-separators with dots, no decimals."""
    if value is None:
        return "-"
    try:
        iv = int(round(float(value)))
    except Exception:
        return "-"
    s = f"{iv:,}".replace(",", ".")
    return s


# legacy global_check builder removed — generation of intermediate
# global_check LaTeX files is deprecated. Canonical global tables under
# Overleaf_LaTeX/tabellen/ are the single source of truth.


def make_plot(df: pd.DataFrame, x_col: str, xlabel: str, out_path: Path, xlim=None):
    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 7))

    color = COLOR_SINGLE if "single" in out_path.stem.lower() else COLOR_DOUBLE
    # For visibility: do not modify numeric values, but apply a tiny visual
    # floor for extremely small non-zero shares so they are still visible in
    # the plot (e.g. 0.00something). This floor is only applied to the
    # displayed bar widths, labels keep the original unmodified values.
    display_vals = df[x_col].astype(float).copy()
    if x_col == "y_D_k" or x_col.lower().startswith("y_"):
        # floor relative to dynamic range but absolute minimum to avoid invisibility
        maxv = float(display_vals.abs().max() if not display_vals.empty else 0.0)
        floor = max(1e-6, maxv * 1e-5)
        # apply floor only to non-zero but sub-threshold values
        small_mask = (display_vals != 0.0) & (display_vals.abs() < floor)
        display_vals[small_mask] = display_vals[small_mask].apply(lambda v: floor if v > 0 else -floor)
    ax.barh(df["Component"], display_vals, color=color)
    ax.invert_yaxis()

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Component")
    if xlim is not None:
        ax.set_xlim(*xlim)
    _style_axis(ax, grid_axis="x")

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def _yd_axis_limit(df: pd.DataFrame, col: str = "y_D_k"):
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        return (0, 1)

    share_le_half = (values <= 0.5).mean()
    # If most components are very small, use a tighter axis to enhance visibility.
    if share_le_half >= 0.8:
        return (0, 0.3)

    # Compute a high-percentile upper bound and cap it at 0.3 to show more bars.
    upper = float(values.quantile(0.95)) * 1.1
    # Allow very small upper if data warrants, but cap maximum to 0.3
    upper = max(upper, 0.01)
    upper = min(upper, 0.3)
    return (0, upper)


def _annotate_vertical_bars(ax, bars, values, unit="MW"):
    ymax = ax.get_ylim()[1]
    offset = ymax * 0.015
    for bar, val in zip(bars, values):
        if val is None:
            continue
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + offset,
            f"{_format_decimal_comma(val, decimals=3, trim=False)} {unit}",
            ha="center",
            va="bottom",
            fontsize=9,
            rotation=0,
        )


def _annotate_horizontal_bars(ax, bars, unit="MW"):
    xmax = ax.get_xlim()[1]
    offset = xmax * 0.01
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + offset,
            bar.get_y() + bar.get_height() / 2,
            f"{_format_decimal_comma(width, decimals=3, trim=False)} {unit}",
            va="center",
            ha="left",
            fontsize=8,
        )


def _format_percent_de(value, digits: int = 4):
    """Format percent value for DE/LaTeX output.

    Do NOT coerce very small values to exactly zero here — keep precision so
    that tiny non-zero shares remain visible in textual outputs. Visual
    plotting may still apply a minimal floor for visibility only.
    """
    if value is None:
        return "-"
    x = float(value)
    # Normalize tiny numerical noise to exact 0 only when it's numerically zero.
    if x == 0.0:
        return f"{0:.{digits}f}".replace(".", ",")
    return f"{x:.{digits}f}".replace(".", ",")


def parse_component_yd_percent_from_json(json_path: Path, allowed_components: set[str] | None = None) -> dict[str, float]:
    raise RuntimeError(
        "JSON input is disabled for result calculations. Use the LaTeX tables under Overleaf_LaTeX/tabellen/ as authoritative sources."
    )


def _build_yd_large_vs_small_latex_table(
    yd_double_large: dict[str, float],
    yd_double_small: dict[str, float],
    yd_single_large: dict[str, float],
    yd_single_small: dict[str, float],
) -> str:
    def _rows_for_model(large_map: dict[str, float], small_map: dict[str, float], model_label: str):
        components = sorted(set(large_map.keys()) | set(small_map.keys()))

        rows = []
        for comp in components:
            y_large = large_map.get(comp)
            y_small = small_map.get(comp)
            diff = None
            if isinstance(y_large, (int, float)) and isinstance(y_small, (int, float)):
                diff = y_small - y_large

            rows.append(
                " & ".join(
                    [
                        model_label,
                        comp,
                        _format_percent_de(y_large),
                        _format_percent_de(y_small),
                        _format_percent_de(diff),
                    ]
                )
                + r" \\\\" 
            )
        return rows

    rows = []
    rows.extend(_rows_for_model(yd_double_large, yd_double_small, "Doppel"))
    rows.append(r"\hline")
    rows.extend(_rows_for_model(yd_single_large, yd_single_small, "Single"))

    lines = [
        r"\begin{longtable}{llrrr}",
        r"\caption{Vergleich der Exergievernichtungsanteile $y_D$ zwischen grosser und kleiner Variante} \\\\ ",
        r"\hline",
        r"Modell & Komponente & $y_D$ (Gross) [\%] & $y_D$ (Klein) [\%] & Differenz [Prozentpunkte] \\\\ ",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def round_latex_tables(tab_dir: Path):
    """Round numeric entries in LaTeX tables under `tab_dir`.

    - Skip files that contain 'stream_molfrac' in their filename.
    - For component tables (filename contains 'components'), round columns
      named 'Epsilon', 'yDK' or 'y*DK' to 4 decimals; round other numeric
      columns to 2 decimals.
    - For all other .tex files, round all numeric table cells to 2 decimals.
    """
    # If NO_ROUNDING requested, skip the rounding pass entirely.
    if globals().get("NO_ROUNDING", False):
        return

    num_re = re.compile(r"-?\d[\d\.,eE+\-]*")

    for tex_path in sorted(Path(tab_dir).glob("*.tex")):
        name = tex_path.name
        # skip any molfrac tables (user-specified)
        if "molfrac" in name.lower():
            continue

        is_component = "components" in name.lower()

        text = tex_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        out_lines = []

        # determine header column indices for component special columns
        special_indices = set()
        header_parsed = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith("\\"):
                out_lines.append(ln)
                continue
            if "&" not in ln:
                out_lines.append(ln)
                continue

            parts = [p.strip() for p in ln.replace("\\\\", "").split("&")]
            # if a header-like line (contains non-numeric tokens), parse it to find
            # special columns for component tables
            if is_component and not header_parsed:
                # header detection: remove common LaTeX markup and inspect for
                # varepsilon / epsilon and y_{D,k} / y^* patterns
                hdr_text = " ".join(parts)
                hdr_text_lower = hdr_text.lower()
                # look for common LaTeX token names
                if (r"\varepsilon" in hdr_text_lower) or ("epsilon" in hdr_text_lower) or ("y_{d" in hdr_text_lower) or ("y^" in hdr_text_lower) or ("y_d" in hdr_text_lower):
                    # identify indices of special columns by cleaning tokens
                    for idx, cell in enumerate(parts):
                        cell_norm = re.sub(r"[\\$%\{\}_\^\s,]", "", cell).lower()
                        if any(k in cell_norm for k in ("varepsilon", "epsilon", "ydk", "ydk", "y*dk", "yd,k", "y")):
                            # be conservative: ensure not to match Component or Type columns
                            if idx > 1:
                                special_indices.add(idx)
                    header_parsed = True
                    out_lines.append(ln)
                    continue

            # process data lines: replace numeric tokens according to rules
            new_parts = []
            for idx, cell in enumerate(parts):
                # preserve trailing backslashes removed earlier; we will add them back for last cell
                original = cell
                # find first numeric token in the cell
                m = num_re.search(cell)
                if m:
                    num_txt = m.group(0)
                    val = _to_float_latex_number(num_txt)
                    if val is None:
                        new_parts.append(original)
                        continue
                    # choose decimals
                    if is_component and idx in special_indices:
                        decimals = 4
                    else:
                        decimals = 2
                    # format using existing helper (decimal comma)
                    fmt = _format_decimal_comma(val, decimals=decimals, trim=False)
                    # replace numeric substring with formatted string
                    new_cell = cell[: m.start()] + fmt + cell[m.end():]
                    new_parts.append(new_cell)
                else:
                    new_parts.append(original)

            # reconstruct line: append trailing \\\ if original line had it
            line_ends_with = "\\\\" if ln.rstrip().endswith("\\\\") else ""
            out_lines.append(" & ".join(new_parts) + (" \\\\" if line_ends_with else ""))

        # write back only if changed
        new_text = "\n".join(out_lines) + "\n"
        if new_text != text:
            tex_path.write_text(new_text, encoding="utf-8")


if False:  # previously: run rounding on invocation; disabled to preserve raw/unrounded LaTeX values
    try:
        round_latex_tables(TAB_DIR)
    except Exception as e:
        print("Rounding tables failed:", e)


def compute_n2_recovery(streams_single: dict, streams_double: dict) -> dict:
    """Compute N2 recovery metrics for both models.

    Returns dict with keys:
      single_eta_pct   – η_N2 Single [%]:  N2 in product / N2 in feed × 100
      double_eta_pct   – η_N2 Double [%]
      single_ratio     – mol product / mol feed air (Single)
      double_ratio     – mol product / mol feed air (Double)
    """
    def _recovery(feed: dict, product: dict):
        n_feed    = feed["n_mol_s"]
        n_product = product["n_mol_s"]
        x_n2_feed    = feed["x_N2"]
        x_n2_product = product["x_N2"]
        n2_in_feed    = n_feed    * x_n2_feed
        n2_in_product = n_product * x_n2_product
        eta_pct = n2_in_product / n2_in_feed * 100.0
        ratio   = n_product / n_feed
        return eta_pct, ratio

    eta_s, ratio_s = _recovery(streams_single["S1"], streams_single["S24"])
    eta_d, ratio_d = _recovery(streams_double["S1"], streams_double["S32"])

    return {
        "single_eta_pct": eta_s,
        "double_eta_pct": eta_d,
        "single_ratio":   ratio_s,
        "double_ratio":   ratio_d,
    }


def _build_n2_recovery_latex_table(recovery: dict) -> str:
    """Build a small LaTeX table with N2 recovery results."""
    def fc(x, d=4):
        return _format_decimal_comma(x, d)

    rows = [
        r"Modell & $\eta_{N_2}$ [\%] & $\dot{n}_{\text{Produkt}} / \dot{n}_{\text{Luft}}$ [-] \\\\",
        r"\hline",
        f"Singlekolonne & {fc(recovery['single_eta_pct'], 2)} & {fc(recovery['single_ratio'], 6)} \\\\",
        f"Doppelkolonne & {fc(recovery['double_eta_pct'], 2)} & {fc(recovery['double_ratio'], 6)} \\\\",
    ]
    lines = [
        r"\begin{tabular}{lrr}",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{tabular}",
    ]
    return "\n".join(lines)


def _build_werte_tex(recovery: dict, streams_single: dict, streams_double: dict) -> str:
    """Build central LaTeX value file with simulation results as \newcommand macros."""

    def _fmt_value(value: float, digits: int = 10) -> str:
        if value is None:
            return "0"
        text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
        return text if text else "0"

    single_product = streams_single.get("S24", {})
    double_product = streams_double.get("S32", {})

    single_o2_ppm = float(single_product.get("x_O2", 0.0)) * 1e6
    single_ar_ppm = float(single_product.get("x_AR", 0.0)) * 1e6
    double_o2_ppm = float(double_product.get("x_O2", 0.0)) * 1e6
    double_ar_ppm = float(double_product.get("x_AR", 0.0)) * 1e6

    lines = [
        r"% werte.tex",
        r"% Zentrale Sammlung wichtiger Ergebniswerte aus der Simulation.",
        r"% Diese Datei wird automatisch von tools/plot_exergy_results.py erzeugt.",
        r"% Konventionen:",
        r"% - Alle Werte als \newcommand mit Prefix val",
        r"% - Nur Zahlenwerte im Makro, Einheit als Kommentar",
        "",
        r"% ------------------------------------------------------------",
        r"% Rueckgewinnung",
        r"% ------------------------------------------------------------",
        f"\\newcommand{{\\valSingleRueckgewinnungN2}}{{{_fmt_value(recovery.get('single_eta_pct'), 8)}}} % [%]",
        f"\\newcommand{{\\valDoppelRueckgewinnungN2}}{{{_fmt_value(recovery.get('double_eta_pct'), 8)}}} % [%]",
        f"\\newcommand{{\\valSingleN2ProduktZuLuft}}{{{_fmt_value(recovery.get('single_ratio'), 10)}}} % [-]",
        f"\\newcommand{{\\valDoppelN2ProduktZuLuft}}{{{_fmt_value(recovery.get('double_ratio'), 10)}}} % [-]",
        "",
        r"% ------------------------------------------------------------",
        r"% Druecke",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Massenstroeme",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Temperaturen",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Zusammensetzung N2-Produktstrom (ppm)",
        r"% Basis: Single S24, Doppel S32",
        r"% ------------------------------------------------------------",
        f"\\newcommand{{\\valSingleN2ProduktO2Ppm}}{{{_fmt_value(single_o2_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valSingleN2ProduktArPpm}}{{{_fmt_value(single_ar_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valDoppelN2ProduktO2Ppm}}{{{_fmt_value(double_o2_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valDoppelN2ProduktArPpm}}{{{_fmt_value(double_ar_ppm, 10)}}} % [ppm]",
    ]

    return "\n".join(lines) + "\n"


def _build_stream_comparison_latex_table(
    streams_single: dict,
    streams_double: dict,
) -> str:
    """Build LaTeX table comparing key process streams for Single and Double column models."""

    def fmt_x(x_n2: float, x_o2: float, x_ar: float) -> str:
        return (
            f"{_format_decimal_comma(x_n2, 6)} / "
            f"{_format_decimal_comma(x_o2, 6)} / "
            f"{_format_decimal_comma(x_ar, 6)}"
        )

    def fmt_p(p_Pa: float) -> str:
        return _format_decimal_comma(p_Pa / 1e5, 2)

    def fmt_T(T: float) -> str:
        return _format_decimal_comma(T, 2)

    def fmt_m(m: float) -> str:
        return _format_decimal_comma(m, 2)

    # (single_stream_key, double_stream_key, row_label)
    stream_defs = [
        ("S1",  "S1",  "Luft (S1)"),
        ("S24", "S32", r"N$_2$-Produkt (S24 / S32)"),
        ("S21", "S28", "Reststrom (S21 / S28)"),
    ]

    rows = []
    for s_key, d_key, label in stream_defs:
        s = streams_single.get(s_key, {})
        d = streams_double.get(d_key, {})
        m_s = fmt_m(s.get("m_dot"))
        m_d = fmt_m(d.get("m_dot"))
        p_val = fmt_p(s.get("p_Pa", 0.0))
        T_s = fmt_T(s.get("T", 0.0))
        T_d = fmt_T(d.get("T", 0.0))
        rows.append(
            f"{label} & {m_s} & {m_d} & {fmt_x(s.get('x_N2', 0.0), s.get('x_O2', 0.0), s.get('x_AR', 0.0))} "
            f"& {fmt_x(d.get('x_N2', 0.0), d.get('x_O2', 0.0), d.get('x_AR', 0.0))} & {p_val} & {T_s} & {T_d} \\\\" 
        )

    lines = [
        r"\begin{longtable}{lrrrrrrrr}",
        r"\caption{Gegenüberstellung der Ergebnisse der Prozesssimulation für das Singlekolonnenmodell und das Doppelkolonnenmodell anhand ausgewählter Stoffstromgrößen, Zusammensetzungen und thermodynamischer Zustandsparameter.} \\",
        r"\hline",
        (
            r"Stoffstrom & $\dot{m}_{\text{Single}}$ [kg/s] & $\dot{m}_{\text{Doppel}}$ [kg/s]"
            r" & $x_{\text{N}_2/\text{O}_2/\text{Ar},\,\text{Single}}$ [-] & $x_{\text{N}_2/\text{O}_2/\text{Ar},\,\text{Doppel}}$ [-]"
            r" & $p$ [bar] & $T_{\text{Single}}$ [K] & $T_{\text{Doppel}}$ [K] \\"
        ),
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def plot_grouped_system_metrics(metrics_double_mw, metrics_single_mw, out_path: Path):
    categories = [r"$\dot{E}_{F,tot}$", r"$\dot{E}_{P,tot}$", r"$\dot{E}_{D,tot}$", r"$\dot{E}_{L,tot}$"]
    vals_double = [metrics_double_mw.get(c) if metrics_double_mw.get(c) is not None else 0.0 for c in categories]
    vals_single = [metrics_single_mw.get(c) if metrics_single_mw.get(c) is not None else 0.0 for c in categories]

    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(categories))
    width = 0.38

    bars_double = ax.bar([i - width / 2 for i in x], vals_double, width=width, label="Doppelkolonne", color=COLOR_DOUBLE)
    bars_single = ax.bar([i + width / 2 for i in x], vals_single, width=width, label="Singlekolonne", color=COLOR_SINGLE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories)
    ax.set_ylabel("Exergiestrom [MW]")
    _style_axis(ax, grid_axis="y")
    _style_bottom_legend(ax)

    _annotate_vertical_bars(ax, bars_double, vals_double, unit="MW")
    _annotate_vertical_bars(ax, bars_single, vals_single, unit="MW")

    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_grouped_specific_system_metrics(metrics_double_spec, metrics_single_spec, out_path: Path):
    # Lookup keys correspond to the computed specific metrics (capital E labels).
    lookup_keys = [r"$\dot{E}_{F,tot}$", r"$\dot{E}_{P,tot}$", r"$\dot{E}_{D,tot}$", r"$\dot{E}_{L,tot}$"]
    # Display labels should show lowercase e as requested.
    display_labels = [r"$\dot{e}_{f,tot}$", r"$\dot{e}_{p,tot}$", r"$\dot{e}_{d,tot}$", r"$\dot{e}_{l,tot}$"]
    vals_double = [metrics_double_spec.get(k) if metrics_double_spec.get(k) is not None else 0.0 for k in lookup_keys]
    vals_single = [metrics_single_spec.get(k) if metrics_single_spec.get(k) is not None else 0.0 for k in lookup_keys]

    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(lookup_keys))
    width = 0.38

    bars_double = ax.bar([i - width / 2 for i in x], vals_double, width=width, label="Doppelkolonne", color=COLOR_DOUBLE)
    bars_single = ax.bar([i + width / 2 for i in x], vals_single, width=width, label="Singlekolonne", color=COLOR_SINGLE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(display_labels)
    ax.set_ylabel(r"Spezifischer Exergiestrom [kJ/kg]")
    _style_axis(ax, grid_axis="y")
    _style_bottom_legend(ax)

    _annotate_vertical_bars(ax, bars_double, vals_double, unit="kJ/kg")
    _annotate_vertical_bars(ax, bars_single, vals_single, unit="kJ/kg")

    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_component_pareto_comparison(df_double: pd.DataFrame, df_single: pd.DataFrame, out_path: Path):
    _apply_plot_theme()
    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)

    bars_d = axes[0].barh(df_double["Component"], df_double["E_D_MW"], color=COLOR_DOUBLE)
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[0].set_ylabel("Doppelkolonne")
    _style_axis(axes[0], grid_axis="x")
    _annotate_horizontal_bars(axes[0], bars_d, unit="MW")

    bars_s = axes[1].barh(df_single["Component"], df_single["E_D_MW"], color=COLOR_SINGLE)
    axes[1].invert_yaxis()
    axes[1].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[1].set_ylabel("Singlekolonne")
    _style_axis(axes[1], grid_axis="x")
    _annotate_horizontal_bars(axes[1], bars_s, unit="MW")

    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.08, top=0.98, hspace=0.25)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_absolute_ed_large_vs_small(df_large: pd.DataFrame, df_small: pd.DataFrame, model_label: str, out_path: Path):
    _apply_plot_theme()
    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)

    color = COLOR_DOUBLE if "doppel" in model_label.lower() else COLOR_SINGLE

    bars_large = axes[0].barh(df_large["Component"], df_large["E_D_MW"], color=color)
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[0].set_ylabel(f"{model_label} groß")
    _style_axis(axes[0], grid_axis="x")
    _annotate_horizontal_bars(axes[0], bars_large, unit="MW")

    bars_small = axes[1].barh(df_small["Component"], df_small["E_D_MW"], color=color)
    axes[1].invert_yaxis()
    axes[1].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[1].set_ylabel(f"{model_label} klein")
    _style_axis(axes[1], grid_axis="x")
    _annotate_horizontal_bars(axes[1], bars_small, unit="MW")

    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.08, top=0.98, hspace=0.25)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TAB_DIR, exist_ok=True)

    df_double = parse_component_table(TABLE_DOUBLE)
    df_single = parse_component_table(TABLE_SINGLE)
    # Recompute y_D_k from the component E_D totals in the LaTeX tables
    # User request: y_D_k = E_D_component / sum(|E_D_component|) per model
    def _recompute_yd(df: pd.DataFrame) -> pd.DataFrame:
        if "E_D_W" not in df.columns:
            return df
        total = df["E_D_W"].abs().sum()
        if total <= 0:
            df["y_D_k"] = 0.0
        else:
            df["y_D_k"] = df["E_D_W"].abs() / total
        return df

    df_double = _recompute_yd(df_double)
    df_single = _recompute_yd(df_single)
    ed_map_double = parse_component_ed_map(TABLE_DOUBLE)
    ed_map_single = parse_component_ed_map(TABLE_SINGLE)
    df_mol_double = parse_molfrac_table(MOLFRAC_DOUBLE)
    df_mol_single = parse_molfrac_table(MOLFRAC_SINGLE)
    stream_mdot_double = parse_stream_mass_flows(STREAMS_DOUBLE)
    stream_mdot_single = parse_stream_mass_flows(STREAMS_SINGLE)
    # Legacy `global_check` files are no longer used. Canonical global tables
    # under Overleaf_LaTeX/tabellen/ are authoritative; do not seed or generate
    # intermediate `global_check` files.

    # Parse the canonical global LaTeX tables (do not use legacy global_check files)
    metrics_double_w, metrics_double_mw, product_stream_double, raw_double = parse_global_master_table(
        TAB_DIR / "aspen_luftzerlegung_global_double.tex"
    )
    metrics_single_w, metrics_single_mw, product_stream_single, raw_single = parse_global_master_table(
        TAB_DIR / "aspen_luftzerlegung_global_single.tex"
    )

    # Also compute global metrics from component and stream tables (authoritative LaTeX sources)
    streams_double_thermo = parse_stream_thermo_data(STREAMS_DOUBLE)
    streams_single_thermo = parse_stream_thermo_data(STREAMS_SINGLE)

    computed_double = compute_global_metrics_from_tables(df_double, streams_double_thermo, product_stream_double, "Doppelkolonne")
    computed_single = compute_global_metrics_from_tables(df_single, streams_single_thermo, product_stream_single, "Einzelkolonne")

    # prefer computed product stream identifiers when parse did not provide them
    product_stream_double = computed_double.get("product_stream") or product_stream_double
    product_stream_single = computed_single.get("product_stream") or product_stream_single

    # Prefer computed values from tables when available, else fall back to parsed global file
    def _coalesce(a, b):
        return a if isinstance(a, (int, float)) else b

    # Overwrite metrics_w entries with computed values when available to keep consistency
    if isinstance(metrics_double_w, dict):
        metrics_double_w[r"$\dot{E}_{F,tot}$"] = _coalesce(computed_double.get("E_in_sum"), metrics_double_w.get(r"$\dot{E}_{F,tot}$"))
        metrics_double_w[r"$\dot{E}_{P,tot}$"] = _coalesce(computed_double.get("E_P"), metrics_double_w.get(r"$\dot{E}_{P,tot}$"))
        metrics_double_w[r"$\dot{E}_{D,tot}$"] = _coalesce(computed_double.get("E_D"), metrics_double_w.get(r"$\dot{E}_{D,tot}$"))
        metrics_double_w[r"$\dot{E}_{L,tot}$"] = _coalesce(computed_double.get("E_L"), metrics_double_w.get(r"$\dot{E}_{L,tot}$"))
    if isinstance(metrics_single_w, dict):
        metrics_single_w[r"$\dot{E}_{F,tot}$"] = _coalesce(computed_single.get("E_in_sum"), metrics_single_w.get(r"$\dot{E}_{F,tot}$"))
        metrics_single_w[r"$\dot{E}_{P,tot}$"] = _coalesce(computed_single.get("E_P"), metrics_single_w.get(r"$\dot{E}_{P,tot}$"))
        metrics_single_w[r"$\dot{E}_{D,tot}$"] = _coalesce(computed_single.get("E_D"), metrics_single_w.get(r"$\dot{E}_{D,tot}$"))
        metrics_single_w[r"$\dot{E}_{L,tot}$"] = _coalesce(computed_single.get("E_L"), metrics_single_w.get(r"$\dot{E}_{L,tot}$"))

    try:
        # build double using computed values where possible
        raw_for_double = raw_double.copy() if isinstance(raw_double, dict) else {}
        raw_for_double["E_in_sum"] = _coalesce(computed_double.get("E_in_sum"), raw_double.get("E_in_sum") if isinstance(raw_double, dict) else None)
        raw_for_double["E_prod"] = _coalesce(computed_double.get("E_P"), raw_double.get("E_prod") if isinstance(raw_double, dict) else None)
        raw_for_double["E_dest"] = _coalesce(computed_double.get("E_D"), raw_double.get("E_dest") if isinstance(raw_double, dict) else None)
        raw_for_double["E_loss"] = _coalesce(computed_double.get("E_L"), raw_double.get("E_loss") if isinstance(raw_double, dict) else None)
        # ensure Verdichterleistung is present: prefer raw/global, then derived from components/streams, then JSON fallback
        if not isinstance(raw_for_double.get("E_comp"), (int, float)):
            # try to derive from parsed values: compressors in components may not include power, so try JSON
            comp_power = parse_compressor_power_from_json(JSON_DOUBLE)
            if isinstance(comp_power, (int, float)):
                raw_for_double["E_comp"] = comp_power

        # fill Feed-Strom 1 from stream thermo table if available
        try:
            s1_val = streams_double_thermo.get("S1", {}).get("E_W") if streams_double_thermo.get("S1") else None
            if isinstance(s1_val, (int, float)) and not isinstance(raw_for_double.get("E_s1"), (int, float)):
                raw_for_double["E_s1"] = float(s1_val)
        except Exception:
            pass

        # if Gesamtaufwand missing, try to compute as E_s1 + E_comp
        if not isinstance(raw_for_double.get("E_in_sum"), (int, float)):
            if isinstance(raw_for_double.get("E_s1"), (int, float)) and isinstance(raw_for_double.get("E_comp"), (int, float)):
                raw_for_double["E_in_sum"] = float(raw_for_double.get("E_s1")) + float(raw_for_double.get("E_comp"))

        # do not generate legacy global_check double table
    except Exception:
        pass
    try:
        raw_for_single = raw_single.copy() if isinstance(raw_single, dict) else {}
        raw_for_single["E_in_sum"] = _coalesce(computed_single.get("E_in_sum"), raw_single.get("E_in_sum") if isinstance(raw_single, dict) else None)
        raw_for_single["E_prod"] = _coalesce(computed_single.get("E_P"), raw_single.get("E_prod") if isinstance(raw_single, dict) else None)
        raw_for_single["E_dest"] = _coalesce(computed_single.get("E_D"), raw_single.get("E_dest") if isinstance(raw_single, dict) else None)
        raw_for_single["E_loss"] = _coalesce(computed_single.get("E_L"), raw_single.get("E_loss") if isinstance(raw_single, dict) else None)
        if not isinstance(raw_for_single.get("E_comp"), (int, float)):
            comp_power = parse_compressor_power_from_json(JSON_SINGLE)
            if isinstance(comp_power, (int, float)):
                raw_for_single["E_comp"] = comp_power

        # fill Feed-Strom 1 from stream thermo table if available
        try:
            s1_val = streams_single_thermo.get("S1", {}).get("E_W") if streams_single_thermo.get("S1") else None
            if isinstance(s1_val, (int, float)) and not isinstance(raw_for_single.get("E_s1"), (int, float)):
                raw_for_single["E_s1"] = float(s1_val)
        except Exception:
            pass

        # if Gesamtaufwand missing, try to compute as E_s1 + E_comp
        if not isinstance(raw_for_single.get("E_in_sum"), (int, float)):
            if isinstance(raw_for_single.get("E_s1"), (int, float)) and isinstance(raw_for_single.get("E_comp"), (int, float)):
                raw_for_single["E_in_sum"] = float(raw_for_single.get("E_s1")) + float(raw_for_single.get("E_comp"))

        # do not generate legacy global_check single table
    except Exception:
        pass

    # Inject authoritative unrounded stream E_W values into the canonical global single/double files
    try:
        single_keys = {"feed": "S1", "product": computed_single.get("product_stream") or "S24", "rest": "S21"}
        double_keys = {"feed": "S1", "product": computed_double.get("product_stream") or "S32", "rest": "S28"}
        _inject_streams_into_canonical(TAB_DIR / "aspen_luftzerlegung_global_single.tex", streams_single_thermo, single_keys)
        _inject_streams_into_canonical(TAB_DIR / "aspen_luftzerlegung_global_double.tex", streams_double_thermo, double_keys)
    except Exception:
        pass

    if product_stream_double not in stream_mdot_double:
        raise ValueError(f"Produktstrom {product_stream_double} nicht in {STREAMS_DOUBLE} gefunden.")
    if product_stream_single not in stream_mdot_single:
        raise ValueError(f"Produktstrom {product_stream_single} nicht in {STREAMS_SINGLE} gefunden.")

    metrics_double_spec = compute_specific_metrics(metrics_double_w, stream_mdot_double[product_stream_double])
    metrics_single_spec = compute_specific_metrics(metrics_single_w, stream_mdot_single[product_stream_single])

    make_plot(
        df_double,
        x_col="E_D_MW",
        xlabel=r"$\dot{E}_D$ [MW]",
        out_path=OUT_DIR / "doppelkolonne_E_D_barh.png",
    )
    make_plot(
        df_double,
        x_col="y_D_k",
        xlabel=r"$y_{D,k}$ [-]",
        xlim=_yd_axis_limit(df_double, "y_D_k"),
        out_path=OUT_DIR / "doppelkolonne_yDk_barh.png",
    )

    make_plot(
        df_single,
        x_col="E_D_MW",
        xlabel=r"$\dot{E}_D$ [MW]",
        out_path=OUT_DIR / "singlekolonne_E_D_barh.png",
    )
    make_plot(
        df_single,
        x_col="y_D_k",
        xlabel=r"$y_{D,k}$ [-]",
        xlim=_yd_axis_limit(df_single, "y_D_k"),
        out_path=OUT_DIR / "singlekolonne_yDk_barh.png",
    )

    # Prefer canonical simple CSV-like global comparison table when present
    gv_single, gv_double = parse_global_vergleich_txt(TAB_DIR / "Global_Vergleich.txt")
    if isinstance(gv_single, dict) and isinstance(gv_double, dict):
        # If the file provides the values, use them directly for the grouped plot.
        metrics_double_mw = gv_double
        metrics_single_mw = gv_single

    plot_grouped_system_metrics(
        metrics_double_mw,
        metrics_single_mw,
        out_path=OUT_DIR / "vergleich_global_kennzahlen_grouped.png",
    )

    # If Global_Vergleich.txt provided values, compute specific metrics from
    # those canonical MW values divided by product mass flows (S24 for Single,
    # S32 for Double) to get kJ/kg.
    if isinstance(gv_single, dict) and isinstance(gv_double, dict):
        try:
            mdot_single = stream_mdot_single.get(product_stream_single)
            mdot_double = stream_mdot_double.get(product_stream_double)
            metrics_single_spec = {}
            metrics_double_spec = {}
            for k in [r"$\dot{E}_{F,tot}$", r"$\dot{E}_{P,tot}$", r"$\dot{E}_{D,tot}$", r"$\dot{E}_{L,tot}$"]:
                v_s_mw = metrics_single_mw.get(k)
                v_d_mw = metrics_double_mw.get(k)
                metrics_single_spec[k] = (v_s_mw * 1000.0 / mdot_single) if (isinstance(v_s_mw, (int, float)) and mdot_single) else None
                metrics_double_spec[k] = (v_d_mw * 1000.0 / mdot_double) if (isinstance(v_d_mw, (int, float)) and mdot_double) else None
        except Exception:
            # fallback to previously computed specific metrics
            pass

    plot_grouped_specific_system_metrics(
        metrics_double_spec,
        metrics_single_spec,
        out_path=OUT_DIR / "vergleich_global_kennzahlen_grouped_spezifisch.png",
    )

    plot_component_pareto_comparison(
        df_double,
        df_single,
        out_path=OUT_DIR / "vergleich_component_pareto_ED.png",
    )

    # Gross/Klein comparison plots removed per user request.

    plot_grouped_product_purity(
        df_mol_double,
        df_mol_single,
        out_path=OUT_DIR / "vergleich_reinheit_produktstroeme_dualaxis.png",
    )

    plot_block_yd_comparison(
        ed_map_single,
        ed_map_double,
        out_path=OUT_DIR / "vergleich_yD_funktionsbloecke.png",
    )

    # Gross/Klein y_D comparison removed per user request.

    # Build stream thermo + molfraction payloads from LaTeX tables (not JSON)
    thermo_tex_single = parse_stream_thermo_data(STREAMS_SINGLE)
    thermo_tex_double = parse_stream_thermo_data(STREAMS_DOUBLE)

    # mol fraction tables provide x_N2, x_O2, x_AR
    mol_single = parse_molfrac_table(MOLFRAC_SINGLE).set_index("Stream").to_dict(orient="index")
    mol_double = parse_molfrac_table(MOLFRAC_DOUBLE).set_index("Stream").to_dict(orient="index")

    def _combine_streams(thermo_map, mol_map, keys: list[str]):
        out = {}
        for k in keys:
            t = thermo_map.get(k, {})
            m = mol_map.get(k, {})
            out[k] = {
                "m_dot": t.get("m_dot"),
                "n_mol_s": t.get("n_mol_s"),
                "T": t.get("T"),
                "p_Pa": t.get("p_Pa"),
                "x_N2": m.get("x_N2", 0.0),
                "x_O2": m.get("x_O2", 0.0),
                "x_AR": m.get("x_AR", 0.0),
            }
        return out

    thermo_single = _combine_streams(thermo_tex_single, mol_single, ["S1", "S21", "S24"])
    thermo_double = _combine_streams(thermo_tex_double, mol_double, ["S1", "S28", "S32"])

    recovery = compute_n2_recovery(thermo_single, thermo_double)
    print("\n=== N2-Rueckgewinnung ===")
    print(f"  Single  eta_N2 = {recovery['single_eta_pct']:.4f} %   ratio = {recovery['single_ratio']:.6f} mol/mol")
    print(f"  Doppel  eta_N2 = {recovery['double_eta_pct']:.4f} %   ratio = {recovery['double_ratio']:.6f} mol/mol")
    recovery_table = _build_n2_recovery_latex_table(recovery)
    recovery_out = TAB_DIR / "aspen_luftzerlegung_n2_recovery.tex"
    with recovery_out.open("w", encoding="utf-8") as f:
        f.write(recovery_table)
    print("N2-Rueckgewinnung gespeichert:", recovery_out)

    stream_comp_table = _build_stream_comparison_latex_table(
        thermo_single,
        thermo_double,
    )
    stream_comp_out = TAB_DIR / "aspen_luftzerlegung_streams_vergleich.tex"
    with stream_comp_out.open("w", encoding="utf-8") as f:
        f.write(stream_comp_table)

    werte_tex = _build_werte_tex(recovery, thermo_single, thermo_double)
    with WERTE_TEX.open("w", encoding="utf-8") as f:
        f.write(werte_tex)
    print("Werte-Datei gespeichert:", WERTE_TEX)

    # additional comparison plot: component work side-by-side
    try:
        out_cmp = OUT_DIR / "vergleich_component_work_side_by_side.png"
        # Use the dedicated component work tables (single and double)
        plot_component_work_side_by_side(TAB_DIR / "aspen_luftzerlegung_components_work_single.tex", TAB_DIR / "aspen_luftzerlegung_components_work.tex", out_cmp)
        print("Component work comparison saved:", out_cmp)
    except Exception as e:
        print("Fehler beim Erstellen des Vergleichsplots:", e)

    print("Plots gespeichert in:")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
