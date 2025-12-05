import sys
from unittest.mock import MagicMock

# Mock cartopy before it's imported by the package
sys.modules["cartopy"] = MagicMock()
sys.modules["cartopy.crs"] = MagicMock()
sys.modules["cartopy.feature"] = MagicMock()

import pytest
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, Point

@pytest.fixture
def sample_q_series():
    """Create a sample daily streamflow series (mm/day)."""
    dates = pd.date_range(start="2000-01-01", end="2002-12-31", freq="D")
    # Generate synthetic flow: baseflow + some peaks
    q = np.ones(len(dates)) * 1.0
    # Add seasonal signal
    q += np.sin(np.linspace(0, 4*np.pi, len(dates))) * 0.5
    # Add random noise/peaks
    np.random.seed(42)
    q += np.random.exponential(scale=0.5, size=len(dates))
    q = np.maximum(q, 0.0)  # Ensure non-negative
    return pd.Series(q, index=dates)

@pytest.fixture
def sample_p_series():
    """Create a sample daily precipitation series (mm/day)."""
    dates = pd.date_range(start="2000-01-01", end="2002-12-31", freq="D")
    np.random.seed(43)
    p = np.random.exponential(scale=2.0, size=len(dates))
    # Add some dry days
    p[p < 0.5] = 0.0
    return pd.Series(p, index=dates)

@pytest.fixture
def sample_watershed_gdf():
    """Create a sample watershed GeoDataFrame."""
    # Create a simple square polygon
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = gpd.GeoDataFrame({'geometry': [poly], 'gauge_id': ['01000000']}, crs="EPSG:4326")
    return gdf
