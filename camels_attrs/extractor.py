"""
Main CAMELS extractor class that orchestrates all attribute extraction
"""

import pandas as pd
from typing import Dict, Optional
from collections import OrderedDict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from .watershed import delineate_watershed
from .topography import extract_topographic_attributes
from .climate import fetch_climate_data, compute_climate_indices
from .soil import extract_soil_attributes
from .vegetation import extract_vegetation_attributes
from .geology import extract_geological_attributes
from .hydrology import extract_hydrological_signatures
from .timeseries import (
    fetch_forcing_data, 
    calculate_pet_hargreaves,
    calculate_forcing_statistics,
    get_monthly_summary,
    calculate_water_balance
)


class CamelsExtractor:
    """
    Extract CAMELS-like catchment attributes for any USGS gauge site.
    
    This class provides a simple interface to extract comprehensive catchment
    attributes following the CAMELS methodology.
    
    Parameters
    ----------
    gauge_id : str
        USGS gauge identifier (e.g., '01031500')
    climate_start : str, optional
        Start date for climate data (default: '1990-01-01')
    climate_end : str, optional
        End date for climate data (default: '2020-12-31')
    hydro_start : str, optional
        Start date for streamflow data (default: '1990-01-01')
    hydro_end : str, optional
        End date for streamflow data (default: '2023-12-31')
    
    Examples
    --------
    >>> from camels_attributes import CamelsExtractor
    >>> 
    >>> # Extract attributes for a single gauge
    >>> extractor = CamelsExtractor('01031500')
    >>> attributes = extractor.extract_all()
    >>> 
    >>> # Export to CSV
    >>> df = extractor.to_dataframe()
    >>> df.to_csv('camels_attributes.csv', index=False)
    """
    
    def __init__(
        self,
        gauge_id: str,
        climate_start: str = "1990-01-01",
        climate_end: str = "2020-12-31",
        hydro_start: str = "1990-01-01",
        hydro_end: str = "2020-12-31"
    ):
        self.gauge_id = str(gauge_id)
        self.climate_start = climate_start
        self.climate_end = climate_end
        self.hydro_start = hydro_start
        self.hydro_end = hydro_end
        
        # Initialize storage
        self.watershed_gdf = None
        self.watershed_geom = None
        self.metadata = None
        self.area_km2 = None
        self.attributes = OrderedDict()
    
    def delineate(self):
        """Delineate watershed boundary."""
        (
            self.watershed_gdf,
            self.watershed_geom,
            self.metadata,
            self.area_km2
        ) = delineate_watershed(self.gauge_id)
        return self.watershed_gdf
    
    def extract_all(self, verbose: bool = True, raise_on_error: bool = False) -> Dict:
        """
        Extract all CAMELS attributes with metadata-first column ordering.
        
        Parameters
        ----------
        verbose : bool
            Print progress messages
        raise_on_error : bool
            If True, raise exception on critical errors. If False, continue with warnings.
        
        Returns
        -------
        dict
            OrderedDict containing all extracted attributes with '_status' key indicating
            which modules succeeded/failed. Metadata columns appear first.
        
        Raises
        ------
        Exception
            If raise_on_error=True and watershed delineation or topography extraction fails
        """
        # Clear any previous extraction results
        self.attributes = OrderedDict()
        self.watershed_gdf = None
        self.watershed_geom = None
        self.metadata = None
        self.area_km2 = None
        
        # Track extraction status
        extraction_status = {
            "watershed": False,
            "topography": False,
            "climate": False,
            "soil": False,
            "vegetation": False,
            "geology": False,
            "hydrology": False
        }
        
        if verbose:
            logger.info(f"\n{'='*70}")
            logger.info(f"EXTRACTING CAMELS ATTRIBUTES - Gauge {self.gauge_id}")
            logger.info(f"{'='*70}\n")
        
        # ====================================================================
        # 1. WATERSHED DELINEATION (CRITICAL - must succeed)
        # ====================================================================
        if verbose:
            logger.info("[1/7] Delineating watershed...")
        try:
            self.delineate()
            extraction_status["watershed"] = True
            
            # Add metadata FIRST (right after successful delineation)
            if self.metadata:
                self.attributes.update(OrderedDict([
                    ("gauge_id", self.metadata["gauge_id"]),
                    ("gauge_name", self.metadata["gauge_name"]),
                    ("gauge_lat", self.metadata["gauge_lat"]),
                    ("gauge_lon", self.metadata["gauge_lon"]),
                    ("area_km2", self.area_km2)
                ]))
            
            if verbose:
                logger.info(f"  ✓ Watershed delineated ({self.area_km2:.2f} km²)\n")
            
        except Exception as e:
            error_msg = f"CRITICAL: Watershed delineation failed - {str(e)}"
            if verbose:
                logger.error(f"  ✗ {error_msg}\n")
            if raise_on_error:
                raise Exception(error_msg)
            else:
                self.attributes["_errors"] = [error_msg]
                self.attributes["_status"] = extraction_status
                return dict(self.attributes)
        
        # ====================================================================
        # 2. TOPOGRAPHIC ATTRIBUTES (CRITICAL - must succeed)
        # ====================================================================
        if verbose:
            logger.info("[2/7] Extracting topographic attributes...")
        try:
            topo_attrs = extract_topographic_attributes(self.watershed_geom)
            self.attributes.update(topo_attrs)
            extraction_status["topography"] = True
            if verbose:
                logger.info(f"  ✓ Topography extracted ({len(topo_attrs)} attributes)\n")
        except Exception as e:
            error_msg = f"CRITICAL: Topographic extraction failed - {str(e)}"
            if verbose:
                logger.error(f"  ✗ {error_msg}\n")
            if raise_on_error:
                raise Exception(error_msg)
            else:
                if "_errors" not in self.attributes:
                    self.attributes["_errors"] = []
                self.attributes["_errors"].append(error_msg)
        
        # ====================================================================
        # 3. CLIMATE INDICES (OPTIONAL - warn on failure)
        # ====================================================================
        if verbose:
            logger.info("[3/7] Extracting climate indices...")
        try:
            climate_ds = fetch_climate_data(
                self.watershed_geom, self.climate_start, self.climate_end
            )
            climate_attrs = compute_climate_indices(climate_ds)
            self.attributes.update(climate_attrs)
            extraction_status["climate"] = True
            if verbose:
                logger.info(f"  ✓ Climate extracted ({len(climate_attrs)} attributes)\n")
        except Exception as e:
            warning_msg = f"Climate extraction failed - {str(e)}"
            if verbose:
                logger.warning(f"  ⚠ Warning: {warning_msg}\n")
            if "_warnings" not in self.attributes:
                self.attributes["_warnings"] = []
            self.attributes["_warnings"].append(warning_msg)
        
        # ====================================================================
        # 4. SOIL CHARACTERISTICS (OPTIONAL - warn on failure)
        # ====================================================================
        if verbose:
            logger.info("[4/7] Extracting soil characteristics...")
        try:
            soil_attrs = extract_soil_attributes(self.watershed_geom)
            self.attributes.update(soil_attrs)
            extraction_status["soil"] = True
            if verbose:
                logger.info(f"  ✓ Soil extracted ({len(soil_attrs)} attributes)\n")
        except Exception as e:
            warning_msg = f"Soil extraction failed - {str(e)}"
            if verbose:
                logger.warning(f"  ⚠ Warning: {warning_msg}\n")
            if "_warnings" not in self.attributes:
                self.attributes["_warnings"] = []
            self.attributes["_warnings"].append(warning_msg)
        
        # ====================================================================
        # 5. VEGETATION CHARACTERISTICS (OPTIONAL - warn on failure)
        # ====================================================================
        if verbose:
            logger.info("[5/7] Extracting vegetation characteristics...")
        try:
            veg_attrs = extract_vegetation_attributes(
                self.watershed_geom, 
                self.gauge_id
            )
            self.attributes.update(veg_attrs)
            extraction_status["vegetation"] = True
            if verbose:
                logger.info(f"  ✓ Vegetation extracted ({len(veg_attrs)} attributes)\n")
        except Exception as e:
            warning_msg = f"Vegetation extraction failed - {str(e)}"
            if verbose:
                logger.warning(f"  ⚠ Warning: {warning_msg}\n")
            if "_warnings" not in self.attributes:
                self.attributes["_warnings"] = []
            self.attributes["_warnings"].append(warning_msg)
        
        # ====================================================================
        # 6. GEOLOGICAL CHARACTERISTICS (OPTIONAL - warn on failure)
        # ====================================================================
        if verbose:
            logger.info("[6/7] Extracting geological characteristics...")
        try:
            geol_attrs = extract_geological_attributes(self.watershed_gdf)
            self.attributes.update(geol_attrs)
            extraction_status["geology"] = True
            if verbose:
                logger.info(f"  ✓ Geology extracted ({len(geol_attrs)} attributes)\n")
        except Exception as e:
            warning_msg = f"Geology extraction failed - {str(e)}"
            if verbose:
                logger.warning(f"  ⚠ Warning: {warning_msg}\n")
            if "_warnings" not in self.attributes:
                self.attributes["_warnings"] = []
            self.attributes["_warnings"].append(warning_msg)
        
        # ====================================================================
        # 7. HYDROLOGICAL SIGNATURES (OPTIONAL - warn on failure)
        # ====================================================================
        if verbose:
            logger.info("[7/7] Computing hydrological signatures...")
        try:
            hydro_attrs = extract_hydrological_signatures(
                gauge_id=self.gauge_id,
                watershed_gdf=self.watershed_gdf,
                start_date=self.hydro_start,
                end_date=self.hydro_end
            )
            self.attributes.update(hydro_attrs)
            extraction_status["hydrology"] = True
            if verbose:
                logger.info(f"  ✓ Hydrology extracted ({len(hydro_attrs)} attributes)\n")
        except Exception as e:
            warning_msg = f"Hydrology extraction failed - {str(e)}"
            if verbose:
                logger.warning(f"  ⚠ Warning: {warning_msg}\n")
            if "_warnings" not in self.attributes:
                self.attributes["_warnings"] = []
            self.attributes["_warnings"].append(warning_msg)
        
        # ====================================================================
        # Add extraction status at the end
        # ====================================================================
        self.attributes["_status"] = extraction_status
        
        # ====================================================================
        # Report results
        # ====================================================================
        successful = sum(extraction_status.values())
        total = len(extraction_status)
        
        if verbose:
            logger.info(f"{'='*70}")
            logger.info(f"EXTRACTION COMPLETE")
            logger.info(f"{'='*70}")
            logger.info(f"Total attributes: {len([k for k in self.attributes.keys() if not k.startswith('_')])}")
            logger.info(f"Modules: {successful}/{total} successful")
            if "_errors" in self.attributes:
                logger.info(f"Errors: {len(self.attributes['_errors'])}")
            if "_warnings" in self.attributes:
                logger.info(f"Warnings: {len(self.attributes['_warnings'])}")
            logger.info(f"{'='*70}\n")
        
        return dict(self.attributes)
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert attributes to pandas DataFrame with proper column ordering.
        
        Column order:
        1. Metadata (gauge_id, gauge_name, gauge_lat, gauge_lon, area_km2)
        2. Topographic attributes
        3. Climate attributes
        4. Soil attributes
        5. Vegetation attributes
        6. Geological attributes
        7. Hydrological signatures
        8. Special fields (_status, _errors, _warnings)
        
        Returns
        -------
        pd.DataFrame
            DataFrame with one row containing all attributes
        """
        if not self.attributes:
            raise ValueError("No attributes extracted. Call extract_all() first.")
        
        # Convert OrderedDict to DataFrame (preserves order)
        df = pd.DataFrame([dict(self.attributes)])
        
        return df
    
    def to_dict(self) -> Dict:
        """
        Get attributes as dictionary.
        
        Returns
        -------
        dict
            Dictionary of all attributes (preserves extraction order)
        """
        return dict(self.attributes)
    
    def extract_timeseries(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_hargreaves_pet: bool = True
    ) -> pd.DataFrame:
        """
        Extract hydrometeorological time series data from GridMET.
        
        Parameters
        ----------
        start_date : str, optional
            Start date (YYYY-MM-DD). Defaults to self.climate_start
        end_date : str, optional
            End date (YYYY-MM-DD). Defaults to self.climate_end
        include_hargreaves_pet : bool, optional
            Whether to calculate PET using Hargreaves method
        
        Returns
        -------
        pd.DataFrame
            Daily hydrometeorological forcing data
        """
        # Use dates from initialization if not provided
        start = start_date or self.climate_start
        end = end_date or self.climate_end
        
        logger.info(f"\nExtracting timeseries data for gauge {self.gauge_id}...")
        logger.info(f"Period: {start} to {end}")
        
        # Delineate watershed if not already done
        if self.watershed_geom is None:
            self.delineate()
        
        # Fetch forcing data
        df = fetch_forcing_data(self.watershed_geom, start, end)
        
        if df is None:
            raise Exception("Failed to fetch forcing data")
        
        # Calculate additional PET if requested
        if include_hargreaves_pet:
            centroid = self.watershed_gdf.to_crs('EPSG:4326').centroid.iloc[0]
            df = calculate_pet_hargreaves(df, centroid.y)
        
        logger.info(f"✓ Retrieved {len(df)} days of forcing data")
        
        return df
    
    def get_forcing_statistics(self, forcing_df: pd.DataFrame) -> Dict:
        """
        Calculate statistics from forcing timeseries.
        
        Parameters
        ----------
        forcing_df : pd.DataFrame
            Daily forcing data from extract_timeseries()
        
        Returns
        -------
        dict
            Climate forcing statistics
        """
        return calculate_forcing_statistics(forcing_df)
    
    def save(self, filepath: str, format: str = "csv"):
        """
        Save attributes to file.
        
        Parameters
        ----------
        filepath : str
            Output file path
        format : str
            Output format ('csv' or 'json')
        """
        df = self.to_dataframe()
        
        if format.lower() == "csv":
            df.to_csv(filepath, index=False)
        elif format.lower() == "json":
            df.to_json(filepath, orient="records", indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"✓ Attributes saved to {filepath}")
    
    def create_comprehensive_map(self, save_path: str = None, show: bool = True):
        """
        Create a comprehensive multi-panel watershed visualization.
        
        This method generates a rich, publication-ready watershed map with:
        - DEM elevation background
        - Watershed boundary and stream network
        - Gauge location marker
        - USA location context map
        - Key statistics panel (topography, climate, vegetation, hydrology)
        - Elevation profile
        - Land cover distribution pie chart
        - Climate water balance summary
        
        Parameters
        ----------
        save_path : str, optional
            Path to save the figure (e.g., 'watershed_map.png')
        show : bool, optional
            Whether to display the figure (default: True)
        
        Returns
        -------
        matplotlib.figure.Figure
            The created figure object
        
        Examples
        --------
        >>> extractor = CamelsExtractor('01031500')
        >>> attributes = extractor.extract_all()
        >>> fig = extractor.create_comprehensive_map(save_path='map.png')
        """
        from .visualization import create_comprehensive_watershed_map
        import matplotlib.pyplot as plt
        
        if self.watershed_gdf is None or self.metadata is None:
            raise ValueError(
                "Watershed not delineated. Call extract_all() or delineate() first."
            )
        
        fig = create_comprehensive_watershed_map(
            watershed_gdf=self.watershed_gdf,
            watershed_geom=self.watershed_geom,
            metadata=self.metadata,
            attributes=self.attributes if self.attributes else None,
            gauge_id=self.gauge_id,
            save_path=save_path
        )
        
        if show:
            plt.show()
        
        return fig


def extract_multiple_gauges(gauge_ids: list, **kwargs) -> pd.DataFrame:
    """
    Extract attributes for multiple gauges.
    
    Parameters
    ----------
    gauge_ids : list
        List of USGS gauge identifiers
    **kwargs
        Additional arguments passed to CamelsExtractor
    
    Returns
    -------
    pd.DataFrame
        Combined dataframe with attributes for all gauges
    
    Examples
    --------
    >>> gauge_list = ['01031500', '01047000', '01052500']
    >>> df = extract_multiple_gauges(gauge_list)
    >>> df.to_csv('multiple_gauges.csv', index=False)
    """
    results = []
    
    logger.info(f"\n{'='*70}")
    logger.info(f"BATCH EXTRACTION - {len(gauge_ids)} gauges")
    logger.info(f"{'='*70}\n")
    
    for i, gauge_id in enumerate(gauge_ids, 1):
        logger.info(f"[{i}/{len(gauge_ids)}] Processing gauge {gauge_id}...")
        try:
            extractor = CamelsExtractor(gauge_id, **kwargs)
            attributes = extractor.extract_all(verbose=False)
            results.append(attributes)
            
            # Count successful attributes (excluding metadata and special fields)
            attr_count = len([k for k in attributes.keys() 
                            if not k.startswith('_') and k not in 
                            ['gauge_id', 'gauge_name', 'gauge_lat', 'gauge_lon', 'area_km2']])
            logger.info(f"  ✓ Success ({attr_count} attributes)\n")
            
        except Exception as e:
            logger.error(f"  ✗ Failed: {str(e)}\n")
    
    if results:
        logger.info(f"{'='*70}")
        logger.info(f"BATCH COMPLETE - {len(results)}/{len(gauge_ids)} successful")
        logger.info(f"{'='*70}\n")
        return pd.DataFrame(results)
    else:
        raise Exception("No gauges were successfully processed")