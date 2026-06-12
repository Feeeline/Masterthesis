#!/usr/bin/env python3
"""Recreate the singlekolonne E_D plot and save as PNG.

Saves to Overleaf_LaTeX/bilder/singlekolonne_E_Dbarh_recreated.png
"""
import os
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def main():
    # Apply same theme as tools/plot_exergy_results.py
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
        }
    )

    labels = [
        "D2",
        "ZK2",
        "ZK1",
        "MH",
        "LK2",
        "LK1",
        "RECO",
        "KOL",
        "TURB",
        "D1",
        "MIX",
        "GW1",
        "GW2",
    ]

    values = [
        2.745,
        1.383,
        1.022,
        0.969,
        0.703,
        0.702,
        0.442,
        0.356,
        0.153,
        0.089,
        0.070,
        0.062,
        0.033,
    ]

    # Reverse so the first entry appears at top (like the reference image)
    labels_rev = labels[::-1]
    vals_rev = values[::-1]

    fig, ax = plt.subplots(figsize=(10, 7))

    # use the repository's defined single color
    green = "#55A868"
    bars = ax.barh(labels_rev, vals_rev, color=green)

    ax.set_xlabel(r'$\dot{E}_D$ [MW]')
    ax.set_ylabel("Component")
    ax.set_xlim(0, max(values) * 1.12)

    # Do not annotate bars with values to match original style

    # style axis similar to original: dashed grid on x, lighter alpha, remove top/right spines
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    out_dir = os.path.join("Overleaf_LaTeX", "bilder")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "singlekolonne_E_Dbarh_recreated.png")
    plt.savefig(out_path, dpi=300)
    print(f"Saved plot to: {out_path}")


if __name__ == "__main__":
    main()
