"""Testing suite avg3, using dataio output."""

import textwrap
from pathlib import Path

from grid3d_maps.avghc_v2 import _configparser


def test_parse_yaml_hcthickness_minimal(tmp_path):
    """Test minimum setup for HC thickness map"""

    YAMLCONTENT = textwrap.dedent("""
    # as minimum, only input and script is required in addition to version
    version: 2
    script: hcthickness

    input:
      eclroot: tests/data/reek/REEK
      dates:
        - 19991201
    """)

    yamlfile = tmp_path / "config.yaml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_config(yamlfile)
    assert config.title == "Name missing"
    assert config.input.eclroot == "tests/data/reek/REEK"
    assert config.input.dates == [19991201]
    assert config.zonation is None
    assert config.computesettings is None


def test_parse_yaml1(tmp_path):
    """Test HC thickness map piped through dataio"""

    YAMLCONTENT = textwrap.dedent("""
    title: Reek
    version: 2
    input:
      eclroot: tests/data/reek/REEK
      dates:
        - 19991201

    zonation:
      zranges:
        - Z1: [1, 5]
        - Z2: [6, 10]
        - Z3: [11, 14]

    computesettings:
      mode: oil
      critmode: No
      shc_interval: [0.1, 1] # saturation interval
      method: use_porv
      zone: Yes
      all: Yes
    """)

    yamlfile = tmp_path / "config.yaml"
    yamlfile.write_text(YAMLCONTENT)
    config = _configparser.parse_validate_config(yamlfile)
    assert config.title == "Reek"
    assert config.input.eclroot == "tests/data/reek/REEK"
    assert config.input.dates == [19991201]
    assert config.zonation.zranges == [
        {"Z1": [1, 5]},
        {"Z2": [6, 10]},
        {"Z3": [11, 14]},
    ]
    assert config.computesettings.mode == "oil"
    assert config.computesettings.critmode == "No"
    assert config.computesettings.shc_interval == [0.1, 1]
    assert config.computesettings.method == "use_porv"
    assert config.computesettings.zone is True
    assert config.computesettings.all is True
    assert config.output.tag == ""
    assert config.output.mapfolder == "dataio"
    assert config.output.plotfolder == ""
    assert config.output.prefix == ""
    assert config.output.tag == ""
    assert config.output.mapfolder == "dataio"
    assert config.output.plotfolder == ""
