#!/usr/bin/env python
import os
import sys
import tempfile
import xtgeo
from typing import List
from xtgeoapp_grd3dmaps.aggregate import (
    _co2_mass,
    _config,
    _parser,
    grid3d_aggregate_map,
)
from xtgeoapp_grd3dmaps.aggregate._config import CO2MassSettings
from ccs_scripts.co2_containment.co2_calculation import calculate_co2

PROPERTIES_TO_EXTRACT = [
    "RPORV",
    "PORV",
    "SGAS",
    "DGAS",
    "BGAS",
    "DWAT",
    "BWAT",
    "AMFG",
    "YMFG",
    "XMF2",
    "YMF2",
]


# Module variables for ERT hook implementation:
# DESCRIPTION = (
#     "Generate migration time property maps. Docs:\n"
#     + "https://fmu-docs.equinor.com/docs/xtgeoapp-grd3dmaps/"
# )
# CATEGORY = "modelling.reservoir"
# EXAMPLES = """
# .. code-block:: console
#
#   FORWARD_MODEL GRID3D_MIGRATION_TIME(<CONFIG_MIGTIME>=conf.yml, <ECLROOT>=<ECLBASE>)
# """


def calculate_mass_property(
    grid_file: str,
    co2_mass_settings: CO2MassSettings,
    out_folder: _config.Output,
) -> List[List[xtgeo.GridProperty]]:
    """
    Calculates and exports 3D CO2 mass properties from the provided grid and config files

    Args:
        grid_file (str): Path to EGRID-file
        co2_mass_settings (CO2MassSettings): Settings from config file for calculation
                                             of CO2 mass maps.
        out_folder (str): Path to store the produced 3D GridProperties.


    Returns:
        List[List[xtgeo.GridProperty].

    """
    co2_data = calculate_co2(grid_file,co2_mass_settings.unrst_source,"mass",co2_mass_settings.init_source,None)

    out_property_list = _co2_mass.translate_co2data_to_property(
        co2_data,
        grid_file,
        co2_mass_settings,
        PROPERTIES_TO_EXTRACT,
        out_folder.mapfolder + "/grid",
    )
    return out_property_list


def co2_mass_property_to_map(
    config_: _config.RootConfig,
    t_prop: xtgeo.GridProperty,
):
    """
    Aggregates with SUM and writes a CO2 mass property to file using `grid3d_aggregate_map`.
    The property is written to a temporary file while performing the
    aggregation.

    Args:
        config_: Arguments in the config file
        t_prop: Grid property to be aggregated

    """
    config_.input.properties = []
    config_.computesettings.aggregation = _config.AggregationMethod.SUM
    config_.output.aggregation_tag = False
    _, temp_path = tempfile.mkstemp()
    config_.input.properties.append(_config.Property(temp_path, t_prop.name, None))
    t_prop.to_file(temp_path)
    grid3d_aggregate_map.generate_from_config(config_)
    os.unlink(temp_path)


def main(arguments=None):
    """
    Takes input arguments and calculates co2 mass as a property and aggregates it to a 2D map
    at each time step, divided into different phases and locations(TODO).
    """
    if arguments is None:
        arguments = sys.argv[1:]
    config_ = _parser.process_arguments(arguments)
    if config_.input.properties:
        raise ValueError("CO2 mass computation does not take a property as input")
    if config_.co2_mass_settings is None:
        raise ValueError("CO2 mass computation needs co2_mass_settings as input")
    out_property_list = calculate_mass_property(
        config_.input.grid,
        config_.co2_mass_settings,
        config_.output,
    )

    for props in out_property_list:
        for prop in props:
            co2_mass_property_to_map(config_, prop)


if __name__ == "__main__":
    main()
