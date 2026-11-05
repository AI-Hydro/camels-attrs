"""
Topographic attributes extraction from DEM data
"""

import py3dep
import xrspatial
import geopandas as gpd

# tan(slope) [m/m] x 1000 = m/km. Through camels-attrs 2.0.1 the factor was 100 (percent) under the same keys.
SLOPE_M_PER_KM_FACTOR = 1000.0


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
        - slope_mean: mean slope, tan(slope) x 1000 (m/km, the CAMELS unit)
        - slope_std: slope standard deviation, same unit (m/km)
        - area_geospa_fabric: drainage area (km²)
    
    Notes
    -----
    ``slope_mean`` / ``slope_std`` are in m/km (= 10 x percent). Through 2.0.1 they were in
    percent under the same key names; see CHANGELOG ("slope_mean / slope_std units").
    These are CAMELS-like, not CAMELS-identical: CAMELS takes slope from N15 ("USGS data"),
    whose DEM and method are not stated, so this 30 m 3DEP slope is expected to read higher.

    Raises
    ------
    Exception
        If DEM extraction fails
    """
    try:
        # Get DEM data
        dem = py3dep.get_dem(watershed_geom, resolution=resolution)
        dem_proj = dem.rio.reproject("EPSG:5070")  # Equal-area projection
        
        # Compute slope
        slope_deg = xrspatial.slope(dem_proj)
        slope_mpm = py3dep.deg2mpm(slope_deg)  # tan(slope), m per m
        slope_mkm = slope_mpm * SLOPE_M_PER_KM_FACTOR  # m/km, the CAMELS slope_mean unit
        
        # Calculate elevation statistics
        elevation_stats = {
            "elev_mean": float(dem_proj.mean().values),
            "elev_min": float(dem_proj.min().values),
            "elev_max": float(dem_proj.max().values),
            "elev_std": float(dem_proj.std().values),
        }
        
        # Calculate slope statistics
        slope_stats = {
            "slope_mean": float(slope_mkm.mean().values),
            "slope_std": float(slope_mkm.std().values),
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
