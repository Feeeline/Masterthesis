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
# Fallback to the original hardcoded path for backward compatibility.
default_model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne_klein\Single_Column_Simulation_Final.bkp"
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


# Emit compact comparison block for RC
_log_component_custom_compare('RC', rc_comp)

# --- Custom calculation for MH/MW (MultiHeat) using provided formulas
# Ep = ET11
# Ef = EPH14 - EPH15 + EPH20 - EPH21 + EPH25 - EPH24 + EM8 - EM11 + ET8
mh_comp = (
    ean.components.get("MH")
    or ean.components.get("MW")
    or next((c for n, c in ean.components.items() if str(n).upper().startswith(("MH", "MW"))), None)
)

# find required streams
s8 = _find_conn_by_suffix("8")
s11 = _find_conn_by_suffix("11")
s14 = _find_conn_by_suffix("14")
s15 = _find_conn_by_suffix("15")
s20 = _find_conn_by_suffix("20")
s21 = _find_conn_by_suffix("21")
s24 = _find_conn_by_suffix("24")
s25 = _find_conn_by_suffix("25")

def _total_eph_effective(conn):
    if not conn:
        return None
    eph_tot = _total_from_permass(conn, "e_PH")
    if eph_tot is not None:
        return eph_tot
    et_tot = _total_from_permass(conn, "e_T")
    em_tot = _total_from_permass(conn, "e_M")
    if et_tot is not None and em_tot is not None:
        return et_tot + em_tot
    return None

et8_tot = _total_from_permass(s8, "e_T")
et11_tot = _total_from_permass(s11, "e_T")

eph14_tot = _total_eph_effective(s14)
eph15_tot = _total_eph_effective(s15)
eph20_tot = _total_eph_effective(s20)
eph21_tot = _total_eph_effective(s21)
eph24_tot = _total_eph_effective(s24)
eph25_tot = _total_eph_effective(s25)

em8_tot = _total_from_permass(s8, "e_M")
em11_tot = _total_from_permass(s11, "e_M")

ep_mh = None
ef_mh = None
ed_mh = None

if et11_tot is not None:
    ep_mh = et11_tot

required_ef_terms = [
    eph14_tot,
    eph15_tot,
    eph20_tot,
    eph21_tot,
    eph25_tot,
    eph24_tot,
    em8_tot,
    em11_tot,
    et8_tot,
]
if all(v is not None for v in required_ef_terms):
    ef_mh = (
        (eph14_tot - eph15_tot)
        + (eph20_tot - eph21_tot)
        + (eph25_tot - eph24_tot)
        + (em8_tot - em11_tot)
        + et8_tot
    )

if ef_mh is not None and ep_mh is not None:
    ed_mh = ef_mh - ep_mh

# Best-effort: if some terms are present, compute partial sums instead of leaving None
if ep_mh is None:
    # try compute ep_mh from available et11_tot
    if et11_tot is not None:
        ep_mh = et11_tot

if ef_mh is None:
    # try to sum available terms (treat missing terms as 0) but only if at least one term exists
    required_terms = [eph14_tot, eph15_tot, eph20_tot, eph21_tot, eph25_tot, eph24_tot, em8_tot, em11_tot, et8_tot]
    if any(isinstance(v, (int, float)) for v in required_terms):
        # use 0 for missing
        eph14_tot = eph14_tot or 0.0
        eph15_tot = eph15_tot or 0.0
        eph20_tot = eph20_tot or 0.0
        eph21_tot = eph21_tot or 0.0
        eph25_tot = eph25_tot or 0.0
        eph24_tot = eph24_tot or 0.0
        em8_tot = em8_tot or 0.0
        em11_tot = em11_tot or 0.0
        et8_tot = et8_tot or 0.0
        ef_mh = (eph14_tot - eph15_tot) + (eph20_tot - eph21_tot) + (eph25_tot - eph24_tot) + (em8_tot - em11_tot) + et8_tot

if ed_mh is None and ef_mh is not None and ep_mh is not None:
    ed_mh = ef_mh - ep_mh

logging.info("\nMH custom calculation (user total balance):")
logging.info(f"  ET11={et11_tot} -> Ep_mh={ep_mh}")
logging.info(
    f"  Ef terms: (EPH14-EPH15)=({eph14_tot}-{eph15_tot}), "
    f"(EPH20-EPH21)=({eph20_tot}-{eph21_tot}), "
    f"(EPH25-EPH24)=({eph25_tot}-{eph24_tot}), "
    f"(EM8-EM11)=({em8_tot}-{em11_tot}), ET8={et8_tot}"
)
logging.info(f"  Ef_mh = {ef_mh}")
logging.info(f"  Ed_mh = Ef_mh - Ep_mh = {ed_mh}")

if mh_comp is not None:
    comp_ed = getattr(mh_comp, "E_D", None)
    if comp_ed is not None and ed_mh is not None:
        logging.info(
            "  Ed match (component vs custom): "
            + ("YES" if _cmp(comp_ed, ed_mh) else f"NO (diff={comp_ed - ed_mh:.6g})")
        )
    else:
        logging.info("  Ed match (component vs custom): N/A")

# Attach to MH component for display/export
if mh_comp is not None:
    try:
        mh_comp.E_P_custom = ep_mh
        mh_comp.E_F_custom = ef_mh
        mh_comp.E_D_custom = ed_mh
        mh_comp.epsilon_custom = (ep_mh / ef_mh) if (ef_mh and ef_mh != 0) else None
    except Exception:
        pass

# Compact comparison for MH
_log_component_custom_compare('MH', mh_comp)

# --- Custom calculation for GW1 (Flash) using user formulas
# Ep = m6 * (ech6 - ech5)
# Ef = m6 * (eph5 - eph6) + E7
gw1_comp = ean.components.get("GW1") or next((c for n, c in ean.components.items() if str(n).upper().startswith("GW1")), None)

# find streams S5, S6, S7 (exact match to avoid finding S15, S16, etc.)
def _find_exact_stream(stream_name: str):
    for key, conn in connections_now.items():
        name = str(conn.get("name", ""))
        if name == stream_name or str(key) == stream_name:
            return conn
    return None

s5 = _find_exact_stream("S5")
s6 = _find_exact_stream("S6")
s7 = _find_exact_stream("S7")

# GW1 Flash: Complete exergy balance
# Ep = m6 * (ech6 - ech5)  -- chemical exergy change in gas stream
# Ef = EPH5 - EPH6 - EPH7  -- physical exergy fuel term
# El = E7 = m7*(ePH7 + eCH7) -- exergy loss stream
# Ed = Ef - Ep - El

m5 = _get_val(s5, "m")
m6 = _get_val(s6, "m")
m7 = _get_val(s7, "m")
eph5 = _get_eph_effective(s5)
eph6 = _get_eph_effective(s6)
eph7 = _get_eph_effective(s7)
ech5 = _get_val(s5, "e_CH")
ech6 = _get_val(s6, "e_CH")
ech7 = _get_val(s7, "e_CH")

ep_gw1 = None
ef_gw1 = None
ed_gw1 = None
el_gw1 = None
# Ep = product (chemical exergy increase in gas stream)
# Best-effort: compute using available chemical exergies; treat missing terms as 0 when mass present
if isinstance(m6, (int, float)) and (isinstance(ech6, (int, float)) or isinstance(ech5, (int, float))):
    ep_gw1 = _safe_diff_mult(m6, ech6, ech5)

# Ef = fuel (physical exergy formulation) -- compute per-term if available
t1 = _term_m_eph(s5)
t2 = _term_m_eph(s6)
t3 = _term_m_eph(s7)
if any(isinstance(v, (int, float)) for v in (t1, t2, t3)):
    ef_gw1 = (t1 or 0.0) - (t2 or 0.0) - (t3 or 0.0)

# El = exergy loss in stream 7 (total exergy)
t_el = None
if isinstance(m7, (int, float)):
    eph7_eff = _get_eph_effective(s7)
    if isinstance(eph7_eff, (int, float)) or isinstance(ech7, (int, float)):
        e_ph_term = eph7_eff if isinstance(eph7_eff, (int, float)) else 0.0
        e_ch_term = float(ech7) if isinstance(ech7, (int, float)) else 0.0
        t_el = float(m7) * (e_ph_term + e_ch_term)
if t_el is not None:
    el_gw1 = t_el

# Ed = destruction (separate from losses) - compute if any inputs available
if any(isinstance(v, (int, float)) for v in (ef_gw1, ep_gw1, el_gw1)):
    ef_calc_val = ef_gw1 or 0.0
    ep_calc_val = ep_gw1 or 0.0
    el_calc_val = el_gw1 or 0.0
    ed_gw1 = ef_calc_val - ep_calc_val - el_calc_val

logging.info("\nGW1 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m5={m5}, m6={m6}, m7={m7} kg/s")
logging.info(f"  Physical: eph5={eph5}, eph6={eph6}, eph7={eph7} J/kg")
logging.info(f"  Chemical: ech5={ech5}, ech6={ech6}, ech7={ech7} J/kg")
logging.info(f"  Ep_gw1 = m6*(ech6-ech5) = {ep_gw1} W")
logging.info(f"  Ef_gw1 = m5*eph5 - m6*eph6 - m7*eph7 = {ef_gw1} W")
logging.info(f"  El_gw1 = m7*(eph7+ech7) = {el_gw1} W")
logging.info(f"  Ed_gw1 = Ef - Ep - El = {ed_gw1} W")

# Attach to GW1 component for display/export
if gw1_comp is not None:
    try:
        gw1_comp.E_P_custom = ep_gw1
        gw1_comp.E_F_custom = ef_gw1
        gw1_comp.E_D_custom = ed_gw1
        gw1_comp.E_L_custom = el_gw1
        gw1_comp.epsilon_custom = (ep_gw1 / ef_gw1) if (ef_gw1 and ef_gw1 != 0) else None
    except Exception:
        pass

# Compact comparison for GW1
_log_component_custom_compare('GW1', gw1_comp)


# --- GW2 custom calculations using streams 6, 8, 9, 10
# GW2 Separator: Complete exergy balance
# Ep = m8 * (ech8 - ech6)  -- chemical exergy gain in product stream 8
# Ef = EPH6 - EPH8 - EPH9 - EPH10  -- physical exergy fuel term
# El = E9 + E10 (total exergy losses)
# Ed = Ef - Ep - El

gw2_comp = ean.components.get("GW2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("GW2")), None)

# locate streams 6, 8, 9, 10
s6 = _find_exact_stream("S6")
s8 = _find_exact_stream("S8")
s9 = _find_exact_stream("S9")
s10 = _find_exact_stream("S10")

m6 = _get_val(s6, "m")
m8 = _get_val(s8, "m")
m9 = _get_val(s9, "m")
m10 = _get_val(s10, "m")

eph6 = _get_eph_effective(s6)
eph8 = _get_eph_effective(s8)
eph9 = _get_eph_effective(s9)
eph10 = _get_eph_effective(s10)

ech6 = _get_val(s6, "e_CH")
ech8 = _get_val(s8, "e_CH")
ech9 = _get_val(s9, "e_CH")
ech10 = _get_val(s10, "e_CH")

ep_gw2 = None
ef_gw2 = None
ed_gw2 = None
el_gw2 = None

# Ep = product (chemical exergy gain in main product stream S8)
# Ep = product (chemical exergy gain in main product stream S8)
if isinstance(m8, (int, float)) and (isinstance(ech8, (int, float)) or isinstance(ech6, (int, float))):
    ep_gw2 = _safe_diff_mult(m8, ech8, ech6)

# Ef = fuel (physical exergy formulation) -- compute per-term if available
t6 = _term_m_eph(s6)
t8 = _term_m_eph(s8)
t9 = _term_m_eph(s9)
t10 = _term_m_eph(s10)
if any(isinstance(v, (int, float)) for v in (t6, t8, t9, t10)):
    ef_gw2 = (t6 or 0.0) - (t8 or 0.0) - (t9 or 0.0) - (t10 or 0.0)
    # losses as totals where possible
    E9_total = t9 if isinstance(t9, (int, float)) else (m9 * ( (eph9 or 0.0) + (ech9 or 0.0)) if isinstance(m9, (int, float)) else None)
    E10_total = t10 if isinstance(t10, (int, float)) else (m10 * ( (eph10 or 0.0) + (ech10 or 0.0)) if isinstance(m10, (int, float)) else None)
    losses = 0.0
    if isinstance(E9_total, (int, float)):
        losses += E9_total
    if isinstance(E10_total, (int, float)):
        losses += E10_total
    el_gw2 = losses if losses != 0.0 else None

# Ed = destruction (separate from losses)
if any(isinstance(v, (int, float)) for v in (ef_gw2, ep_gw2, el_gw2)):
    ef_val = ef_gw2 or 0.0
    ep_val = ep_gw2 or 0.0
    el_val = el_gw2 or 0.0
    ed_gw2 = ef_val - ep_val - el_val

logging.info("\nGW2 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m6={m6}, m8={m8}, m9={m9}, m10={m10} kg/s")
logging.info(f"  Physical [J/kg]: eph6={eph6}, eph8={eph8}, eph9={eph9}, eph10={eph10}")
logging.info(f"  Chemical [J/kg]: ech6={ech6}, ech8={ech8}, ech9={ech9}, ech10={ech10}")
logging.info(f"  Ep_gw2 = m8*(ech8-ech6) = {ep_gw2} W")
logging.info(f"  Ef_gw2 = m6*eph6 - m8*eph8 - m9*eph9 - m10*eph10 = {ef_gw2} W")
logging.info(f"  El_gw2 = E9 + E10 = {el_gw2} W")
logging.info(f"  Ed_gw2 = Ef - Ep - El = {ed_gw2} W")

# Attach to GW2 component for display/export
if gw2_comp is not None:
    try:
        gw2_comp.E_P_custom = ep_gw2
        gw2_comp.E_F_custom = ef_gw2
        gw2_comp.E_D_custom = ed_gw2
        gw2_comp.E_L_custom = el_gw2
        gw2_comp.epsilon_custom = (ep_gw2 / ef_gw2) if (ef_gw2 and ef_gw2 != 0) else None
    except Exception:
        pass

# Compact comparison for GW2
_log_component_custom_compare('GW2', gw2_comp)


# --- MIX custom calculation using thermal exergy (e_T) per user spec
# Use thermic term only: E_F_custom = m_S17*(e_T_S17 - e_T_S20)
#                        E_P_custom = m_S19*(e_T_S20 - e_T_S19)
#                        E_D_custom = E_F_custom - E_P_custom
mix_comp = ean.components.get("MIX") or next(
    (c for n, c in ean.components.items() if str(n).strip().upper() == "MIX"),
    None,
)

# Try to find streams S17, S19, S20 (best-effort using suffix or exact name)
s17 = _find_conn_by_suffix("17") or _find_exact_stream("S17")
s19 = _find_conn_by_suffix("19") or _find_exact_stream("S19")
s20 = _find_conn_by_suffix("20") or _find_exact_stream("S20")

mix_E_F_custom = None
mix_E_P_custom = None
mix_E_D_custom = None
mix_E_L_custom = 0.0

def _num(x):
    return float(x) if isinstance(x, (int, float)) else None

# If the required mass and e_T terms are available, compute per spec
if s17 is not None and s19 is not None and s20 is not None:
    m17 = _get_val(s17, "m")
    m19 = _get_val(s19, "m")
    eT17 = _get_val(s17, "e_T")
    eT19 = _get_val(s19, "e_T")
    eT20 = _get_val(s20, "e_T")

    if isinstance(m17, (int, float)) and isinstance(eT17, (int, float)) and isinstance(eT20, (int, float)):
        mix_E_F_custom = float(m17) * (float(eT17) - float(eT20))
    if isinstance(m19, (int, float)) and isinstance(eT20, (int, float)) and isinstance(eT19, (int, float)):
        mix_E_P_custom = float(m19) * (float(eT20) - float(eT19))
    if isinstance(mix_E_F_custom, (int, float)) or isinstance(mix_E_P_custom, (int, float)):
        mix_E_D_custom = (mix_E_F_custom or 0.0) - (mix_E_P_custom or 0.0)

logging.info("\nMIX custom calculation (thermal e_T based):")
logging.info(f"  streams -> S17={s17 and s17.get('name')}, S19={s19 and s19.get('name')}, S20={s20 and s20.get('name')}")
logging.info(f"  E_F_custom = {mix_E_F_custom} W")
logging.info(f"  E_P_custom = {mix_E_P_custom} W")
logging.info(f"  E_D_custom = {mix_E_D_custom} W")

if mix_comp is not None:
    try:
        mix_comp.E_F_custom = mix_E_F_custom
        mix_comp.E_P_custom = mix_E_P_custom
        mix_comp.E_D_custom = mix_E_D_custom
        mix_comp.E_L_custom = mix_E_L_custom
        mix_comp.epsilon_custom = (mix_E_P_custom / mix_E_F_custom) if (isinstance(mix_E_P_custom, (int, float)) and isinstance(mix_E_F_custom, (int, float)) and mix_E_F_custom != 0) else None
    except Exception:
        pass

_log_component_custom_compare('MIX', mix_comp)


# --- RC (formerly RECO) custom calculations using streams SZ25, SZ26, SZ27, SZ28
# Ep = ETSZ26 - ETSZ25
# Ef = EPHSZ27 - EPHSZ28 + EMSZ25 - EMSZ26

# Prefer the renamed key "RC" (falls back to legacy "RECO")
reco_comp = (
    ean.components.get("RC")
    or ean.components.get("RECO")
    or next(
        (c for n, c in ean.components.items() if str(n).upper().startswith("RC") or str(n).upper().startswith("RECO")),
        None,
    )
)

sz25 = _find_exact_stream("SZ25")
sz26 = _find_exact_stream("SZ26")
sz27 = _find_exact_stream("SZ27")
sz28 = _find_exact_stream("SZ28")

etsz25 = _total_from_permass(sz25, "e_T")
etsz26 = _total_from_permass(sz26, "e_T")
ephsz27 = _total_eph_effective(sz27)
ephsz28 = _total_eph_effective(sz28)
emsz25 = _total_from_permass(sz25, "e_M")
emsz26 = _total_from_permass(sz26, "e_M")

ep_reco = None
ef_reco = None
ed_reco = None

# Best-effort: compute ep_reco and ef_reco using available terms (use 0 for missing per-term values)
if isinstance(etsz26, (int, float)) or isinstance(etsz25, (int, float)):
    ep_reco = (etsz26 or 0.0) - (etsz25 or 0.0)

if any(isinstance(v, (int, float)) for v in [ephsz27, ephsz28, emsz25, emsz26]):
    ef_reco = (ephsz27 or 0.0) - (ephsz28 or 0.0) + (emsz25 or 0.0) - (emsz26 or 0.0)

if any(isinstance(v, (int, float)) for v in [ef_reco, ep_reco]):
    ed_reco = (ef_reco or 0.0) - (ep_reco or 0.0)

logging.info("\nRC custom calculation (user formula):")
logging.info(f"  Ep_reco = ETSZ26 - ETSZ25 = {etsz26} - {etsz25} = {ep_reco} W")
logging.info(
    f"  Ef_reco = EPHSZ27 - EPHSZ28 + EMSZ25 - EMSZ26 = "
    f"{ephsz27} - {ephsz28} + {emsz25} - {emsz26} = {ef_reco} W"
)
logging.info(f"  Ed_reco = Ef - Ep = {ed_reco} W")

if reco_comp is not None:
    try:
        reco_comp.E_P_custom = ep_reco
        reco_comp.E_F_custom = ef_reco
        reco_comp.E_D_custom = ed_reco
        reco_comp.epsilon_custom = (ep_reco / ef_reco) if (ef_reco and ef_reco != 0) else None
    except Exception:
        pass

_log_component_custom_compare('RC', reco_comp)


# --- KOL custom calculations (single column) using user formulas
# Produkt:
#   Ep = sum_{i in [23,12]} m_i*(e_CH,i - e_CH,11) + sum_{i in [23,12]} m_i*(e_T,i - e_T,11)
# Brennstoff:
#   Ef = (E_SZ26,liq - E_SZ26,gas) + sum_{i in [23,12]} m_i*(e_M,11 - e_M,i)
# Hinweis: im vorliegenden Modell wird der gasfoermige Kondensatorzweig als SZ25 gefuehrt,
#          daher: E_SZ26,gas -> E_SZ25.

kol_comp = ean.components.get("KOL") or next((c for n, c in ean.components.items() if str(n).strip().upper() == "KOL"), None)

s11_kol = _find_exact_stream("S11")
s12_kol = _find_exact_stream("S12")
s23_kol = _find_exact_stream("S23")
sz25_kol = _find_exact_stream("SZ25")
sz26_kol = _find_exact_stream("SZ26")

m12_kol = _get_val(s12_kol, "m")
m23_kol = _get_val(s23_kol, "m")

ech11_kol = _get_val(s11_kol, "e_CH")
ech12_kol = _get_val(s12_kol, "e_CH")
ech23_kol = _get_val(s23_kol, "e_CH")

et11_kol = _get_val(s11_kol, "e_T")
et12_kol = _get_val(s12_kol, "e_T")
et23_kol = _get_val(s23_kol, "e_T")

em11_kol = _get_val(s11_kol, "e_M")
em12_kol = _get_val(s12_kol, "e_M")
em23_kol = _get_val(s23_kol, "e_M")

esz26_liq = _total_eph_effective(sz26_kol)
esz26_gas = _total_eph_effective(sz25_kol)

ep_ch_kol = None
ep_t_kol = None
ep_kol = None
ef_kond_kol = None
ef_mech_kol = None
ef_kol = None
ed_kol = None

# Best-effort chemical exergy part
parts_ch = []
term = _safe_diff_mult(m12_kol, ech12_kol, ech11_kol) if isinstance(m12_kol, (int, float)) and (ech12_kol is not None or ech11_kol is not None) else None
if term is not None:
    parts_ch.append(term)
term = _safe_diff_mult(m23_kol, ech23_kol, ech11_kol) if isinstance(m23_kol, (int, float)) and (ech23_kol is not None or ech11_kol is not None) else None
if term is not None:
    parts_ch.append(term)
if parts_ch:
    ep_ch_kol = sum(parts_ch)

# Best-effort thermal exergy part
parts_t = []
term = _safe_diff_mult(m12_kol, et12_kol, et11_kol) if isinstance(m12_kol, (int, float)) and (et12_kol is not None or et11_kol is not None) else None
if term is not None:
    parts_t.append(term)
term = _safe_diff_mult(m23_kol, et23_kol, et11_kol) if isinstance(m23_kol, (int, float)) and (et23_kol is not None or et11_kol is not None) else None
if term is not None:
    parts_t.append(term)
if parts_t:
    ep_t_kol = sum(parts_t)

if ep_ch_kol is not None or ep_t_kol is not None:
    ep_kol = (ep_ch_kol or 0.0) + (ep_t_kol or 0.0)

# Condenser fuel term (liq - gas)
if isinstance(esz26_liq, (int, float)) or isinstance(esz26_gas, (int, float)):
    ef_kond_kol = (esz26_liq or 0.0) - (esz26_gas or 0.0)

# Mechanical fuel part
parts_mech = []
term = None
if isinstance(m12_kol, (int, float)) and (em11_kol is not None or em12_kol is not None):
    term = float(m12_kol) * ((em11_kol or 0.0) - (em12_kol or 0.0))
if term is not None:
    parts_mech.append(term)
term = None
if isinstance(m23_kol, (int, float)) and (em11_kol is not None or em23_kol is not None):
    term = float(m23_kol) * ((em11_kol or 0.0) - (em23_kol or 0.0))
if term is not None:
    parts_mech.append(term)
if parts_mech:
    ef_mech_kol = sum(parts_mech)

if ef_kond_kol is not None or ef_mech_kol is not None:
    ef_kol = (ef_kond_kol or 0.0) + (ef_mech_kol or 0.0)

if ef_kol is not None or ep_kol is not None:
    ed_kol = (ef_kol or 0.0) - (ep_kol or 0.0)

e11_tot_kol = None
e12_tot_kol = None
e23_tot_kol = None
e25_tot_kol = None
e26_tot_kol = None
ed_kol_bal = None

if all(v is not None for v in [s11_kol, _get_val(s11_kol, "m"), _get_eph_effective(s11_kol), _get_val(s11_kol, "e_CH")]):
    e11_tot_kol = float(_get_val(s11_kol, "m")) * (float(_get_eph_effective(s11_kol)) + float(_get_val(s11_kol, "e_CH")))

if all(v is not None for v in [s12_kol, _get_val(s12_kol, "m"), _get_eph_effective(s12_kol), _get_val(s12_kol, "e_CH")]):
    e12_tot_kol = float(_get_val(s12_kol, "m")) * (float(_get_eph_effective(s12_kol)) + float(_get_val(s12_kol, "e_CH")))

if all(v is not None for v in [s23_kol, _get_val(s23_kol, "m"), _get_eph_effective(s23_kol), _get_val(s23_kol, "e_CH")]):
    e23_tot_kol = float(_get_val(s23_kol, "m")) * (float(_get_eph_effective(s23_kol)) + float(_get_val(s23_kol, "e_CH")))

if all(v is not None for v in [sz25_kol, _get_val(sz25_kol, "m"), _get_eph_effective(sz25_kol), _get_val(sz25_kol, "e_CH")]):
    e25_tot_kol = float(_get_val(sz25_kol, "m")) * (float(_get_eph_effective(sz25_kol)) + float(_get_val(sz25_kol, "e_CH")))

if all(v is not None for v in [sz26_kol, _get_val(sz26_kol, "m"), _get_eph_effective(sz26_kol), _get_val(sz26_kol, "e_CH")]):
    e26_tot_kol = float(_get_val(sz26_kol, "m")) * (float(_get_eph_effective(sz26_kol)) + float(_get_val(sz26_kol, "e_CH")))

if all(v is not None for v in [e11_tot_kol, e12_tot_kol, e23_tot_kol, e25_tot_kol, e26_tot_kol]):
    ed_kol_bal = (e11_tot_kol + e26_tot_kol) - (e12_tot_kol + e23_tot_kol + e25_tot_kol)

logging.info("\nKOL custom calculation (user formula):")
logging.info(f"  Ep_ch = m12*(eCH12-eCH11) + m23*(eCH23-eCH11) = {ep_ch_kol} W")
logging.info(f"  Ep_T  = m12*(eT12-eT11) + m23*(eT23-eT11) = {ep_t_kol} W")
logging.info(f"  Ep_kol = Ep_ch + Ep_T = {ep_kol} W")
logging.info(f"  Ef_kond = E_SZ26_liq - E_SZ26_gas(=SZ25) = {esz26_liq} - {esz26_gas} = {ef_kond_kol} W")
logging.info(f"  Ef_mech = m12*(eM11-eM12) + m23*(eM11-eM23) = {ef_mech_kol} W")
logging.info(f"  Ef_kol = Ef_kond + Ef_mech = {ef_kol} W")
logging.info(f"  Ed_kol = Ef - Ep = {ed_kol} W")
logging.info(f"  Gesamtbilanz Ed_kol_bal = (E11 + E26) - (E12 + E23 + E25) = {ed_kol_bal} W")
if ed_kol is not None and ed_kol_bal is not None:
    logging.info(f"  Delta (Ed_formel - Ed_bal) = {ed_kol - ed_kol_bal} W")

if kol_comp is not None:
    comp_ed = getattr(kol_comp, "E_D", None)
    if comp_ed is not None and ed_kol is not None:
        logging.info(
            "  Ed match (component vs custom): "
            + ("YES" if _cmp(comp_ed, ed_kol) else f"NO (diff={comp_ed - ed_kol:.6g})")
        )
    else:
        logging.info("  Ed match (component vs custom): N/A")

if kol_comp is not None:
    try:
        kol_comp.E_P_custom = ep_kol
        kol_comp.E_F_custom = ef_kol
        kol_comp.E_D_custom = ed_kol
        kol_comp.epsilon_custom = (ep_kol / ef_kol) if (ef_kol and ef_kol != 0) else None
    except Exception:
        pass

_log_component_custom_compare('KOL', kol_comp)


# KOLLP, KOLHP and RC2 custom blocks are intentionally omitted for single-column mode.


# Log calculated exergy results for all components
logging.info("\n" + "="*100)
logging.info("COMPONENT EXERGY RESULTS")
logging.info("="*100)
# Fallback: if component exergy triplet is missing or zero, try reconstructing from
# connected material streams' serialized exergy `E` values so tables show meaningful numbers.
for comp_name, comp in ean.components.items():
    try:
        # Skip CycleCloser internals
        if comp.__class__.__name__ == "CycleCloser":
            continue
    except Exception:
        continue

    E_F_attr = getattr(comp, 'E_F', None)
    E_P_attr = getattr(comp, 'E_P', None)
    E_D_attr = getattr(comp, 'E_D', None)

    # If any of the main values is present and non-zero, do not override
    has_meaningful = any(isinstance(v, (int, float)) and v != 0 for v in (E_F_attr, E_P_attr, E_D_attr))
    if has_meaningful:
        continue

    inlet_E = 0.0
    outlet_E = 0.0
    found_any = False

    # Prefer runtime component inl/outl mappings if available
    for conn in getattr(comp, 'inl', {}).values():
        if isinstance(conn, dict):
            v = conn.get('E')
            if isinstance(v, (int, float)):
                inlet_E += float(v)
                found_any = True
    for conn in getattr(comp, 'outl', {}).values():
        if isinstance(conn, dict):
            v = conn.get('E')
            if isinstance(v, (int, float)):
                outlet_E += float(v)
                found_any = True

    # Fallback: scan serialized global connections if runtime mappings had none
    if not found_any:
        for cname, cobj in ean.connections.items():
            if not isinstance(cobj, dict):
                continue
            src = cobj.get('source_component')
            tgt = cobj.get('target_component')
            v = cobj.get('E')
            if isinstance(v, (int, float)):
                if str(tgt) == str(comp_name):
                    inlet_E += float(v)
                    found_any = True
                if str(src) == str(comp_name):
                    outlet_E += float(v)
                    found_any = True

    if found_any:
        try:
            comp.E_F = inlet_E
            comp.E_P = outlet_E
            comp.E_D = inlet_E - outlet_E
        except Exception:
            pass
for comp_name, component in ean.components.items():
    if component.__class__.__name__ != "CycleCloser" and str(comp_name).strip().upper() != "RECON":
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

# No-mix overall aggregation: for each component use either full custom triplet
# (E_F_custom, E_P_custom, E_D_custom) or full standard triplet (E_F, E_P, E_D).
# E_L is handled as additional additive term (custom if available, else standard, else 0).
resolved_components = []
for comp_name, component in ean.components.items():
    if component.__class__.__name__ == "CycleCloser":
        continue
    if str(comp_name).strip().upper() == "RECON":
        continue

    E_F_std = getattr(component, 'E_F', None)
    E_P_std = getattr(component, 'E_P', None)
    E_D_std = getattr(component, 'E_D', None)
    E_L_std = getattr(component, 'E_L', None)
    E_F_custom = getattr(component, 'E_F_custom', None)
    E_P_custom = getattr(component, 'E_P_custom', None)
    E_D_custom = getattr(component, 'E_D_custom', None)
    E_L_custom = getattr(component, 'E_L_custom', None)

    # Only use custom triplet when all values are numeric and finite (no NaN/inf)
    use_custom = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom))
    if use_custom:
        source = "custom"
        E_F_sel, E_P_sel, E_D_sel = E_F_custom, E_P_custom, E_D_custom
        E_L_sel = E_L_custom if E_L_custom is not None else 0.0
    else:
        source = "standard"
        E_F_sel, E_P_sel, E_D_sel = E_F_std, E_P_std, E_D_std
        E_L_sel = E_L_std if E_L_std is not None else 0.0

    resolved_components.append((str(comp_name), source, E_F_sel, E_P_sel, E_D_sel, E_L_sel))

sum_E_F_sel = sum(v for _, _, v, _, _, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_P_sel = sum(v for _, _, _, v, _, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_D_sel = sum(v for _, _, _, _, v, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_L_sel = sum(v for _, _, _, _, _, v in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
closure_sel = sum_E_F_sel - sum_E_P_sel - sum_E_D_sel
closure_sel_with_losses = sum_E_F_sel - sum_E_P_sel - (sum_E_D_sel + sum_E_L_sel)

logging.info("\n" + "="*100)
logging.info("NO-MIX OVERALL (DISPLAY CONSISTENT)")
logging.info("="*100)
logging.info(
    "Rule: per component use CUSTOM iff (E_F_custom, E_P_custom, E_D_custom) all exist; otherwise STANDARD."
)
logging.info(f"Sum selected E_F = {sum_E_F_sel:.2f} W")
logging.info(f"Sum selected E_P = {sum_E_P_sel:.2f} W")
logging.info(f"Sum selected E_D = {sum_E_D_sel:.2f} W")
logging.info(f"Sum selected E_L = {sum_E_L_sel:.2f} W")
logging.info(f"Closure (Sum E_F - Sum E_P - Sum E_D) = {closure_sel:.2f} W")
logging.info(f"Closure (Sum E_F - Sum E_P - Sum(E_D+E_L)) = {closure_sel_with_losses:.2f} W")
sys_diff = None
if isinstance(ean.E_F, (int, float)) and isinstance(ean.E_P, (int, float)):
    sys_diff = ean.E_F - ean.E_P
    logging.info(f"System diff (E_F_tot - E_P_tot) = {sys_diff:.2f} W")
    logging.info(f"Check vs Sum(E_D+E_L): diff = {sys_diff - (sum_E_D_sel + sum_E_L_sel):.2f} W")
logging.info("="*100)

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
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung_single.json")
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
# If RC component did not exist in the model but RC custom calcs were performed,
# include them explicitly so the user's formula is visible in the JSON export.
try:
    rc_missing = ('rc_comp' in locals() and (rc_comp is None))
except Exception:
    rc_missing = False
if rc_missing:
    try:
        rc_vals_present = any(v is not None for v in (globals().get('ep_condens_tot', None), globals().get('ef_custom', None), globals().get('ed_custom', None)))
        if rc_vals_present:
            custom_ex = json_payload.setdefault("custom_exergy", {})
            custom_ex["RC"] = {
                "E_F_custom": globals().get('ef_custom', None),
                "E_P_custom": globals().get('ep_condens_tot', None),
                "E_D_custom": globals().get('ed_custom', None),
                "E_L_custom": None,
                "epsilon_custom": (globals().get('ep_condens_tot', None) / globals().get('ef_custom', None)) if (globals().get('ef_custom', None) and globals().get('ef_custom', None) != 0) else None,
            }
    except Exception:
        pass
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

    header = " & ".join(label for _, label, _ in columns) + " \\\\"
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\\"

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = _stream_value(conn, key)
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\")

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
        ]) + r" \\")

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
            values.append(_format_molfrac_value(val))
        rows.append(" & ".join(values) + r" \\")

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
    ]) + " \\\\"
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)", "(-)", "(-)"]) + " \\\\"
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
            ]) + " \\\\"
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
        " & ".join(sum_row_cells) + r" \\",
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
        r"\begin{longtable}{llr | llr}",
        r"\caption{Exergetische Bilanz des Gesamtsystems des Single-Kolonnenmodells} " + row_end,
        r"\hline",
        r"\multicolumn{3}{l|}{\textbf{Exergetischer Aufwand ($E_{in}$)}} & \multicolumn{3}{l}{\textbf{Exergetischer Verbleib}} " + row_end,
        r"\hline",
        r"Posten & Quelle & Wert (W) & Posten & Typ & Wert (W) " + row_end,
        r"\hline",
        f"Strom 1 & $\\dot{{E}}_{{S1}}$ & {_format_int_de(E_S1)} & Produkt N2 & $\\dot{{E}}_{{{product_stream}}}$ & {_format_int_de(E_product)} " + row_end,
        f"Verdichtung & $\\dot{{W}}_1 + \\dot{{W}}_2$ & {_format_int_de(E_F_comp)} & Turbinenarbeit & $\\dot{{W}}_3$ & {_format_int_de(W_T)} " + row_end,
        f" &  &  & Exerget. Vernichtung & $\\sum \\dot{{E}}_{{D,k}}$ & {_format_int_de(sum_E_D_table)} " + row_end,
        f" &  &  & Austrittsverluste & $\\dot{{E}}_{{S7}}+\\dot{{E}}_{{S9}}+\\dot{{E}}_{{S10}}+\\dot{{E}}_{{S21}}$ & {_format_int_de(sum_E_L_total)} " + row_end,
        r"\hline",
        f"\\textbf{{Summe Ein}} &  & \\textbf{{{_format_int_de(E_in)}}} & \\textbf{{Summe Aus}} &  & \\textbf{{{_format_int_de(sum_out)}}} " + row_end,
        r"\hline",
        f"\\multicolumn{{3}}{{l}}{{}} & \\textbf{{Differenz ($\\Delta$)}} &  & \\textbf{{{delta_text}}} " + row_end,
        r"\hline",
        r"\end{longtable}",
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
        rows.append(" & ".join([block_name, _format_value(ed_sums.get(block_name, 0.0))]) + r" \\")

    lines = [
        r"\begin{longtable}{lr}",
        r"\caption{Summierte Exergievernichtung der Funktionsbloecke des Single-Kolonnenmodells} \\",
        r"\hline",
        r"Block & Summe $\dot{E}_D$ (W) \\",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
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
        rows.append(" & ".join([block_name, _format_value(s_val), _format_value(d_val)]) + r" \\")

    lines = [
        r"\begin{longtable}{lrr}",
        r"\caption{Summierte Exergievernichtung der Funktionsbloecke fuer Single- und Doppelkolonnenmodell} \\",
        r"\hline",
        r"Block & Summe $\dot{E}_D$ Single (W) & Summe $\dot{E}_D$ Doppel (W) \\",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
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
        "aspen_luftzerlegung_streams_single.tex",
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
        "aspen_luftzerlegung_components_single.tex",
    )
)
components_table = _build_component_results_table(ean.components)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

# Write components work (W) table for single model
components_work_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_components_work_single.tex",
    )
)
components_work_table = _build_components_work_table(connections_now, ean.components)
with open(components_work_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_work_table)

global_check_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        # global single table removed per user request
    )
)

block_ed_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed_single.tex",
    )
)
block_ed_table = _build_block_ed_table(ean.components)
with open(block_ed_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_table)

block_ed_comparison_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed_comparison.tex",
    )
)
double_block_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed.tex",
    )
)
single_sums = _compute_block_ed_sums(ean.components, _get_block_map_single())
double_sums = _read_block_ed_table(double_block_path)
block_ed_comparison_table = _build_block_ed_comparison_table(single_sums, double_sums)
with open(block_ed_comparison_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_comparison_table)

molfractions_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams_molfrac_single.tex",
    )
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)
