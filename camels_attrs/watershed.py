"""
Watershed delineation module using NLDI API
"""

from pynhd import NLDI
from pygeohydro import NWIS
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
        nwis = NWIS()
        site_info = nwis.get_info([{"site": gauge_id}])
        site_info["site_no"] = site_info["site_no"].astype(str)
        row = site_info.loc[site_info["site_no"] == str(gauge_id)].iloc[0]
        
        gauge_lat = float(row["dec_lat_va"])
        gauge_lon = float(row["dec_long_va"])
        gauge_name = row["station_nm"]
        
        metadata = {
            "gauge_id": str(gauge_id),
            "gauge_name": gauge_name,
            "gauge_lat": gauge_lat,
            "gauge_lon": gauge_lon,
            "geometry": watershed_geom
        }
        
        return watershed_gdf, watershed_geom, metadata, area_km2
        
    except Exception as e:
        raise Exception(f"Failed to delineate watershed for gauge {gauge_id}: {str(e)}")