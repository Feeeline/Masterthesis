"""
Collect distinct UnitString values from an Aspen Plus model via COM and write them to a file.

Usage (PowerShell):
    python tools\collect_aspen_units.py "path\to\model.apw" "output_units.txt"

The script requires Aspen Plus to be installed (COM interface) and will connect via
win32com.client.Dispatch("Apwn.Document").

It traverses the tree under "\\Data" and collects any `UnitString` attributes.
"""
import sys
import os
from collections import deque


def collect_units_from_model(model_path):
    try:
        from win32com.client import Dispatch
    except Exception as e:
        print("win32com.client not available. Install pywin32 and run on Windows with Aspen installed.")
        raise

    doc = Dispatch("Apwn.Document")
    doc.InitFromArchive2(model_path)
    seen = set()

    root = doc.Tree.FindNode(r"\Data")
    if root is None:
        print("No \Data node found in model.")
        return seen

    queue = deque([root])
    while queue:
        node = queue.popleft()
        try:
            # Try to access UnitString if present
            unit = getattr(node, "UnitString", None)
            if unit and isinstance(unit, str) and unit.strip():
                seen.add(unit.strip())
        except Exception:
            pass

        # Enqueue child elements if present
        try:
            elems = getattr(node, "Elements", None)
            if elems is not None:
                # Elements might be a COM collection; iterate safely
                try:
                    for i in range(elems.Count):
                        child = elems(i)
                        queue.append(child)
                except Exception:
                    # fallback: try python iteration
                    try:
                        for child in elems:
                            queue.append(child)
                    except Exception:
                        pass
        except Exception:
            pass

    return seen


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools\\collect_aspen_units.py <model.apw> [output_file]")
        sys.exit(1)

    model = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "detected_aspen_units.txt"

    if not os.path.exists(model):
        print(f"Model file not found: {model}")
        sys.exit(2)

    units = collect_units_from_model(model)
    units_sorted = sorted(units)
    with open(out, "w", encoding="utf-8") as f:
        for u in units_sorted:
            f.write(u + "\n")

    print(f"Wrote {len(units_sorted)} distinct units to {out}")
