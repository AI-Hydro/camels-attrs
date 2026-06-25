"""
Topographic attributes extraction from DEM data
"""

import geopandas as gpd
import numpy as np


def _slope_percent_from_dem(dem_proj):
    """Return percent slope from a projected DEM without requiring xrspatial.

    xarray-spatial currently resolves through old numba/llvmlite releases that
    do not install on modern Python (3.13). For the package's baseline DEM
    statistics, a deterministic finite-difference slope is sufficient and keeps
    installation practical for current Python users.
    """
    arr = np.asarray(dem_proj.values, dtype=float)
    if arr.ndim > 2:
        arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise ValueError(f"Expected a 2-D DEM array, got shape {arr.shape!r}")

    transform = getattr(getattr(dem_proj, "rio", None), "transform", lambda: None)()
    if transform is not None:
        dx = abs(float(transform.a)) or 1.0
        dy = abs(float(transform.e)) or 1.0
    else:
        x = dem_proj.coords.get("x")
        y = dem_proj.coords.get("y")
        dx = float(abs(np.nanmedian(np.diff(x.values)))) if x is not None and x.size > 1 else 1.0
        dy = float(abs(np.nanmedian(np.diff(y.values)))) if y is not None and y.size > 1 else 1.0

    dz_dy, dz_dx = np.gradient(arr, dy, dx)
    return np.sqrt(dz_dx**2 + dz_dy**2) * 100.0


def extract_topographic_attributes(watershed_geom, resolution=30):
    """
    Extract topographic attributes from DEM data.
    
    Parameters
    ----------
    watershed_geom : shapely.geometry
        Watershed boundary geometry
    resolution : int, optional
        DEM resolution in meters (default: 30)
    
    Returns
    -------
    dict
        Topographic attributes with keys:
        - elev_mean: mean elevation (m)
        - elev_min: minimum elevation (m)
        - elev_max: maximum elevation (m)
        - elev_std: elevation standard deviation (m)
        - slope_mean: mean slope (%)
        - slope_std: slope standard deviation (%)
        - area_geospa_fabric: drainage area (km²)
    
    Raises
    ------
    Exception
        If DEM extraction fails
    """
    try:
        import py3dep

        # Get DEM data
        dem = py3dep.get_dem(watershed_geom, resolution=resolution)
        dem_proj = dem.rio.reproject("EPSG:5070")  # Equal-area projection
        
        # Compute slope
        slope_pct = _slope_percent_from_dem(dem_proj)
        
        # Calculate elevation statistics
        elevation_stats = {
            "elev_mean": float(dem_proj.mean().values),
            "elev_min": float(dem_proj.min().values),
            "elev_max": float(dem_proj.max().values),
            "elev_std": float(dem_proj.std().values),
        }
        
        # Calculate slope statistics
        slope_stats = {
            "slope_mean": float(np.nanmean(slope_pct)),
            "slope_std": float(np.nanstd(slope_pct)),
        }
        
        # Calculate drainage area
        watershed_proj = gpd.GeoDataFrame(
            [1], geometry=[watershed_geom], crs="EPSG:4326"
        ).to_crs("EPSG:5070")
        area_km2 = watershed_proj.geometry.area.iloc[0] / 1e6
        
        topo_attrs = {
            **elevation_stats,
            **slope_stats,
            "area_geospa_fabric": area_km2,
        }
        
        return topo_attrs
        
    except Exception as e:
        raise Exception(f"Failed to extract topographic attributes: {str(e)}")
