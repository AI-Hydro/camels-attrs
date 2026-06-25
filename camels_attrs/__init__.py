"""
CAMELS Attrs Extractor

A Python package for extracting CAMELS-like catchment attributes
and hydrometeorological timeseries data for any USGS gauge site 
in the United States.

Author: Mohammad Galib
Email: mgalib@purdue.edu
"""

__version__ = "1.0.3"
__author__ = "Mohammad Galib"
__email__ = "mgalib@purdue.edu"

from .timeseries import (
    calculate_pet_hargreaves,
    calculate_forcing_statistics,
    calculate_water_balance,
    fetch_forcing_data,
    get_monthly_summary,
)


_LAZY_EXPORTS = {
    "CamelsExtractor": (".extractor", "CamelsExtractor"),
    "extract_multiple_gauges": (".extractor", "extract_multiple_gauges"),
    "create_comprehensive_watershed_map": (
        ".visualization",
        "create_comprehensive_watershed_map",
    ),
    "plot_attributes_comparison": (".multi_gauge_viz", "plot_attributes_comparison"),
    "create_multi_gauge_comparison": (".multi_gauge_viz", "create_multi_gauge_comparison"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value

__all__ = [
    "CamelsExtractor",
    "extract_multiple_gauges",
    "fetch_forcing_data",
    "calculate_pet_hargreaves",
    "get_monthly_summary",
    "calculate_water_balance",
    "calculate_forcing_statistics",
    "create_comprehensive_watershed_map",
    "plot_attributes_comparison",
    "create_multi_gauge_comparison",
]
