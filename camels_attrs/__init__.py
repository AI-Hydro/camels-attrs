"""
CAMELS Attrs Extractor

A Python package for extracting CAMELS-like catchment attributes
and hydrometeorological timeseries data for any USGS gauge site 
in the United States.

Author: Mohammad Galib
Email: mgalib@purdue.edu
"""

__version__ = "1.0.2"
__author__ = "Mohammad Galib"
__email__ = "mgalib@purdue.edu"

from .extractor import CamelsExtractor, extract_multiple_gauges
from .timeseries import (
    fetch_forcing_data,
    calculate_pet_hargreaves,
    get_monthly_summary,
    calculate_water_balance,
    calculate_forcing_statistics
)
from .visualization import create_comprehensive_watershed_map
from .multi_gauge_viz import plot_attributes_comparison, create_multi_gauge_comparison

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
