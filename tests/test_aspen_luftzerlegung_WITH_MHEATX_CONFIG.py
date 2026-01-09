# Beispiel: MHeatX mit aktivierter spezProdukt-Konfiguration
# Kopieren Sie diese Datei und passen Sie sie an Ihre MHeatX-Blöcke an

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

model_path = r'C:\Users\Felin\Documents\Masterthesis\Code\Exerpy\exerpy\examples\asu_aspen\Doppelkolonne.bkp'

ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)

# ===== MHeatX CONFIGURATION (spezProdukt mode - EXAMPLE) =====
# Dies ist ein BEISPIEL mit aktivierter Konfiguration für MW und RC.
# Passen Sie die Stream-Nummern (0, 1, 2, ...) an Ihre Komponenten an!
#
# Tipps zum Finden von Stream-Namen:
# 1. Aktivieren Sie Balance-Mode (immer aktiv)
# 2. Suchen Sie im Log nach "Component inputs before calc | MW (MHeatX) |"
# 3. Die Felder "inlets=[...]" und "outlets=[...]" zeigen verfügbare Nummern
#
# Beispiel aus dem Log:
#   inlets=[
#     {'name': 0, 'T': 308.15, 'm': 24.8, ...},
#     {'name': 2, 'T': 96.71, 'm': 8.06, ...},
#     ...
#   ]
# Stream-Namen sind hier: 0, 2, 1, 4, 3
# Verwenden Sie diese in den Paaren!

MHEATX_CFG = {
    "MW": {
        "part": "E_PH",
        
        # hot_pairs: Ströme, die Exergie ABGEBEN (normalerweise Kühlung)
        # Aus dem Log für MW:
        # Inlet 0 (warm, m=24.8): E_in  = 3744706.73 W, E_out = 7626066.64 W → wird gekühlt
        # Inlet 2 (warm, m=8.06): E_in  = 2353688.21 W, E_out = 1228743.46 W → wird gekühlt
        "hot_pairs": [
            (0, 0),   # Inlet 0 -> Outlet 0 (Hauptluft-Kühlstrom)
            (2, 2)    # Inlet 2 -> Outlet 2 (Prozessfluid-Kühlstrom)
        ],
        
        # cold_pairs: Ströme, die Exergie AUFNEHMEN (normalerweise Erwärmung)
        # Inlet 1 (kalt, m=4.7): E_in  = 713003.53 W, E_out = 1270701.42 W → wird erwärmt
        # Inlet 3 (kalt, m=13.48): E_in  = 3629349.53 W, E_out = 1107769.80 W → wird erwärmt
        # Inlet 4 (kalt, m=8.01): E_in  = 1970929.41 W, E_out = 723334.81 W → wird erwärmt
        "cold_pairs": [
            (1, 1),   # Inlet 1 -> Outlet 1 (Nebenluft-Erwärmung)
            (3, 3),   # Inlet 3 -> Outlet 3 (Prozessfluid-Erwärmung 1)
            (4, 4)    # Inlet 4 -> Outlet 4 (Prozessfluid-Erwärmung 2)
        ],
        
        # product_pairs: Welche der cold_pairs sind "Produkt"?
        # Dies ist domain-spezifisch und muss vom Nutzer entschieden werden!
        # Beispiel: Nur Nebenluft-Erwärmung ist Produkt
        "product_pairs": [
            (1, 1)    # Nur dieser Strom zählt als Produkt
        ],
        
        # fuel_pairs: Optional - Fuel-Definition überschreiben
        # Falls nicht angegeben, wird hot_pairs als Fuel verwendet
        # Beispiel: fuel_pairs = [(0, 0)]  würde nur Hauptluft zählen
        # fuel_pairs: None  # Leer lassen für Default = hot_pairs
    },
    
    "RC": {
        # RC ist der Rückkühl-Wärmewechsler mit einfacherer Struktur (2 inlets, 2 outlets)
        "part": "E_PH",
        
        "hot_pairs": [
            (0, 0)    # Ein heißer Strom wird gekühlt
        ],
        
        "cold_pairs": [
            (1, 1)    # Ein kalter Strom wird erwärmt
        ],
        
        "product_pairs": [
            (1, 1)    # Dieser Strom ist Produkt
        ],
    }
}

# Apply configuration to ExergyAnalysis
if MHEATX_CFG:
    logging.info("===== MHEATX CONFIGURATION ACTIVE =====")
    ean.set_mheatx_config(MHEATX_CFG)
    logging.info(f"MHeatX configuration applied to: {list(MHEATX_CFG.keys())}")
    logging.info("==========================================\n")

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
