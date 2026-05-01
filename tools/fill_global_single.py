from pathlib import Path
from tools.plot_exergy_results import parse_stream_thermo_data, _format_w_tex, STREAMS_SINGLE, TAB_DIR


def main():
    tex = TAB_DIR / "aspen_luftzerlegung_global_single.tex"
    if not tex.exists():
        print("Target single global tex not found:", tex)
        return

    thermo = parse_stream_thermo_data(STREAMS_SINGLE)

    def fmt(k):
        s = thermo.get(k)
        if not isinstance(s, dict):
            return "-"
        return _format_w_tex(s.get("E_W"))

    replacements = {
        "$\\dot{E}_{S1}$ & 0 W": f"$\\dot{{E}}_{{S1}}$ & {fmt('S1')}",
        "$\\dot{E}_{S24}$ & 0 W": f"$\\dot{{E}}_{{S24}}$ & {fmt('S24')}",
        "$\\dot{E}_{S21}$ & 0 W": f"$\\dot{{E}}_{{S21}}$ & {fmt('S21')}",
    }

    text = tex.read_text(encoding="utf-8")

    old1 = "\\textbf{Zugef\u00fchrte Exergie} & Feed-Strom Luft (S1) & $\\dot{E}_{S1}$ & 0 W \\\\"
    new1 = f"\\textbf{{Zugef\u00fchrte Exergie}} & Feed-Strom Luft (S1) & $\\dot{{E}}_{{S1}}$ & {fmt('S1')} \\\\"

    old2 = "\\textbf{Abgef\u00fchrte Exergie} & $N_2$-Produktstrom (S24) & $\\dot{E}_{S24}$ & 0 W \\\\"
    new2 = f"\\textbf{{Abgef\u00fchrte Exergie}} & $N_2$-Produktstrom (S24) & $\\dot{{E}}_{{S24}}$ & {fmt('S24')} \\\\"

    old3 = " & Restgas / Abgas (S21) & $\\dot{E}_{S21}$ & 0 W \\\\"
    new3 = f" & Restgas / Abgas (S21) & $\\dot{{E}}_{{S21}}$ & {fmt('S21')} \\\\"

    text = text.replace(old1, new1).replace(old2, new2).replace(old3, new3)

    tex.write_text(text, encoding="utf-8")
    print("Updated:", tex)


if __name__ == "__main__":
    main()
