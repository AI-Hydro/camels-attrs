"""Test-only cross-check (NOT a package dependency): camels_attrs.usgs_daily vs the
aihydro-data USGS Water Data adapter on the same recorded fixture.

    PYTHONPATH=<aihydro-data checkout> python scripts/crosscheck_adapter.py
Offline; both transports are replaced by a replay of tests/fixtures/usgs_waterdata.
"""
import gzip, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camels_attrs import usgs_daily as ud
from aihydro_data.sources import usgs_waterdata as uw

FIX = ROOT / "tests" / "fixtures" / "usgs_waterdata"
e = next(x for x in json.loads((FIX / "index.json").read_text())["entries"] if x["file"].startswith("001"))
data = gzip.decompress((FIX / e["file"]).read_bytes())

ud._http_get = lambda url, params=None: (200, data)
uw._http_get = lambda url, params=None, headers=None: (200, {}, data)

mine = ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
theirs = uw.get_daily("01013500", "1989-10-01", "2009-09-30").frame
assert len(mine) == len(theirs) == 7305
assert (mine.index == theirs["time"]).all()
assert np.array_equal(mine["q_cms"].values, theirs["value_m3s"].values), "q_cms != adapter value_m3s"
assert (mine["approval_status"].values == theirs["approval_status"].values).all()
print("OK: q_cms == adapter value_m3s exactly for", len(mine), "days; approval_status equal; adapter from", uw.__file__)
