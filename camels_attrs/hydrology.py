"""
Hydrological signatures calculation from streamflow data (CAMELS-Consistent)
"""

import logging

import numpy as np
import pandas as pd
import pygridmet as gridmet
import geopandas as gpd
from typing import Optional

from .baseflow import (
    LH_ALPHA,
    LH_N_REFLECT,
    LH_PASSES,
    LYNE_HOLLICK_LADSON2013_REFERENCE,
    lyne_hollick_ladson2013,
)
from .usgs_daily import UsgsDailyError, fetch_daily_discharge

logger = logging.getLogger(__name__)

_SIGNATURE_KEYS = [
    "q_mean", "q_std", "q5", "q95", "q_median", "baseflow_index",
    "runoff_ratio", "stream_elas", "slope_fdc", "slope_fdc_sawicz2011",
    "high_q_freq", "high_q_dur", "low_q_freq", "low_q_dur",
    "zero_q_freq", "flow_variability", "hfd_mean", "half_flow_date_std",
]


def _hydro_failure(status, reason):
    out = {k: np.nan for k in _SIGNATURE_KEYS}
    out.update(hydro_status=status, hydro_reason=reason,
               hydro_provisional_fraction=np.nan, hydro_null_dropped=np.nan)
    return out

# ------------------------------
# Utility Functions (From Reference)
# ------------------------------

def _year_series(dti: pd.DatetimeIndex, hydro_year_start_month=10) -> np.ndarray:
    """Hydrologic year ID (integer). October=10 for CONUS (CAMELS)."""
    return dti.year + (dti.month >= hydro_year_start_month)

def _consecutive_event_lengths(mask: np.ndarray) -> list:
    """Given a 0/1 mask, return lengths of consecutive 1's runs."""
    lengths, run = [], 0
    for v in mask:
        if v:
            run += 1
        elif run > 0:
            lengths.append(run)
            run = 0
    if run > 0:
        lengths.append(run)
    return lengths

def _lyne_hollick_baseflow(q: np.ndarray, alpha: float = LH_ALPHA, passes: int = LH_PASSES) -> np.ndarray:
    """Baseflow of ``q`` by the canonical Lyne-Hollick kernel (Ladson et al. 2013, CAMELS recipe).

    Since 2.0.0 this is :func:`camels_attrs.baseflow.lyne_hollick_ladson2013` (BREAKING-VALUE,
    see CHANGELOG). Before 2.0.0 each sweep clamped ``0 <= b <= q`` and fed the clamped value back
    into the recursion, with no 30-day reflection; that read 5-19% below CAMELS on the verified
    basins. ``q`` must be a daily series with NaN for missing days (calendar gaps are segment
    boundaries); it must be longer than 30 days.
    """
    q = np.asarray(q, dtype=float)
    if q.size == 0 or np.all(~np.isfinite(q)):
        return np.full_like(q, np.nan, dtype=float)
    return np.clip(lyne_hollick_ladson2013(q, alpha=alpha, passes=passes), 0, q)


def compute_baseflow_index(q: pd.Series) -> float:
    """CAMELS baseflow index of a daily series: ``sum(baseflow) / sum(q)`` over the days that have a baseflow value.

    ``q`` is placed on the full daily calendar first so a gap in the record is a segment boundary
    for the filter and is not spliced. Result clipped to [0, 1]; NaN if the series is too short.
    """
    if isinstance(q.index, pd.DatetimeIndex):
        x = q.sort_index().resample("D").asfreq().to_numpy(dtype=float)
    else:
        x = np.asarray(q, dtype=float)
    if x.size <= LH_N_REFLECT:
        return float("nan")
    bf = _lyne_hollick_baseflow(x)
    ok = np.isfinite(bf) & np.isfinite(x)
    den = float(np.sum(x[ok]))
    if not ok.any() or den <= 0:
        return float("nan")
    return float(max(0.0, min(1.0, float(np.sum(bf[ok])) / den)))


def compute_slope_fdc_camels(q_vals) -> dict:
    """``slope_fdc`` as distributed in CAMELS-US v1.2, plus the Sawicz et al. (2011) log-space value.

    ``slope_fdc`` = ``(Q66 - Q33) / (mean(q) * 0.33)`` with Q33, Q66 the 33rd and 66th
    (non-exceedance, linear-interpolation / R type 7) percentiles, zero-flow days kept; NaN unless
    there are >= 100 finite values and ``mean(q) > 0``.
    ``slope_fdc_sawicz2011`` = ``(ln Q33exc - ln Q66exc) / 0.33``, exceedance points taken as
    non-exceedance quantiles 0.67 and 0.34, zeros dropped, > 100 positive days (the value that
    was reported as ``slope_fdc`` before 2.0.0).
    """
    q = np.asarray(q_vals, dtype=float)
    q = q[np.isfinite(q)]
    out = {"slope_fdc": np.nan, "slope_fdc_sawicz2011": np.nan}
    if q.size >= 100 and float(np.mean(q)) > 0:
        out["slope_fdc"] = float((np.quantile(q, 0.66) - np.quantile(q, 0.33)) / (float(np.mean(q)) * 0.33))
    pos = q[q > 0]
    if pos.size > 100:
        q33, q66 = np.quantile(pos, 0.67), np.quantile(pos, 0.34)
        if q66 > 0 and q33 > 0:
            out["slope_fdc_sawicz2011"] = float((np.log(q33) - np.log(q66)) / (0.66 - 0.33))
    return out


_SLOPE_FDC_CAMELS_FILE_SOURCE = (
    "slope of the flow duration curve between the 33rd and 66th percentiles, mean-normalised, as in "
    "the CAMELS-US v1.2 distributed file (naddor/camels@88e7a0d2d2 hydro/hydro_signatures.R:97). "
    "Reproduces the file at <=2.3e-7 relative on 01013500 and 01031500, and 9.7e-5 on 01516500. "
    "Its zero-structure prediction holds on all 671 basins. Not proven to be the script that "
    "produced the file."
)

#: Machine-readable definition of every hydrology signature whose meaning is a choice, so a
#: consumer can tell whether two numbers with the same name are the same quantity.
SIGNATURE_DEFINITIONS = {
    "slope_fdc": {
        "formula": "(Q66 - Q33) / (mean(q) * 0.33), Q66 and Q33 the 66th and 33rd percentiles of q",
        "quantile_type": "non-exceedance, linear interpolation (R type 7; numpy default)",
        "zero_handling": "zero-flow days kept; defined only when mean(q) > 0",
        "log_transform": False,
        "source": _SLOPE_FDC_CAMELS_FILE_SOURCE,
        "evidence": "docs/vision-2040/evidence/signature-definitions-1 (AI-Hydro workspace)",
        "comparable_to": "CAMELS-US v1.2 slope_fdc column only; not the Sawicz et al. (2011) signature "
                         "and not necessarily the same quantity as 'slope_fdc' in other CAMELS datasets",
    },
    "slope_fdc_sawicz2011": {
        "formula": "(ln Q33exc - ln Q66exc) / 0.33, Q33exc and Q66exc the flows exceeded 33% and 66% of the time",
        "quantile_type": "exceedance points as non-exceedance quantiles 0.67 and 0.34, linear interpolation (type 7)",
        "zero_handling": "zero-flow days dropped; needs > 100 positive days",
        "log_transform": True,
        "source": "log-space FDC slope (Sawicz et al. 2011). This is the pre-2.0.0 camels-attrs 'slope_fdc' value.",
    },
    "baseflow_index": {
        "formula": "sum(baseflow) / sum(q)",
        "method": "lyne_hollick_ladson2013",
        "parameters": {"alpha": LH_ALPHA, "passes": LH_PASSES, "n_reflect": LH_N_REFLECT},
        "zero_handling": "baseflow clipped at zero; quick flow subtracted only where positive; "
                         "30-day reflection at both ends",
        "source": LYNE_HOLLICK_LADSON2013_REFERENCE,
        "evidence": "docs/vision-2040/evidence/signature-definitions-1 (CAMELS v1.2 reproduced to <=2e-6 relative)",
    },
    "high_q_freq": {"formula": "days with q > 9 * median(q), divided by available days, times 365.25",
                    "units": "days/year", "source": "Addor et al. (2017) Table 3; naddor/camels compute_hf_freq_dur"},
    "low_q_freq": {"formula": "days with q <= 0.2 * mean(q), divided by available days, times 365.25",
                   "units": "days/year", "source": "Addor et al. (2017) Table 3; naddor/camels compute_lf_freq_dur"},
    "zero_q_freq": {"formula": "days with q <= 0, divided by available days", "units": "fraction",
                    "source": "naddor/camels compute_no_flow (sum(q<=0)/length)"},
}

def _align_daily(q_series: pd.Series, p_series: pd.Series, min_days: int = 365):
    """Align to common daily index (naive datetime), drop NaNs."""
    if q_series is None or p_series is None:
        return None, None
    qi = pd.to_datetime(q_series.index).tz_localize(None)
    pi = pd.to_datetime(p_series.index).tz_localize(None)
    q = pd.Series(q_series.values, index=qi, dtype=float).dropna()
    p = pd.Series(p_series.values, index=pi, dtype=float).dropna()
    common = q.index.intersection(p.index)
    if len(common) < min_days:
        return None, None
    return q.loc[common], p.loc[common]

# ------------------------------
# Computation Functions (CAMELS Methodology)
# ------------------------------

def compute_water_balance_camels(q_mm_day: pd.Series, p_mm_day: pd.Series) -> dict:
    """Runoff ratio and streamflow elasticity using median interannual anomaly."""
    q_aln, p_aln = _align_daily(q_mm_day, p_mm_day, min_days=365)
    if q_aln is None:
        return dict(runoff_ratio=np.nan, stream_elas=np.nan)

    # Runoff Ratio
    mean_q, mean_p = float(q_aln.mean()), float(p_aln.mean())
    rr = mean_q / mean_p if mean_p > 0 else np.nan

    # Elasticity (Sankarasubramanian et al.)
    hy = _year_series(q_aln.index, hydro_year_start_month=10)
    mp = pd.Series(p_aln.values, index=hy).groupby(level=0).mean()
    mq = pd.Series(q_aln.values, index=hy).groupby(level=0).mean()

    if len(mp) < 3 or len(mq) < 3:
        return dict(runoff_ratio=rr, stream_elas=np.nan)

    mp_tot, mq_tot = float(mp.mean()), float(mq.mean())
    dp, dq = (mp - mp_tot), (mq - mq_tot)
    
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = (dq / mq_tot) / (dp / mp_tot)
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    elas = float(np.median(ratio)) if len(ratio) > 0 else np.nan

    return dict(runoff_ratio=rr, stream_elas=elas)

def compute_timing_stats_camels(q_mm_day: pd.Series) -> dict:
    """Half-flow date based on Hydrologic Year (Oct 1 start)."""
    if q_mm_day is None or len(q_mm_day) < 365:
        return dict(hfd_mean=np.nan, half_flow_date_std=np.nan)

    df = q_mm_day.dropna().to_frame("q")
    hy = _year_series(df.index, hydro_year_start_month=10)
    df["hy"] = hy
    
    # Create water year start date for each row
    df["hyd_start"] = pd.to_datetime([f"{y-1}-10-01" for y in hy])
    
    # ✅ FIX: Calculate day of water year with .dt accessor
    df["day"] = (df.index - df["hyd_start"]).dt.days + 1

    hfd_list = []
    for g, grp in df.groupby("hy"):
        qsum = grp["q"].sum()
        if len(grp) >= 300 and qsum > 0:
            csum = grp["q"].cumsum()
            idx = np.argmax(csum.values >= 0.5 * qsum)
            hfd_list.append(int(grp["day"].iloc[idx]))

    if len(hfd_list) >= 2:
        return dict(hfd_mean=float(np.mean(hfd_list)),
                    half_flow_date_std=float(np.std(hfd_list)))
    return dict(hfd_mean=np.nan, half_flow_date_std=np.nan)

# ------------------------------
# Main Extraction Logic
# ------------------------------

def compute_flow_quantiles_camels(q_vals) -> dict:
    """CAMELS q5 / q95 (Addor et al. 2017, Table 3).

    ``q5`` is the 5% flow quantile (low flow) and ``q95`` the 95% flow quantile
    (high flow): plain non-exceedance quantiles of the daily series. Versions
    before the P2-D0 fix returned them the other way round.
    """
    return {
        "q5": float(np.quantile(q_vals, 0.05)),
        "q95": float(np.quantile(q_vals, 0.95)),
    }


def extract_hydrological_signatures(
    gauge_id, 
    watershed_gdf,  # ✅ Changed from watershed_geom to watershed_gdf
    start_date="2000-01-01", 
    end_date="2020-12-31"
):
    """
    Compute CAMELS-style hydrological signatures.
    
    Parameters
    ----------
    gauge_id : str
        USGS gauge identifier
    watershed_gdf : GeoDataFrame
        Watershed boundary GeoDataFrame (used to extract area and geometry)
    start_date : str
        Start date for analysis
    end_date : str
        End date for analysis
    
    Returns
    -------
    dict
        Dictionary of 18 hydrological signatures (the 17 CAMELS ones plus ``slope_fdc_sawicz2011``)
    """
    try:
        # ✅ Extract area and geometry from GeoDataFrame
        area_km2 = watershed_gdf.to_crs("EPSG:5070").geometry.area.iloc[0] / 1e6
        watershed_geom = watershed_gdf.geometry.iloc[0]
        
        # Fetch streamflow data
        try:
            q_df = fetch_streamflow_data(gauge_id, start_date, end_date)
        except UsgsDailyError as e:
            logger.error(f"USGS streamflow refused for {gauge_id}: {e}")
            return _hydro_failure("refused", e.code)
        q_cms = q_df["q_cms"]
        if len(q_cms) < 365:
            logger.error(f"Insufficient streamflow data for {gauge_id}: {len(q_cms)} days")
            return _hydro_failure("insufficient_data", "LT_365_DAYS")
        
        # Convert to mm/day
        q_mm_day = q_cms * (86.4 / area_km2)
        q_mm_day.index = pd.to_datetime(q_mm_day.index).tz_localize(None)

        # Fetch precipitation
        p_series = fetch_precipitation_data(watershed_geom, start_date, end_date)
        
        hydro_sigs = {}
        q_vals = q_mm_day.values

        # --- 1. Basic Flow Stats ---
        hydro_sigs["q_mean"] = float(np.mean(q_vals))
        hydro_sigs["q_std"] = float(np.std(q_vals))
        hydro_sigs.update(compute_flow_quantiles_camels(q_vals))
        hydro_sigs["q_median"] = float(np.median(q_vals))
        
        # --- 2. Baseflow Index ---
        # Ladson et al. (2013) kernel, as CAMELS (BREAKING-VALUE vs camels-attrs < 2.0.0).
        hydro_sigs["baseflow_index"] = compute_baseflow_index(q_mm_day)
        
        # --- 3. Water Balance (Elasticity & Runoff Ratio) ---
        wb_stats = compute_water_balance_camels(q_mm_day, p_series)
        hydro_sigs.update(wb_stats)
        
        # --- 4. Flow Duration Curve Slope ---
        # slope_fdc = CAMELS-US v1.2 file definition (BREAKING-VALUE vs camels-attrs < 2.0.0);
        # the old log-space value is slope_fdc_sawicz2011. See SIGNATURE_DEFINITIONS.
        hydro_sigs.update(compute_slope_fdc_camels(q_vals))
        
        # --- 5. Event Statistics ---
        mean_q = np.mean(q_vals)
        med_q = np.median(q_vals)
        
        # High flow: > 9 * Median
        high_mask = (q_vals > 9.0 * med_q)
        hydro_sigs["high_q_freq"] = float(np.sum(high_mask) / len(q_vals) * 365.25)
        hydro_sigs["high_q_dur"] = float(np.mean(_consecutive_event_lengths(high_mask))) if np.any(high_mask) else np.nan

        # Low flow: <= 0.2 * Mean
        low_mask = (q_vals <= 0.2 * mean_q)
        hydro_sigs["low_q_freq"] = float(np.sum(low_mask) / len(q_vals) * 365.25)
        hydro_sigs["low_q_dur"] = float(np.mean(_consecutive_event_lengths(low_mask))) if np.any(low_mask) else np.nan
        
        # Zero flow frequency (fraction, dimensionless); CAMELS compute_no_flow counts q <= 0
        hydro_sigs["zero_q_freq"] = float(np.sum(q_vals <= 0) / len(q_vals))
        
        # Flow variability (coefficient of variation)
        hydro_sigs["flow_variability"] = float(np.std(q_vals) / mean_q) if mean_q > 0 else np.nan
        
        # --- 6. Timing Statistics (Half Flow Date) ---
        timing_stats = compute_timing_stats_camels(q_mm_day)
        hydro_sigs.update(timing_stats)
        hydro_sigs["hydro_status"] = "ok"
        hydro_sigs["hydro_reason"] = ""
        hydro_sigs["hydro_provisional_fraction"] = float(
            (q_df["approval_status"] == "Provisional").mean())
        hydro_sigs["hydro_null_dropped"] = int(q_df.attrs.get("null_dropped", 0))

        return hydro_sigs
        
    except Exception as e:
        logger.error(f"Error computing hydrological signatures: {e}")
        return _hydro_failure("error", f"COMPUTE_ERROR: {type(e).__name__}")


# ------------------------------
# Data Fetchers (Wrappers)
# ------------------------------

def fetch_streamflow_data(gauge_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily mean streamflow from the USGS Water Data API.

    Returns a DataFrame indexed by date with ``q_cms`` (m^3/s), ``q_native`` and
    ``approval_status`` (Approved / Provisional). Raises
    :class:`camels_attrs.usgs_daily.UsgsDailyError` on any failure (empty result,
    sentinel / unparseable values, unknown units); it never returns an empty success.
    """
    return fetch_daily_discharge(gauge_id, start_date, end_date)

def fetch_precipitation_data(watershed_geom, start_date, end_date):
    """Fetch GridMET precipitation."""
    try:
        ds = gridmet.get_bygeom(
            geometry=watershed_geom,
            dates=(start_date, end_date),
            variables=["pr"],
            crs="EPSG:4326",
        )
        if "pr" not in ds.data_vars:
            return None
        pr_daily = ds["pr"].mean(dim=["lat", "lon"])
        s = pr_daily.to_series().dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        return s
    except Exception as e:
        logger.error(f"Error fetching precipitation: {e}")
        return None


# ============================================================================
# UNITS REFERENCE
# ============================================================================

HYDRO_SIGNATURE_UNITS = {
    "q_mean": "mm/day",
    "q_std": "mm/day",
    "q5": "mm/day",
    "q95": "mm/day",
    "q_median": "mm/day",
    "baseflow_index": "–",
    "runoff_ratio": "–",
    "stream_elas": "–",
    "high_q_freq": "days/yr",
    "high_q_dur": "days",
    "low_q_freq": "days/yr",
    "low_q_dur": "days",
    "zero_q_freq": "–",
    "flow_variability": "–",
    "hfd_mean": "day-of-year",
    "half_flow_date_std": "days",
    # (Q66 - Q33) / (mean(q) * 0.33), the CAMELS-US v1.2 file definition (not a log slope since 2.0.0)
    "slope_fdc": "–",
    "slope_fdc_sawicz2011": "log-slope",
}
