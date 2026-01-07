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

        Parameters
        ----------
        T0 : float
            Ambient temperature in Kelvin.
        p0 : float
            Ambient pressure in Pascal.
        split_physical_exergy : bool
            Flag indicating whether physical exergy is split into thermal and mechanical components.
        """
        if len(self.inl) < 1 or len(self.outl) < 2:
            raise ValueError("Sep requires one inlet and at least two outlets.")

        exergy_type = "e_T" if split_physical_exergy else "e_PH"

        self.E_F = self._sum_exergy(self.inl, exergy_type)
        self.E_P = self._sum_exergy(self.outl, exergy_type)
        self.E_D = self.E_F - self.E_P
        self.epsilon = self.calc_epsilon()

        logging.info(
            f"Exergy balance of Sep {self.name} calculated: "
            f"E_F = {self.E_F:.2f} W, E_P = {self.E_P:.2f} W, E_D = {self.E_D:.2f} W, "
            f"Efficiency = {self.epsilon:.2%}"
        )
