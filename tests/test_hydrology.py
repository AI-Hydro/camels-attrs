import pytest
import numpy as np
import pandas as pd
from camels_attrs.hydrology import (
    _year_series,
    _consecutive_event_lengths,
    _lyne_hollick_baseflow,
    compute_water_balance_camels,
    compute_timing_stats_camels
)

def test_year_series():
    dates = pd.to_datetime(["2000-09-30", "2000-10-01", "2001-01-01"])
    years = _year_series(dates, hydro_year_start_month=10)
    assert np.array_equal(years, [2000, 2001, 2001])

def test_consecutive_event_lengths():
    mask = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1])
    lengths = _consecutive_event_lengths(mask)
    assert lengths == [2, 1, 3]
    
    mask_empty = np.zeros(5)
    assert _consecutive_event_lengths(mask_empty) == []

def test_lyne_hollick_baseflow():
    q = np.array([10, 12, 15, 20, 15, 12, 10])
    bf = _lyne_hollick_baseflow(q, alpha=0.925, passes=3)
    
    # Baseflow should be <= streamflow
    assert np.all(bf <= q)
    # Baseflow should be non-negative
    assert np.all(bf >= 0)
    # Should be smoother (lower standard deviation)
    assert np.std(bf) < np.std(q)

def test_compute_water_balance_camels(sample_q_series, sample_p_series):
    stats = compute_water_balance_camels(sample_q_series, sample_p_series)
    
    assert "runoff_ratio" in stats
    assert "stream_elas" in stats
    
    # Runoff ratio should be between 0 and roughly 1 (can be >1 locally but usually <1)
    # Given our synthetic data, it should be reasonable
    rr = stats["runoff_ratio"]
    assert 0 <= rr <= 2.0  # Loose bound for synthetic data
    
    # Elasticity should be a float
    assert isinstance(stats["stream_elas"], float)

def test_compute_timing_stats_camels(sample_q_series):
    stats = compute_timing_stats_camels(sample_q_series)
    
    assert "hfd_mean" in stats
    assert "half_flow_date_std" in stats
    
    # HFD should be a day of year (1-366)
    if not np.isnan(stats["hfd_mean"]):
        assert 1 <= stats["hfd_mean"] <= 366
