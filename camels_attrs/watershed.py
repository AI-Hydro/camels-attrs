"""
Watershed delineation module using NLDI API
"""

from pynhd import NLDI
from .usgs_daily import fetch_monitoring_location
import geopandas as gpd


def delineate_watershed(gauge_id):
    """
    Delineate watershed boundary for a given USGS gauge.
    
    Parameters
    ----------
    gauge_id : str
        USGS gauge identifier (e.g., '01031500')
    
    Returns
    -------
    tuple
        (watershed_gdf, watershed_geom, metadata, area_km2)
        - watershed_gdf: GeoDataFrame with watershed boundary
        - watershed_geom: Shapely geometry of watershed
        - metadata: Dictionary with gauge information
        - area_km2: Watershed area in square kilometers
    
    Raises
    ------
    Exception
        If watershed delineation fails
    """
    try:
        # Delineate watershed using NLDI
        nldi = NLDI()
        watershed_gdf = nldi.get_basins(gauge_id)
        
        # Ensure CRS is WGS84
        if watershed_gdf.crs != "EPSG:4326":
            watershed_gdf = watershed_gdf.to_crs("EPSG:4326")
        
        watershed_geom = watershed_gdf.geometry.iloc[0]
        
        # Calculate area in km²
        area_km2 = watershed_gdf.to_crs("EPSG:5070").geometry.area.iloc[0] / 1e6
        
        # Fetch gauge metadata
        loc = fetch_monitoring_location(gauge_id)
        gauge_lat = loc["lat"]
        gauge_lon = loc["lon"]
        gauge_name = loc["name"]

        metadata = {
            "gauge_id": str(gauge_id),
            "gauge_name": gauge_name,
            "gauge_lat": gauge_lat,
            "gauge_lon": gauge_lon,
            "gauge_datum": loc["original_horizontal_datum"],
            "geometry": watershed_geom
        }
        
        return watershed_gdf, watershed_geom, metadata, area_km2
        
    except Exception as e:
        raise Exception(f"Failed to delineate watershed for gauge {gauge_id}: {str(e)}")