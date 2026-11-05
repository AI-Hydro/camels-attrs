"""slope_mean / slope_std are m/km (tan x 1000), the CAMELS unit; they were percent through 2.0.1.

Offline: py3dep.get_dem is replaced by an analytic inclined plane on an EPSG:4326 grid, which the
extractor reprojects to EPSG:5070 and differentiates with xrspatial (Horn). No network.
"""
import math

import numpy as np
import pytest
import xarray as xr
from pyproj import Transformer
from shapely.geometry import box

rioxarray = pytest.importorskip("rioxarray")
py3dep = pytest.importorskip("py3dep")
pytest.importorskip("xrspatial")

import camels_attrs.topography as topo  # noqa: E402


def _plane_4326(t, lat, step_arcsec=1.0, size_deg=0.12, lon=-100.0):
    """Plane of true slope t in the EPSG:5070 metric frame (the frame the extractor differentiates in)."""
    step = step_arcsec / 3600.0
    n = int(round(size_deg / step))
    lons = lon + step * np.arange(n)
    lats = (lat + step * np.arange(n))[::-1]
    LON, LAT = np.meshgrid(lons, lats)
    E, N = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform(LON, LAT)
    th = math.radians(35.0)
    z = 300.0 + t * ((E - E.min()) * math.cos(th) + (N - N.min()) * math.sin(th))
    da = xr.DataArray(z, dims=("y", "x"), coords={"y": lats, "x": lons})
    return da.rio.write_crs("EPSG:4326")


@pytest.fixture
def plane(monkeypatch):
    def _install(t, lat):
        monkeypatch.setattr(topo.py3dep, "get_dem", lambda geom, resolution=30: _plane_4326(t, lat))
    return _install


GEOM = box(-100.0, 35.0, -99.9, 35.1)


@pytest.mark.parametrize("lat", [0.0, 35.0, 47.0])
@pytest.mark.parametrize("t", [0.0723, 0.25])
def test_slope_mean_is_m_per_km_on_an_analytic_plane(plane, lat, t):
    plane(t, lat)
    out = topo.extract_topographic_attributes(GEOM)
    # 1000 t m/km; tolerance covers nearest-neighbour resampling onto the EPSG:5070 grid
    assert out["slope_mean"] == pytest.approx(1000.0 * t, rel=0.03)


def test_slope_is_ten_times_the_old_percent_value(plane):
    """Migration check: new value = 10 x the value 2.0.1 reported (same DEM, same kernel)."""
    import xrspatial

    t = 0.0723
    plane(t, 35.0)
    new = topo.extract_topographic_attributes(GEOM)
    dem = _plane_4326(t, 35.0).rio.reproject("EPSG:5070")
    old_percent = float((py3dep.deg2mpm(xrspatial.slope(dem)) * 100).mean().values)  # the 2.0.1 line
    assert new["slope_mean"] == pytest.approx(10.0 * old_percent, rel=1e-5)  # float32 raster


def test_slope_independent_of_pixel_size(monkeypatch):
    t = 0.0723
    vals = []
    for step in (0.5, 1.0, 2.4):
        monkeypatch.setattr(topo.py3dep, "get_dem",
                            lambda geom, resolution=30, s=step: _plane_4326(t, 35.0, step_arcsec=s, size_deg=0.2))
        vals.append(topo.extract_topographic_attributes(GEOM)["slope_mean"])
    assert max(vals) - min(vals) <= 0.04 * 1000 * t


def test_conversion_factor_is_the_camels_unit():
    assert topo.SLOPE_M_PER_KM_FACTOR == 1000.0  # tan [m/m] x 1000 = m/km = 10 x percent


def test_units_are_documented_as_m_per_km():
    doc = topo.extract_topographic_attributes.__doc__
    assert "m/km" in doc
    assert "slope_mean: mean slope (%)" not in doc
