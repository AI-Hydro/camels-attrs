# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **`q5` / `q95` follow CAMELS (defect P2-D0).** `extract_hydrological_signatures` set `q5`
  to the 95th percentile of daily flow and `q95` to the 5th, the opposite of CAMELS (Addor
  et al. 2017, Table 3: `q5` = 5% flow quantile, low flow; `q95` = 95% flow quantile, high
  flow). Values returned by earlier versions (including 1.0.3) have the two keys swapped.
  New helper `compute_flow_quantiles_camels`; test `tests/test_flow_quantiles.py`.

## [0.1.0] - 2025-10-07

### Added
- Initial release of camels-attrs package
- **Static Catchment Attributes:**
  - Watershed delineation using NLDI API
  - Topographic attributes extraction from USGS 3DEP
  - Climate indices calculation from GridMET
  - Soil characteristics from gNATSGO and POLARIS
  - Vegetation metrics from MODIS and NLCD
  - Geological properties from GLiM and GLHYMPS (optional)
  - Hydrological signatures from USGS NWIS
- **Hydrometeorological Timeseries Data:**
  - Daily forcing data from GridMET (precipitation, temperature, solar radiation, wind, humidity)
  - PET calculations (GridMET and Hargreaves-Samani methods)
  - Monthly aggregation functions
  - Water balance calculations
  - Forcing statistics computation
- Python API via `CamelsExtractor` class
- Command-line interface via `camels-extract` command with timeseries support
- Support for single and multiple gauge processing
- Comprehensive documentation and examples

### Features
- 70+ catchment attributes following CAMELS methodology
- Daily hydrometeorological forcing data extraction
- Graceful handling of missing data with default values
- Customizable date ranges for climate and hydrology data
- CSV and JSON export formats
- Batch processing capability
- Optional monthly aggregations
- Separate timeseries extraction mode

### Dependencies
- Core: numpy, pandas, geopandas, xarray, rioxarray
- HyRiver ecosystem: pynhd, py3dep, pygridmet, pygeohydro
- Remote sensing: pystac-client, planetary-computer
- Optional: pygeoglim (for geological attributes)

### Known Issues
- Large watersheds may require significant processing time
- Some remote sensing products may timeout for complex watersheds
- pygeoglim must be installed separately if not available on PyPI

## [Unreleased]

### Planned
- Caching mechanism for downloaded geospatial data
- Parallel processing for multiple gauges
- Validation against original CAMELS dataset
- Additional vegetation indices (EVI, SAVI)
- Snow cover attributes from MODIS
- Landform classification attributes
- Support for custom attribute plugins
