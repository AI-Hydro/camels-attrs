# CAMELS Attrs

![CAMELS Attrs](assets/thumbnail.png)

[![PyPI version](https://badge.fury.io/py/camels-attrs.svg)](https://pypi.org/project/camels-attrs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/camels-attrs)](https://pepy.tech/project/camels-attrs)
[![CI](https://github.com/galib9690/camels-attrs/actions/workflows/ci.yml/badge.svg)](https://github.com/galib9690/camels-attrs/actions/workflows/ci.yml)

A Python package for extracting CAMELS-like catchment attributes and hydrometeorological timeseries for any USGS gauge in the United States.

## Key Capabilities

- **Automated Attribute Extraction**: Extract 60+ catchment attributes following CAMELS methodology
- **Watershed Delineation**: Automatic watershed boundary extraction for any USGS gauge
- **Timeseries Data**: Fetch daily hydrometeorological forcing data (precipitation, temperature, PET, etc.)
- **Batch Processing**: Process multiple gauges simultaneously
- **Visualization**: Create publication-ready watershed maps
- **CLI & Python API**: Use via command-line or integrate into Python workflows

## Installation

```bash
pip install camels-attrs
```

## Quick Start

### Command Line

```bash
# Extract all attributes for a gauge
camels-extract 01031500 -o attributes.csv

# Extract multiple gauges
camels-extract 01031500 02177000 06803530 -o combined.csv

# Include timeseries data
camels-extract 01031500 --timeseries -o data.csv

# Custom date ranges
camels-extract 01031500 --climate-start 2010-01-01 --climate-end 2020-12-31
```

### Python API

```python
from camels_attrs import CamelsExtractor

# Single gauge extraction
extractor = CamelsExtractor('01031500')
attributes = extractor.extract_all()

# Save to file
extractor.save('attributes.csv')

# Extract timeseries
forcing_data = extractor.extract_timeseries(
    start_date='2010-01-01',
    end_date='2020-12-31'
)

# Create watershed map
extractor.create_comprehensive_map(save_path='watershed_map.png')
```

```python
from camels_attrs import extract_multiple_gauges

# Batch processing
gauge_list = ['01031500', '02177000', '06803530']
df = extract_multiple_gauges(
    gauge_list,
    climate_start='2010-01-01',
    climate_end='2020-12-31'
)
df.to_csv('batch_attributes.csv')
```

## Extracted Attributes (60+)

| Category | Count | Examples |
|----------|-------|----------|
| **Topographic** | 7 | Elevation statistics, slope, drainage area |
| **Climate** | 13 | Precipitation, temperature, aridity, seasonality, extremes |
| **Soil** | 9 | Texture, depth, porosity, conductivity, water content |
| **Vegetation** | 13 | LAI, NDVI/GVF, land cover fractions, root depth |
| **Geological** | 7 | Lithology fractions, porosity, permeability |
| **Hydrological** | 17 | Flow statistics, baseflow, runoff ratio, event characteristics |

<details>
<summary>View complete attribute list</summary>

### Topographic
`gauge_lat`, `gauge_lon`, `elev_mean`, `elev_min`, `elev_max`, `slope_mean`, `area_gages2`, aspect statistics

### Climate  
`p_mean`, `pet_mean`, `aridity`, `p_seasonality`, `frac_snow`, temperature statistics, `high_prec_freq`, `high_prec_dur`, `low_prec_freq`, `low_prec_dur`

### Soil
Sand/silt/clay fractions, `soil_depth_pelletier`, `soil_depth_statsgo`, `soil_porosity`, `soil_conductivity`, water content, bulk density, organic carbon

### Vegetation
`lai_max`, `lai_diff`, `gvf_max`, `gvf_diff`, `ndvi_max`, `ndvi_diff`, land cover fractions, `dom_land_cover`, `dom_land_cover_frac`

### Geology
Lithology fractions (siliciclastic, carbonate, etc.), `geol_porosity`, `geol_permeability`

### Hydrology
`q_mean`, `runoff_ratio`, `baseflow_index`, `stream_elas`, `slope_fdc`, `flow_variability`, `high_q_freq`, `high_q_dur`, `low_q_freq`, `low_q_dur`, `zero_q_freq`, `hfd_mean`, `half_flow_date_std`

</details>

## Data Sources

| Data Type | Source | Resolution |
|-----------|--------|------------|
| Watershed Boundaries | USGS NLDI | Vector |
| Topography | USGS 3DEP | 10m-30m DEM |
| Climate | GridMET | 4km daily |
| Soil | gNATSGO, POLARIS | 30m-90m |
| Vegetation | MODIS, NLCD | 250m-30m |
| Geology | GLiM, GLHYMPS | Vector |
| Streamflow | USGS NWIS | Daily |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# With coverage
pytest tests/ --cov=camels_attrs
```

## Citation

If you use this package in your research, please cite:

```bibtex
Galib, M., & Merwade, V. (2025). camels-attrs: A Python Package for Extracting 
CAMELS-like Catchment Attributes (v1.0.2). Zenodo. 
https://doi.org/10.5281/zenodo.17315038
```

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17315038.svg)](https://doi.org/10.5281/zenodo.17315038)

## References

- Newman et al. (2015). Development of a large-sample watershed-scale hydrometeorological dataset. NCAR Technical Note
- Addor et al. (2017). The CAMELS data set: catchment attributes and meteorology for large-sample studies. Hydrology and Earth System Sciences, 21, 5293-5313

## Contributing

Contributions are welcome! Please submit a Pull Request or open an Issue.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contact

Mohammad Galib - mgalib@purdue.edu  
Venkatesh Merwade - vmerwade@purdue.edu

Purdue University
