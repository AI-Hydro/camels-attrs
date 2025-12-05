import pytest
from unittest.mock import MagicMock, patch
from camels_attrs.extractor import CamelsExtractor
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon

def test_extractor_initialization():
    extractor = CamelsExtractor('01031500')
    assert extractor.gauge_id == '01031500'
    assert extractor.climate_start == '1990-01-01'
    assert extractor.attributes == {}

@patch('camels_attrs.extractor.delineate_watershed')
def test_delineate(mock_delineate, sample_watershed_gdf):
    # Setup mock return
    mock_delineate.return_value = (
        sample_watershed_gdf,
        sample_watershed_gdf.geometry.iloc[0],
        {'gauge_id': '01031500', 'gauge_name': 'Test Creek', 'gauge_lat': 40.0, 'gauge_lon': -80.0},
        100.0
    )
    
    extractor = CamelsExtractor('01031500')
    gdf = extractor.delineate()
    
    assert gdf is not None
    assert extractor.area_km2 == 100.0
    assert extractor.metadata['gauge_name'] == 'Test Creek'
    mock_delineate.assert_called_once_with('01031500')

@patch('camels_attrs.extractor.delineate_watershed')
@patch('camels_attrs.extractor.extract_topographic_attributes')
@patch('camels_attrs.extractor.fetch_climate_data')
@patch('camels_attrs.extractor.compute_climate_indices')
def test_extract_all_mocked(mock_compute_clim, mock_fetch_clim, mock_topo, mock_delineate, sample_watershed_gdf):
    # Setup mocks
    mock_delineate.return_value = (
        sample_watershed_gdf,
        sample_watershed_gdf.geometry.iloc[0],
        {'gauge_id': '01031500', 'gauge_name': 'Test Creek', 'gauge_lat': 40.0, 'gauge_lon': -80.0},
        100.0
    )
    mock_topo.return_value = {'elev_mean': 500.0}
    mock_fetch_clim.return_value = MagicMock()
    mock_compute_clim.return_value = {'p_mean': 2.5}
    
    # We mock other modules to avoid errors or long execution
    with patch('camels_attrs.extractor.extract_soil_attributes', return_value={}), \
         patch('camels_attrs.extractor.extract_vegetation_attributes', return_value={}), \
         patch('camels_attrs.extractor.extract_geological_attributes', return_value={}), \
         patch('camels_attrs.extractor.extract_hydrological_signatures', return_value={}):
        
        extractor = CamelsExtractor('01031500')
        attrs = extractor.extract_all(verbose=False)
        
        assert attrs['gauge_id'] == '01031500'
        assert attrs['elev_mean'] == 500.0
        assert attrs['p_mean'] == 2.5
        assert attrs['_status']['watershed'] is True
        assert attrs['_status']['topography'] is True

def test_to_dataframe():
    extractor = CamelsExtractor('01031500')
    extractor.attributes = {'gauge_id': '01031500', 'val': 1}
    df = extractor.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]['gauge_id'] == '01031500'
