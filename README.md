# CAMELS Attrs
![CAMELS Attrs](assets/thumbnail.png)
[![PyPI version](https://badge.fury.io/py/camels-attrs.svg)](https://pypi.org/project/camels-attrs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/camels-attrs)](https://pepy.tech/project/camels-attrs)

A Python package for extracting CAMELS-like catchment attributes for any USGS gauge site in the United States.

## Overview

This package provides a simple, reproducible way to extract comprehensive catchment attributes following the CAMELS (Catchment Attributes and Meteorology for Large-sample Studies) methodology. It automates the extraction of topographic, climatic, soil, vegetation, geological, and hydrological characteristics for any USGS-monitored watershed.

Additionally, it can fetch daily hydrometeorological forcing data (precipitation, temperature, solar radiation, wind speed, humidity) from the GridMET dataset for user-defined date ranges. The package also includes a new feature to create a comprehensive multi-panel watershed map that visualizes key attributes and spatial context.

## Features

### Static Catchment Attributes

- **Watershed Delineation**: Automated watershed boundary extraction using NLDI
- **Topographic Attributes**: Elevation, slope, and drainage area from 3DEP DEM
- **Climate Indices**: Precipitation, temperature, aridity, seasonality from GridMET
- **Soil Characteristics**: Texture, porosity, conductivity from gNATSGO and POLARIS
- **Vegetation Metrics**: LAI, NDVI/GVF, land cover from MODIS and NLCD
- **Geological Properties**: Lithology and permeability from GLiM and GLHYMPS
- **Hydrological Signatures**: Flow statistics, baseflow index, event characteristics

### Hydrometeorological Timeseries Data

- **Daily Forcing Data**: Precipitation, temperature (min/max/avg), solar radiation, wind speed, humidity
- **PET Calculations**: GridMET PET and Hargreaves-Samani PET
- **Custom Date Ranges**: Fetch data for any USGS gauge and time period
- **Quality Control**: Automatic handling of missing data

### Watershed Visualization

- **Multi-Panel Map Creation**: Comprehensive watershed maps with USGS gauge location, elevation, land cover, soil characteristics, and streamflow data
- **Publication-Ready Figures**: High-quality plots with proper legends and coordinate reference systems

## Installation

```bash
pip install camels-attrs
```

## Quick Start

### Extract Static Attributes

```python
from camels_attrs import extract_static_attrs

# Extract attributes for a USGS gauge
result = extract_static_attrs(
    usgs_id='01013500',
    output_dir='output'
)
```

### Get Forcing Data

```python
from camels_attrs import extract_forcing_data

# Fetch daily forcing data
forcing = extract_forcing_data(
    usgs_id='01013500',
    start_date='2010-01-01',
    end_date='2020-12-31'
)
```

### Create Watershed Map

```python
from camels_attrs import create_watershed_map

# Create a comprehensive watershed map
create_watershed_map(
    usgs_id='01013500',
    output_file='watershed_map.png'
)
```

## Extracted Attributes

### Topographic (16 attributes)

- `gauge_lat`, `gauge_lon`
- `elev_mean`, `elev_min`, `elev_max`
- `slope_mean`, `area_gages2`
- Aspect statistics (N, E, S, W)

### Climate (18 attributes)

- `p_mean`, `pet_mean`, `aridity`
- `p_seasonality`, `frac_snow`
- Temperature statistics
- `high_prec_freq`, `high_prec_dur`
- `low_prec_freq`, `low_prec_dur`

### Soil (24 attributes)

- Texture fractions (sand, silt, clay)
- `soil_depth_pelletier`, `soil_depth_statsgo`
- `soil_porosity`, `soil_conductivity`
- Water content characteristics
- Bulk density, organic carbon

### Vegetation (15 attributes)

- `lai_max`, `lai_diff`
- `gvf_max`, `gvf_diff`
- `ndvi_max`, `ndvi_diff`
- Land cover fractions (forest, shrub, grass, wetland, etc.)
- `dom_land_cover`, `dom_land_cover_frac`

### Geology (6 attributes)

- Lithology fractions (siliciclastic, carbonate, etc.)
- `geol_porosity`, `geol_permeability`

### Hydrology (15 attributes)

- `q_mean`, `runoff_ratio`
- `baseflow_index`, `stream_elas`
- `slope_fdc`, `flow_variability`
- `high_q_freq`, `high_q_dur`
- `low_q_freq`, `low_q_dur`
- `zero_q_freq`
- `hfd_mean`, `half_flow_date_std`

## Requirements

- Python >=3.8
- numpy, pandas, geopandas
- xarray, rioxarray, rasterio
- pynhd, py3dep, pygridmet, pygeohydro
- pygeoglim, planetary-computer
- scipy, matplotlib

See `pyproject.toml` for complete dependency list.

## Data Sources

- **Watershed boundaries**: USGS NLDI
- **Topography**: USGS 3DEP
- **Climate**: GridMET
- **Soil**: gNATSGO, POLARIS
- **Vegetation**: MODIS (LAI, NDVI), NLCD
- **Geology**: GLiM, GLHYMPS
- **Streamflow**: USGS NWIS

## References

This package implements the methodology described in:

- Newman et al. (2015). Development of a large-sample watershed-scale hydrometeorological dataset. NCAR Technical Note
- Addor et al. (2017). The CAMELS data set: catchment attributes and meteorology for large-sample studies. Hydrology and Earth System Sciences

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Citation

If you use this package in your research, please cite:

```
Galib, M., & Merwade, V. (2025). camels-attrs: A Python Package for Extracting CAMELS-like Catchment Attributes (v1.0.1). Zenodo. https://doi.org/10.5281/zenodo.17315038
```

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17315038.svg)](https://doi.org/10.5281/zenodo.17315038)

## Contact

Mohammad Galib - mgalib@purdue.edu  
Venkatesh Merwade - vmerwade@purdue.edu

## Acknowledgments

We acknowledge the support and resources provided by Purdue University and the hydrological research community.
