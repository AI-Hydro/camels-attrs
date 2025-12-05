"""
Hydrological signatures calculation from streamflow data (CAMELS-Consistent)
"""

import numpy as np
import pandas as pd
import hydrofunctions as hf
import pygridmet as gridmet
import geopandas as gpd

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

def _lyne_hollick_baseflow(q: np.ndarray, alpha: float = 0.925, passes: int = 3) -> np.ndarray:
    """Lyne–Hollick digital filter. Non-negative constraint."""
    if q.size == 0 or np.all(~np.isfinite(q)):
        return np.full_like(q, np.nan, dtype=float)

    def one_pass_forward(x):
        y = np.zeros_like(x, dtype=float)
        y[0] = x[0]
        for t in range(1, len(x)):
            y[t] = alpha * y[t-1] + (1 + alpha) / 2 * (x[t] - x[t-1])
            y[t] = min(max(y[t], 0.0), x[t])
        return y

    def one_pass_backward(x):
        y = np.zeros_like(x, dtype=float)
        y[-1] = x[-1]
        for t in range(len(x) - 2, -1, -1):
            y[t] = alpha * y[t+1] + (1 + alpha) / 2 * (x[t] - x[t+1])
            y[t] = min(max(y[t], 0.0), x[t])
        return y

    bf = q.copy().astype(float)
    for _ in range(passes):
        bf = one_pass_forward(bf)
        bf = one_pass_backward(bf)
    return np.clip(bf, 0, q)

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
        Dictionary of 17 CAMELS hydrological signatures
    """
    try:
        # ✅ Extract area and geometry from GeoDataFrame
        area_km2 = watershed_gdf.to_crs("EPSG:5070").geometry.area.iloc[0] / 1e6
        watershed_geom = watershed_gdf.geometry.iloc[0]
        
        # Fetch streamflow data
        q_cms = fetch_streamflow_data(gauge_id, start_date, end_date)
        if q_cms is None or len(q_cms) < 365:
            raise Exception("Insufficient streamflow data")
        
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
        hydro_sigs["q5"] = float(np.quantile(q_vals, 0.95)) # CAMELS High Flow
        hydro_sigs["q95"] = float(np.quantile(q_vals, 0.05)) # CAMELS Low Flow
        hydro_sigs["q_median"] = float(np.median(q_vals))
        
        # --- 2. Baseflow Index ---
        baseflow = _lyne_hollick_baseflow(q_vals)
        bfi = float(np.nansum(baseflow) / np.nansum(q_vals)) if np.nansum(q_vals) > 0 else np.nan
        hydro_sigs["baseflow_index"] = max(0.0, min(1.0, bfi)) if np.isfinite(bfi) else np.nan
        
        # --- 3. Water Balance (Elasticity & Runoff Ratio) ---
        wb_stats = compute_water_balance_camels(q_mm_day, p_series)
        hydro_sigs.update(wb_stats)
        
        # --- 4. Flow Duration Curve Slope ---
        # Log slope between 33% and 66% exceedance
        q_pos = q_vals[q_vals > 0]
        if len(q_pos) > 100:
            q33, q66 = np.quantile(q_pos, 0.67), np.quantile(q_pos, 0.34)
            if q66 > 0 and q33 > 0:
                hydro_sigs["slope_fdc"] = float((np.log(q33) - np.log(q66)) / (0.66 - 0.33))
            else:
                hydro_sigs["slope_fdc"] = np.nan
        else:
            hydro_sigs["slope_fdc"] = np.nan
        
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
        
        # Zero flow frequency (fraction, dimensionless)
        hydro_sigs["zero_q_freq"] = float(np.sum(q_vals == 0) / len(q_vals))
        
        # Flow variability (coefficient of variation)
        hydro_sigs["flow_variability"] = float(np.std(q_vals) / mean_q) if mean_q > 0 else np.nan
        
        # --- 6. Timing Statistics (Half Flow Date) ---
        timing_stats = compute_timing_stats_camels(q_mm_day)
        hydro_sigs.update(timing_stats)
        
        return hydro_sigs
        
    except Exception as e:
        logger.error(f"Error computing hydrological signatures: {e}")
        # Return NaNs on failure
        return {k: np.nan for k in [
            "q_mean", "q_std", "q5", "q95", "q_median", "baseflow_index",
            "runoff_ratio", "stream_elas", "slope_fdc", 
            "high_q_freq", "high_q_dur", "low_q_freq", "low_q_dur",
            "zero_q_freq", "flow_variability", "hfd_mean", "half_flow_date_std"
        ]}


# ------------------------------
# Data Fetchers (Wrappers)
# ------------------------------

def fetch_streamflow_data(gauge_id: str, start_date: str, end_date: str) -> pd.Series | None:
    """Fetch daily streamflow from USGS NWIS."""
    try:
        nwis = hf.NWIS(gauge_id, "dv", start_date, end_date)
        df = nwis.df()
        if df.empty:
            return None
        q_cfs = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        q_cms = q_cfs * 0.0283168
        q_cms.index = pd.to_datetime(q_cms.index).tz_localize(None)
        return q_cms.dropna()
    except Exception as e:
        print(f"    ✗ Error fetching streamflow: {e}")
        return None

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
    "high_q_freq": "events/yr",
    "high_q_dur": "days",
    "low_q_freq": "events/yr",
    "low_q_dur": "days",
    "zero_q_freq": "–",
    "flow_variability": "–",
    "hfd_mean": "day-of-year",
    "half_flow_date_std": "days",
    "slope_fdc": "log-slope"
}