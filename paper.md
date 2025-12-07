---
title: 'camels-attrs: A Python Package for Extracting CAMELS-like Catchment Attributes for Any USGS Gauge in the United States'
tags:
  - Python
  - hydrology
  - catchment attributes
  - CAMELS
  - watershed characterization
  - geospatial data
  - reproducible research
authors:
  - name: Mohammad Galib
    orcid: 0000-0001-8593-9110
    corresponding: true
    affiliation: 1
  - name: Venkatesh Merwade
    orcid: 0000-0001-5518-2890
    affiliation: 1
affiliations:
  - name: Lyles School of Civil Engineering, Purdue University, West Lafayette, IN, USA
    index: 1
date: 6 December 2025
bibliography: paper.bib
---

# Summary

Understanding watersheds is fundamental to managing water resources, predicting floods, and assessing environmental change. Scientists characterize watersheds using attributes such as average elevation, soil type, vegetation cover, and climate patterns. The Catchment Attributes and Meteorology for Large-sample Studies (CAMELS) dataset [@addor2017camels; @newman2015development] provides standardized attributes for 671 watersheds across the United States and has become a cornerstone resource in hydrology research.

`camels-attrs` is an open-source Python package (MIT Licensed) that extends the CAMELS methodology to any United States Geological Survey (USGS) stream gauge location in the country. Given a gauge identifier, the package automatically delineates the upstream watershed boundary according to drainage basins and extracts over 70 standardized catchment attributes spanning topography, climate, soil, vegetation, geology, and hydrology. The software also retrieves daily hydrometeorological forcing data (precipitation, temperature, solar radiation, wind speed, humidity) for user-specified time periods. Visualization tools produce publication-ready watershed maps and multi-gauge comparison figures. The package is available on PyPI and GitHub.

# Statement of Need

Large-sample hydrology—studying many watersheds simultaneously to understand hydrological processes across environmental gradients—has transformed water science over the past decade [@gupta2014large]. The CAMELS dataset catalyzed this paradigm shift by providing consistent catchment attributes for model benchmarking, machine learning applications, and comparative studies. However, CAMELS remains limited to a fixed set of 671 pre-selected gauges, creating barriers for hydrologists, environmental scientists, and water resource engineers who wish to: (1) include additional study sites in their analyses, (2) apply the same methodology to new locations, (3) update attributes as source datasets improve, or (4) customize extraction parameters for specific applications.

Existing tools for hydrological data retrieval are fragmented across purpose-specific packages. The `dataretrieval` package [@dataretrieval] focuses on USGS water observations without catchment characterization. The `hydrofunctions` package [@hydrofunctions] provides Pythonic access to streamflow timeseries but does not extract landscape attributes. The HyRiver suite [@hydrodata], which includes `pynhd`, `py3dep`, `pygeohydro`, and `pygridmet`, offers low-level access to individual geospatial datasets but requires users to implement their own extraction workflows and ensure methodological consistency with CAMELS.

`camels-attrs` addresses these gaps by providing a unified, high-level interface that orchestrates watershed delineation and attribute extraction from multiple authoritative data sources—USGS 3DEP for topography, GridMET for climate, gNATSGO and POLARIS for soils, MODIS and NLCD for vegetation, GLiM and GLHYMPS for geology, and USGS NWIS for streamflow. The package implements the same algorithms and definitions used in the original CAMELS dataset, ensuring methodological consistency while enabling on-demand extraction for any USGS gauge. This capability supports prediction in ungauged basins, model transferability studies, and extension of existing large-sample analyses to new regions.

The software follows modern Python packaging standards, provides both programmatic and command-line interfaces, and includes comprehensive documentation with usage examples. Error handling ensures graceful degradation when individual data sources are unavailable, and the modular architecture allows researchers to extend the package with custom attribute extractors.

# Implemented Functionality

The package extracts attributes organized into six categories following CAMELS conventions:

- **Topography**: Elevation statistics (mean, minimum, maximum, standard deviation), slope metrics, and drainage area from 30-meter digital elevation models.
- **Climate**: Mean precipitation, potential evapotranspiration, temperature, aridity index, seasonality indices, snow fraction, and extreme precipitation event characteristics from GridMET data.
- **Soil**: Porosity, available water capacity, texture fractions (sand, silt, clay), depth, and hydraulic conductivity from gNATSGO and POLARIS datasets.
- **Vegetation**: Leaf area index, normalized difference vegetation index (converted to green vegetation fraction), land cover fractions, and root depth estimates from MODIS imagery and the National Land Cover Database.
- **Geology**: Lithology classes, carbonate rock fraction, geological permeability, and porosity from the Global Lithological Map and Global Hydrogeology Maps via the `pygeoglim` package [@pygeoglim].
- **Hydrology**: Flow statistics (mean, percentiles, variability), baseflow index computed using the Lyne-Hollick digital filter, runoff ratio, streamflow elasticity, flow duration curve slope, and timing metrics.

Additionally, the package extracts daily hydrometeorological forcing timeseries and provides functions for computing monthly aggregations, annual water balances, and climate statistics suitable for hydrological model input preparation.

# Ongoing Research Applications

The package is actively supporting advanced watershed characterization for hydrological modeling studies at Purdue University. Researchers are leveraging the tool to develop distributed hydrological models that demand consistent, high-quality catchment parameterization across diverse study sites. By automating the retrieval of critical attributes—such as topography, climate, and soil characteristics—the package has dramatically streamlined the workflow, reducing the time required for model setup from weeks of manual data collection to just minutes of automated processing. This efficiency gain allows for more robust, large-scale comparative analyses and accelerates the development of reliable hydrological models.

# Acknowledgements

This work was supported by the Lyles School of Civil Engineering at Purdue University. We acknowledge the developers of the HyRiver suite of Python packages upon which this package builds, and the agencies—including USGS, NOAA, and NASA—that provide open access to hydrological and geospatial data.

# References
