import json
import logging
import os

from exerpy.functions import convert_to_SI, fluid_property_data

from .aspen_config import connector_mappings, grouped_components


class AspenModelParser:
    """
    A class to parse Aspen Plus models, simulate them, extract data, and write to JSON.
    """

    def __init__(self, model_path, split_physical_exergy=True):
        """
        Initializes the parser with the given model path.

        Parameters:
            model_path (str): Path to the Aspen Plus model file.
            split_physical_exergy (bool): Flag to split physical exergy into thermal and mechanical components.
        """
        self.model_path = model_path
        self.split_physical_exergy = split_physical_exergy
        self.aspen = None  # Aspen Plus application instance
        self.components_data = {}  # Dictionary to store component data
        self.connections_data = {}  # Dictionary to store connection data

        # Dictionary to map component types to specific connector assignment functions
        self.connector_assignment_functions = {
            "Mixer": self.assign_mixer_connectors,
            "RStoic": self.assign_combustion_chamber_connectors,
            "FSplit": self.assign_splitter_connectors,
            "Flash2": self.assign_multiport_connectors,
            "MHeatX": self.assign_multiport_connectors,
            "RadFrac": self.assign_multiport_connectors,
            "Sep": self.assign_multiport_connectors,
            # Add other specific component functions here
        }

    def initialize_model(self):
        """
        Initializes the Aspen Plus application and opens the specified model.
        """
        from win32com.client import Dispatch

        try:
            # Start Aspen Plus application via COM Dispatch
            self.aspen = Dispatch("Apwn.Document")
            # Load the Aspen model file
            self.aspen.InitFromArchive2(self.model_path)
            logging.info(f"Model opened successfully: {self.model_path}")
        except Exception as e:
            logging.error(f"Failed to initialize the model: {e}")
            raise

    def parse_model(self):
        """
        Parses the components and connections from the Aspen model.
        """
        try:
            # Parse Tamb and pamb
            self.parse_ambient_conditions()

            # Parse streams (connections)
            self.parse_streams()

            # Parse blocks (components)
            self.parse_blocks()

        except Exception as e:
            logging.error(f"Error while parsing the model: {e}")
            raise

    def parse_streams(self):
        """
        Parses the streams (connections) in the Aspen model.
        """
        # Get the stream nodes and their names
        stream_nodes = self.aspen.Tree.FindNode(r"\Data\Streams").Elements
        stream_names = [stream_node.Name for stream_node in stream_nodes]

        # ALL ASPEN CONNECTIONS
        # Log stream tree for visibility before parsing streams
        logging.warning(f"Stream tree discovered: {stream_names}")
        logging.warning("Stream parsing will collect standard properties (T, p, h, s, m, exergy) and user-requested properties: LFRAC->lf, VFRAC_OUT->vf, VLSTD->vstd, MOLEFRAC(N2/O2/AR/CO2/H2O)->mfn2/mfo2/mfar/mfco/mfho, HMX->hmx, SMX->smx, STRM_UPP USRE*->ech/em/eph/eth")

        # Initialize connection data with the common fields
        for stream_name in stream_names:
            self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}")
            connection_data = {
                "name": stream_name,
                "kind": None,
                "source_component": None,
                "source_connector": None,
                "target_component": None,
                "target_connector": None,
            }

            # Find the source and target components
            source_port_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Ports\SOURCE")
            if source_port_node is not None and source_port_node.Elements.Count > 0:
                connection_data["source_component"] = source_port_node.Elements(0).Name

            destination_port_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Ports\DEST")
            if destination_port_node is not None and destination_port_node.Elements.Count > 0:
                connection_data["target_component"] = destination_port_node.Elements(0).Name

            # HEAT AND POWER STREAMS
            if self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Input\WORK") is not None:
                connection_data["kind"] = "power"
                connection_data["energy_flow"] = (
                    convert_to_SI(
                        "power",
                        abs(self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\POWER_OUT").Value),
                        self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\POWER_OUT").UnitString,
                        context=f"stream:{stream_name}:POWER_OUT",
                    )
                    if self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\POWER_OUT") is not None
                    else None
                )
            elif self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Input\HEAT") is not None:
                connection_data["kind"] = "heat"
                connection_data["energy_flow"] = (
                    convert_to_SI(
                        "power",
                        abs(self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\QCALC").Value),
                        self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\QCALC").UnitString,
                        context=f"stream:{stream_name}:QCALC",
                    )
                    if self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\QCALC") is not None
                    else None
                )

            # MATERIAL STREAMS
            else:
                # Assume it's a material stream and retrieve additional properties
                # Pre-fetch some nodes to avoid repeated FindNode calls and handle missing values safely
                hmx_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\HMX_FLOW\MIXED")
                temp_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\TEMP_OUT\MIXED")
                pres_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\PRES_OUT\MIXED")
                hmx_mass_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\HMX_MASS\MIXED")
                smx_mass_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\SMX_MASS\MIXED")
                massflm_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\MASSFLMX\MIXED")
                exergy_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\STRM_UPP\EXERGYMS\MIXED\TOTAL")
                totflow_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\TOT_FLOW")
                lfrac_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\LFRAC\MIXED")
                vfrac_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\VFRAC_OUT\MIXED")
                vlstd_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\VLSTD")
                hmx_total_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\HMX\MIXED")
                smx_total_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\SMX\MIXED")
                usrech_node = self.aspen.Tree.FindNode(
                    rf"\Data\Streams\{stream_name}\Output\STRM_UPP\USRECH\MIXED\TOTAL"
                )
                usreme_node = self.aspen.Tree.FindNode(
                    rf"\Data\Streams\{stream_name}\Output\STRM_UPP\USREME\MIXED\TOTAL"
                )
                usreph_node = self.aspen.Tree.FindNode(
                    rf"\Data\Streams\{stream_name}\Output\STRM_UPP\USREPH\MIXED\TOTAL"
                )
                usreth_node = self.aspen.Tree.FindNode(
                    rf"\Data\Streams\{stream_name}\Output\STRM_UPP\USRETH\MIXED\TOTAL"
                )
                # Warn if nodes exist but have no value
                if temp_node is not None and temp_node.Value is None:
                    logging.warning(f"TEMP_OUT node for stream {stream_name} has no value")
                if pres_node is not None and pres_node.Value is None:
                    logging.warning(f"PRES_OUT node for stream {stream_name} has no value")
                if hmx_mass_node is not None and hmx_mass_node.Value is None:
                    logging.warning(f"HMX_MASS node for stream {stream_name} has no value")
                if hmx_node is not None and hmx_node.Value is None:
                    logging.warning(f"HMX_FLOW node for stream {stream_name} has no value")
                if smx_mass_node is not None and smx_mass_node.Value is None:
                    logging.warning(f"SMX_MASS node for stream {stream_name} has no value")
                if massflm_node is not None and massflm_node.Value is None:
                    logging.warning(f"MASSFLMX node for stream {stream_name} has no value")
                if exergy_node is not None and exergy_node.Value is None:
                    logging.warning(f"EXERGYMS node for stream {stream_name} has no value")
                if totflow_node is not None and totflow_node.Value is None:
                    logging.warning(f"TOT_FLOW node for stream {stream_name} has no value")
                if lfrac_node is not None and lfrac_node.Value is None:
                    logging.warning(f"LFRAC node for stream {stream_name} has no value")
                if vfrac_node is not None and vfrac_node.Value is None:
                    logging.warning(f"VFRAC_OUT node for stream {stream_name} has no value")
                if vlstd_node is not None and vlstd_node.Value is None:
                    logging.warning(f"VLSTD node for stream {stream_name} has no value")
                if hmx_total_node is not None and hmx_total_node.Value is None:
                    logging.warning(f"HMX node for stream {stream_name} has no value")
                if smx_total_node is not None and smx_total_node.Value is None:
                    logging.warning(f"SMX node for stream {stream_name} has no value")
                if usrech_node is not None and usrech_node.Value is None:
                    logging.warning(f"USRECH node for stream {stream_name} has no value")
                if usreme_node is not None and usreme_node.Value is None:
                    logging.warning(f"USREME node for stream {stream_name} has no value")
                if usreph_node is not None and usreph_node.Value is None:
                    logging.warning(f"USREPH node for stream {stream_name} has no value")
                if usreth_node is not None and usreth_node.Value is None:
                    logging.warning(f"USRETH node for stream {stream_name} has no value")

                connection_data.update(
                    {
                        "kind": "material",
                        "T": (
                            convert_to_SI("T", temp_node.Value, temp_node.UnitString, context=f"stream:{stream_name}:TEMP_OUT")
                            if (temp_node is not None and temp_node.Value is not None)
                            else None
                        ),
                        "T_unit": fluid_property_data["T"]["SI_unit"],
                        "p": (
                            convert_to_SI("p", pres_node.Value, pres_node.UnitString, context=f"stream:{stream_name}:PRES_OUT")
                            if (pres_node is not None and pres_node.Value is not None)
                            else None
                        ),
                        "p_unit": fluid_property_data["p"]["SI_unit"],
                        "h": (
                            convert_to_SI("h_m", hmx_mass_node.Value, hmx_mass_node.UnitString, context=f"stream:{stream_name}:HMX_MASS")
                            if (hmx_mass_node is not None and hmx_mass_node.Value is not None)
                            else None
                        ),
                        "h_unit": fluid_property_data["h"]["SI_unit"],
                        "s": (
                            convert_to_SI("s_m", smx_mass_node.Value, smx_mass_node.UnitString, context=f"stream:{stream_name}:SMX_MASS")
                            if (smx_mass_node is not None and smx_mass_node.Value is not None)
                            else None
                        ),
                        "s_unit": fluid_property_data["s"]["SI_unit"],
                        "m": (
                            convert_to_SI("m", massflm_node.Value, massflm_node.UnitString, context=f"stream:{stream_name}:MASSFLMX")
                            if (massflm_node is not None and massflm_node.Value is not None)
                            else None
                        ),
                        "m_unit": fluid_property_data["m"]["SI_unit"],
                        "energy_flow": (
                            abs(hmx_node.Value)
                            if (hmx_node is not None and hmx_node.Value is not None)
                            else None
                        ),
                        "energy_flow_unit": (
                            hmx_node.UnitString
                            if (hmx_node is not None and hmx_node.Value is not None)
                            else None
                        ),
                        "n": (
                            convert_to_SI("n", totflow_node.Value, totflow_node.UnitString, context=f"stream:{stream_name}:TOT_FLOW")
                            if (totflow_node is not None and totflow_node.Value is not None)
                            else None
                        ),
                        "n_unit": fluid_property_data["n"]["SI_unit"],
                        "lfrac": lfrac_node.Value if (lfrac_node is not None and lfrac_node.Value is not None) else None,
                        "lfrac_unit": (
                            lfrac_node.UnitString if (lfrac_node is not None and lfrac_node.Value is not None) else None
                        ),
                        "vfrac_out": vfrac_node.Value if (vfrac_node is not None and vfrac_node.Value is not None) else None,
                        "vfrac_out_unit": (
                            vfrac_node.UnitString if (vfrac_node is not None and vfrac_node.Value is not None) else None
                        ),
                        "vlstd": vlstd_node.Value if (vlstd_node is not None and vlstd_node.Value is not None) else None,
                        "vlstd_unit": (
                            vlstd_node.UnitString if (vlstd_node is not None and vlstd_node.Value is not None) else None
                        ),
                        "hmx": (
                            hmx_total_node.Value
                            if (hmx_total_node is not None and hmx_total_node.Value is not None)
                            else None
                        ),
                        "hmx_unit": (
                            hmx_total_node.UnitString
                            if (hmx_total_node is not None and hmx_total_node.Value is not None)
                            else None
                        ),
                        "smx": (
                            smx_total_node.Value
                            if (smx_total_node is not None and smx_total_node.Value is not None)
                            else None
                        ),
                        "smx_unit": (
                            smx_total_node.UnitString
                            if (smx_total_node is not None and smx_total_node.Value is not None)
                            else None
                        ),
                        "usrech": (
                            usrech_node.Value if (usrech_node is not None and usrech_node.Value is not None) else None
                        ),
                        "usrech_unit": (
                            usrech_node.UnitString
                            if (usrech_node is not None and usrech_node.Value is not None)
                            else None
                        ),
                        "usreme": (
                            usreme_node.Value if (usreme_node is not None and usreme_node.Value is not None) else None
                        ),
                        "usreme_unit": (
                            usreme_node.UnitString
                            if (usreme_node is not None and usreme_node.Value is not None)
                            else None
                        ),
                        "usreph": (
                            usreph_node.Value if (usreph_node is not None and usreph_node.Value is not None) else None
                        ),
                        "usreph_unit": (
                            usreph_node.UnitString
                            if (usreph_node is not None and usreph_node.Value is not None)
                            else None
                        ),
                        "usreth": (
                            usreth_node.Value if (usreth_node is not None and usreth_node.Value is not None) else None
                        ),
                        "usreth_unit": (
                            usreth_node.UnitString
                            if (usreth_node is not None and usreth_node.Value is not None)
                            else None
                        ),
                        "mass_composition": {},
                        "molar_composition": {},
                    }
                )
                # Retrieve the fluid names for the stream
                mole_frac_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED")
                if mole_frac_node is not None:
                    fluid_names = [fluid.Name for fluid in mole_frac_node.Elements]

                    # Retrieve the molar composition for each fluid
                    for fluid_name in fluid_names:
                        mole_frac = self.aspen.Tree.FindNode(
                            rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{fluid_name}"
                        ).Value
                        if mole_frac not in [0, None]:  # Skip fluids with 0 or None as the fraction
                            connection_data["molar_composition"][fluid_name] = mole_frac

                for fluid_name in ["N2", "O2", "AR", "CO2", "H2O"]:
                    mole_frac_node = self.aspen.Tree.FindNode(
                        rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{fluid_name}"
                    )
                    if mole_frac_node is not None:
                        mole_frac = mole_frac_node.Value
                        if mole_frac not in [0, None]:
                            connection_data["molar_composition"][fluid_name] = mole_frac

                mass_frac_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\MASSFRAC\MIXED")
                if mass_frac_node is not None:
                    # Retrieve the mass composition for each fluid
                    for fluid_name in [fluid.Name for fluid in mass_frac_node.Elements]:
                        mass_frac = self.aspen.Tree.FindNode(
                            rf"\Data\Streams\{stream_name}\Output\MASSFRAC\MIXED\{fluid_name}"
                        ).Value
                        if mass_frac not in [0, None]:  # Skip fluids with 0 or None as the fraction
                            connection_data["mass_composition"][fluid_name] = mass_frac

                # Map the user-requested nodes into explicit properties
                # Use 'x' conversion (unitless fraction) where appropriate
                if lfrac_node is not None and lfrac_node.Value is not None:
                    raw_unit = lfrac_node.UnitString or "1"
                    try:
                        connection_data["lf"] = convert_to_SI("xlf", lfrac_node.Value, raw_unit, context=f"stream:{stream_name}:LFRAC")
                        connection_data["lf_unit"] = fluid_property_data["x"]["SI_unit"]
                    except Exception:
                        logging.warning(f"Conversion for LFRAC in stream {stream_name} failed; storing raw value.")
                        connection_data["lf"] = lfrac_node.Value
                        connection_data["lf_unit"] = None
                    connection_data["lf_raw"] = lfrac_node.Value
                    connection_data["lf_raw_unit"] = raw_unit
                else:
                    connection_data["lf"] = None
                    connection_data["lf_unit"] = None
                    connection_data["lf_raw"] = None
                    connection_data["lf_raw_unit"] = None

                if vfrac_node is not None and vfrac_node.Value is not None:
                    raw_unit = vfrac_node.UnitString or "1"
                    try:
                        connection_data["vf"] = convert_to_SI("xvf", vfrac_node.Value, raw_unit, context=f"stream:{stream_name}:VFRAC_OUT")
                        connection_data["vf_unit"] = fluid_property_data["x"]["SI_unit"]
                    except Exception:
                        logging.warning(f"Conversion for VFRAC_OUT in stream {stream_name} failed; storing raw value.")
                        connection_data["vf"] = vfrac_node.Value
                        connection_data["vf_unit"] = None
                    connection_data["vf_raw"] = vfrac_node.Value
                    connection_data["vf_raw_unit"] = raw_unit
                else:
                    connection_data["vf"] = None
                    connection_data["vf_unit"] = None
                    connection_data["vf_raw"] = None
                    connection_data["vf_raw_unit"] = None

                if vlstd_node is not None and vlstd_node.Value is not None:
                    raw_unit = vlstd_node.UnitString or "1"
                    try:
                        connection_data["vstd"] = convert_to_SI("vstd", vlstd_node.Value, raw_unit, context=f"stream:{stream_name}:VLSTD")
                        connection_data["vstd_unit"] = fluid_property_data["x"]["SI_unit"]
                    except Exception:
                        logging.warning(f"Conversion for VLSTD in stream {stream_name} failed; storing raw value.")
                        connection_data["vstd"] = vlstd_node.Value
                        connection_data["vstd_unit"] = None
                    connection_data["vstd_raw"] = vlstd_node.Value
                    connection_data["vstd_raw_unit"] = raw_unit
                else:
                    connection_data["vstd"] = None
                    connection_data["vstd_unit"] = None
                    connection_data["vstd_raw"] = None
                    connection_data["vstd_raw_unit"] = None

                # Explicit species mole fractions
                for sp, key in [("N2", "mfn2"), ("O2", "mfo2"), ("AR", "mfar"), ("CO2", "mfco"), ("H2O", "mfho")]:
                    sp_node = self.aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{sp}")
                    if sp_node is not None and sp_node.Value is not None:
                        raw_unit = sp_node.UnitString or "1"
                        property_key = {
                            "N2": "x_n2",
                            "O2": "x_o2",
                            "AR": "x_ar",
                            "CO2": "x_co2",
                            "H2O": "x_h2o",
                        }[sp]
                        try:
                            connection_data[key] = convert_to_SI(property_key, sp_node.Value, raw_unit, context=f"stream:{stream_name}:MOLEFRAC:{sp}")
                            connection_data[f"{key}_unit"] = fluid_property_data["x"]["SI_unit"]
                        except Exception:
                            logging.warning(f"Conversion for MOLEFRAC {sp} in stream {stream_name} failed; storing raw value.")
                            connection_data[key] = sp_node.Value
                            connection_data[f"{key}_unit"] = None
                        connection_data[f"{key}_raw"] = sp_node.Value
                        connection_data[f"{key}_raw_unit"] = raw_unit
                        if sp_node.Value not in [0, None]:
                            connection_data["molar_composition"].setdefault(sp, sp_node.Value)
                    else:
                        connection_data[key] = None
                        connection_data[f"{key}_unit"] = None
                        connection_data[f"{key}_raw"] = None
                        connection_data[f"{key}_raw_unit"] = None

                # HMX and SMX (per-mole/kmol properties) as explicit fields
                # HMX and SMX (per-mole/kmol properties) as explicit fields
                if hmx_total_node is not None and hmx_total_node.Value is not None:
                    # store raw values
                    connection_data["hmx_raw"] = hmx_total_node.Value
                    connection_data["hmx_raw_unit"] = hmx_total_node.UnitString
                    try:
                        connection_data["hmx"] = convert_to_SI("h", hmx_total_node.Value, hmx_total_node.UnitString, context=f"stream:{stream_name}:HMX")
                        connection_data["hmx_unit"] = fluid_property_data["h"]["SI_unit"]
                    except Exception as e:
                        logging.warning(f"HMX conversion for stream {stream_name} failed: {e}. Setting to None.")
                        connection_data["hmx"] = None
                        connection_data["hmx_unit"] = None
                else:
                    connection_data["hmx"] = None
                    connection_data["hmx_unit"] = None
                    connection_data["hmx_raw"] = None
                    connection_data["hmx_raw_unit"] = None

                if smx_total_node is not None and smx_total_node.Value is not None:
                    connection_data["smx_raw"] = smx_total_node.Value
                    connection_data["smx_raw_unit"] = smx_total_node.UnitString
                    try:
                        connection_data["smx"] = convert_to_SI("s", smx_total_node.Value, smx_total_node.UnitString, context=f"stream:{stream_name}:SMX")
                        connection_data["smx_unit"] = fluid_property_data["s"]["SI_unit"]
                    except Exception as e:
                        logging.warning(f"SMX conversion for stream {stream_name} failed: {e}. Setting to None.")
                        connection_data["smx"] = None
                        connection_data["smx_unit"] = None
                else:
                    connection_data["smx"] = None
                    connection_data["smx_unit"] = None
                    connection_data["smx_raw"] = None
                    connection_data["smx_raw_unit"] = None

                # STRM_UPP user-supplied exergy terms
                for node, key, name, property_key in [
                    (usrech_node, "ech", "USRECH", "e_ch"),
                    (usreme_node, "em", "USREME", "e_m"),
                    (usreph_node, "eph", "USREPH", "e_ph"),
                    (usreth_node, "eth", "USRETH", "e_th"),
                ]:
                    if node is not None and node.Value is not None:
                        connection_data[f"{key}_raw"] = node.Value
                        connection_data[f"{key}_raw_unit"] = node.UnitString
                        try:
                            connection_data[key] = convert_to_SI(property_key, node.Value, node.UnitString, context=f"stream:{stream_name}:{name}")
                            connection_data[f"{key}_unit"] = fluid_property_data["e"]["SI_unit"]
                        except Exception as e:
                            logging.warning(f"Conversion for {name} in stream {stream_name} failed: {e}. Setting to None.")
                            connection_data[key] = None
                            connection_data[f"{key}_unit"] = None
                    else:
                        connection_data[key] = None
                        connection_data[f"{key}_raw"] = None
                        connection_data[f"{key}_raw_unit"] = None
                        connection_data[f"{key}_unit"] = None

                # Log parsed properties for visibility
                # Build a more detailed summary including raw units and raw values when available
                summary_parts = []
                def add_part(key, pretty):
                    val = connection_data.get(key)
                    raw = connection_data.get(f"{key}_raw")
                    raw_unit = connection_data.get(f"{key}_raw_unit")
                    unit = connection_data.get(f"{key}_unit")
                    if val is None and raw is None:
                        summary_parts.append(f"{pretty}=None")
                    else:
                        if raw is not None and raw_unit is not None:
                            summary_parts.append(f"{pretty}={val} (raw={raw} {raw_unit})")
                        elif raw is not None:
                            summary_parts.append(f"{pretty}={val} (raw={raw})")
                        else:
                            summary_parts.append(f"{pretty}={val}")

                add_part("lf", "lf")
                add_part("vf", "vf")
                add_part("vstd", "vstd")
                add_part("mfn2", "mfn2")
                add_part("mfo2", "mfo2")
                add_part("mfar", "mfar")
                add_part("mfco", "mfco")
                add_part("mfho", "mfho")
                add_part("hmx", "hmx")
                add_part("smx", "smx")
                add_part("ech", "ech")
                add_part("em", "em")
                add_part("eph", "eph")
                add_part("eth", "eth")

                logging.warning(f"Parsed stream {stream_name}: " + ", ".join(summary_parts))

            # Store connection data
            self.connections_data[stream_name] = connection_data

    def parse_blocks(self):
        """
        Parses the blocks (components) in the Aspen model and ensures that all components, including motors created from pumps, are properly grouped.
        """
        block_nodes = self.aspen.Tree.FindNode(r"\Data\Blocks").Elements
        block_names = [block_node.Name for block_node in block_nodes]

        # Process each block
        for block_name in block_names:
            model_type_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Input\MODEL_TYPE")
            model_type = model_type_node.Value if model_type_node is not None else None

            component_type_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}")
            if component_type_node is None:
                continue
            component_type = component_type_node.AttributeValue(6)
            if component_type == "Mixer":
                mixer_value = component_type_node.Value
                if mixer_value in ["TRIANGLE", "HEAT"]:
                    logging.info(f"Ignoring Mixer {block_name} with value {mixer_value}.")
                    continue

            component_data = {
                "name": block_name,
                "type": component_type,
                "eta_s": (
                    self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\EFF_ISEN").Value
                    if self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\EFF_ISEN") is not None
                    else None
                ),
                "eta_mech": (
                    self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\EFF_MECH").Value
                    if self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\EFF_MECH") is not None
                    else None
                ),
                "Q": (
                    convert_to_SI(
                        "heat",
                        self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\QNET").Value,
                        self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\QNET").UnitString,
                        context=f"block:{block_name}:QNET",
                    )
                    if (self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\QNET") is not None and self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\QNET").Value is not None)
                    else None
                ),
                "Q_unit": fluid_property_data["heat"]["SI_unit"],
                "P": (
                    convert_to_SI(
                        "power",
                        abs(self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BRAKE_POWER").Value),
                        self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BRAKE_POWER").UnitString,
                        context=f"block:{block_name}:BRAKE_POWER",
                    )
                    if (self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BRAKE_POWER") is not None and self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BRAKE_POWER").Value is not None)
                    else None
                ),
                "P_unit": fluid_property_data["power"]["SI_unit"],
            }

            # Override component type based on model_type
            if model_type is not None:
                if model_type == "COMPRESSOR":
                    component_data["type"] = "Compressor"
                elif model_type == "TURBINE":
                    component_data["type"] = "Turbine"

            # Handle Generators & Motors (if not in a Pump) as multiplier blocks
            if component_type == "Mult":
                mult_value_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}")
                mult_value = mult_value_node.Value if mult_value_node is not None else None
                if mult_value == "WORK":
                    factor_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Input\FACTOR")
                    factor = factor_node.Value if factor_node is not None else None
                    if factor is not None:
                        if factor < 1:
                            component_data.update({"eta_el": factor, "type": "Generator"})
                        elif factor > 1:
                            elec_power_node = self.aspen.Tree.FindNode(
                                rf"\Data\Blocks\{block_name}\Ports\WS(OUT)"
                            ).Elements(0)
                            elec_power_name = elec_power_node.Name
                            if elec_power_name in self.connections_data:
                                elec_energy = self.connections_data[elec_power_name].get("energy_flow")
                                elec_power = abs(elec_energy) if elec_energy is not None else None
                            else:
                                logging.warning(f"No WS(IN) ports found for block {block_name}")
                                elec_power = None
                            brake_power_node = self.aspen.Tree.FindNode(
                                rf"\Data\Blocks\{block_name}\Ports\WS(IN)"
                            ).Elements(0)
                            brake_power_name = brake_power_node.Name
                            if brake_power_name in self.connections_data:
                                brake_energy = self.connections_data[brake_power_name].get("energy_flow")
                                brake_power = abs(brake_energy) if brake_energy is not None else None
                            else:
                                logging.warning(f"No WS(IN) ports found for block {block_name}")
                                brake_power = None
                            component_data.update(
                                {
                                    "eta_el": 1 / factor,
                                    "multiplier factor": factor,
                                    "type": "Motor",
                                    "P_el": elec_power,
                                    "P_el_unit": fluid_property_data["power"]["SI_unit"],
                                    "P_mech": brake_power,
                                    "P_mech_unit": fluid_property_data["power"]["SI_unit"],
                                }
                            )
                        else:  # factor == 1
                            choice = (
                                input(
                                    f"Multiplier Block '{block_name}' has factor = 1. Enter 'G' if it is a Generator or 'M' for Motor: "
                                )
                                .strip()
                                .upper()
                            )
                            if choice == "M":
                                elec_power_node = self.aspen.Tree.FindNode(
                                    rf"\Data\Blocks\{block_name}\Ports\WS(OUT)"
                                ).Elements(0)
                                elec_power_name = elec_power_node.Name
                                if elec_power_name in self.connections_data:
                                    elec_power = abs(self.connections_data[elec_power_name]["energy_flow"])
                                else:
                                    logging.warning(f"No WS(IN) ports found for block {block_name}")
                                    elec_power = None
                                brake_power_node = self.aspen.Tree.FindNode(
                                    rf"\Data\Blocks\{block_name}\Ports\WS(IN)"
                                ).Elements(0)
                                brake_power_name = brake_power_node.Name
                                if brake_power_name in self.connections_data:
                                    brake_power = abs(self.connections_data[brake_power_name]["energy_flow"])
                                else:
                                    logging.warning(f"No WS(IN) ports found for block {block_name}")
                                    brake_power = None
                                component_data.update(
                                    {
                                        "eta_el": factor,
                                        "type": "Motor",
                                        "P_el": elec_power,
                                        "P_el_unit": fluid_property_data["power"]["SI_unit"],
                                        "P_mech": brake_power,
                                        "P_mech_unit": fluid_property_data["power"]["SI_unit"],
                                    }
                                )
                            else:
                                component_data.update({"eta_el": factor, "type": "Generator"})

            # Create a connection for the heat flows of the SimpleHeatExchanger blocks
            if component_type == "Heater":
                heat_connection_name = f"{block_name}_HEAT"
                heat_connection_data = {
                    "name": heat_connection_name,
                    "kind": "heat",
                    "source_component": block_name,
                    "source_connector": 1,  # 00 is reserved for the fluid streams
                    "target_component": None,  # Heat assumed to leave the system (not relevant for exergy analysis)
                    "target_connector": None,  # Heat assumed to leave the system (not relevant for exergy analysis)
                    "energy_flow": (abs(component_data["Q"]) if component_data.get("Q") is not None else None),
                    # the user defines in the balances if the heat flow is positive or negative
                    "energy_flow_unit": fluid_property_data["heat"]["SI_unit"],
                }

                # Store the heat connection
                self.connections_data[heat_connection_name] = heat_connection_data

            # Group the component
            self.group_component(component_data, block_name)

            # Handle Pumps and their associated Motors
            if component_type == "Pump":
                motor_name = f"{block_name}-MOTOR"
                elec_power_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\ELEC_POWER")
                elec_power = (
                    abs(
                        convert_to_SI(
                            "power",
                            elec_power_node.Value,
                            elec_power_node.UnitString,
                            context=f"block:{block_name}:ELEC_POWER",
                        )
                    )
                    if (elec_power_node is not None and elec_power_node.Value is not None)
                    else None
                )
                brake_power_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BRAKE_POWER")
                brake_power = (
                    abs(
                        convert_to_SI(
                            "power",
                            brake_power_node.Value,
                            brake_power_node.UnitString,
                            context=f"block:{block_name}:BRAKE_POWER",
                        )
                    )
                    if (brake_power_node is not None and brake_power_node.Value is not None)
                    else None
                )
                eff_driv_node = self.aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\EFF_DRIV")
                eff_driv = eff_driv_node.Value if eff_driv_node is not None else None

                motor_data = {
                    "name": motor_name,
                    "type": "Motor",
                    "P_el": elec_power,
                    "P_el_unit": fluid_property_data["power"]["SI_unit"],
                    "P_mech": brake_power,
                    "P_mech_unit": fluid_property_data["power"]["SI_unit"],
                    "eta_el": (eff_driv if eff_driv is not None else None),
                }

                # Group the motor
                self.group_component(motor_data, motor_name)

                # Create a new connection for the motor
                if elec_power is not None:
                    electr_connection_name = f"{block_name}_ELEC"
                    electr_connection_data = {
                        "name": electr_connection_name,
                        "kind": "power",
                        "source_component": None,  # Electrical power usually leaves the system
                        "source_connector": None,  # Electrical power usually leaves the system
                        "target_component": motor_name,
                        "target_connector": 0,
                        "energy_flow": motor_data["P_el"],
                        "energy_flow_unit": fluid_property_data["power"]["SI_unit"],
                    }

                    mech_connection_name = f"{block_name}_MECH"
                    mech_connection_data = {
                        "name": mech_connection_name,
                        "kind": "power",
                        "source_component": motor_name,
                        "source_connector": 0,
                        "target_component": block_name,
                        "target_connector": 1,
                        "energy_flow": motor_data["P_mech"],
                        "energy_flow_unit": fluid_property_data["power"]["SI_unit"],
                    }

                    # Store the motor connection
                    self.connections_data[electr_connection_name] = electr_connection_data
                    self.connections_data[mech_connection_name] = mech_connection_data

            # Assign connectors
            self.assign_connectors(component_data, block_name)

    def assign_connectors(self, component_data, block_name):
        """
        Assigns connectors to streams for each component based on its type.
        """
        component_type = component_data["type"]

        # Check if there is a specific assignment function for this component type
        if component_type in self.connector_assignment_functions:
            # Call the specific function for the component type
            self.connector_assignment_functions[component_type](block_name, self.aspen, self.connections_data)
        else:
            # Fall back to the generic connector assignment logic
            self.assign_generic_connectors(
                block_name, component_type, self.aspen, self.connections_data, connector_mappings
            )

    def assign_mixer_connectors(self, block_name, aspen, connections_data):
        """
        Assign connectors for a Mixer by examining connected streams and their source/target components.
        """
        ports_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports")
        if ports_node is None:
            logging.warning(f"No Ports node found for Mixer block: {block_name}")
            return

        inlet_streams = []
        outlet_streams = []

        for port in ports_node.Elements:
            port_label = port.Name
            port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
            if port_node is not None and port_node.Elements.Count > 0:
                for element in port_node.Elements:
                    stream_name = element.Name
                    if stream_name in connections_data:
                        stream_data = connections_data[stream_name]
                        if stream_data.get("target_component") == block_name:
                            inlet_streams.append((port_label, stream_name))
                        elif stream_data.get("source_component") == block_name:
                            outlet_streams.append((port_label, stream_name))
                        else:
                            logging.warning(
                                f"Stream {stream_name} connected to {block_name} but source/target components do not match."
                            )

        # Assign connectors to inlet streams
        for idx, (port_label, stream_name) in enumerate(inlet_streams):
            connections_data[stream_name]["target_connector"] = idx
            logging.debug(f"Assigned connector {idx} to inlet stream: {stream_name}")

        # Assign connector to outlet stream
        if outlet_streams:
            for idx, (port_label, stream_name) in enumerate(outlet_streams):
                connections_data[stream_name]["source_connector"] = 0  # Assuming single outlet for mixer
                logging.debug(f"Assigned connector 0 to outlet stream: {stream_name}")

    def assign_splitter_connectors(self, block_name, aspen, connections_data):
        """
        Assign connectors for a Splitter (FSplit) by examining connected streams and their source/target components.
        The inlet stream is assigned 'target_connector' = 0.
        The outlet streams are assigned 'source_connector' numbers starting from 0.
        """
        ports_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports")
        if ports_node is None:
            logging.warning(f"No Ports node found for Splitter block: {block_name}")
            return

        inlet_streams = []
        outlet_streams = []

        # Iterate over all ports connected to the splitter
        for port in ports_node.Elements:
            port_label = port.Name
            port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
            if port_node is not None and port_node.Elements.Count > 0:
                for element in port_node.Elements:
                    stream_name = element.Name
                    if stream_name in connections_data:
                        stream_data = connections_data[stream_name]
                        # Determine if the stream is an inlet or outlet based on source and target components
                        if stream_data.get("target_component") == block_name:
                            inlet_streams.append((port_label, stream_name))
                        elif stream_data.get("source_component") == block_name:
                            outlet_streams.append((port_label, stream_name))
                        else:
                            logging.warning(
                                f"Stream {stream_name} connected to {block_name} but source/target components do not match."
                            )

        # Assign connector to inlet stream(s)
        for idx, (port_label, stream_name) in enumerate(inlet_streams):
            connections_data[stream_name]["target_connector"] = 0  # Assuming single inlet for splitter
            logging.debug(f"Assigned connector 0 to inlet stream: {stream_name}")

        # Assign connectors to outlet streams
        for idx, (port_label, stream_name) in enumerate(outlet_streams):
            connections_data[stream_name]["source_connector"] = idx
            logging.debug(f"Assigned connector {idx} to outlet stream: {stream_name}")

    def assign_multiport_connectors(self, block_name, aspen, connections_data):
        """
        Assign connectors for multi-port components by examining connected streams and
        their source/target components. Inlets are assigned target_connector values
        from 0..N-1, outlets are assigned source_connector values from 0..M-1.
        """
        ports_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports")
        if ports_node is None:
            logging.warning(f"No Ports node found for block: {block_name}")
            return

        inlet_streams = []
        outlet_streams = []

        for port in ports_node.Elements:
            port_label = port.Name
            port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
            if port_node is not None and port_node.Elements.Count > 0:
                for element in port_node.Elements:
                    stream_name = element.Name
                    if stream_name in connections_data:
                        stream_data = connections_data[stream_name]
                        if stream_data.get("target_component") == block_name:
                            inlet_streams.append((port_label, stream_name))
                        elif stream_data.get("source_component") == block_name:
                            outlet_streams.append((port_label, stream_name))
                        else:
                            logging.warning(
                                f"Stream {stream_name} connected to {block_name} but source/target components do not match."
                            )

        for idx, (port_label, stream_name) in enumerate(inlet_streams):
            connections_data[stream_name]["target_connector"] = idx
            logging.debug(f"Assigned connector {idx} to inlet stream: {stream_name}")

        for idx, (port_label, stream_name) in enumerate(outlet_streams):
            connections_data[stream_name]["source_connector"] = idx
            logging.debug(f"Assigned connector {idx} to outlet stream: {stream_name}")

    def assign_combustion_chamber_connectors(self, block_name, aspen, connections_data):
        """
        Assign connectors for a combustion chamber (RStoic), based on stream types (air, fuel, etc.).
        """
        ports_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports")
        if ports_node is None:
            logging.warning(f"No Ports node found for combustion chamber block: {block_name}")
            return

        # Iterate over all ports and assign connectors based on port labels
        for port in ports_node.Elements:
            port_label = port.Name

            # Handle inlet ports
            if "(IN)" in port_label:
                port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
                if port_node is not None and port_node.Elements.Count > 0:
                    for element in port_node.Elements:
                        stream_name = element.Name
                        if stream_name in connections_data:
                            molar_composition = connections_data[stream_name].get("molar_composition", {})
                            if molar_composition.get("O2", 0) > 0.15:
                                connections_data[stream_name]["target_connector"] = 0  # Air inlet
                                logging.debug(f"Assigned connector 0 to air inlet stream: {stream_name}")
                            elif molar_composition.get("CH4", 0) > 0.15:
                                connections_data[stream_name]["target_connector"] = 1  # Fuel inlet
                                logging.debug(f"Assigned connector 1 to fuel inlet stream: {stream_name}")
                            else:
                                logging.warning(f"Stream {stream_name} in {block_name} has ambiguous composition.")

            # Handle outlet ports
            elif "(OUT)" in port_label:
                port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
                if port_node is not None and port_node.Elements.Count > 0:
                    for element in port_node.Elements:
                        stream_name = element.Name
                        if stream_name in connections_data:
                            connections_data[stream_name]["source_connector"] = 0  # Outlet stream
                            logging.info(f"Assigned connector 0 to outlet stream: {stream_name}")

    def assign_generic_connectors(self, block_name, component_type, aspen, connections_data, connector_mappings):
        """
        Generic function for components with predefined connector mappings.
        """
        if component_type in connector_mappings:
            mapping = connector_mappings[component_type]

            # Access the ports of the component to find the connected streams
            for port_label, connector_num in mapping.items():
                port_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Ports\{port_label}")
                if port_node is not None and port_node.Elements.Count > 0:
                    for element in port_node.Elements:
                        stream_name = element.Name
                        # Assign the connector number to the appropriate stream in the connection data
                        if stream_name in connections_data:
                            if (
                                "source_component" in connections_data[stream_name]
                                and connections_data[stream_name]["source_component"] == block_name
                            ):
                                connections_data[stream_name]["source_connector"] = connector_num
                                logging.debug(f"Assigned connector {connector_num} to source stream: {stream_name}")
                            elif (
                                "target_component" in connections_data[stream_name]
                                and connections_data[stream_name]["target_component"] == block_name
                            ):
                                connections_data[stream_name]["target_connector"] = connector_num
                                logging.debug(f"Assigned connector {connector_num} to target stream: {stream_name}")
        else:
            logging.warning(f"No connector mapping defined for component type {component_type}.")

    def group_component(self, component_data, component_name):
        """
        Group the component based on its type into the correct group within components_data.

        Parameters:
        - component_data: The dictionary of component attributes.
        - component_name: The name of the component.
        """
        # Determine the group for the component based on its type
        group = None
        for group_name, type_list in grouped_components.items():
            if component_data["type"] in type_list:
                group = group_name
                break

        # If the component doesn't belong to any predefined group, use its type name
        if not group:
            group = component_data["type"]

        # Initialize the group in the components_data dictionary if not already present
        if group not in self.components_data:
            self.components_data[group] = {}

        # Store the component data in the appropriate group
        self.components_data[group][component_name] = component_data

    def parse_ambient_conditions(self):
        """
        Parses the ambient conditions from the Aspen model and stores them as class attributes.
        Raises an error if Tamb or pamb are not found or are set to None.
        """
        try:
            # Parse ambient temperature (Tamb)
            temp_node = self.aspen.Tree.FindNode(r"\Data\Setup\Sim-Options\Input\REF_TEMP")
            self.Tamb = (
                convert_to_SI("T", temp_node.Value, temp_node.UnitString, context="ambient:REF_TEMP")
                if (temp_node is not None and temp_node.Value is not None)
                else None
            )

            if self.Tamb is None:
                raise ValueError(
                    "Ambient temperature (Tamb) not found in the Aspen model. Please set it in Setup > Calculation Options."
                )

            # Parse ambient pressure (pamb)
            pres_node = self.aspen.Tree.FindNode(r"\Data\Setup\Sim-Options\Input\REF_PRES")
            self.pamb = (
                convert_to_SI("p", pres_node.Value, pres_node.UnitString, context="ambient:REF_PRES")
                if (pres_node is not None and pres_node.Value is not None)
                else None
            )

            if self.pamb is None:
                raise ValueError(
                    "Ambient pressure (pamb) not found in the Aspen model. Please set it in Setup > Calculation Options."
                )

            logging.info(f"Parsed ambient conditions: Tamb = {self.Tamb} K, pamb = {self.pamb} Pa")

        except Exception as e:
            logging.error(f"Error parsing ambient conditions: {e}")
            raise

    def get_sorted_data(self):
        """
        Sorts the component and connection data alphabetically by name.

        Returns:
            dict: A dictionary containing sorted 'components', 'connections', and ambient conditions data.
        """
        sorted_components = {comp_name: self.components_data[comp_name] for comp_name in sorted(self.components_data)}
        sorted_connections = {
            conn_name: self.connections_data[conn_name] for conn_name in sorted(self.connections_data)
        }
        ambient_conditions = {
            "Tamb": self.Tamb,
            "Tamb_unit": fluid_property_data["T"]["SI_unit"],
            "pamb": self.pamb,
            "pamb_unit": fluid_property_data["p"]["SI_unit"],
        }
        return {
            "components": sorted_components,
            "connections": sorted_connections,
            "ambient_conditions": ambient_conditions,
        }

    def write_to_json(self, output_path):
        """
        Writes the parsed and sorted data to a JSON file.

        Parameters:
            output_path (str): Path where the JSON file will be saved.
        """
        data = self.get_sorted_data()

        try:
            with open(output_path, "w") as json_file:
                json.dump(data, json_file, indent=4)
            logging.info(f"Data successfully written to {output_path}")
        except Exception as e:
            logging.error(f"Failed to write data to JSON: {e}")
            raise


def run_aspen(model_path, output_dir=None, split_physical_exergy=True):
    """
    Main function to process the Aspen model and return parsed data.
    Optionally writes the parsed data to a JSON file.

    Parameters:
        model_path (str): Path to the Aspen model file.
        output_dir (str): Optional path where the parsed data should be saved as a JSON file.
        split_physical_exergy (bool): Flag to split physical exergy into thermal and mechanical components.

    Returns:
        dict: Parsed data in dictionary format.
    """
    if not os.path.exists(model_path):
        error_msg = f"Model file not found at: {model_path}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)

    parser = AspenModelParser(model_path, split_physical_exergy=split_physical_exergy)

    try:
        parser.initialize_model()
        parser.parse_model()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise RuntimeError(f"An error occurred: {e}")

    parsed_data = parser.get_sorted_data()

    if output_dir is not None:
        try:
            parser.write_to_json(output_dir)
        except Exception as e:
            logging.error(f"Failed to write output file: {e}")
            raise RuntimeError(f"Failed to write output file: {e}")

    return parsed_data
