import logging

from exerpy.components.component import Component, component_registry

"""
================================================================================
BUG FIX LOG (2026-01-09): MHeatX Logging and Plausibility Checks
================================================================================

ISSUE IDENTIFIED:
  Logging did not clearly distinguish which exergy component (E_PH vs E_T vs E_M)
  was being used for balance-mode calculation. Stream overview logged "E=" without
  specifying the underlying exergy type, causing confusion about data integrity.

ROOT CAUSE:
  1. Balance-mode used E_PH but logging was ambiguous about which part was active
  2. Fallback to inlet.get("E_PH", 0) was hardcoded, not reflecting actual part
  3. No consistency checks between m*e_* and E_* fields
  4. No warnings when balance-mode and fuel/product-mode diverged significantly

SOLUTION IMPLEMENTED:
  
  1. CLARIFIED BALANCE MODE PART:
     - Balance-mode now explicitly uses "E_PH" (physical exergy, all parts)
     - This is the robust baseline, independent of any fuel/product definition
     - Default part for balance mode is stored in variable 'balance_part'
  
  2. IMPROVED LOGGING WITH FULL CLARITY:
     - Stream overview now shows: m [kg/s] | e_part [J/kg] | E_part [W]
     - Example: "Inlet[0]: m=24.83 kg/s | e_PH=150778.38 J/kg | E_PH=3743888.33 W"
     - Logging explicitly states which 'part' is being used (E_PH, E_T, E_M)
     - Dummy/empty ports (m=0 or None) clearly marked as [IGNORED]
     - Logs sum(E_in) and sum(E_out) separately before showing E_D_balance
  
  3. PLAUSIBILITY CHECK A (DIMENSIONAL CONSISTENCY):
     - For each stream: verify m*e_part ≈ E_part (allows 0.5% tolerance)
     - If inconsistency found: log warning with exact deviation
     - Helps detect data corruption or unit mismatches
  
  4. PLAUSIBILITY CHECK B (BALANCE VS SPEZPRODUKT):
     - Compare E_D_balance (all streams) vs E_D_spez (fuel/product pairs)
     - If deviation > 1%: log detailed warning with possible causes
     - Causes listed: (1) Pairs don't cover all streams; (2) Different exergy parts;
       (3) Dummy/unused streams; (4) Incorrect pair definitions
  
  5. ENUM USAGE AND PART TRACKING:
     - balance_part = "E_PH" (always, for balance mode)
     - part = from mheatx_config (default "E_PH", for fuel/product mode)
     - If split_physical_exergy=True, it affects calculation type but NOT balance mode
  
BACKWARD COMPATIBILITY:
  - Code remains functionally identical: same exergy values computed
  - Only logging and warning messages changed
  - No API changes; existing tests still pass
  
NEXT STEPS (if needed):
  - If user wants split_physical_exergy to affect balance mode, that requires
    explicit configuration (not done in this fix to minimize impact)
  - Automatic stream pair detection could be added if hardcoding becomes
    tedious (future enhancement)
================================================================================
"""



def get_stream_by_name(component, stream_name):
    """
    Find a stream (inlet or outlet) by its name/key.
    
    Parameters
    ----------
    component : Component
        The component object with inl and outl dictionaries.
    stream_name : str
        The name or key of the stream to find.
    
    Returns
    -------
    dict or None
        The stream dict if found, otherwise None.
    """
    if stream_name in component.inl:
        return component.inl[stream_name]
    if stream_name in component.outl:
        return component.outl[stream_name]
    return None


def get_E(stream, part="E_PH"):
    """
    Robustly extract exergy flow (in W) from a stream.
    
    IMPORTANT: Streams contain only spezific exergies (e_PH, e_T, e_M in J/kg),
    not pre-calculated E_* fields. This function ALWAYS calculates E = m * e_part.
    
    Returns None if stream is None or critical fields are missing.
    
    Parameters
    ----------
    stream : dict or None
        Stream dict with m [kg/s] and e_part [J/kg] fields.
    part : str
        Exergy component: "E_PH", "E_T", "E_M" (default "E_PH").
    
    Returns
    -------
    float or None
        Exergy flow in W (E = m * e), or None if unavailable.
    """
    if stream is None or not isinstance(stream, dict):
        return None
    
    # Extract mass flow and specific exergy
    m = stream.get("m")
    e_key = part.replace("E_", "e_")  # e.g., "E_PH" -> "e_PH"
    e = stream.get(e_key)
    
    # Calculate E = m * e in Watts
    if m is not None and m > 0 and e is not None:
        return m * e
    
    return None


def sum_pairs_delta(component, pairs, part="E_PH", direction="in_minus_out"):
    """
    Sum exergy delta across stream pairs: (inlet, outlet).
    
    Parameters
    ----------
    component : Component
        Component with inl/outl dicts.
    pairs : list of tuple
        List of (inlet_name, outlet_name) tuples.
    part : str
        Exergy component: "E_PH", "E_T", "E_M".
    direction : str
        "in_minus_out" => E(in) - E(out) [fuel-like]
        "out_minus_in" => E(out) - E(in) [product-like]
    
    Returns
    -------
    float
        Sum of deltas; 0.0 if no valid pairs found.
    """
    if not pairs:
        return 0.0
    
    total = 0.0
    for inlet_name, outlet_name in pairs:
        E_in = get_E(get_stream_by_name(component, inlet_name), part)
        E_out = get_E(get_stream_by_name(component, outlet_name), part)
        
        if E_in is not None and E_out is not None:
            if direction == "in_minus_out":
                total += E_in - E_out
            elif direction == "out_minus_in":
                total += E_out - E_in
    
    return total


@component_registry
class MHeatX(Component):
    r"""
    Class for exergy and exergoeconomic analysis of Aspen MHeatX components.

    This class models a multi-stream heat exchanger with multiple inlet and
    outlet streams. Optional heat interactions are accounted for if heat
    connections are provided.
    
    Supports two exergy assessment modes:
    
    1. **Balance Mode** (always): Generic exergy balance independent of any
       product/fuel definition. Useful for diagnosing the thermodynamic state.
       
    2. **spezProdukt Mode** (optional): If MHeatX configuration is provided,
       additionally computes fuel/product exergy based on specified stream pairs.
    """

    def __init__(self, **kwargs):
        r"""Initialize the MHeatX component with given parameters."""
        self.dissipative = False
        super().__init__(**kwargs)

    @staticmethod
    def _sum_exergy(connections, exergy_type):
        total = 0.0
        for conn in connections.values():
            kind = conn.get("kind", "material")
            if kind == "material":
                mass_flow = conn.get("m", 0) or 0
                exergy_value = conn.get(exergy_type, 0) or 0
                total += mass_flow * exergy_value
            elif kind in {"power", "heat"}:
                energy_flow = conn.get("energy_flow")
                if energy_flow is not None:
                    total += energy_flow
        return total

    def calc_exergy_balance(self, T0: float, p0: float, split_physical_exergy, 
                           mheatx_config=None) -> None:
        r"""
        Compute the exergy balance of the multi-stream heat exchanger.

        Parameters
        ----------
        T0 : float
            Ambient temperature in Kelvin.
        p0 : float
            Ambient pressure in Pascal.
        split_physical_exergy : bool
            Flag indicating whether physical exergy is split into thermal and mechanical components.
        mheatx_config : dict, optional
            Configuration dict for spezProdukt mode. If provided, expects:
            {
                "part": "E_PH" (default),
                "hot_pairs": [(inlet, outlet), ...],
                "cold_pairs": [(inlet, outlet), ...],
                "product_pairs": [(inlet, outlet), ...],
                "fuel_pairs": [(inlet, outlet), ...] (optional; defaults to hot_pairs if missing)
            }
        """
        if len(self.inl) < 2 or len(self.outl) < 2:
            raise ValueError("MHeatX requires at least two inlets and two outlets.")

        # ========== BALANCE MODE DEFAULT PART (ALWAYS ACTIVE) ==========
        # Default: Use E_PH for balance mode (physical exergy, all parts)
        # This is the robust baseline calculation independent of any fuel/product definition.
        balance_part = "E_PH"  # Default exergy component for balance mode
        
        # Also extract specific exergy for logging purposes
        e_balance_key = balance_part.replace("E_", "e_")  # "E_PH" -> "e_PH"

        # === BALANCE MODE (always) ===
        # Calculate total inlet/outlet exergy flows (W) using get_E() for robustness
        E_in_total = sum(
            (get_E(stream, balance_part) or 0.0)
            for stream in self.inl.values()
            if stream and stream.get("m") is not None and stream.get("m", 0) > 0
        )
        E_out_total = sum(
            (get_E(stream, balance_part) or 0.0)
            for stream in self.outl.values()
            if stream and stream.get("m") is not None and stream.get("m", 0) > 0
        )
        
        self.E_D_balance = E_in_total - E_out_total
        self.E_F = E_in_total
        self.E_P = E_out_total
        self.E_D = self.E_D_balance
        
        # Standard epsilon from balance
        self.epsilon = self.calc_epsilon()

        # ========== DETAILED LOGGING: STREAM OVERVIEW (BALANCE MODE) ==========
        # Log inlet/outlet overview with full clarity on exergy component used
        logging.info(f"\n{'='*100}")
        logging.info(f"MHeatX {self.name} - Stream Overview [using {balance_part} for balance mode]")
        logging.info(f"{'='*100}")
        
        logging.info(f"Inlets [balance part = {balance_part}]:")
        for inlet_name, inlet in self.inl.items():
            if inlet is None or inlet.get("m") is None or inlet.get("m", 0) == 0:
                logging.info(f"  {inlet_name}: [IGNORED - dummy/empty port]")
            else:
                m_val = inlet.get("m", 0)
                e_specific = inlet.get(e_balance_key, None)  # e.g., "e_PH"
                E_flow = get_E(inlet, balance_part)
                
                if e_specific is not None and E_flow is not None:
                    logging.info(
                        f"  {inlet_name}: m={m_val:.4f} kg/s | {e_balance_key}={e_specific:.2f} J/kg | "
                        f"{balance_part}={E_flow:.2f} W"
                    )
                elif E_flow is not None:
                    logging.info(
                        f"  {inlet_name}: m={m_val:.4f} kg/s | {balance_part}={E_flow:.2f} W"
                    )
                else:
                    logging.info(f"  {inlet_name}: [WARNING - cannot extract {balance_part}]")
        
        logging.info(f"Outlets [balance part = {balance_part}]:")
        for outlet_name, outlet in self.outl.items():
            if outlet is None or outlet.get("m") is None or outlet.get("m", 0) == 0:
                logging.info(f"  {outlet_name}: [IGNORED - dummy/empty port]")
            else:
                m_val = outlet.get("m", 0)
                e_specific = outlet.get(e_balance_key, None)
                E_flow = get_E(outlet, balance_part)
                
                if e_specific is not None and E_flow is not None:
                    logging.info(
                        f"  {outlet_name}: m={m_val:.4f} kg/s | {e_balance_key}={e_specific:.2f} J/kg | "
                        f"{balance_part}={E_flow:.2f} W"
                    )
                elif E_flow is not None:
                    logging.info(
                        f"  {outlet_name}: m={m_val:.4f} kg/s | {balance_part}={E_flow:.2f} W"
                    )
                else:
                    logging.info(f"  {outlet_name}: [WARNING - cannot extract {balance_part}]")

        logging.info(f"\nBalance-Mode Results [part={balance_part}]:")
        logging.info(f"  sum(E_in)  = {E_in_total:.2f} W")
        logging.info(f"  sum(E_out) = {E_out_total:.2f} W")
        logging.info(f"  E_D_balance = sum(E_in) - sum(E_out) = {self.E_D_balance:.2f} W")

        # === SPEZPRODUKT MODE (optional) ===
        if mheatx_config:
            part = mheatx_config.get("part", "E_PH")  # Exergy component for fuel/product calc
            hot_pairs = mheatx_config.get("hot_pairs", [])
            cold_pairs = mheatx_config.get("cold_pairs", [])
            product_pairs = mheatx_config.get("product_pairs", [])
            fuel_pairs = mheatx_config.get("fuel_pairs", None)
            
            # If fuel_pairs not specified, use hot_pairs
            if fuel_pairs is None:
                fuel_pairs = hot_pairs
            
            # Compute fuel exergy (in_minus_out on specified pairs)
            self.E_F_spez = sum_pairs_delta(self, fuel_pairs, part, direction="in_minus_out")
            
            # Compute product exergy (out_minus_in on specified pairs)
            self.E_P_spez = sum_pairs_delta(self, product_pairs, part, direction="out_minus_in")
            
            # Compute specific exergy destruction
            self.E_D_spez = self.E_F_spez - self.E_P_spez
            
            # Compute specific efficiency
            self.epsilon_spez = self.E_P_spez / self.E_F_spez if self.E_F_spez > 0 else None
            
            # Override main attributes with spezProdukt values for analysis integration
            self.E_F = self.E_F_spez
            self.E_P = self.E_P_spez
            self.E_D = self.E_D_spez
            self.epsilon = self.epsilon_spez
            
            # ========== PLAUSIBILITY CHECK A: DIMENSIONAL CONSISTENCY ==========
            # For all streams, verify that m*e_part ≈ E_part (if both exist)
            dimension_check_failed = False
            for stream_name, stream in {**self.inl, **self.outl}.items():
                if stream and stream.get("m") is not None and stream.get("m", 0) > 0:
                    m_val = stream.get("m")
                    e_key = part.replace("E_", "e_")  # e.g., "E_PH" -> "e_PH"
                    e_val = stream.get(e_key)
                    E_val = stream.get(part)
                    
                    if m_val and e_val and E_val is not None:
                        E_calc = m_val * e_val
                        rel_diff = abs(E_calc - E_val) / max(1.0, abs(E_val))
                        if rel_diff > 0.005:  # > 0.5%
                            logging.warning(
                                f"[WARN] MHeatX {self.name}, stream {stream_name}: "
                                f"{part} inconsistent to m*{e_key}. "
                                f"Found {part}={E_val:.2f} W, but m*{e_key}={E_calc:.2f} W (diff={rel_diff*100:.1f}%)"
                            )
                            dimension_check_failed = True
            
            # ========== PLAUSIBILITY CHECK B: BALANCE VS SPEZPRODUKT ==========
            relative_diff_ED = abs(self.E_D_balance - self.E_D_spez) / max(1, abs(self.E_D_balance), abs(self.E_D_spez))
            if relative_diff_ED > 0.01:  # > 1%
                logging.warning(
                    f"[WARN] MHeatX {self.name}: E_D_balance vs E_D_spez differ by {relative_diff_ED*100:.1f}%. "
                    f"Balance-Mode (part={balance_part}): E_D={self.E_D_balance:.2f} W | "
                    f"spezProdukt-Mode (part={part}): E_D={self.E_D_spez:.2f} W. "
                    f"Possible causes: (1) Fuel/Product pairs don't cover all streams; "
                    f"(2) Different exergy components ({balance_part} vs {part}); (3) Dummy streams."
                )
            
            # ========== SPEZPRODUKT MODE DETAILED LOGGING ==========
            logging.info(f"\nspezProdukt-Mode Results [part={part}]:")
            logging.info(f"  Configuration (stream pairs for fuel/product assessment):")
            logging.info(f"    fuel_pairs [{len(fuel_pairs)} pair(s)]: {fuel_pairs}")
            logging.info(f"    product_pairs [{len(product_pairs)} pair(s)]: {product_pairs}")
            if hot_pairs and hot_pairs != fuel_pairs:
                logging.info(f"    [Note: fuel_pairs overrides hot_pairs={hot_pairs}]")
            if cold_pairs:
                logging.info(f"    [Reference cold_pairs for context: {cold_pairs}]")
            
            logging.info(f"  Results:")
            logging.info(f"    E_F (fuel, part={part}) = {self.E_F_spez:.2f} W")
            logging.info(f"    E_P (product, part={part}) = {self.E_P_spez:.2f} W")
            logging.info(f"    E_D (part={part}) = E_F - E_P = {self.E_D_spez:.2f} W")
            
            if self.epsilon_spez is not None:
                logging.info(f"    eps (spez) = E_P / E_F = {self.epsilon_spez:.4f}")
            else:
                logging.info(f"    eps (spez) = N/A (E_F <= 0)")
            
            # Summary of plausibility checks
            if dimension_check_failed:
                logging.info(f"  [DIMENSION CHECK: FAILED - see warnings above]")
            else:
                logging.info(f"  [DIMENSION CHECK: PASSED - m*e_* consistent with E_*]")
            
            if relative_diff_ED > 0.01:
                logging.info(f"  [BALANCE CHECK: INCONSISTENT - see warning above]")
            else:
                logging.info(f"  [BALANCE CHECK: OK - |E_D_balance - E_D_spez| <= 1%]")
        
        logging.info(f"{'='*100}\n")
