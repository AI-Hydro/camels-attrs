"""Minimal, self-contained USGS Water Data API ``/daily`` client.

camels-attrs is the independent CONUS reference that aihydro-lsh is validated against,
so it deliberately does NOT import the aihydro-data adapter (plan Wave U, D4). This
module re-implements only what CAMELS-style extraction needs and is held to the same
recorded-fixture contract (tests/test_usgs_daily.py).

Contract (identical to the adapter's, so the two can be cross-checked):

* ``GET https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items`` with
  ``parameter_code=00060`` (discharge), ``statistic_id=00003`` (mean),
  ``monitoring_location_id=USGS-<site>``; follows ``rel=next`` links only if they are
  https on the allow-listed host; redirects are never followed.
* ``API_USGS_PAT`` (optional) is sent ONLY as the ``X-Api-Key`` header and never logged.
* Discharge is converted ft^3/s -> m^3/s with the exact factor 0.028316846592
  (1 ft = 0.3048 m). Any other unit is refused.
* Refused (raise :class:`UsgsDailyError`): the legacy ``-999999`` no-data sentinel,
  non-finite / unparseable values, unknown ``approval_status``, mixed units, duplicate
  dates, more than one time series, an empty result, non-200 statuses.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import pandas as pd

BASE = "https://api.waterdata.usgs.gov/ogcapi/v1"
_ALLOWED_HOSTS = frozenset({"api.waterdata.usgs.gov"})

# Exact by definition: 1 ft = 0.3048 m  =>  1 ft^3 = 0.028316846592 m^3.
CFS_TO_M3S = 0.028316846592
_UNIT_FACTORS = {"ft^3/s": CFS_TO_M3S, "ft3/s": CFS_TO_M3S}

LEGACY_SENTINEL = -999999.0
APPROVAL_CODES = {"Approved": "A", "Provisional": "P"}
PAGE_LIMIT = 10000
_MAX_PAGES = 200
_VALUE_RE = re.compile(r"-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?", re.ASCII)


class UsgsDailyError(RuntimeError):
    """Explicit, coded failure. Never an empty success."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https":
        raise UsgsDailyError("USGS_URL_REFUSED", f"refusing non-https URL (scheme {u.scheme!r})")
    if u.hostname not in _ALLOWED_HOSTS:
        raise UsgsDailyError("USGS_HOST_NOT_ALLOWED", f"refusing request to {u.hostname!r}")


def _http_get(url: str, params: Optional[Mapping[str, Any]] = None):
    """The ONLY network call in this module (the test seam). Returns (status, body bytes).

    https + host allow-list are enforced per request; redirects are never followed
    (a 3xx is returned and treated as an error) so the API key cannot leave the host."""
    import requests

    _check_url(url)
    headers = {"User-Agent": "camels-attrs/usgs_daily", "Accept": "application/json"}
    key = os.environ.get("API_USGS_PAT")
    if key:
        headers["X-Api-Key"] = key
    try:
        r = requests.get(url, params=params, headers=headers, timeout=120, allow_redirects=False)
    except requests.exceptions.Timeout as e:
        raise UsgsDailyError("USGS_TIMEOUT", "timeout talking to api.waterdata.usgs.gov") from e
    except requests.exceptions.ConnectionError as e:
        raise UsgsDailyError("USGS_UNREACHABLE", "cannot reach api.waterdata.usgs.gov") from e
    except requests.exceptions.RequestException as e:
        raise UsgsDailyError("USGS_TRANSPORT", f"transport failure: {type(e).__name__}") from e
    return r.status_code, r.content


def _site_id(site: str) -> str:
    s = str(site).strip()
    if s.upper().startswith("USGS-"):
        s = s[5:]
    if not re.fullmatch(r"[0-9]{8,15}", s, re.ASCII):
        raise UsgsDailyError("USGS_SITE_INVALID", f"{site!r} is not an 8-15 digit USGS site number")
    return f"USGS-{s}"


def _parse_value(v: Any, when: Any) -> float:
    if not isinstance(v, str) or not _VALUE_RE.fullmatch(v):
        raise UsgsDailyError("USGS_VALUE_UNPARSEABLE", f"value {v!r} at {when} is not a plain decimal string")
    x = float(v)
    if not math.isfinite(x):
        raise UsgsDailyError("USGS_VALUE_UNPARSEABLE", f"value {v!r} at {when} is not finite")
    if x == LEGACY_SENTINEL:
        raise UsgsDailyError("USGS_VALUE_SENTINEL", f"value {v!r} at {when} is the legacy no-data sentinel")
    return x


def _get_json(url: str, params: Optional[Mapping[str, Any]]) -> dict:
    import json

    status, body = _http_get(url, params)
    if status == 429:
        raise UsgsDailyError("USGS_RATE_LIMITED", "HTTP 429; set API_USGS_PAT or retry later")
    if status != 200:
        raise UsgsDailyError("USGS_HTTP_ERROR", f"HTTP {status} from {urlparse(url).hostname}")
    try:
        doc = json.loads(body)
    except ValueError as e:
        raise UsgsDailyError("USGS_BAD_JSON", "response body is not valid JSON") from e
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        raise UsgsDailyError("USGS_BAD_SCHEMA", "response is not a GeoJSON FeatureCollection")
    return doc


def _paged_features(url: str, params: Mapping[str, Any]) -> list:
    feats: list = []
    doc = _get_json(url, params)
    for _ in range(_MAX_PAGES):
        feats.extend(doc["features"])
        nxt = next((l.get("href") for l in doc.get("links", []) if l.get("rel") == "next"), None)
        if not nxt:
            return feats
        _check_url(nxt)                      # https + host re-checked on every hop
        doc = _get_json(nxt, None)
    raise UsgsDailyError("USGS_PAGING_RUNAWAY", f"more than {_MAX_PAGES} pages")


def fetch_daily_discharge(gauge_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Daily mean discharge for ``[start_date, end_date]`` (inclusive, 'YYYY-MM-DD').

    Returns a DataFrame indexed by calendar date (tz-naive) with columns
    ``q_cms`` (m^3/s), ``q_native`` (as published), ``approval_status`` ('Approved' /
    'Provisional'). Null upstream values are dropped (counted in ``df.attrs``); an empty
    result or any contract violation raises :class:`UsgsDailyError`.
    """
    sid = _site_id(gauge_id)
    params = {"monitoring_location_id": sid, "parameter_code": "00060", "statistic_id": "00003",
              "time": f"{str(start_date)[:10]}/{str(end_date)[:10]}", "limit": PAGE_LIMIT, "f": "json"}
    feats = _paged_features(f"{BASE}/collections/daily/items", params)
    if not feats:
        raise UsgsDailyError("USGS_NO_DATA", f"no daily discharge for {sid} in {start_date}..{end_date}")
    try:
        props = [f["properties"] for f in feats]
        for p in props:
            if not isinstance(p.get("time"), str):
                raise KeyError("time")
    except (KeyError, TypeError, AttributeError) as e:
        raise UsgsDailyError("USGS_BAD_SCHEMA", "a feature lacks properties/time") from e
    if len({p.get("time_series_id") for p in props}) > 1:
        raise UsgsDailyError("USGS_MULTIPLE_SERIES", f"{sid} returned more than one time series; refusing to guess "
                              "(known limitation: this client has no series selector; "
                              "use the aihydro-data adapter's time_series_id selection)")
    units = {p.get("unit_of_measure") for p in props}
    if len(units) != 1:
        raise UsgsDailyError("USGS_UNIT_UNKNOWN", f"mixed or missing units: {sorted(map(str, units))}")
    unit = units.pop()
    factor = _UNIT_FACTORS.get(unit)
    if factor is None:
        raise UsgsDailyError("USGS_UNIT_UNKNOWN", f"unrecognised discharge unit {unit!r}")
    vals, nulls = [], 0
    for p in props:
        if p.get("value") is None:
            vals.append(float("nan"))
            nulls += 1
        else:
            vals.append(_parse_value(p["value"], p.get("time")))
    approvals = [p.get("approval_status") for p in props]
    bad = sorted({str(a) for a in approvals if a not in APPROVAL_CODES})
    if bad:
        raise UsgsDailyError("USGS_APPROVAL_UNKNOWN", f"unrecognised approval_status values: {bad}")
    times = pd.DatetimeIndex(pd.to_datetime([p["time"] for p in props])).tz_localize(None)
    df = pd.DataFrame({"q_native": vals, "approval_status": approvals}, index=times)
    df.index.name = "date"
    df = df.sort_index(kind="mergesort")
    if df.index.duplicated().any():
        raise UsgsDailyError("USGS_DUPLICATE_TIME", f"duplicate date {df.index[df.index.duplicated()][0]}")
    df["q_cms"] = df["q_native"] * factor
    df = df.dropna(subset=["q_native"])
    if df.empty:
        raise UsgsDailyError("USGS_NO_DATA", f"all {nulls} daily values for {sid} were null")
    df.attrs["null_dropped"] = nulls
    df.attrs["units_native"] = unit
    return df[["q_cms", "q_native", "approval_status"]]
