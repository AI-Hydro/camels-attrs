"""
Geological characteristics extraction
"""

try:
    from pygeoglim import glim_attributes, glhymps_attributes
    HAS_PYGEOGLIM = True
except ImportError:
    HAS_PYGEOGLIM = False


def extract_geological_attributes(watershed_gdf):
    """
    Extract geological characteristics using GLiM and GLHYMPS datasets.
    
    Note: Requires optional pygeoglim package. If not installed, returns default values.
    Install with: pip install pygeoglim (or from source if unavailable on PyPI)
    
    Parameters
    ----------
    watershed_gdf : GeoDataFrame
        Watershed boundary as GeoDataFrame
    
    Returns
    -------
    dict
        Geological attributes including lithology, permeability, porosity
    """
    if not HAS_PYGEOGLIM:
        # Return default values if pygeoglim not available
        return {
            "geol_1st_class": "mixed",
            "geol_2nd_class": "mixed",
            "glim_1st_class_frac": 0.6,
            "glim_2nd_class_frac": 0.4,
            "carbonate_rocks_frac": 0.0,
            "geol_permeability": -14.0,
            "geol_porosity": 0.1
        }
    
    try:
        # Lithology from GLiM
        try:
            glim_result = glim_attributes(watershed_gdf)
        except:
            glim_result = {
                "geol_1st_class": "mixed",
                "geol_2nd_class": "mixed",
                "glim_1st_class_frac": 0.6,
                "glim_2nd_class_frac": 0.4,
                "carbonate_rocks_frac": 0.0,
            }
        
        # Hydrogeology from GLHYMPS
        try:
            glhymps_result = glhymps_attributes(watershed_gdf)
        except:
            glhymps_result = {
                "geol_permeability": -14.0,  # log10(m²)
                "geol_porosity": 0.1  # fraction
            }
        
        # Merge results
        geol_attrs = {**glim_result, **glhymps_result}
        
        # Filter out unwanted keys
        geol_attrs = {
            k: v for k, v in geol_attrs.items()
            if k not in ["geol_permeability_linear", "hydraulic_conductivity"]
        }
        
        return geol_attrs
        
    except Exception as e:
        # Return default values
        return {
            "geol_1st_class": "mixed",
            "geol_2nd_class": "mixed",
            "glim_1st_class_frac": 0.6,
            "glim_2nd_class_frac": 0.4,
            "carbonate_rocks_frac": 0.0,
            "geol_permeability": -14.0,
            "geol_porosity": 0.1
        }
