"""Offline contract tests for camels_attrs.usgs_daily (Wave U / U3c).

``usgs_daily._http_get`` is replaced by a replay of bodies recorded from the live
Water Data API (tests/fixtures/usgs_waterdata, sha256-verified against index.json).
"""
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

import numpy as np
import pandas as pd
import pytest

from camels_attrs import usgs_daily as ud

FIX = Path(__file__).parent / "fixtures" / "usgs_waterdata"
LEG = FIX / "legacy_waterservices"


def _raw(path: Path) -> bytes:
    b = path.read_bytes()
    return gzip.decompress(b) if path.suffix == ".gz" else b


def _entries(root: Path):
    return {e["file"]: e for e in json.loads((root / "index.json").read_text())["entries"]}


IDX, LIDX = _entries(FIX), _entries(LEG)


def body(prefix: str) -> bytes:
    f = next(k for k in IDX if k.startswith(prefix))
    return _raw(FIX / f)


def _key(url, params=None):
    if params:
        url = url + "?" + urlencode(params)
    u = urlparse(url)
    return (u.hostname, u.path, tuple(sorted(parse_qsl(u.query))))


def _recorded_key(prefix):
    f = next(k for k in IDX if k.startswith(prefix))
    return _key(IDX[f]["url"])


@pytest.fixture
def replay(monkeypatch):
    """Install a replay seam; returns (register, calls)."""
    table, calls = {}, []

    def reg(prefix, status=200, data=None):
        table[_recorded_key(prefix)] = (status, data if data is not None else body(prefix))

    def fake(url, params=None):
        ud._check_url(url)
        calls.append(_key(url, params))
        k = _key(url, params)
        if k not in table:
            raise AssertionError(f"unrecorded request {k}")
        return table[k]

    monkeypatch.setattr(ud, "_http_get", fake)
    return reg, calls


def test_fixture_hashes():
    for root, idx in ((FIX, IDX), (LEG, LIDX)):
        for name, e in idx.items():
            p = root / name
            if p.exists():
                assert hashlib.sha256(_raw(p)).hexdigest() == e["body_sha256"], name


def test_unit_constant_exact():
    assert ud.CFS_TO_M3S == 0.028316846592


def test_wy1990_2009_parse(replay):
    reg, _ = replay
    reg("001")
    df = ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
    doc = json.loads(body("001"))
    assert len(df) == len(doc["features"]) == 7305
    assert list(df.columns) == ["q_cms", "q_native", "approval_status"]
    assert df.index.is_monotonic_increasing and df.index.tz is None
    assert df.loc["1989-10-01", "q_native"] == 300.0
    assert df.loc["1989-10-01", "q_cms"] == 300.0 * 0.028316846592
    assert np.isfinite(df["q_cms"]).all()
    assert set(df["approval_status"]) == {"Approved"}
    assert df.attrs["units_native"] == "ft^3/s"


def test_provisional_approval_column(replay):
    reg, _ = replay
    reg("006")
    df = ud.fetch_daily_discharge("USGS-01013500", "2026-06-19", "2026-10-17")
    assert "Provisional" in set(df["approval_status"])


def test_paging(replay, monkeypatch):
    reg, calls = replay
    monkeypatch.setattr(ud, "PAGE_LIMIT", 2000)
    # page 1 keyed by params; later pages by their rel=next hrefs
    reg("037")
    for pfx in ("038", "039", "040"):
        reg(pfx)
    df = ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
    assert len(calls) == 4
    assert len(df) == 7305
    full = ud.fetch_daily_discharge  # noqa: F841
    # identical content to the unpaged single-body fixture
    reg("001")
    monkeypatch.setattr(ud, "PAGE_LIMIT", 10000)
    one = ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
    pd.testing.assert_frame_equal(df, one)


def test_no_next_host_or_scheme_escape(replay, monkeypatch):
    reg, _ = replay
    doc = json.loads(body("037"))
    for bad in ("http://api.waterdata.usgs.gov/x", "https://evil.example.com/x"):
        d = json.loads(json.dumps(doc))
        for l in d["links"]:
            if l["rel"] == "next":
                l["href"] = bad
        reg("037", data=json.dumps(d).encode())
        monkeypatch.setattr(ud, "PAGE_LIMIT", 2000)
        with pytest.raises(ud.UsgsDailyError) as e:
            ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
        assert e.value.code in ("USGS_URL_REFUSED", "USGS_HOST_NOT_ALLOWED")


def test_empty_is_error(replay):
    reg, _ = replay
    f = next(k for k in IDX if k.startswith("007"))
    table_key = _key(IDX[f]["url"])
    # site 00000000 -> 8 digits, valid format; recorded window 2020
    reg("007")
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("00000000", "2020-01-01", "2020-12-31")
    assert e.value.code == "USGS_NO_DATA"
    assert table_key  # key exists


def _mutated(prefix, fn):
    d = json.loads(body(prefix))
    fn(d["features"])
    return json.dumps(d).encode()


@pytest.mark.parametrize("value,code", [
    ("-999999", "USGS_VALUE_SENTINEL"),
    ("-999999.0", "USGS_VALUE_SENTINEL"),
    ("NaN", "USGS_VALUE_UNPARSEABLE"),
    ("Infinity", "USGS_VALUE_UNPARSEABLE"),
    ("1e999", "USGS_VALUE_UNPARSEABLE"),
    ("12abc", "USGS_VALUE_UNPARSEABLE"),
    (" 5", "USGS_VALUE_UNPARSEABLE"),
    ("", "USGS_VALUE_UNPARSEABLE"),
    (5, "USGS_VALUE_UNPARSEABLE"),
])
def test_bad_values_refused(replay, value, code):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda f: f[3]["properties"].__setitem__("value", value)))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == code


def test_unknown_unit_refused(replay):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda fs: [f["properties"].__setitem__("unit_of_measure", "m^3/s") for f in fs]))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_UNIT_UNKNOWN"


def test_ft3s_alias_accepted(replay):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda fs: [f["properties"].__setitem__("unit_of_measure", "ft3/s") for f in fs]))
    df = ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert (df["q_cms"] == df["q_native"] * 0.028316846592).all()


def test_unknown_approval_and_dup_and_multi_series(replay):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda f: f[0]["properties"].__setitem__("approval_status", "Weird")))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_APPROVAL_UNKNOWN"
    reg("006", data=_mutated("006", lambda f: f[1]["properties"].__setitem__("time", f[0]["properties"]["time"])))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_DUPLICATE_TIME"
    reg("006", data=_mutated("006", lambda f: f[1]["properties"].__setitem__("time_series_id", "other")))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_MULTIPLE_SERIES"


def test_null_values_dropped_and_counted(replay):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda f: f[2]["properties"].__setitem__("value", None)))
    df = ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert df.attrs["null_dropped"] == 1 and df["q_cms"].notna().all()


def test_non_200_is_error(replay):
    reg, _ = replay
    reg("006", status=302, data=b"")
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_HTTP_ERROR"


def test_bad_site_refused():
    with pytest.raises(ud.UsgsDailyError):
        ud.fetch_daily_discharge("abc", "2020-01-01", "2020-01-02")


def test_fetch_streamflow_data_series(replay):
    from camels_attrs.hydrology import fetch_streamflow_data
    reg, _ = replay
    reg("001")
    s = fetch_streamflow_data("01013500", "1989-10-01", "2009-09-30")
    assert isinstance(s, pd.DataFrame) and len(s) == 7305
    assert s["approval_status"].iloc[0] == "Approved"


def test_legacy_parity(replay):
    """Same site/window: Water Data API values equal the legacy NWIS dv bytes (ft3/s)."""
    reg, _ = replay
    reg("001")
    df = ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
    leg = json.loads(_raw(LEG / "037_legacy_dv_01013500.json"))
    ts = leg["value"]["timeSeries"]
    assert len(ts) == 1 and ts[0]["variable"]["unit"]["unitCode"] == "ft3/s"
    rows = ts[0]["values"][0]["value"]
    idx = pd.to_datetime([r["dateTime"] for r in rows])
    lv = pd.Series([float(r["value"]) for r in rows], index=idx)
    assert (lv != ud.LEGACY_SENTINEL).all()
    assert len(lv) == len(df)
    assert (lv.index == df.index).all()
    assert np.array_equal(lv.values, df["q_native"].values)
    assert np.array_equal(lv.values * 0.028316846592, df["q_cms"].values)


def test_api_key_header_only_and_no_redirect(monkeypatch):
    import requests
    seen = {}

    class R:
        status_code = 200
        content = b"{}"

    def fake_get(url, params=None, headers=None, timeout=None, allow_redirects=True):
        seen.update(url=url, headers=dict(headers), allow_redirects=allow_redirects)
        return R()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("API_USGS_PAT", "SECRET-TOKEN")
    ud._http_get(ud.BASE + "/collections/daily/items", {"a": "b"})
    assert seen["headers"]["X-Api-Key"] == "SECRET-TOKEN"
    assert seen["allow_redirects"] is False
    assert "SECRET-TOKEN" not in seen["url"]
    assert [k for k, v in seen["headers"].items() if v == "SECRET-TOKEN"] == ["X-Api-Key"]
    monkeypatch.delenv("API_USGS_PAT")
    ud._http_get(ud.BASE + "/collections/daily/items")
    assert "X-Api-Key" not in seen["headers"]
    with pytest.raises(ud.UsgsDailyError):
        ud._http_get("https://evil.example.com/x")


# ---- review round: raw-body numerics, real-seam paging, strictness, hydrology status ----

def test_provisional_numeric_vs_raw_body(replay):
    reg, _ = replay
    reg("006")
    df = ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    feats = json.loads(body("006"))["features"]
    raw = {f["properties"]["time"]: f["properties"] for f in feats if f["properties"]["value"] is not None}
    assert len(df) == len(raw)
    for t, row in df.iterrows():
        p = raw[t.strftime("%Y-%m-%d")]
        assert row["q_native"] == float(p["value"])
        assert row["q_cms"] == float(p["value"]) * 0.028316846592
        assert row["approval_status"] == p["approval_status"]


def _fake_requests(monkeypatch, pages):
    """Mock requests.get below _http_get so the real _check_url runs on every hop."""
    import requests
    seen = []

    class R:
        def __init__(self, c):
            self.status_code, self.content = 200, c

    def fake_get(url, params=None, headers=None, timeout=None, allow_redirects=True):
        seen.append(url)
        return R(pages[len(seen) - 1])

    monkeypatch.setattr(requests, "get", fake_get)
    return seen


def test_real_seam_paging_checks_next(monkeypatch):
    monkeypatch.setattr(ud, "PAGE_LIMIT", 2000)
    pages = [body(p) for p in ("037", "038", "039", "040")]
    seen = _fake_requests(monkeypatch, pages)
    assert len(ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")) == 7305
    assert len(seen) == 4
    d = json.loads(pages[0])
    for l in d["links"]:
        if l["rel"] == "next":
            l["href"] = "https://evil.example.com/x"
    seen = _fake_requests(monkeypatch, [json.dumps(d).encode()])
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "1989-10-01", "2009-09-30")
    assert e.value.code == "USGS_HOST_NOT_ALLOWED" and len(seen) == 1


def test_transport_and_429(monkeypatch):
    import requests

    def boom(*a, **k):
        raise requests.exceptions.ChunkedEncodingError("x")
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(ud.UsgsDailyError) as e:
        ud._http_get(ud.BASE + "/collections/daily/items")
    assert e.value.code == "USGS_TRANSPORT"
    monkeypatch.setattr(ud, "_http_get", lambda url, params=None: (429, b""))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2020-01-01", "2020-01-02")
    assert e.value.code == "USGS_RATE_LIMITED"


def test_unicode_digits_and_missing_time_refused(replay):
    reg, _ = replay
    reg("006", data=_mutated("006", lambda f: f[0]["properties"].__setitem__("value", "١٢")))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_VALUE_UNPARSEABLE"
    reg("006", data=_mutated("006", lambda f: f[0]["properties"].pop("time")))
    with pytest.raises(ud.UsgsDailyError) as e:
        ud.fetch_daily_discharge("01013500", "2026-06-19", "2026-10-17")
    assert e.value.code == "USGS_BAD_SCHEMA"
    with pytest.raises(ud.UsgsDailyError):
        ud.fetch_daily_discharge("١" * 8, "2020-01-01", "2020-01-02")


def test_crosscheck_script_runs():
    import subprocess, sys, os
    adapter = Path("/Users/mgalib/Documents/AI-Hydro/.worktrees/v2040-u1b")
    adapter = Path(os.environ.get("AIHYDRO_DATA_PATH", adapter))
    if not (adapter / "aihydro_data" / "sources" / "usgs_waterdata.py").exists():
        pytest.skip("aihydro-data adapter not available")
    script = Path(__file__).parents[1] / "scripts" / "crosscheck_adapter.py"
    r = subprocess.run([sys.executable, str(script)], env={**os.environ, "PYTHONPATH": str(adapter)},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    assert "OK:" in r.stdout


# hydrology status
import geopandas as gpd
from shapely.geometry import box


def _gdf():
    return gpd.GeoDataFrame(geometry=[box(-69, 47, -68.5, 47.5)], crs="EPSG:4326")


def test_hydro_refused_status(monkeypatch, caplog):
    import camels_attrs.hydrology as h

    def refuse(*a, **k):
        raise ud.UsgsDailyError("USGS_VALUE_SENTINEL", "sentinel")
    monkeypatch.setattr(h, "fetch_streamflow_data", refuse)
    with caplog.at_level("ERROR"):
        out = h.extract_hydrological_signatures("01013500", _gdf())
    assert out["hydro_status"] == "refused" and out["hydro_reason"] == "USGS_VALUE_SENTINEL"
    assert np.isnan(out["q_mean"])
    assert "USGS_VALUE_SENTINEL" in caplog.text


def test_hydro_insufficient_status(monkeypatch):
    import camels_attrs.hydrology as h
    df = pd.DataFrame({"q_cms": np.ones(100), "q_native": np.ones(100),
                       "approval_status": "Approved"}, index=pd.date_range("2000-01-01", periods=100))
    monkeypatch.setattr(h, "fetch_streamflow_data", lambda *a, **k: df)
    out = h.extract_hydrological_signatures("01013500", _gdf())
    assert out["hydro_status"] == "insufficient_data" and out["hydro_reason"] == "LT_365_DAYS"


def test_hydro_ok_status_and_provisional_fraction(monkeypatch):
    import camels_attrs.hydrology as h
    idx = pd.date_range("2000-01-01", periods=800)
    ap = np.where(np.arange(800) < 200, "Provisional", "Approved")
    q = 1 + np.abs(np.sin(np.arange(800) / 20.0))
    df = pd.DataFrame({"q_cms": q, "q_native": q, "approval_status": ap}, index=idx)
    df.attrs["null_dropped"] = 3
    monkeypatch.setattr(h, "fetch_streamflow_data", lambda *a, **k: df)
    monkeypatch.setattr(h, "fetch_precipitation_data", lambda *a, **k: None)
    out = h.extract_hydrological_signatures("01013500", _gdf())
    assert out["hydro_status"] == "ok", out
    assert out["hydro_provisional_fraction"] == 0.25 and out["hydro_null_dropped"] == 3


def test_extractor_flags_non_ok(monkeypatch):
    import camels_attrs.extractor as ex
    src = Path(ex.__file__).read_text()
    assert 'hydro_attrs.get("hydro_status") == "ok"' in src


def test_hydro_error_status(monkeypatch):
    import camels_attrs.hydrology as h
    idx = pd.date_range("2000-01-01", periods=800)
    df = pd.DataFrame({"q_cms": np.ones(800), "q_native": np.ones(800),
                       "approval_status": "Approved"}, index=idx)
    monkeypatch.setattr(h, "fetch_streamflow_data", lambda *a, **k: df)

    def boom(*a, **k):
        raise ZeroDivisionError("x")
    monkeypatch.setattr(h, "fetch_precipitation_data", boom)
    out = h.extract_hydrological_signatures("01013500", _gdf())
    assert out["hydro_status"] == "error" and out["hydro_reason"] == "COMPUTE_ERROR: ZeroDivisionError"
