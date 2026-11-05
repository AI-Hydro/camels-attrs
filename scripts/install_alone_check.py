"""Install-alone task for camels-attrs.

Run by ``.github/workflows/install-alone.yml`` with the *venv's* interpreter,
from a directory outside the checkout, after installing ONLY the built wheel
and its PyPI dependencies. No AI-Hydro package is present (camels-attrs sits
beside the stack, not in it) and every socket connection is refused.

Task: CAMELS flow signatures with analytic expectations, from synthetic series.
  1. ``compute_flow_quantiles_camels`` on 1..1000 gives q5 = 50.95 and
     q95 = 950.05 (linear-interpolated quantiles are exactly 1 + 999 p);
  2. streamflow equal to 0.4 x precipitation gives runoff_ratio = 0.4 and
     stream_elas = 1 (the elasticity of a proportional response);
  3. a constant-flow record has a baseflow index of ~1;
  4. the ``camels-extract`` console script is installed.

Nothing here is a hydrological result; every expectation is derived by hand
from the definition, and the data are synthetic.
"""
from __future__ import annotations

import math
import os
import socket
import subprocess
import sys


def _block_network() -> None:
    def refuse(*_a, **_k):
        raise RuntimeError("network access attempted during an install-alone check")

    socket.socket.connect = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.getaddrinfo = refuse  # type: ignore[assignment]


def main() -> int:
    import camels_attrs

    where = camels_attrs.__file__
    assert "site-packages" in where, f"imported from a source tree, not the wheel: {where}"

    exe = os.path.join(os.path.dirname(sys.executable), "camels-extract")
    subprocess.run([exe, "--help"], check=True, capture_output=True, text=True)

    _block_network()
    import numpy as np
    import pandas as pd

    from camels_attrs.hydrology import (
        compute_baseflow_index,
        compute_flow_quantiles_camels,
        compute_water_balance_camels,
    )

    qs = compute_flow_quantiles_camels(np.arange(1, 1001, dtype=float))
    assert math.isclose(qs["q5"], 50.95, abs_tol=1e-9), qs
    assert math.isclose(qs["q95"], 950.05, abs_tol=1e-9), qs

    days = pd.date_range("2000-10-01", "2007-09-30", freq="D")  # 7 water years
    wy = np.where(days.month >= 10, days.year + 1, days.year)
    rng = np.random.default_rng(3)
    # Year-to-year variation in precipitation so the elasticity is defined.
    p = pd.Series(rng.gamma(2.0, 1.0, len(days)) * (1.0 + 0.2 * (wy - wy.min())), index=days)
    q = 0.4 * p
    wb = compute_water_balance_camels(q, p)
    assert math.isclose(wb["runoff_ratio"], 0.4, rel_tol=1e-12), wb
    assert math.isclose(wb["stream_elas"], 1.0, rel_tol=1e-9), wb

    bfi = compute_baseflow_index(pd.Series(5.0, index=days))
    assert bfi > 0.99, bfi

    print(f"camels-attrs {camels_attrs.__version__}: install-alone task OK ({where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
