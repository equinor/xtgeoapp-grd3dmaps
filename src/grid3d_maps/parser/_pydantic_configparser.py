import datetime
import logging
import os
import pathlib
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import xtgeo
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


class _BaseConfig(BaseModel):
    """Main levels in the configuration file."""

    version: int = 1
    script: Literal["hcthickness", "averagemap"] = Field(
        default="hcthickness", description="Script name to run"
    )
    title: Optional[str] = Field(default=None, description="Title of the configuration")
    input: Optional[Dict[str, Any]] = Field(default=None, description="Input data")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Filter data")
    zonation: Optional[Dict[str, Any]] = Field(
        default=None, description="Zonation data"
    )
    computesettings: Optional[Dict[str, Any]] = Field(
        default=None, description="Compute settings"
    )
    mapsettings: Optional[Dict[str, Any]] = Field(
        default=None, description="Map settings"
    )
    plotsettings: Optional[Dict[str, Any]] = Field(
        default=None, description="Plot settings"
    )
    output: Optional[Dict[str, Any]] = Field(
        default=None, description="Output settings"
    )


# ======================================================================================
# The <input> section
# ======================================================================================


# class Property(BaseModel):
#     name: str
#     source: Optional[str] = None
#     dates: List[int] = Field(default_factory=list)
#     diffdates: List[int] = Field(default_factory=list)


class _Dates(BaseModel):
    """Dates can have multiple input formats.

    Result is a list of strings, where each string is a date in format 'YYYYMMDD' or
    a 'diffdate' on form 'YYYYMMDD-YYYYMMDD'.
    """

    dates: List[Union[int, str, datetime.date, Any]] = Field(
        default_factory=list, description="Dates"
    )
    diffdates: List[Union[str, Any]] = Field(
        default_factory=list, description="Differerence dates"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("dates", "diffdates", mode="before")
    @classmethod
    def validate_dates(cls, values):
        logger.debug(f"Validating dates: {values}")
        return cls._process_dates(values)

    @classmethod
    def _process_dates(cls, values):
        svalues = []  # convert to string for all dates
        for v in values:
            if isinstance(v, int):
                if not re.match(r"^\d{8}$", str(v)):
                    raise ValueError(f"Invalid date format: {v}")
                svalues.append(str(v))
            elif isinstance(v, datetime.date):
                svalues.append(v.strftime("%Y%m%d"))
            elif isinstance(v, str):
                if not re.match(r"^\d{8}-\d{8}$", v):
                    raise ValueError(f"Invalid date format: {v}")
                svalues.append(v)
            elif isinstance(v, list):
                svalues.extend(cls._process_dates(v))  # recursive call
            else:
                raise ValueError(f"Invalid date type: {v}")
        return svalues

    @model_validator(mode="after")
    def validate_process_diffdates(self):
        if self.diffdates:
            v = self.diffdates
            if isinstance(v, list) and len(v) == 2:
                d1 = v[0]
                d2 = v[1]

                d1 = str(d1) if isinstance(d1, (int, str)) else d1.strftime("%Y%m%d")
                d2 = str(d2) if isinstance(d2, (int, str)) else d2.strftime("%Y%m%d")
                self.dates.append(f"{d1}-{d2}")
            elif isinstance(v, str):
                self.dates.append(v)
            else:
                raise ValueError(f"Invalid diffdate format: {v}")
        return self


class _Input(BaseModel):
    eclroot: Optional[str] = Field(
        default=None, description="Root path for ECLIPSE files"
    )
    grid: str = Field(
        default="$eclroot.EGRID", description="Path to ECLIPSE or ROFF grid file, "
    )
    dates: List[Union[int, str, datetime.date, Any]]
    diffdates: List[Union[str, Any]]
    # properties: Optional[List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("dates", mode="before")
    @classmethod
    def validate_dates(cls, values):
        logger.debug("Validating dates...")
        return _Dates(dates=values).dates

    @model_validator(mode="after")
    def validate_set_grid(self):
        logger.debug("Validating set grid...")
        if self.eclroot and self.grid.startswith("$eclroot"):
            self.grid = self.grid.replace("$eclroot", self.eclroot)
        return self


# ======================================================================================
# The <zonation> section
# ======================================================================================


class _Zranges(BaseModel):
    """Validation for <zonation.zranges>, on format Z1: [1, 5].

    The keys are the zone names, and the values are lists of two integers, where the
    first is the start of the zone, and the second is the end of the zone. Hence, the
    first integer must be less than the second.
    """

    zranges: List[Dict[str, Tuple[int, int]]]

    @field_validator("zranges")
    @classmethod
    def validate_zranges(cls, values):
        logger.debug(f"Validating zranges: {values}")
        result = []
        for entry in values:
            for _, v in entry.items():
                if not isinstance(v, tuple) or len(v) != 2:
                    raise ValueError(f"Invalid zrange format (1): {v}")
                if not all(isinstance(i, int) for i in v):
                    raise ValueError(f"Invalid zrange format: {v}")
                if v[0] >= v[1]:
                    raise ValueError(
                        "Invalid zrange format, first layer number is larger "
                        f"than the second: {v}"
                    )
            result.append({k: list(v) for k, v in entry.items()})
        return result


class _SuperRanges(BaseModel):
    """Validation for <zonation.superranges>, on format SOME: [Z1, Z3].

    The values are the zone names from zonation.zranges, and the keys are free-form.
    """

    superranges: List[Dict[str, List[str]]] = Field(default_factory=list)
    zranges: List[Dict[str, Tuple[int, int]]] = Field(default_factory=list)

    @field_validator("superranges")
    @classmethod
    def validate_superranges(cls, values):
        logger.debug(f"Validating superranges: {values}")
        for entry in values:
            for key, value in entry.items():
                if not isinstance(key, str) or not all(
                    isinstance(item, str) for item in value
                ):
                    raise ValueError(f"Invalid superrange format: {entry}")
        return values


class _XValidateZrangesSuperranges(BaseModel):
    zranges: List[Dict[str, Tuple[int, int]]] = Field(default_factory=list)
    superranges: List[Dict[str, List[str]]] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_superranges_keys(self):
        sr = self.get("superranges")
        zr = self.get("zranges")
        logger.debug("Validating superranges_keys %s vs zranges %s:", sr, zr)
        zranges_keys = [list(item.keys())[0] for item in zr]
        svalues = [value for item in sr for value in item.values()]
        # # Flatten the list of lists and make a set of unique values
        superranges_values = {val for sublist in svalues for val in sublist}
        if not superranges_values.issubset(zranges_keys):
            raise ValueError(
                "Some values in superranges are not present in zranges: "
                f"{zranges_keys} - {superranges_values}"
            )
        logger.debug("Validating superranges_keys done.")
        return self


class _Zonation(BaseModel):
    """Validation for top level entry <zonation>."""

    zranges: List[Dict[str, List[int]]] = Field(default_factory=list)
    superranges: List[Dict[str, List[str]]] = Field(default_factory=list)

    @field_validator("zranges", mode="after")
    @classmethod
    def validate_zranges(cls, values):
        logger.debug("Validating zranges...")
        return _Zranges(zranges=values).zranges

    @field_validator("superranges", mode="after")
    @classmethod
    def validate_superranges(cls, svalues):
        logger.debug("Validating superranges...")
        return _SuperRanges(superranges=svalues).superranges

    @model_validator(mode="after")
    def validate_superranges_keys(self):
        logger.debug("Validating superranges_keys... (cross validation)")
        _XValidateZrangesSuperranges(zranges=self.zranges, superranges=self.superranges)
        return self


# ======================================================================================
# The <filter> section
# ======================================================================================

# class Filter(BaseModel):
#     name: str
#     discrete: bool
#     source: str
#     discrange: List[int]

# ======================================================================================
# The <computesettings> section
# ======================================================================================


class _ComputeSettings(BaseModel):
    zone: bool = Field(default=False, description="If True, compute per zone")
    all: bool = Field(default=True)
    mask_zeros: bool = Field(default=True)


class _ComputeSettingsHCThickness(_ComputeSettings):
    """Additional settings for HCthickness computation."""

    mode: Literal["oil", "gas", "both"] = "oil"
    critmode: bool = False
    shc_interval: Tuple[float, float] = (0.0, 1)
    method: Literal["use_poro", "use_porv"] = "use_poro"
    unit: Literal["m", "feet"] = Field(default="m", description="Unit for calculations")

    @field_validator("shc_interval", mode="after")
    @classmethod
    def validate_shc_interval(cls, values):
        logger.debug(f"Validating shc_interval: {values}")
        if values is not None:
            if not isinstance(values, (tuple, list)) or len(values) != 2:
                raise ValueError(f"Invalid shc_interval format: {values}")
            if not all(isinstance(i, (int, float)) for i in values):
                raise ValueError(f"Invalid shc_interval format: {values}")
            if values[0] >= values[1] or values[0] < 0 or values[1] > 1:
                logger.debug(f"Invalid shc_interval format: {values} -> Error")
                raise ValueError(
                    "Invalid shc_interval format, values must increase "
                    f"and range must be in [0, 1]: {values}"
                )
        return values


# ======================================================================================
# The <mapsettings> section
# ======================================================================================


class _MapSettings(BaseModel):
    """Either a template file or detailed map settings.

    The special here is that the result shall be an instance of xtgeo RegularSurface.
    TODO: if mapsettings input is missing?
    """

    templatefile: Optional[str] = None
    xori: Optional[float] = None
    xinc: Optional[float] = None
    yori: Optional[float] = None
    yinc: Optional[float] = None
    ncol: Optional[int] = None
    nrow: Optional[int] = None
    regsurf: Optional[xtgeo.RegularSurface] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("templatefile", mode="after")
    @classmethod
    def validate_templatefile(cls, value):
        logger.debug(f"Validating templatefile (file path): {value}")
        if value is not None and not os.path.exists(value):
            raise ValueError(f"Template file does not exist: {value}")
        return value

    @field_validator("xori", "yori", "xinc", "yinc", mode="after")
    @classmethod
    def validate_mapsettings(cls, value):
        logger.debug(f"Validating map setting...: {value}")
        if value is not None and value < 0:
            raise ValueError(f"Value must be greater or equal 0.0, got: {value}")
        return value

    @field_validator("ncol", "nrow", mode="after")
    @classmethod
    def validate_mapnodes(cls, value):
        logger.debug(f"Validating map ncol/nrow...: {value}")
        if value is not None and value < 3:
            raise ValueError(f"Value must be greater or equal 3, got: {value}")
        return value

    @model_validator(mode="after")
    def create_map(self):
        logger.debug("Creating map...")
        if self.templatefile is not None:
            logger.debug("Creating map from template...")
            self.regsurf = xtgeo.surface_from_file(self.templatefile)
        else:
            logger.debug("Creating map from scratch...")
            self.regsurf = xtgeo.RegularSurface(
                xori=self.xori,
                xinc=self.xinc,
                yori=self.yori,
                yinc=self.yinc,
                ncol=self.ncol,
                nrow=self.nrow,
            )

        self.ncol = None
        self.nrow = None
        self.xori = None
        self.xinc = None
        self.yori = None
        self.yinc = None
        self.templatefile = None

        return self


# ======================================================================================
# The <output> section
# ======================================================================================


class Output(BaseModel):
    tag: str = Field(default="", description="Tag name for output files")
    mapfolder: str = Field(default="dataio", description="Folder path for maps")
    plotfolder: str = Field(default="", description="Folder path for plots")
    prefix: str = Field(default="", description="Prefix for output files")


# ======================================================================================
# HCthicknessMapConfig
# ======================================================================================


class HCthicknessMapConfig(_BaseConfig):
    input: _Input = Field(default_factory=_Input)
    script: Literal["hcthickness"] = "hcthickness"
    version: int = 1
    zonation: Optional[_Zonation] = None
    computesettings: Optional[_ComputeSettingsHCThickness] = None
    mapsettings: Optional[_MapSettings] = None
    output: Output = Field(default_factory=Output)


class _IncludeFromLoader:
    """Allow to include data from other files with: !include_from file.yaml::key"""

    def __init__(self, base_path):
        self.base_path = base_path

    def __call__(self, loader, node):
        file_path, key = loader.construct_scalar(node).split("::")
        full_path = os.path.join(self.base_path, file_path)
        with open(full_path, "r") as f:
            data = YAML().load(f)
        for part in key.split("."):
            data = data[part]
        return data


def parse_validate_hcthickness_config(
    filename: str | pathlib.Path,
) -> HCthicknessMapConfig:
    yaml = YAML()
    yaml.Constructor.add_constructor("!include_from", _IncludeFromLoader(base_path="."))
    with open(filename, "r") as stream:
        yaml_data = yaml.load(stream)
    return HCthicknessMapConfig(**yaml_data)
