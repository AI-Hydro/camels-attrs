"""camels-attrs 2.0.0: slope_fdc and baseflow_index follow the CAMELS-US v1.2 definitions.

Locked references: CAMELS-US v1.2 ``camels_hydro.txt`` (Zenodo 15529996, md5-verified; values
quoted in docs/vision-2040/evidence/signature-definitions-1 of the AI-Hydro workspace).
Streamflow fixtures are USGS daily series, WY1990-2009, 7305 days (see
tests/fixtures/signature_definitions/README.md). Offline.
"""
import hashlib
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from camels_attrs import hydrology as hy
from camels_attrs.baseflow import WarmupBiasWarning, lyne_hollick_ladson2013
from camels_attrs.hydrology import (
    SIGNATURE_DEFINITIONS,
    compute_baseflow_index,
    compute_slope_fdc_camels,
    extract_hydrological_signatures,
)

FIX = Path(__file__).parent / "fixtures" / "signature_definitions"
SHA = {
    "served_streamflow_01013500.csv": "683ccb1619efe82e3c124f8a540bdc9af93269af12efe5c3681d88d9438d359a",
    "served_streamflow_01031500.csv": "e01921cdd60e1750e3d27323aea4f8dc32632976c68fd0e961a3b64a444cbccc",
}
# camels_hydro.txt rows
CAMELS = {
    "01013500": {"slope_fdc": 1.52821853538976, "baseflow_index": 0.585225955779508,
                 "high_q_freq": 6.1, "low_q_freq": 41.35, "zero_q_freq": 0.0},
    "01031500": {"slope_fdc": 1.49401920331253, "baseflow_index": 0.445090526012048,
                 "high_q_freq": 18.9, "low_q_freq": 94.8, "zero_q_freq": 0.0},
}
# Documented outputs of the aihydro-watershed 0.2.0 kernel (evidence results_bfi_check.txt,
# "ladson2013 (BFI.R port)"): this port must agree with it, not merely with CAMELS.
WATERSHED_020_BFI = {"01013500": 0.5852258906480455, "01031500": 0.445091368746438}
SAWICZ_01013500 = 2.6965378024424225  # pre-2.0.0 camels-attrs slope_fdc (log-space)
AREA_KM2 = 1000.0  # every statistic tested here is scale-invariant


def _q(gauge):
    f = FIX / ("served_streamflow_%s.csv" % gauge)
    assert hashlib.sha256(f.read_bytes()).hexdigest() == SHA[f.name]
    return pd.read_csv(f, parse_dates=["date"]).set_index("date")["q_cms"]


@pytest.mark.parametrize("gauge", ["01013500", "01031500"])
def test_slope_fdc_matches_camels_file(gauge):
    out = compute_slope_fdc_camels(_q(gauge).to_numpy())
    assert out["slope_fdc"] == pytest.approx(CAMELS[gauge]["slope_fdc"], rel=1e-6)


def test_slope_fdc_sawicz2011_is_the_old_log_value():
    out = compute_slope_fdc_camels(_q("01013500").to_numpy())
    assert out["slope_fdc_sawicz2011"] == pytest.approx(SAWICZ_01013500, rel=1e-9)


def test_slope_fdc_zero_structure():
    # >= 66% zero days: Q33 = Q66 = 0 -> exactly 0 (finite); the log form drops zeros.
    q = np.concatenate([np.zeros(700), np.linspace(1, 50, 300)])
    out = compute_slope_fdc_camels(q)
    assert out["slope_fdc"] == 0.0
    # zero mean -> undefined
    assert np.isnan(compute_slope_fdc_camels(np.zeros(500))["slope_fdc"])
    # fewer than 100 values -> undefined
    assert np.isnan(compute_slope_fdc_camels(np.linspace(1, 2, 99))["slope_fdc"])


@pytest.mark.parametrize("gauge", ["01013500", "01031500"])
def test_baseflow_index_matches_camels_file(gauge):
    bfi = compute_baseflow_index(_q(gauge))
    assert bfi == pytest.approx(CAMELS[gauge]["baseflow_index"], rel=1e-5)
    # ... and the watershed 0.2.0 kernel, to numerical identity
    assert bfi == pytest.approx(WATERSHED_020_BFI[gauge], rel=1e-9)


def test_kernel_recipe_edge_cases():
    q = _q("01013500").to_numpy()
    assert np.all(lyne_hollick_ladson2013(q) >= 0)
    with pytest.raises(ValueError):
        lyne_hollick_ladson2013(q[:30])
    with pytest.warns(WarmupBiasWarning):
        lyne_hollick_ladson2013(q[:200])
    # NaN gap: days outside a run of > 30 finite values stay NaN, segments are filtered separately
    x = q[:800].copy()
    x[400:405] = np.nan
    x[500:510] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", WarmupBiasWarning)
        bf = lyne_hollick_ladson2013(x)
    assert np.isnan(bf[400:405]).all() and np.isnan(bf[500:510]).all()
    assert np.isfinite(bf[:400]).all() and np.isfinite(bf[510:]).all()
    assert bf[:400] == pytest.approx(lyne_hollick_ladson2013(x[:400]))


# The neutral provenance string (PD-F2), verbatim. "<=" is ASCII on purpose.
M2_PROVENANCE = (
    "slope of the flow duration curve between the 33rd and 66th percentiles, mean-normalised, as in the CAMELS-US v1.2 distributed file (naddor/camels@88e7a0d2d2 hydro/hydro_signatures.R:97). Reproduces the file at <=2.3e-7 relative on 01013500 and 01031500, and 9.7e-5 on 01516500. Its zero-structure prediction holds on all 671 basins. Not proven to be the script that produced the file."
)


def test_slope_fdc_value_unchanged_by_rewording_01013500():
    # pinned from the 2.0.0 release code before the 2.0.1 wording-only change
    out = compute_slope_fdc_camels(_q("01013500").to_numpy())
    assert out["slope_fdc"] == pytest.approx(1.5282185220180324, rel=1e-12)


def test_m2_provenance_string_is_verbatim():
    assert SIGNATURE_DEFINITIONS["slope_fdc"]["source"] == M2_PROVENANCE


def test_sawicz_threshold_is_the_pre_2_0_0_one():
    # 1.x required len(q_pos) > 100 positive days: 100 positive days -> NaN, 101 -> finite
    assert np.isnan(compute_slope_fdc_camels(np.linspace(1, 2, 100))["slope_fdc_sawicz2011"])
    assert np.isfinite(compute_slope_fdc_camels(np.linspace(1, 2, 101))["slope_fdc_sawicz2011"])


def test_signature_definitions_carry_source_and_formula():
    d = SIGNATURE_DEFINITIONS
    src = d["slope_fdc"]["source"]
    assert "naddor/camels@88e7a0d2d2 hydro/hydro_signatures.R:97" in src
    assert "Not proven to be the script that produced the file" in src
    assert d["slope_fdc"]["log_transform"] is False and d["slope_fdc_sawicz2011"]["log_transform"] is True
    for k in ("formula", "quantile_type", "zero_handling"):
        assert d["slope_fdc"][k]
    assert d["baseflow_index"]["parameters"] == {"alpha": 0.925, "passes": 3, "n_reflect": 30}
    assert d["high_q_freq"]["units"] == d["low_q_freq"]["units"] == "days/year"
    assert d["zero_q_freq"]["units"] == "fraction" and "q <= 0" in d["zero_q_freq"]["formula"]
    assert hy.HYDRO_SIGNATURE_UNITS["high_q_freq"] == hy.HYDRO_SIGNATURE_UNITS["low_q_freq"] == "days/yr"


@pytest.fixture
def run_extractor(monkeypatch):
    side = (AREA_KM2 * 1e6) ** 0.5
    gdf = gpd.GeoDataFrame(geometry=[box(0, 0, side, side)], crs="EPSG:5070")

    def run(q_cms):
        df = pd.DataFrame({"q_cms": q_cms, "q_native": q_cms, "approval_status": "Approved"})
        monkeypatch.setattr(hy, "fetch_streamflow_data", lambda *a, **k: df)
        monkeypatch.setattr(hy, "fetch_precipitation_data", lambda *a, **k: None)
        return extract_hydrological_signatures("00000000", gdf)

    return run


@pytest.mark.parametrize("gauge", ["01013500", "01031500"])
def test_extractor_reproduces_camels_definitions(run_extractor, gauge):
    out = run_extractor(_q(gauge))
    assert out["hydro_status"] == "ok"
    ref = CAMELS[gauge]
    assert out["slope_fdc"] == pytest.approx(ref["slope_fdc"], rel=1e-6)
    assert out["baseflow_index"] == pytest.approx(ref["baseflow_index"], rel=1e-5)
    # days/yr, days/yr, fraction: CAMELS prints these to 2 decimals
    assert out["high_q_freq"] == pytest.approx(ref["high_q_freq"], abs=0.05)
    assert out["low_q_freq"] == pytest.approx(ref["low_q_freq"], abs=0.05)
    assert out["zero_q_freq"] == ref["zero_q_freq"]
    assert "slope_fdc_sawicz2011" in out


def test_zero_q_freq_counts_non_positive_days(run_extractor):
    q = _q("01013500").copy()
    q.iloc[100:110] = 0.0
    out = run_extractor(q)
    assert out["zero_q_freq"] == pytest.approx(10 / len(q))
