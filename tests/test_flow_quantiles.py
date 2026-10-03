"""Regression for defect P2-D0: q5 / q95 follow CAMELS (Addor et al. 2017, Table 3)."""
from __future__ import annotations

import numpy as np

from camels_attrs.hydrology import compute_flow_quantiles_camels


def test_q5_is_low_flow_q95_is_high_flow():
    # 1..1000: linear-interpolated quantiles are exactly 1 + p * 999.
    out = compute_flow_quantiles_camels(np.arange(1, 1001, dtype=float))
    assert abs(out["q5"] - 50.95) < 1e-9
    assert abs(out["q95"] - 950.05) < 1e-9
    assert out["q5"] < out["q95"]


def test_matches_numpy_quantiles_on_skewed_data():
    q = np.random.default_rng(11).lognormal(0.0, 1.2, size=3000)
    out = compute_flow_quantiles_camels(q)
    assert out["q5"] == np.quantile(q, 0.05)
    assert out["q95"] == np.quantile(q, 0.95)
