import logging

from exerpy.components.component import Component, component_registry


@component_registry
class Flash2(Component):
    r"""
    Class for exergy and exergoeconomic analysis of Aspen Flash2 components.

    This class models a phase-separation (flash drum) unit with one inlet and
    multiple outlet streams. Optional heat interactions are accounted for if
    heat connections are provided.
    """

    def __init__(self, **kwargs):
        r"""Initialize the Flash2 component with given parameters."""
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

    def calc_exergy_balance(self, T0: float, p0: float, split_physical_exergy) -> None:
        r"""
        Compute the exergy balance of the Flash2 component as an adiabatic, workless separator.

        This component represents a water separator with:
        - One material inlet (mixed stream)
        - Two material outlets:
          * Gas outlet (typically "dry air" product)
          * Liquid outlet (water waste stream)
        
        For a simple adiabatic separator with no work input (W=0), the exergy balance is:
            E_D = E_in - E_out
        
        where E_in and E_out are the total material exergy flow rates. Both gas and liquid
        outlets must be counted in E_out, even though the liquid stream is considered waste
        from a process perspective - it still carries exergy out of the component.

        Parameters
        ----------
        T0 : float
            Ambient temperature in Kelvin.
        p0 : float
            Ambient pressure in Pascal.
        split_physical_exergy : bool
            Flag indicating whether physical exergy is split into thermal and mechanical components.
        
        Notes
        -----
        This implementation uses total physical exergy (e_PH) for the balance computation
        to avoid temperature-regime complications. The exergy destruction should be positive
        for a real separator due to irreversibilities (pressure drop, mixing effects).
        """
        if len(self.inl) < 1 or len(self.outl) < 2:
            raise ValueError("Flash2 requires one inlet and at least two outlets.")

        # Use total physical exergy (e_PH) for adiabatic separator balance
        # This avoids issues with temperature-regime Fuel/Product definitions
        E_in = self._sum_exergy(self.inl, "e_PH")
        E_out = self._sum_exergy(self.outl, "e_PH")
        
        # Calculate exergy destruction: should be positive for real process
        self.E_D = E_in - E_out
        
        # Clamp small negative values caused by numerical rounding
        # If |E_D| < 1e-6 * max(E_in, 1.0), treat as zero
        if self.E_D < 0 and abs(self.E_D) < 1e-6 * max(E_in, 1.0):
            logging.warning(
                f"Flash2 {self.name}: Tiny negative E_D={self.E_D:.6f} W clamped to zero "
                f"(likely numerical error). E_in={E_in:.2f} W, E_out={E_out:.2f} W"
            )
            self.E_D = 0.0
        
        # Set E_F and E_P for reporting consistency
        # Option B: E_F = E_in, E_P = E_out
        self.E_F = E_in
        self.E_P = E_out
        self.epsilon = self.calc_epsilon()

        logging.info(
            f"Exergy balance of Flash2 {self.name} (adiabatic separator): "
            f"E_in={E_in:.2f} W, E_out={E_out:.2f} W, E_D={self.E_D:.2f} W, "
            f"epsilon={self.epsilon:.2%} | "
            f"[Note: Both gas and liquid outlets counted in E_out]"
        )
