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

# --- Additional RC re-calculation and comparison (sanity check) ---
export_now = ean._serialize()
connections_now = export_now.get("connections", {})

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

# Try to locate streams 33..36 by suffix (best-effort)
s33 = _find_conn_by_suffix("33")
s34 = _find_conn_by_suffix("34")
s35 = _find_conn_by_suffix("35")
s36 = _find_conn_by_suffix("36")

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
et33_tot = _total_from_permass(s33, "e_T")
et34_tot = _total_from_permass(s34, "e_T")
ep_condens_tot = None
if et33_tot is not None and et34_tot is not None:
    # determine which stream has larger thermal exergy and take the difference
    larger = et33_tot if et33_tot >= et34_tot else et34_tot
    smaller = et34_tot if et33_tot >= et34_tot else et33_tot
    ep_condens_tot = larger - smaller

logging.info("\nCondensation thermal exergy (E_T) comparison:")
logging.info(f"  E_T33 = {et33_tot}, E_T34 = {et34_tot}, Ep_condensation = {ep_condens_tot}")
if E_P_comp is not None and ep_condens_tot is not None:
    logging.info("  Ep_cond match: " + ("YES" if _cmp(E_P_comp, ep_condens_tot) else f"NO (diff={E_P_comp - ep_condens_tot:.6g})"))
else:
    logging.info("  Ep_cond match: N/A (missing values)")

# --- Ef per user's spec:
#  - physical exergy difference of reboiler streams 35 and 36 (non-negative)
#  - plus mechanical exergy difference of 33 and 34 (non-negative, represents pressure loss)
eph35_tot = _total_from_permass(s35, "e_PH")
eph36_tot = _total_from_permass(s36, "e_PH")
em33_tot = _total_from_permass(s33, "e_M")
em34_tot = _total_from_permass(s34, "e_M")

phys_diff = None
mech_diff = None
ef_custom = None

if eph35_tot is not None and eph36_tot is not None:
    phys_diff = abs(eph35_tot - eph36_tot)

if em33_tot is not None and em34_tot is not None:
    mech_diff = abs(em33_tot - em34_tot)

if phys_diff is not None and mech_diff is not None:
    ef_custom = phys_diff + mech_diff

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

# --- Repeat the same custom-calculation workflow for RC2 using streams SZ37..SZ40
s37 = _find_conn_by_suffix("37")
s38 = _find_conn_by_suffix("38")
s39 = _find_conn_by_suffix("39")
s40 = _find_conn_by_suffix("40")

# Recompute condensation thermal exergy for RC2 (E_T difference between 37 and 38)
ep_condens_tot_rc2 = None
et37_tot = _total_from_permass(s37, "e_T")
et38_tot = _total_from_permass(s38, "e_T")
if et37_tot is not None and et38_tot is not None:
    larger = et37_tot if et37_tot >= et38_tot else et38_tot
    smaller = et38_tot if et37_tot >= et38_tot else et37_tot
    ep_condens_tot_rc2 = larger - smaller

# Ef for RC2: phys diff of reboiler streams (39/40) + mech diff of 37/38
eph39_tot = _total_from_permass(s39, "e_PH")
eph40_tot = _total_from_permass(s40, "e_PH")
em37_tot = _total_from_permass(s37, "e_M")
em38_tot = _total_from_permass(s38, "e_M")

phys_diff_rc2 = None
mech_diff_rc2 = None
ef_custom_rc2 = None

if eph39_tot is not None and eph40_tot is not None:
    phys_diff_rc2 = abs(eph39_tot - eph40_tot)

if em37_tot is not None and em38_tot is not None:
    mech_diff_rc2 = abs(em37_tot - em38_tot)

if phys_diff_rc2 is not None and mech_diff_rc2 is not None:
    ef_custom_rc2 = phys_diff_rc2 + mech_diff_rc2

ed_custom_rc2 = None
if ef_custom_rc2 is not None and ep_condens_tot_rc2 is not None:
    ed_custom_rc2 = ef_custom_rc2 - ep_condens_tot_rc2

logging.info("\nRC2 custom calculation (streams 37..40):")
logging.info(f"  E_T37 = {et37_tot}, E_T38 = {et38_tot}, Ep_cond_RC2 = {ep_condens_tot_rc2}")
logging.info(f"  phys | E_PH39 = {eph39_tot}, E_PH40 = {eph40_tot}, phys_diff = {phys_diff_rc2}")
logging.info(f"  mech | E_M37 = {em37_tot}, E_M38 = {em38_tot}, mech_diff = {mech_diff_rc2}")
logging.info(f"  Ef_custom_RC2 = {ef_custom_rc2}")
logging.info(f"  Ed_custom_RC2 = {ed_custom_rc2}")

# Attach custom values to RC2 component for display/export
rc2_comp = ean.components.get("RC2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC2")), None)
if rc2_comp is not None:
    try:
        rc2_comp.E_P_custom = ep_condens_tot_rc2
        rc2_comp.E_F_custom = ef_custom_rc2
        rc2_comp.E_D_custom = ed_custom_rc2
        rc2_comp.epsilon_custom = (ep_condens_tot_rc2 / ef_custom_rc2) if (ef_custom_rc2 and ef_custom_rc2 != 0) else None
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
    E_F_c = getattr(comp, 'E_F_custom', None)
    E_P_c = getattr(comp, 'E_P_custom', None)
    E_D_c = getattr(comp, 'E_D_custom', None)
    eps = getattr(comp, 'epsilon', None)
    eps_c = getattr(comp, 'epsilon_custom', None)

    logging.info("\n--- Compact comparison for %s ---" % name)
    logging.info(f"component | E_F={E_F} W | E_P={E_P} W | E_D={E_D} W | eps={eps}")
    logging.info(f"custom    | E_F={E_F_c} W | E_P={E_P_c} W | E_D={E_D_c} W | eps={eps_c}")
    if E_D is not None and E_D_c is not None:
        logging.info("Ed equal: " + ("YES" if _cmp(E_D, E_D_c) else f"NO (diff={E_D - E_D_c:.6g})"))
    else:
        logging.info("Ed equal: N/A")


# Emit compact comparison blocks for RC and RC2
_log_component_custom_compare('RC', rc_comp)
_log_component_custom_compare('RC2', rc2_comp)

# --- Repeat same custom-formula process for RC2 using streams 37..40
rc2_comp = ean.components.get("RC2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC2")), None)

# locate streams 37..40
s37 = _find_conn_by_suffix("37")
s38 = _find_conn_by_suffix("38")
s39 = _find_conn_by_suffix("39")
s40 = _find_conn_by_suffix("40")

ep_condens2_tot = None
ef_custom2 = None
ed_custom2 = None

# Ep as difference of E_T totals for streams 37 and 38
et37_tot = _total_from_permass(s37, "e_T")
et38_tot = _total_from_permass(s38, "e_T")
if et37_tot is not None and et38_tot is not None:
    larger = et37_tot if et37_tot >= et38_tot else et38_tot
    smaller = et38_tot if et37_tot >= et38_tot else et37_tot
    ep_condens2_tot = larger - smaller

# Ef: physical difference of reboiler streams 39/40 + mechanical difference of 37/38
eph39_tot = _total_from_permass(s39, "e_PH")
eph40_tot = _total_from_permass(s40, "e_PH")
em37_tot = _total_from_permass(s37, "e_M")
em38_tot = _total_from_permass(s38, "e_M")

phys_diff2 = None
mech_diff2 = None

if eph39_tot is not None and eph40_tot is not None:
    phys_diff2 = abs(eph39_tot - eph40_tot)

if em37_tot is not None and em38_tot is not None:
    mech_diff2 = abs(em37_tot - em38_tot)

if phys_diff2 is not None and mech_diff2 is not None:
    ef_custom2 = phys_diff2 + mech_diff2

if ef_custom2 is not None and ep_condens2_tot is not None:
    ed_custom2 = ef_custom2 - ep_condens2_tot

logging.info("\nRC2 custom check (streams 37..40):")
logging.info(f"  Ep_cond2 = {ep_condens2_tot}")
logging.info(f"  Ef_custom2 = {ef_custom2}")
logging.info(f"  Ed_custom2 = {ed_custom2}")
if getattr(rc2_comp, 'E_D', None) is not None and ed_custom2 is not None:
    logging.info("  Ed match (RC2 component vs custom): " + ("YES" if _cmp(getattr(rc2_comp, 'E_D', None), ed_custom2) else f"NO (diff={getattr(rc2_comp, 'E_D', None) - ed_custom2:.6g})"))
else:
    logging.info("  Ed match (RC2): N/A (missing values)")

# Attach custom values to RC2 component object for display/export
if rc2_comp is not None:
    try:
        rc2_comp.E_P_custom = ep_condens2_tot
        rc2_comp.E_F_custom = ef_custom2
        rc2_comp.E_D_custom = ed_custom2
        rc2_comp.epsilon_custom = (ep_condens2_tot / ef_custom2) if (ef_custom2 and ef_custom2 != 0) else None
    except Exception:
        pass


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
        # Safe formatting for possibly-missing values
        def _fmt_w(v):
            return f"{v:.2f} W" if isinstance(v, (int, float)) else ("N/A" if v is None else str(v))

        epsilon_str = f"{epsilon:.4f}" if isinstance(epsilon, (int, float)) else "N/A"

        result_msg = (
            f"Component results | {comp_name} ({component.__class__.__name__}) | "
            f"E_F={_fmt_w(E_F)} | E_P={_fmt_w(E_P)} | E_D={_fmt_w(E_D)} | eps={epsilon_str}"
        )

        # Include custom user-defined exergy results when present on the component
        E_P_custom = getattr(component, 'E_P_custom', None)
        E_F_custom = getattr(component, 'E_F_custom', None)
        E_D_custom = getattr(component, 'E_D_custom', None)
        eps_custom = getattr(component, 'epsilon_custom', None)
        custom_parts = []
        if E_F_custom is not None or E_P_custom is not None or E_D_custom is not None or eps_custom is not None:
            custom_parts.append("[custom]")
            if E_F_custom is not None:
                custom_parts.append(f"E_F_custom={_fmt_w(E_F_custom)}")
            if E_P_custom is not None:
                custom_parts.append(f"E_P_custom={_fmt_w(E_P_custom)}")
            if E_D_custom is not None:
                custom_parts.append(f"E_D_custom={_fmt_w(E_D_custom)}")
            if eps_custom is not None:
                eps_c = f"{eps_custom:.6g}" if isinstance(eps_custom, (int, float)) else str(eps_custom)
                custom_parts.append(f"eps_custom={eps_c}")
            result_msg = result_msg + " | " + " ".join(custom_parts)

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

# Inject custom exergy results (from test calculations) into JSON export for traceability
custom_exergy = {}
for comp_name, comp in ean.components.items():
    E_F_custom = getattr(comp, 'E_F_custom', None)
    E_P_custom = getattr(comp, 'E_P_custom', None)
    E_D_custom = getattr(comp, 'E_D_custom', None)
    eps_custom = getattr(comp, 'epsilon_custom', None)
    if any(v is not None for v in (E_F_custom, E_P_custom, E_D_custom, eps_custom)):
        custom_exergy[str(comp_name)] = {
            "E_F_custom": E_F_custom,
            "E_P_custom": E_P_custom,
            "E_D_custom": E_D_custom,
            "epsilon_custom": eps_custom,
        }

if custom_exergy:
    json_payload["custom_exergy"] = custom_exergy
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
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Thermodynamische und exergetische Kenngrößen der simulierten Prozessströme} \\",
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
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Stoffliche Zusammensetzung der Prozessströme} \\",
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
    header = " & ".join([
        "Component",
        "Type",
        r"$\dot{E}_F$",
        r"$\dot{E}_P$",
        r"$\dot{E}_D$",
        r"$\varepsilon$",
    ]) + " \\\\"
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)"]) + " \\\\"

    rows = []
    for comp_name, component in components.items():
        if component.__class__.__name__ in {"CycleCloser", "Mixer", "Splitter"}:
            continue
        # standard values
        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        epsilon = getattr(component, "epsilon", None)

        # if this component has custom values (e.g. RC), use them for display in the standard columns
        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        epsilon_custom = getattr(component, "epsilon_custom", None)

        display_E_F = E_F_custom if E_F_custom is not None else E_F
        display_E_P = E_P_custom if E_P_custom is not None else E_P
        display_E_D = E_D_custom if E_D_custom is not None else E_D
        display_epsilon = epsilon_custom if epsilon_custom is not None else epsilon

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(component.__class__.__name__),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value(display_epsilon),
            ]) + r" \\\\" )

    col_spec = "l" + "l" + "r" * 4
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

components_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_components.tex",
    )
)
components_table = _build_component_results_table(ean.components)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

molfractions_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams_molfrac.tex",
    )
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)
