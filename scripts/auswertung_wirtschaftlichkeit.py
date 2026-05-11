import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Output directories
PLOTS_DIR = Path(r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder")
TABLES_DIR = Path("auswertung_tabellen")


def ensure_dirs():
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)


def deutsch_format(x, decimals=1, thousands_sep='.', decimal_sep=','):
    # Format number for labels in German style (only for display)
    fmt = f"{x:,.{decimals}f}"
    # Python uses ',' as thousands sep and '.' decimal when using locale-independent formatting with ,
    # replace to desired German style
    parts = fmt.split('.')
    int_part = parts[0].replace(',', thousands_sep)
    dec_part = parts[1] if len(parts) > 1 else '0'*decimals
    return f"{int_part}{decimal_sep}{dec_part}"


def main():
    ensure_dirs()

    variants = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]

    # Raw data
    netto_kw = {
        "Einzel klein": 3003.57,
        "Einzel groß": 10094.96,
        "Doppel klein": 2272.78,
        "Doppel groß": 7505.85,
    }

    fci = {
        "Einzel klein": 6216132,
        "Einzel groß": 18066209,
        "Doppel klein": 8241858,
        "Doppel groß": 42959075,
    }

    tci = fci.copy()

    # Jahreskosten
    CC_L = {"Einzel klein": 730396, "Einzel groß": 2122780, "Doppel klein": 968418, "Doppel groß": 5047691}
    OM_L = {"Einzel klein": 377412, "Einzel groß": 1096890, "Doppel klein": 500404, "Doppel groß": 2608260}
    EC_L = {"Einzel klein": 5063683, "Einzel groß": 17018972, "Doppel klein": 3831653, "Doppel groß": 12654022}
    TRR_L = {"Einzel klein": 6171491, "Einzel groß": 20238641, "Doppel klein": 5300475, "Doppel groß": 20309974}

    # Sensitivitäten TRR
    strompreise = [0.13, 0.16, 0.19]
    trr_sens = {
        "Einzel klein": [5222050, 6171491, 7120931],
        "Einzel groß": [17047584, 20238641, 23429699],
        "Doppel klein": [4582040, 5300475, 6018909],
        "Doppel groß": [17937345, 20309974, 22682603],
    }

    # Stickstoff
    n2_mass_flow = {"Einzel klein": 4.65, "Einzel groß": 15.91, "Doppel klein": 4.65, "Doppel groß": 15.91}
    n2_annual_t = {"Einzel klein": 133920, "Einzel groß": 458208, "Doppel klein": 133920, "Doppel groß": 458208}
    spezif_kosten = {"Einzel klein": 46.08, "Einzel groß": 44.17, "Doppel klein": 39.58, "Doppel groß": 44.32}

    # Sensitivitäten spezifische Kosten
    spezif_sens = {
        "Einzel klein": [38.99, 46.08, 53.17],
        "Einzel groß": [37.20, 44.17, 51.13],
        "Doppel klein": [34.21, 39.58, 44.94],
        "Doppel groß": [39.15, 44.32, 49.50],
    }

    # Bare module costs
    kostenblaecke = [
        "Verdichter",
        "Turbine/Expander",
        "Zwischenkühler",
        "Hauptwärmeübertrager",
        "Reboiler/Kondensatoren",
        "Kolonnen",
        "Luftvorreinigung",
    ]

    bare_module = {
        "Einzel klein": [2139703, 431846, 91513, 375332, 568371, 657500, 341077],
        "Einzel groß": [3766430, 899251, 247739, 1384486, 5290883, 802300, 991287],
        "Doppel klein": [2253355, 179827, 70120, 827218, 992632, 1329700, 452228],
        "Doppel groß": [3967903, 374456, 176253, 16665085, 6692487, 1588200, 2357151],
    }

    # --- Create DataFrames / Tables ---
    # 1. Nettoleistung (MW) und FCI (Mio EUR)
    df_netto_fci = pd.DataFrame(
        {
            "Elektrische Nettoleistung (MW)": [netto_kw[v] / 1000.0 for v in variants],
            "FCI (Mio. EUR)": [fci[v] / 1e6 for v in variants],
        },
        index=variants,
    )

    # 2. Jahreskosten mit TCI, CC_L, OM_L, EC_L, TRR_L (in Mio EUR)
    df_jahreskosten = pd.DataFrame(
        {
            "TCI (Mio. EUR)": [tci[v] / 1e6 for v in variants],
            "CC_L (Mio. EUR/a)": [CC_L[v] / 1e6 for v in variants],
            "OM_L (Mio. EUR/a)": [OM_L[v] / 1e6 for v in variants],
            "EC_L (Mio. EUR/a)": [EC_L[v] / 1e6 for v in variants],
            "TRR_L (Mio. EUR/a)": [TRR_L[v] / 1e6 for v in variants],
        },
        index=variants,
    )

    # 3. Stickstoffproduktion und spezifische Kosten
    df_stickstoff = pd.DataFrame(
        {
            "N2-Massenstrom (kg/s)": [n2_mass_flow[v] for v in variants],
            "N2-Produktion (t/a)": [n2_annual_t[v] for v in variants],
            "Spezifische Kosten (EUR/t_N2)": [spezif_kosten[v] for v in variants],
        },
        index=variants,
    )

    # 4. TRR Sensitivität
    df_trr_sens = pd.DataFrame({v: trr_sens[v] for v in variants}, index=strompreise)
    df_trr_sens.index.name = "Strompreis (EUR/kWh)"

    # 5. Spezifische Kosten Sensitivität
    df_spez_sens = pd.DataFrame({v: spezif_sens[v] for v in variants}, index=strompreise)
    df_spez_sens.index.name = "Strompreis (EUR/kWh)"

    # 6. Bare-Module Kosten nach Kostenblock und Variante (Mio EUR)
    df_bare = pd.DataFrame({v: [x / 1e6 for x in bare_module[v]] for v in variants}, index=kostenblaecke)

    # 7. Prozenttabelle der Bare-Module-Kostenanteile je Variante
    df_bare_pct = df_bare.div(df_bare.sum(axis=0), axis=1) * 100

    # --- Save tables ---
    # Individual CSVs
    tables = [
        ("table_01_nettoleistung_fci.csv", df_netto_fci),
        ("table_02_jahreskosten.csv", df_jahreskosten),
        ("table_03_stickstoff.csv", df_stickstoff),
        ("table_04_trr_sens.csv", df_trr_sens),
        ("table_05_spez_sens.csv", df_spez_sens),
        ("table_06_bare_module.csv", df_bare),
        ("table_07_bare_module_pct.csv", df_bare_pct),
    ]

    for fname, df in tables:
        path = Path("auswertung_tabellen") / fname
        df.to_csv(path, float_format="%.6f", sep=';')

    # Combined Excel
    excel_path = Path("auswertung_tabellen") / "auswertung_tabs.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_netto_fci.to_excel(writer, sheet_name="Nettoleistung_FCI")
        df_jahreskosten.to_excel(writer, sheet_name="Jahreskosten")
        df_stickstoff.to_excel(writer, sheet_name="Stickstoff")
        df_trr_sens.to_excel(writer, sheet_name="TRR_Sensitivitaet")
        df_spez_sens.to_excel(writer, sheet_name="Spez_Sensitivitaet")
        df_bare.to_excel(writer, sheet_name="Bare_Module")
        df_bare_pct.to_excel(writer, sheet_name="Bare_Module_Prozent")

    # --- Plotting setup ---
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.color": "#cccccc",
        "grid.alpha": 0.3,
    })

    # Colors: variant colors (colorblind-friendly using tab10)
    cmap = plt.get_cmap("tab10")
    variant_colors = {
        "Einzel klein": cmap(0),
        "Einzel groß": cmap(1),
        "Doppel klein": cmap(2),
        "Doppel groß": cmap(3),
    }

    # Colors for cost blocks
    block_colors = {
        "Verdichter": cmap(4),
        "Turbine/Expander": cmap(5),
        "Zwischenkühler": cmap(6),
        "Hauptwärmeübertrager": cmap(7),
        "Reboiler/Kondensatoren": cmap(8),
        "Kolonnen": cmap(9),
        "Luftvorreinigung": (0.6, 0.6, 0.6),
    }

    fontsize = {"title": 13, "axes": 11, "ticks": 10, "legend": 9, "values": 9}

    # Helper for saving both png and pdf
    def savefig(base_name, fig):
        png = PLOTS_DIR / (base_name + ".png")
        fig.savefig(png, dpi=300, bbox_inches="tight")

    # Plot 1: Nettoleistung (MW)
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(variants))
    values_mw = [netto_kw[v] / 1000.0 for v in variants]
    bars = ax.bar(x, values_mw, width=0.65, color=[variant_colors[v] for v in variants])
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("Elektrische Nettoleistung (MW)", fontsize=fontsize["axes"])
    ax.set_title("Elektrische Nettoleistungsaufnahme der Prozessvarianten.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # values
    for b, val in zip(bars, values_mw):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(values_mw)*0.01, deutsch_format(val, 1),
                ha="center", va="bottom", fontsize=fontsize["values"])
    plt.tight_layout()
    savefig("plot_01_nettoleistung", fig)
    plt.close(fig)

    # Plot 2: FCI in Mio EUR
    fig, ax = plt.subplots(figsize=(8, 5))
    values_mio = [fci[v] / 1e6 for v in variants]
    bars = ax.bar(x, values_mio, width=0.65, color=[variant_colors[v] for v in variants])
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("FCI (Mio. EUR)", fontsize=fontsize["axes"])
    ax.set_title("Fixed Capital Investment der Prozessvarianten.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for b, val in zip(bars, values_mio):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(values_mio)*0.01, deutsch_format(val, 1),
                ha="center", va="bottom", fontsize=fontsize["values"])
    plt.tight_layout()
    savefig("plot_02_fci", fig)
    plt.close(fig)

    # Plot 3: Gestapeltes Balkendiagramm Bare-Module (Mio EUR)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottoms = np.zeros(len(variants))
    for block in kostenblaecke:
        vals = [bare_module[v][kostenblaecke.index(block)] / 1e6 for v in variants]
        ax.bar(x, vals, bottom=bottoms, color=block_colors[block], label=block)
        bottoms += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("Kosten (Mio. EUR)", fontsize=fontsize["axes"])
    ax.set_title("Verteilung der Bare-Module-Kosten nach Kostenblöcken.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # show totals above bars
    totals = df_bare.sum(axis=0).values
    for xi, tot in zip(x, totals):
        ax.text(xi, tot + max(totals)*0.01, deutsch_format(tot, 1), ha="center", va="bottom", fontsize=fontsize["values"])
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_03_bare_module_kostenstruktur", fig)
    plt.close(fig)

    # Plot 4: Prozentuale Verteilung der Bare-Module-Kosten
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottoms = np.zeros(len(variants))
    for block in kostenblaecke:
        vals = [df_bare_pct.loc[block, v] for v in variants]
        ax.bar(x, vals, bottom=bottoms, color=block_colors[block], label=block)
        bottoms += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("Anteil (%)", fontsize=fontsize["axes"])
    ax.set_title("Prozentuale Verteilung der Bare-Module-Kosten.", fontsize=fontsize["title"])
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_04_bare_module_anteile", fig)
    plt.close(fig)

    # Plot 5: Gestapelte Jahreskosten (Mio EUR/a) CC_L + OM_L + EC_L
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottoms = np.zeros(len(variants))
    for comp in ["CC_L", "OM_L", "EC_L"]:
        vals = [ (CC_L[v] if comp=="CC_L" else (OM_L[v] if comp=="OM_L" else EC_L[v]))/1e6 for v in variants]
        ax.bar(x, vals, bottom=bottoms, label=comp, width=0.65)
        bottoms += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("Jahreskosten (Mio. EUR/a)", fontsize=fontsize["axes"])
    ax.set_title("Zusammensetzung des jährlichen Total Revenue Requirement.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    totals = [TRR_L[v]/1e6 for v in variants]
    for xi, tot in zip(x, totals):
        ax.text(xi, tot + max(totals)*0.01, deutsch_format(tot, 1), ha="center", va="bottom", fontsize=fontsize["values"])
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_05_trr_aufteilung", fig)
    plt.close(fig)

    # Plot 6: TRR Sensitivität (Linie)
    fig, ax = plt.subplots(figsize=(8, 5))
    for v in variants:
        yvals = [val / 1e6 for val in trr_sens[v]]
        ax.plot(strompreise, yvals, marker='o', linewidth=2, markersize=5, label=v, color=variant_colors[v])
    ax.set_xticks(strompreise)
    ax.set_xlabel("Strompreis (EUR/kWh)", fontsize=fontsize["axes"])    
    ax.set_ylabel("TRR_L (Mio. EUR/a)", fontsize=fontsize["axes"])
    ax.set_title("Sensitivität des jährlichen TRR gegenüber dem Strompreis.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_06_trr_sensitivitaet_strompreis", fig)
    plt.close(fig)

    # Plot 7: Spezifische Kosten Basisfall
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [spezif_kosten[v] for v in variants]
    bars = ax.bar(x, vals, width=0.65, color=[variant_colors[v] for v in variants])
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax.set_ylabel("EUR/t_N2", fontsize=fontsize["axes"])
    ax.set_title("Spezifische Stickstoffbereitstellungskosten im Basisfall.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for b, val in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(vals)*0.01, deutsch_format(val, 1),
                ha="center", va="bottom", fontsize=fontsize["values"])
    plt.tight_layout()
    savefig("plot_07_spezifische_kosten_basisfall", fig)
    plt.close(fig)

    # Plot 8: Spezifische Kosten Sensitivität
    fig, ax = plt.subplots(figsize=(8, 5))
    for v in variants:
        yvals = [val for val in spezif_sens[v]]
        ax.plot(strompreise, yvals, marker='o', linewidth=2, markersize=5, label=v, color=variant_colors[v])
    ax.set_xticks(strompreise)
    ax.set_xlabel("Strompreis (EUR/kWh)", fontsize=fontsize["axes"])    
    ax.set_ylabel("EUR/t_N2", fontsize=fontsize["axes"])
    ax.set_title("Sensitivität der spezifischen Stickstoffbereitstellungskosten gegenüber dem Strompreis.", fontsize=fontsize["title"])
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_08_spezifische_kosten_sensitivitaet", fig)
    plt.close(fig)

    # Plot 9: Doppelachsenplot FCI vs Nettoleistung
    fig, ax1 = plt.subplots(figsize=(8, 5))
    bars = ax1.bar(x, [fci[v] / 1e6 for v in variants], width=0.65, color=[variant_colors[v] for v in variants])
    ax1.set_xticks(x)
    ax1.set_xticklabels(variants, rotation=25, ha="right", fontsize=fontsize["ticks"])    
    ax1.set_ylabel("FCI (Mio. EUR)", fontsize=fontsize["axes"])
    ax2 = ax1.twinx()
    ax2.plot(x, [netto_kw[v] / 1000.0 for v in variants], marker='o', color='black', linewidth=2, markersize=5, label='Nettoleistung (MW)')
    ax2.set_ylabel("Elektrische Nettoleistung (MW)", fontsize=fontsize["axes"])
    ax1.set_title("Vergleich von Investitionskosten und Nettoleistungsaufnahme.", fontsize=fontsize["title"])
    ax1.grid(axis="y", alpha=0.3)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    # Legends
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=fontsize["legend"]) 
    plt.tight_layout()
    savefig("plot_09_fci_vs_nettoleistung", fig)
    plt.close(fig)

    # --- Terminal summary ---
    # lowest specific cost in basisfall
    min_spec = min(spezif_kosten.items(), key=lambda x: x[1])
    # lowest TRR_L in basisfall
    min_trr = min(TRR_L.items(), key=lambda x: x[1])
    # lowest elektrische nettoleistung
    min_netto = min(netto_kw.items(), key=lambda x: x[1])
    # highest FCI
    max_fci = max(fci.items(), key=lambda x: x[1])
    # dominierender Kostenblock je Variante
    dominierenden = {}
    for v in variants:
        arr = np.array(bare_module[v])
        idx = arr.argmax()
        dominierenden[v] = (kostenblaecke[idx], float(arr[idx]) / arr.sum() * 100.0)

    print("--- Kurze Zusammenfassung ---")
    print(f"Niedrigster spezifischer Kostenwert (Basisfall): {min_spec[0]} = {deutsch_format(min_spec[1],1)} EUR/t_N2")
    print(f"Niedrigster TRR_L (Basisfall): {min_trr[0]} = {deutsch_format(min_trr[1]/1e6,1)} Mio. EUR/a")
    print(f"Niedrigste elektrische Nettoleistung: {min_netto[0]} = {deutsch_format(min_netto[1]/1000.0,1)} MW")
    print(f"Höchstes FCI: {max_fci[0]} = {deutsch_format(max_fci[1]/1e6,1)} Mio. EUR")
    print("Dominierender Kostenblock je Variante (Block, Anteil %):")
    for v in variants:
        block, pct = dominierenden[v]
        print(f" - {v}: {block}, {deutsch_format(pct,1)} %")


if __name__ == "__main__":
    main()
