"""Test the pydantic config parser."""

import datetime
import textwrap

import pytest
import xtgeo
from pydantic import ValidationError

from grid3d_maps.parser import _pydantic_configparser as _configparser


def test_parse_yaml_hcthickness_minimal(tmp_path):
    """Test minimum setup for HC thickness map"""

    YAMLCONTENT = textwrap.dedent("""
    # as minimum example
    title: YouKnowMyName
    input:
      eclroot: tests/data/reek/REEK
      dates:
        - 19991201
    """)

    yamlfile = tmp_path / "config_minimal.yml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_hcthickness_config(yamlfile)
    assert config.title == "YouKnowMyName"
    assert config.input.eclroot == "tests/data/reek/REEK"
    assert config.input.dates == ["19991201"]
    assert config.zonation is None
    assert config.computesettings is None


def test_validate_dates():
    """Test input.date validation, and that dates are converted to strings."""

    dates = _configparser._Dates(dates=[19991201, 20021101, "20010101-19991201"])
    assert dates.dates == ["19991201", "20021101", "20010101-19991201"]


def test_validate_dates_datetime_date_fmt():
    """Test input.date validation, and that dates are converted to strings."""

    d1 = datetime.date(1999, 12, 1)
    d2 = datetime.date(2002, 11, 22)

    dates = _configparser._Dates(dates=[d1, d2], diffdates=[d1, d2])
    assert dates.dates == ["19991201", "20021122", "19991201-20021122"]


def test_validate_zranges():
    """Test zonation.zranges validation."""

    zr = _configparser._Zranges(zranges=[{"Z1": [1, 5]}, {"Z2": [6, 10]}])
    assert zr.zranges == [{"Z1": [1, 5]}, {"Z2": [6, 10]}]

    with pytest.raises(ValidationError, match="first layer number is larger than"):
        zr = _configparser._Zranges(zranges=[{"Z1": [1, 5]}, {"Z2": [10, 6]}])

    with pytest.raises(ValidationError, match="should be a valid integer"):
        zr = _configparser._Zranges(zranges=[{"Z1": ["one", 5]}, {"Z2": [6, 9]}])


def test_validate_superranges():
    """Test zonation.superranges validation."""

    zr = _configparser._Zranges(zranges=[{"Z1": [1, 5]}, {"Z2": [6, 10]}])
    assert zr.zranges == [{"Z1": [1, 5]}, {"Z2": [6, 10]}]

    superr = _configparser._SuperRanges(superranges=[{"ZXX": ["Z1", "Z2"]}])
    assert superr.superranges == [{"ZXX": ["Z1", "Z2"]}]


def test_validate_superranges_keys():
    """Test that keys in zranges are present in superranges."""
    print("test_validate_superranges_keys")
    with pytest.raises(
        ValidationError, match="Some values in superranges are not present in zranges"
    ):
        _configparser._XValidateZrangesSuperranges(
            zranges=[{"Z1": (1, 5)}, {"Z2": (6, 10)}],
            superranges=[{"Z1+3": ["Z1", "ZNOT"]}],
        )
    model = _configparser._XValidateZrangesSuperranges(
        zranges=[{"Z1": (1, 5)}, {"Z2": (6, 10)}],
        superranges=[{"Z1+3": ["Z1", "Z2"]}],
    )
    assert model.superranges == [{"Z1+3": ["Z1", "Z2"]}]


def test_parse_yaml_hcthickness_case1(tmp_path):
    """Test case1 setup for HC thickness map"""

    YAMLCONTENT = textwrap.dedent("""
    title: Reek

    input:
      eclroot: tests/data/reek/REEK
      dates:
        - 19991201
        - 20021101
        - 20021111 # this does not exist but script will ignore with warning
        - 20010101-19991201 # difference map

    zonation:
      # zranges will normally be the Zone parameter, defined as K range cells
      zranges:
        - Z1: [1, 5]
        - Z2: [6, 10]
        - Z3: [11, 14]

      # superranges are collections of zones, and not restricted to be
      # in order (e.g. one can skip certain zones):
      superranges:
        - Z1+3: [Z1, Z3]

    computesettings:
      # choose oil, gas or both
      mode: oil
      critmode: No
      shc_interval: [0.1, 1] # saturation interv
      method: use_poro
      zone: Yes
      all: Yes

    # map definition
    mapsettings:
      xori: 458300
      xinc: 50
      yori: 5928800
      yinc: 50
      ncol: 200
      nrow: 200

    output:
      mapfolder: /tmp
      plotfolder: /tmp

    """)

    yamlfile = tmp_path / "config_hc_case1.yml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_hcthickness_config(yamlfile)
    assert config.title == "Reek"
    assert config.input.eclroot == "tests/data/reek/REEK"
    assert config.input.dates == [
        "19991201",
        "20021101",
        "20021111",
        "20010101-19991201",
    ]
    assert config.input.grid == "tests/data/reek/REEK.EGRID"
    assert config.zonation is not None
    assert config.zonation.zranges == [
        {"Z1": [1, 5]},
        {"Z2": [6, 10]},
        {"Z3": [11, 14]},
    ]
    assert config.zonation.superranges == [{"Z1+3": ["Z1", "Z3"]}]
    assert config.mapsettings.xori is None  # post-processed to None

    assert config.mapsettings.regsurf.xori == 458300

    assert config.output.mapfolder == "/tmp"
    assert config.script == "hcthickness"

    # make invalid superranges
    yamlfile = tmp_path / "config_hc_case1_shall_fail.yml"
    NEWYAML = YAMLCONTENT.replace("[Z1, Z3]", "[Z1, ZNOT]")
    yamlfile.write_text(NEWYAML)
    with pytest.raises(
        ValidationError, match="Some values in superranges are not present"
    ):
        config = _configparser.parse_validate_hcthickness_config(yamlfile)

    # make invalid hc_interval
    yamlfile = tmp_path / "config_hc_case1_shall_fail2.yml"
    NEWYAML = YAMLCONTENT.replace("[0.1, 1]", "[-0.1, 1.2]")
    yamlfile.write_text(NEWYAML)
    with pytest.raises(ValidationError, match="Invalid shc_interval format"):
        config = _configparser.parse_validate_hcthickness_config(yamlfile)


def test_parse_yaml_hcthickness_case2(tmp_path):
    """Test case2 setup for HC thickness map, using a ROFF file for the grid"""

    YAMLCONTENT = textwrap.dedent("""

    title: Reek

    # Using PORV as method, and a rotated template map in mapsettings
    # Reproduce hc_thickness1g.yml

    input:
      eclroot: tests/data/reek/REEK
      grid: tests/data/reek/reek_grid_fromegrid.roff
      dates:
        - 19991201

    zonation:
      zranges:
        - Z1: [1, 5]

    mapsettings:
      templatefile: tests/data/reek/reek_hcmap_rotated.gri

    computesettings:
      # choose oil, gas or both
      mode: both                                  # <<
      critmode: No
      shc_interval: [0.1, 1] # saturation interv
      method: use_porv
      zone: Yes
      all: Yes
      unit: m   # e.g. 'feet'; if missing, default is 'm' for metric

    output:
      tag: hcdataio1b
      mapfolder: fmu-dataio
    """)

    yamlfile = tmp_path / "config_hc_case2.yml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_hcthickness_config(yamlfile)
    assert config.title == "Reek"
    assert config.script == "hcthickness"
    assert config.input.eclroot == "tests/data/reek/REEK"
    assert config.input.grid == "tests/data/reek/reek_grid_fromegrid.roff"
    assert config.input.dates == ["19991201"]
    assert config.zonation is not None
    assert config.zonation.zranges == [{"Z1": [1, 5]}]
    assert config.zonation.superranges == []
    assert isinstance(config.mapsettings.regsurf, xtgeo.RegularSurface)
    assert config.computesettings.unit == "m"
    assert config.output.mapfolder == "fmu-dataio"


def test_parse_yaml_hcthickness_case3(tmp_path):
    """Test case3 setup for HC thickness map, using !include, filter, etc"""

    YAMLCONTENT = textwrap.dedent("""

    title: Reek
    # Case with external config files, e.g. a global config!
    # Reuse dates data from global config

    input:
      eclroot: tests/data/reek/REEK
      dates: !include_from tests/yaml/global_config3a.yml::global.DATES
      # diffdates: !include_from tests/yaml/global_config3a.yml::global.DIFFDATES

    # For filters, there are properties defined at the same grid layout as the grid read in input
    # If several filters, they will be cumulative
    # filters:
    #   - name: PORO
    #     source: $eclroot.INIT
    #     intvrange: [0.2, 1.0] # Filter for a continuous will be an interval
    #   - name: FACIES
    #     discrete: Yes
    #     source: tests/data/reek/reek_sim_facies2.roff
    #     discrange: [1] # Filter for a discrete will be spesic number (or codename?)
    #   - name: Zone
    #     discrete: Yes
    #     source: tests/data/reek/reek_sim_zone.roff
    #     discrange: [1, 3] # Filter for a discrete will be spesic number

    computesettings:
      mode: oil
      critmode: No
      shc_interval: [0.001, 1] # saturation interval
      method: use_poro
      zone: no
      all: yes

    mapsettings:
      xori: 458300
      xinc: 50
      yori: 5928800
      yinc: 50
      ncol: 200
      nrow: 200

    # plotsettings:
    #   faultpolygons: tests/data/reek/top_upper_reek_faultpoly.xyz
    #   valuerange:
    #     [0, 10] # value range min/max (values above below
    #     # will be truncated in plot!)
    #   diffvaluerange: [-3, 0] # value range min/max for date diffs
    #   xlabelrotation: 25 # Rotate the X axis labels (if they may overlap)
    #   colortable:
    #     rainbow # colours jet/rainbow/seismic/gnuplot/gnuplot2/...
    #     # OR from RMS colour file
    #   # individual settings will override general plot settings!
    #   Z1:
    #     valuerange: [0, 8]
    #     colortable: gnuplot2
    #   Z2:
    #     valuerange: [0, 5]

    output:
      mapfolder: /tmp
      plotfolder: /tmp
      tag: hc3b
      prefix: myzone1+3

    """)

    yamlfile = tmp_path / "config_hc_case3.yml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_hcthickness_config(yamlfile)
    assert config.title == "Reek"
