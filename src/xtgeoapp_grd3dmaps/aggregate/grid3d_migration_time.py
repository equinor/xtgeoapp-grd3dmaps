import glob
import os
import sys
import tempfile
from typing import List, Optional, Union

import xtgeo

from xtgeoapp_grd3dmaps.aggregate import (
    _config,
    _migration_time,
    _parser,
    grid3d_aggregate_map,
)

MIGRATION_TIME_PROPERTIES = ["AMFG","AMFW","YMFG","YMFW","XMF1","XMF2","YMF1","YMF2","SGAS","SWAT"]

# Module variables for ERT hook implementation:
DESCRIPTION = (
    "Generate migration time property maps. Docs:\n"
    + "https://fmu-docs.equinor.com/docs/xtgeoapp-grd3dmaps/"
)
CATEGORY = "modelling.reservoir"
EXAMPLES = """
.. code-block:: console

  FORWARD_MODEL GRID3D_MIGRATION_TIME(<CONFIG_MIGTIME>=conf.yml, <ECLROOT>=<ECLBASE>)
"""

def calculate_migration_time_property(
    properties_files: str,
    property_name: Optional[str],
    lower_threshold: Union[float,List],
    grid_file: Optional[str],
    dates: List[str],
):
    """
    Calculates a 3D migration time property from the provided grid and grid property
    files
    """
    prop_spec = [
        _config.Property(source=f, name=name)
        for f in glob.glob(properties_files, recursive=True)
        for name in property_name
    ]
    grid = None if grid_file is None else xtgeo.grid_from_file(grid_file)
    properties = _parser.extract_properties(prop_spec, grid, dates)
    t_prop = _migration_time.generate_migration_time_property(
        properties, lower_threshold
    )
    return t_prop


def migration_time_property_to_map(
    config_: _config.RootConfig,
    t_prop: List[xtgeo.GridProperty],
):
    """
    Aggregates and writes a migration time property to file using `grid3d_aggragte_map`.
    The migration time property is written to a temporary file while performing the
    aggregation.
    """
    config_.computesettings.aggregation = _config.AggregationMethod.MIN
    config_.output.aggregation_tag = False
    for prop in t_prop.values():
        temp_file,temp_path = tempfile.mkstemp()
        os.close(temp_file)
        if config_.input.properties is not None:
            config_.input.properties.append(_config.Property(temp_path,None,None))
        prop.to_file(temp_path)
    grid3d_aggregate_map.generate_from_config(config_)
    os.unlink(temp_path)


def main(arguments=None):
    """
    Calculates a migration time property and aggregates it to a 2D map
    """
    if arguments is None:
        arguments = sys.argv[1:]
    config_ = _parser.process_arguments(arguments)
    if len(config_.input.properties) > 1:
        raise ValueError(
            "Migration time computation is only supported for a single property"
        )
    p_spec = config_.input.properties.pop()
    if isinstance(p_spec.name,str):
        p_spec.name = [p_spec.name]
    if any(x in MIGRATION_TIME_PROPERTIES for x in p_spec.name):
        removed_props = [x for x in p_spec.name if x not in MIGRATION_TIME_PROPERTIES]
        p_spec.name = [x for x in p_spec.name if x in MIGRATION_TIME_PROPERTIES]
        if(len(removed_props)>0):
            print("Time migration maps are not supported for these properties: ", ", ".join(str(x) for x in removed_props))        
    else:
        error_text = "Time migration maps are not supported for any of the properties provided"
        raise ValueError(error_text)
    t_prop = calculate_migration_time_property(
        p_spec.source,
        p_spec.name,
        p_spec.lower_threshold,
        config_.input.grid,
        config_.input.dates,
    )
    migration_time_property_to_map(config_, t_prop)


if __name__ == "__main__":
    main()
