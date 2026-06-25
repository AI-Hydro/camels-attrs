from __future__ import annotations

import numpy as np
import xarray as xr

from camels_attrs.topography import _slope_percent_from_dem


def test_slope_percent_from_dem_is_local_finite_difference():
    dem = xr.DataArray(
        np.array(
            [
                [0.0, 10.0, 20.0],
                [0.0, 10.0, 20.0],
                [0.0, 10.0, 20.0],
            ]
        ),
        dims=("y", "x"),
        coords={"y": [0.0, 10.0, 20.0], "x": [0.0, 10.0, 20.0]},
    )

    slope = _slope_percent_from_dem(dem)

    assert slope.shape == (3, 3)
    assert np.allclose(slope, 100.0)
