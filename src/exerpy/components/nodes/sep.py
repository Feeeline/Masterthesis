import logging

from exerpy.components.component import Component, component_registry


@component_registry
class Sep(Component):
    r"""
    Class for exergy and exergoeconomic analysis of Aspen Sep components.

    This class models a separator/splitter unit with one inlet and multiple
    outlet streams. Optional heat interactions are accounted for if heat
    connections are provided.
    """

    def __init__(self, **kwargs):
        r"""Initialize the Sep component with given parameters."""
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
        Compute the exergy balance of the separator.

        Treats Sep as an adiabatic, workless separator using total physical exergy (e_PH).
        - E_in  = sum(m_in * e_PH) over all material inlets
        - E_out = sum(m_out * e_PH) over ALL material outlets (including waste)
        - E_D   = E_in - E_out (clamped if tiny negative)
        - E_F   = E_in, E_P = E_out, epsilon = E_P/E_F

        Parameters
        ----------
        T0 : float
            Ambient temperature in Kelvin.
        p0 : float
            Ambient pressure in Pascal.
        split_physical_exergy : bool
            Flag indicating whether physical exergy is split into thermal and mechanical components.
            (Note: For Sep, we always use e_PH regardless of this flag.)
        """
        if len(self.inl) < 1 or len(self.outl) < 2:
            raise ValueError("Sep requires one inlet and at least two outlets.")

        # Adiabatic, workless separator: use e_PH for all material streams (inlets and outlets)
        E_in = 0.0
        for conn in self.inl.values():
            if conn.get("kind") == "material":
                mass_flow = conn.get("m", 0) or 0
                e_ph = conn.get("e_PH", 0) or 0
                E_in += mass_flow * e_ph

        E_out = 0.0
        for conn in self.outl.values():
            if conn.get("kind") == "material":
                mass_flow = conn.get("m", 0) or 0
                e_ph = conn.get("e_PH", 0) or 0
                E_out += mass_flow * e_ph

        # Compute exergy destruction
        E_D = E_in - E_out

        # Clamp tiny negative values (numerical rounding)
        tolerance = 1e-6 * max(E_in, 1.0)
        if E_D < 0 and abs(E_D) < tolerance:
            E_D = 0.0

        self.E_F = E_in
        self.E_P = E_out
        self.E_D = E_D
        self.epsilon = self.calc_epsilon()

        # Debug log: note that all outlets (product + waste) are counted
        product_count = sum(1 for conn in self.outl.values() if conn.get("kind") == "material")
        logging.info(
            f"Sep {self.name} (adiabatic separator) | E_in={E_in:.2f} W, E_out={E_out:.2f} W | "
            f"product and waste outlets counted={product_count} | "
            f"E_F={self.E_F:.2f} W, E_P={self.E_P:.2f} W, E_D={self.E_D:.2f} W, "
            f"Efficiency={self.epsilon:.2%}"
        )
