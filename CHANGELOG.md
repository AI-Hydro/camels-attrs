# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-10-22

### BREAKING-VALUE: `slope_fdc` and `baseflow_index` change definition (Science Wave 3, PR-5)

Same keys, different numbers. Do not compare 1.x and 2.0 values of these two attributes, and re-run anything that cached them.

- **`slope_fdc` is now the CAMELS-US v1.2 file definition**, `(Q66 - Q33) / (mean(q) * 0.33)`: non-exceedance (R type 7) percentiles, zero-flow days kept, defined only when `mean(q) > 0` and >= 100 values. It reproduces the distributed `camels_hydro.txt` column to <= 1e-6 relative on 01013500 and 01031500 (observed 8.8e-9 and 2.3e-7). 1.x returned the log-space value `(ln Q33exc - ln Q66exc) / 0.33` (zeros dropped), which is 76% (01013500) and 124% (01031500) above the file value. The old value is kept as the new key **`slope_fdc_sawicz2011`**; its unit is `log-slope`, `slope_fdc` is now dimensionless.
  Provenance: "CAMELS-US v1.2 distributed definition. Reproduces the file at <=2.3e-7 relative on 01013500 and 01031500, and 9.7e-5 on 01516500. Its zero-structure prediction holds on all 671 basins. Source: naddor/camels@88e7a0d2d2 hydro/hydro_signatures.R:97. It contradicts the log-space definition in Addor et al. 2017 (text and Table 3). No erratum or release note found. Not proven to be the script that produced the file." Do not read this as "the CAMELS definition" for other CAMELS datasets (CAMELS-GB used the log `sfdc_sawicz_2011`).
- **`baseflow_index` uses a faithful Ladson et al. (2013) Lyne-Hollick port** (`camels_attrs/baseflow.py`: alpha 0.925, forward-backward-forward, 30-day reflection at both ends, quick flow subtracted only where positive, baseflow clipped at zero, NaN gaps are segment boundaries, > 30 days required, `WarmupBiasWarning` below 365 days). The 1.x filter clamped `0 <= b <= q` at every step and fed the clamped value back; it read low against CAMELS. New values reproduce the file to <= 1e-5 relative (observed 1.1e-7 on 01013500, 1.9e-6 on 01031500). The kernel is a port of `aihydro_watershed.signatures.baseflow.lyne_hollick_ladson2013` (watershed 0.2.0), pinned by a test to that kernel's documented outputs; camels-attrs does not import any aihydro package. `_lyne_hollick_baseflow` is kept as a thin wrapper over the new kernel.
- **`zero_q_freq` counts days with `q <= 0`** (was `q == 0`), as CAMELS `compute_no_flow`. `high_q_freq` / `low_q_freq` were already days/yr (`> 9 * median`, `<= 0.2 * mean`, over available days, x 365.25); `HYDRO_SIGNATURE_UNITS` said `events/yr`, now `days/yr`.
- New `camels_attrs.hydrology.SIGNATURE_DEFINITIONS` (formula, quantile type, zero handling, source, evidence) and `compute_slope_fdc_camels`, `compute_baseflow_index`.

### Tests
- `tests/test_signature_definitions.py`: slope_fdc within 1e-6 and baseflow_index within 1e-5 of CAMELS-US v1.2 on 01013500 and 01031500 (USGS fixtures under `tests/fixtures/signature_definitions/`, provenance in its README), kernel pinned to watershed 0.2.0 outputs, extractor end-to-end offline (days/yr, fraction definitions).
- `tests/test_hydrology.py`: the 7-point filter test now uses a 120-day series (the kernel needs > 30 days).

### Known limitation (not fixed here)
- Climate extraction calls `pygridmet` / `pydaymet` without response validation (no duplicate-timestamp, gap or year-coverage check) and outside the aihydro-data layer's calendar and cache protections. The data-layer fix lives in aihydro-data 0.2.5; camels-attrs is not yet routed through it.

## [1.0.4] - 2026-10-17

### Changed
- **USGS streamflow now comes from the Water Data API, not hydrofunctions/NWIS `dv`
  (Wave U, U3c).** New `camels_attrs/usgs_daily.py` is a minimal stdlib/`requests` client for
  `https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items` (parameter 00060,
  statistic 00003): `rel=next` paging with https + host checks, redirects never followed,
  optional `API_USGS_PAT` sent only as `X-Api-Key` and never logged. It deliberately does
  not import aihydro-data (camels-attrs is the independent reference).
- Discharge is converted with the exact factor 0.028316846592 m^3/ft^3 (previously the
  rounded 0.0283168, a ~7e-8 relative difference); other units are refused.
- `fetch_streamflow_data` raises `UsgsDailyError` instead of printing and returning `None`;
  an empty result, the `-999999` sentinel, non-finite/unparseable values, unknown
  `approval_status` or units are explicit errors. `fetch_streamflow_data` now returns a
  DataFrame (`q_cms`, `q_native`, `approval_status` = Approved / Provisional).
- The hydrology dict now carries `hydro_status` (`ok` | `refused` | `insufficient_data` | `error`),
  `hydro_reason` (the `UsgsDailyError` code, `LT_365_DAYS`, or `COMPUTE_ERROR: <ExceptionType>` for status `error`),
  `hydro_provisional_fraction` and `hydro_null_dropped`. The extractor sets
  `_status["hydrology"]=False` and adds a `_warnings` entry whenever status is not `ok`
  (previously an all-NaN result was reported as successfully extracted).

- Gauge name/lat/lon in `delineate_watershed_for_gauge` now come from the Water Data API
  `monitoring-locations` collection (`usgs_daily.fetch_monitoring_location`) instead of
  pygeohydro `NWIS().get_info` (legacy waterservices `/site`, decommissioned 2027-02-22);
  metadata gains `gauge_datum` (`original_horizontal_datum`; the API states no CRS).

### Removed
- `hydrofunctions` dependency (pygeohydro is kept for its other uses).

### Fixed
- `logger` was undefined in `hydrology.py`, so any error path raised `NameError`.
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
