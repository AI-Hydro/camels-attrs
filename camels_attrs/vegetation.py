"""
Vegetation characteristics extraction for CAMELS-attrs package
================================================================

Extraction hierarchy:
1. PRIMARY: Google Earth Engine (fast, full temporal coverage)
2. BACKUP: Microsoft Planetary Computer (distributed 5-year sampling)
3. FALLBACK: Default CAMELS values

Author: Mohammad Galib
Package: camels-attrs
GitHub: galib9690/camels-attrs
"""

import numpy as np
import geopandas as gpd
import pygeohydro as gh
from typing import Dict, List, Optional
import warnings


def extract_vegetation_attributes(
    watershed_geom, 
    gauge_id: str = "temp_id",
    years: Optional[List[int]] = None,
    method: str = "auto"
) -> Dict[str, float]:
    """
    Extract CAMELS-style vegetation characteristics.
    
    Tries Google Earth Engine first (fast, comprehensive), falls back to
    Microsoft Planetary Computer if GEE unavailable, and uses defaults if both fail.
    
    Parameters
    ----------
    watershed_geom : shapely.geometry
        Watershed boundary (EPSG:4326)
    gauge_id : str
        USGS gauge identifier
    years : list of int, optional
        Years for temporal sampling. If None:
        - GEE: Uses all available years (2000-2021)
        - Planetary Computer: Uses [2003, 2008, 2013, 2018, 2021]
    method : str
        Extraction method: 'auto', 'gee', 'planetary_computer', 'defaults'
        Default 'auto' tries GEE first, then Planetary Computer
    
    Returns
    -------
    dict
        CAMELS vegetation attributes:
        - lai_max: Maximum monthly mean LAI
        - lai_min: Minimum monthly mean LAI  
        - lai_diff: Seasonal LAI amplitude (max - min)
        - gvf_max: Maximum monthly mean GVF
        - gvf_diff: Seasonal GVF amplitude
        - gvf_mean: Annual mean GVF
        - frac_forest: Forest fraction (0-1)
        - frac_cropland: Cropland fraction (0-1)
        - water_frac: Water fraction (0-1)
        - dom_land_cover: Dominant NLCD category
        - dom_land_cover_frac: Dominant category fraction (0-1)
        - root_depth_50: 50th percentile root depth (m)
        - root_depth_99: 99th percentile root depth (m)
        - extraction_method: Method used ('gee', 'planetary_computer', or 'defaults')
    
    Examples
    --------
    >>> # Automatic (tries GEE first)
    >>> veg_attrs = extract_vegetation_attributes(watershed_geom, gauge_id)
    
    >>> # Force specific method
    >>> veg_attrs = extract_vegetation_attributes(
    ...     watershed_geom, gauge_id, method='gee'
    ... )
    
    >>> # Custom years
    >>> veg_attrs = extract_vegetation_attributes(
    ...     watershed_geom, gauge_id, years=[2010, 2015, 2020]
    ... )
    """
    print("  - Extracting vegetation attributes...")
    
    # Set default years based on method
    if years is None:
        default_years_gee = list(range(2005, 2020))  # Most MODIS record
        default_years_pc = [2003, 2008, 2013, 2018, 2021]  # Distributed sampling
    else:
        default_years_gee = years
        default_years_pc = years
    
    veg_attrs = {}
    
    # Try methods in order
    if method == "auto":
        # Try GEE first (fast, comprehensive)
        try:
            print("    → Trying Google Earth Engine (primary method)...")
            veg_attrs = _extract_with_gee(
                watershed_geom, gauge_id, default_years_gee
            )
            veg_attrs['extraction_method'] = 'gee'
            print("    ✓ GEE extraction successful")
            return veg_attrs
        except Exception as e:
            print(f"    ⚠ GEE failed: {str(e)[:80]}")
            print("    → Trying Planetary Computer (backup method)...")
        
        # Fall back to Planetary Computer
        try:
            veg_attrs = _extract_with_planetary_computer(
                watershed_geom, gauge_id, default_years_pc
            )
            veg_attrs['extraction_method'] = 'planetary_computer'
            print("    ✓ Planetary Computer extraction successful")
            return veg_attrs
        except Exception as e:
            print(f"    ⚠ Planetary Computer failed: {str(e)[:80]}")
            print("    → Using default values (fallback)")
    
    elif method == "gee":
        veg_attrs = _extract_with_gee(watershed_geom, gauge_id, default_years_gee)
        veg_attrs['extraction_method'] = 'gee'
        return veg_attrs
    
    elif method == "planetary_computer":
        veg_attrs = _extract_with_planetary_computer(
            watershed_geom, gauge_id, default_years_pc
        )
        veg_attrs['extraction_method'] = 'planetary_computer'
        return veg_attrs
    
    # Fallback to defaults
    veg_attrs = _get_default_vegetation_attributes(watershed_geom, gauge_id)
    veg_attrs['extraction_method'] = 'defaults'
    print("    ✓ Using default CAMELS vegetation values")
    return veg_attrs


# ============================================================================
# PRIMARY METHOD: Google Earth Engine
# ============================================================================

def _extract_with_gee(watershed_geom, gauge_id: str, years: List[int]) -> Dict:
    """
    Extract vegetation attributes using Google Earth Engine (PRIMARY method).
    
    This is the preferred method because:
    - Server-side processing (very fast, 20-40 seconds)
    - Can process full temporal coverage efficiently
    - No data download bottleneck
    - Uses distributed Google infrastructure
    
    Processes all months for specified years to compute robust climatology.
    """
    import ee
    
    # Initialize Earth Engine
    try:
        ee.Initialize(project='ee-mohdgalib9690')
    except Exception as e:
        raise RuntimeError(f"GEE initialization failed: {e}")
    
    # Convert watershed to EE geometry
    ee_watershed = _shapely_to_ee_geometry(watershed_geom)
    
    # Extract MODIS LAI
    lai_stats = _extract_lai_gee(ee_watershed, years)
    
    # Extract MODIS NDVI/GVF
    ndvi_stats = _extract_ndvi_gee(ee_watershed, years)
    
    # Extract NLCD land cover (using pygeohydro - fast enough)
    lc_stats = _extract_nlcd_land_cover(watershed_geom, gauge_id)
    
    # Estimate root depth from dominant land cover
    root_depth = _estimate_root_depth(lc_stats['dom_land_cover'])
    
    # Combine all attributes
    return {
        **lai_stats,
        **ndvi_stats,
        **lc_stats,
        'root_depth_50': float(root_depth[0]),
        'root_depth_99': float(root_depth[1])
    }


def _shapely_to_ee_geometry(shapely_geom):
    """Convert shapely geometry to Earth Engine geometry."""
    import ee
    
    if shapely_geom.geom_type == 'Polygon':
        coords = list(shapely_geom.exterior.coords)
    elif shapely_geom.geom_type == 'MultiPolygon':
        # Use largest polygon
        coords = list(max(shapely_geom.geoms, key=lambda p: p.area).exterior.coords)
    else:
        raise ValueError(f"Unsupported geometry type: {shapely_geom.geom_type}")
    
    ee_coords = [[float(x), float(y)] for x, y in coords]
    return ee.Geometry.Polygon(ee_coords)


def _extract_lai_gee(ee_watershed, years: List[int]) -> Dict:
    """
    Extract LAI climatology from MODIS using Google Earth Engine.
    
    Processes all months for specified years to compute robust monthly climatology,
    then extracts seasonal max/min.
    """
    import ee
    
    try:
        # MODIS LAI collection (Terra, 8-day, 500m)
        lai_collection = ee.ImageCollection('MODIS/006/MOD15A2H') \
            .select('Lai_500m') \
            .filterBounds(ee_watershed)
        
        # Collect monthly means for each year
        monthly_lai_values = []
        
        for year in years:
            for month in range(1, 13):
                start_date = f"{year}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-28"
                
                monthly_images = lai_collection.filterDate(start_date, end_date)
                
                if monthly_images.size().getInfo() > 0:
                    # Mean of all images in the month
                    monthly_mean = monthly_images.mean()
                    
                    # Apply scale factor and extract watershed mean
                    lai_scaled = monthly_mean.multiply(0.1)
                    
                    stats = lai_scaled.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_watershed,
                        scale=500,
                        maxPixels=1e9
                    )
                    
                    lai_value = stats.get('Lai_500m').getInfo()
                    
                    if lai_value is not None and 0 < lai_value <= 10:
                        monthly_lai_values.append((month, lai_value))
        
        # Compute climatological monthly means
        monthly_climatology = {}
        for month in range(1, 13):
            month_values = [val for m, val in monthly_lai_values if m == month]
            if month_values:
                monthly_climatology[month] = np.mean(month_values)
        
        if len(monthly_climatology) >= 6:
            lai_max = float(max(monthly_climatology.values()))
            lai_min = float(min(monthly_climatology.values()))
            lai_diff = lai_max - lai_min
            
            return {
                'lai_max': lai_max,
                'lai_min': lai_min,
                'lai_diff': lai_diff
            }
        else:
            raise ValueError("Insufficient LAI data retrieved")
            
    except Exception as e:
        raise RuntimeError(f"GEE LAI extraction failed: {e}")


def _extract_ndvi_gee(ee_watershed, years: List[int]) -> Dict:
    """
    Extract NDVI/GVF climatology from MODIS using Google Earth Engine.
    
    Processes all months for specified years to compute robust monthly climatology.
    """
    import ee
    
    try:
        # MODIS NDVI collection (Terra, 16-day, 250m)
        ndvi_collection = ee.ImageCollection('MODIS/006/MOD13Q1') \
            .select('NDVI') \
            .filterBounds(ee_watershed)
        
        # Collect monthly means for each year
        monthly_ndvi_values = []
        
        for year in years:
            for month in range(1, 13):
                start_date = f"{year}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-28"
                
                monthly_images = ndvi_collection.filterDate(start_date, end_date)
                
                if monthly_images.size().getInfo() > 0:
                    monthly_mean = monthly_images.mean()
                    
                    # Convert to GVF (scale factor: divide by 10000)
                    gvf_scaled = monthly_mean.divide(10000.0)
                    
                    stats = gvf_scaled.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=ee_watershed,
                        scale=250,
                        maxPixels=1e9
                    )
                    
                    gvf_value = stats.get('NDVI').getInfo()
                    
                    if gvf_value is not None and -1 <= gvf_value <= 1:
                        monthly_ndvi_values.append((month, gvf_value))
        
        # Compute climatological monthly means
        monthly_climatology = {}
        for month in range(1, 13):
            month_values = [val for m, val in monthly_ndvi_values if m == month]
            if month_values:
                monthly_climatology[month] = np.mean(month_values)
        
        if len(monthly_climatology) >= 6:
            gvf_max = float(max(monthly_climatology.values()))
            gvf_min = float(min(monthly_climatology.values()))
            gvf_diff = gvf_max - gvf_min
            gvf_mean = float(np.mean(list(monthly_climatology.values())))
            
            return {
                'gvf_max': gvf_max,
                'gvf_diff': gvf_diff,
                'gvf_mean': gvf_mean
            }
        else:
            raise ValueError("Insufficient NDVI data retrieved")
            
    except Exception as e:
        raise RuntimeError(f"GEE NDVI extraction failed: {e}")


# ============================================================================
# BACKUP METHOD: Microsoft Planetary Computer
# ============================================================================

def _extract_with_planetary_computer(
    watershed_geom, 
    gauge_id: str, 
    years: List[int]
) -> Dict:
    """
    Extract vegetation attributes using Microsoft Planetary Computer (BACKUP method).
    
    Uses distributed temporal sampling (5 years) for computational efficiency.
    This is slower than GEE but doesn't require Earth Engine authentication.
    
    Expected time: 2-10 minutes per watershed
    """
    from pystac_client import Client
    
    client = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    
    # Extract MODIS LAI (distributed years)
    lai_stats = _extract_lai_planetary_computer(client, watershed_geom, years)
    
    # Extract MODIS NDVI/GVF (distributed years)
    ndvi_stats = _extract_ndvi_planetary_computer(client, watershed_geom, years)
    
    # Extract NLCD land cover
    lc_stats = _extract_nlcd_land_cover(watershed_geom, gauge_id)
    
    # Estimate root depth
    root_depth = _estimate_root_depth(lc_stats['dom_land_cover'])
    
    return {
        **lai_stats,
        **ndvi_stats,
        **lc_stats,
        'root_depth_50': float(root_depth[0]),
        'root_depth_99': float(root_depth[1])
    }


def _extract_lai_planetary_computer(client, watershed_geom, years: List[int]) -> Dict:
    """
    Extract LAI from Planetary Computer using distributed temporal sampling.
    
    Samples one scene per month for each year, computes monthly climatology.
    """
    import planetary_computer
    import rioxarray
    
    try:
        monthly_values = {month: [] for month in range(1, 13)}
        
        for year in years:
            for month in range(1, 13):
                try:
                    # Search for scene near mid-month
                    search = client.search(
                        collections=["modis-15A2H-061"],
                        bbox=watershed_geom.bounds,
                        datetime=f"{year}-{month:02d}-10/{year}-{month:02d}-20"
                    )
                    items = list(search.get_items())
                    
                    if not items:
                        # Expand search window
                        search = client.search(
                            collections=["modis-15A2H-061"],
                            bbox=watershed_geom.bounds,
                            datetime=f"{year}-{month:02d}-01/{year}-{month:02d}-28"
                        )
                        items = list(search.get_items())
                    
                    if items:
                        item = planetary_computer.sign(items[0])
                        lai_href = item.assets["Lai_500m"].href
                        
                        lai = rioxarray.open_rasterio(lai_href, masked=True)
                        lai_clipped = lai.rio.clip(
                            [watershed_geom], 
                            crs="EPSG:4326", 
                            drop=True, 
                            invert=False
                        )
                        
                        # Apply scale factor and filter
                        lai_clipped = lai_clipped * 0.1
                        lai_clipped = lai_clipped.where(lai_clipped <= 10)
                        
                        spatial_mean = float(lai_clipped.mean().values)
                        
                        if not np.isnan(spatial_mean) and spatial_mean > 0:
                            monthly_values[month].append(spatial_mean)
                
                except Exception:
                    continue
        
        # Compute monthly climatology
        monthly_climatology = []
        for month in range(1, 13):
            if monthly_values[month]:
                monthly_climatology.append(np.mean(monthly_values[month]))
        
        if len(monthly_climatology) >= 6:
            lai_max = float(np.max(monthly_climatology))
            lai_min = float(np.min(monthly_climatology))
            lai_diff = lai_max - lai_min
            
            return {
                'lai_max': lai_max,
                'lai_min': lai_min,
                'lai_diff': lai_diff
            }
        else:
            raise ValueError("Insufficient LAI data")
            
    except Exception as e:
        raise RuntimeError(f"Planetary Computer LAI extraction failed: {e}")


def _extract_ndvi_planetary_computer(client, watershed_geom, years: List[int]) -> Dict:
    """
    Extract NDVI/GVF from Planetary Computer using distributed temporal sampling.
    """
    import planetary_computer
    import rioxarray
    
    try:
        monthly_values = {month: [] for month in range(1, 13)}
        
        for year in years:
            for month in range(1, 13):
                try:
                    search = client.search(
                        collections=["modis-13Q1-061"],
                        bbox=watershed_geom.bounds,
                        datetime=f"{year}-{month:02d}-10/{year}-{month:02d}-20"
                    )
                    items = list(search.get_items())
                    
                    if not items:
                        search = client.search(
                            collections=["modis-13Q1-061"],
                            bbox=watershed_geom.bounds,
                            datetime=f"{year}-{month:02d}-01/{year}-{month:02d}-28"
                        )
                        items = list(search.get_items())
                    
                    if items:
                        item = planetary_computer.sign(items[0])
                        ndvi_href = item.assets["250m_16_days_NDVI"].href
                        
                        ndvi = rioxarray.open_rasterio(ndvi_href, masked=True)
                        ndvi_clipped = ndvi.rio.clip(
                            [watershed_geom],
                            crs="EPSG:4326",
                            drop=True,
                            invert=False
                        )
                        
                        # Convert to GVF
                        gvf = ndvi_clipped / 10000.0
                        gvf = gvf.where((gvf >= -1) & (gvf <= 1))
                        
                        spatial_mean = float(gvf.mean().values)
                        
                        if not np.isnan(spatial_mean):
                            monthly_values[month].append(spatial_mean)
                
                except Exception:
                    continue
        
        # Compute monthly climatology
        monthly_climatology = []
        for month in range(1, 13):
            if monthly_values[month]:
                monthly_climatology.append(np.mean(monthly_values[month]))
        
        if len(monthly_climatology) >= 6:
            gvf_max = float(np.max(monthly_climatology))
            gvf_min = float(np.min(monthly_climatology))
            gvf_diff = gvf_max - gvf_min
            gvf_mean = float(np.mean(monthly_climatology))
            
            return {
                'gvf_max': gvf_max,
                'gvf_diff': gvf_diff,
                'gvf_mean': gvf_mean
            }
        else:
            raise ValueError("Insufficient NDVI data")
            
    except Exception as e:
        raise RuntimeError(f"Planetary Computer NDVI extraction failed: {e}")


# ============================================================================
# SHARED METHODS: NLCD and Root Depth
# ============================================================================

def _extract_nlcd_land_cover(watershed_geom, gauge_id: str) -> Dict:
    """
    Extract NLCD 2021 land cover statistics using pygeohydro.
    
    This is fast (~2 seconds) so we use it for both GEE and Planetary Computer.
    """
    try:
        gdf = gpd.GeoDataFrame(
            index=[str(gauge_id)], 
            crs="EPSG:4326", 
            geometry=[watershed_geom]
        )
        lulc = gh.nlcd_bygeom(gdf, resolution=30, years={"cover": [2021]}, ssl=False)
        
        # Compute land cover statistics
        stats = gh.cover_statistics(lulc[str(gauge_id)].cover_2021)
        
        # Convert to fractions (0-1)
        categories_frac = {k: v / 100.0 for k, v in stats.categories.items()}
        
        # Extract required attributes
        frac_forest = categories_frac.get("Forest", 0.0)
        frac_cropland = categories_frac.get("Planted/Cultivated", 0.0)
        water_frac = categories_frac.get("Water", 0.0)
        
        dom_land_cover = max(categories_frac, key=categories_frac.get)
        dom_land_cover_frac = categories_frac[dom_land_cover]
        
        return {
            'frac_forest': float(frac_forest),
            'frac_cropland': float(frac_cropland),
            'water_frac': float(water_frac),
            'dom_land_cover': dom_land_cover,
            'dom_land_cover_frac': float(dom_land_cover_frac)
        }
        
    except Exception as e:
        warnings.warn(f"NLCD extraction failed: {e}")
        return {
            'frac_forest': 0.5,
            'frac_cropland': 0.1,
            'water_frac': 0.05,
            'dom_land_cover': 'Forest',
            'dom_land_cover_frac': 0.5
        }


def _estimate_root_depth(dom_land_cover: str) -> tuple:
    """
    Estimate root depth (50th and 99th percentile, in meters) from NLCD class.
    
    Based on literature values for typical vegetation types.
    
    Returns
    -------
    tuple
        (root_depth_50, root_depth_99) in meters
    """
    root_depth_lookup = {
        "Forest": (0.7, 2.0),
        "Shrubland": (0.4, 1.2),
        "Grassland/Herbaceous": (0.3, 1.0),
        "Pasture/Hay": (0.3, 0.8),
        "Planted/Cultivated": (0.3, 0.8),
        "Woody Wetlands": (0.2, 0.5),
        "Emergent Herbaceous Wetlands": (0.2, 0.5),
        "Water": (0.0, 0.0),
        "Barren": (0.1, 0.3),
        "Developed": (0.2, 0.6),
    }
    return root_depth_lookup.get(dom_land_cover, (0.4, 1.0))


# ============================================================================
# FALLBACK: Default Values
# ============================================================================

def _get_default_vegetation_attributes(watershed_geom, gauge_id: str) -> Dict:
    """
    Get default CAMELS vegetation attributes (FALLBACK method).
    
    Uses NLCD for land cover if possible, otherwise uses typical values.
    """
    # Try to at least get NLCD land cover
    lc_stats = _extract_nlcd_land_cover(watershed_geom, gauge_id)
    root_depth = _estimate_root_depth(lc_stats['dom_land_cover'])
    
    return {
        'lai_max': 3.0,
        'lai_min': 1.0,
        'lai_diff': 2.0,
        'gvf_max': 0.7,
        'gvf_diff': 0.5,
        'gvf_mean': 0.45,
        **lc_stats,
        'root_depth_50': float(root_depth[0]),
        'root_depth_99': float(root_depth[1])
    }


# ============================================================================
# BACKWARDS COMPATIBILITY (for existing code)
# ============================================================================

def extract_modis_lai(client, watershed_geom):
    """Legacy function for backwards compatibility."""
    warnings.warn(
        "extract_modis_lai is deprecated. Use extract_vegetation_attributes instead.",
        DeprecationWarning
    )
    years = [2020]
    result = _extract_lai_planetary_computer(client, watershed_geom, years)
    return result


def extract_modis_ndvi(client, watershed_geom):
    """Legacy function for backwards compatibility."""
    warnings.warn(
        "extract_modis_ndvi is deprecated. Use extract_vegetation_attributes instead.",
        DeprecationWarning
    )
    years = [2020]
    result = _extract_ndvi_planetary_computer(client, watershed_geom, years)
    return result


def estimate_root_depth_from_nlcd(dom_land_cover: str):
    """Legacy function for backwards compatibility."""
    warnings.warn(
        "estimate_root_depth_from_nlcd is deprecated. Use _estimate_root_depth instead.",
        DeprecationWarning
    )
    return _estimate_root_depth(dom_land_cover)