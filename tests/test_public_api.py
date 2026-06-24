from __future__ import annotations

import pandas as pd

import camels_attrs
from camels_attrs import CamelsExtractor
from camels_attrs.timeseries import calculate_forcing_statistics, calculate_water_balance


def test_version_present():
    assert isinstance(camels_attrs.__version__, str)
    assert camels_attrs.__version__


def test_public_api_exports_are_importable_and_callable():
    for name in camels_attrs.__all__:
        obj = getattr(camels_attrs, name)
        assert callable(obj), f"{name} should be callable"


def test_camels_extractor_initializes_without_network():
    extractor = CamelsExtractor("01638500")

    assert extractor.gauge_id == "01638500"
    assert extractor.climate_start == "1990-01-01"
    assert extractor.hydro_end == "2020-12-31"
    assert extractor.attributes == {}


def test_forcing_statistics_and_water_balance_are_local_pure_computations():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2000-01-01", periods=366, freq="D"),
            "prcp_mm": [2.0] * 366,
            "pet_mm": [1.0] * 366,
            "tavg_C": [10.0] * 366,
            "tmax_C": [15.0] * 366,
            "tmin_C": [5.0] * 366,
            "srad_Wm2": [100.0] * 366,
        }
    )

    stats = calculate_forcing_statistics(df)
    water_balance = calculate_water_balance(df)

    assert stats["mean_annual_precip_mm"] > stats["mean_annual_pet_mm"]
    assert stats["aridity_index"] == 0.5
    assert water_balance.loc[2000, "water_surplus_mm"] == 366.0
