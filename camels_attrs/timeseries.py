"""
Hydrometeorological time series data extraction from GridMET
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple


def fetch_forcing_data(watershed_geom, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Fetch climate forcing data from GridMET for watershed.
    
    Parameters
    ----------
    watershed_geom : shapely.geometry
        Watershed boundary geometry
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)
        
    Returns
    -------
    pd.DataFrame or None
        Daily climate forcing data with columns:
        - date: timestamp
        - prcp_mm: precipitation (mm/day)
        - tmin_C: minimum temperature (°C)
        - tmax_C: maximum temperature (°C)
        - tavg_C: average temperature (°C)
        - srad_Wm2: solar radiation (W/m²)
        - wind_ms: wind speed (m/s)
        - sph_kgkg: specific humidity (kg/kg)
        - pet_mm: potential evapotranspiration (mm/day)
    """
    try:
        import pygridmet as gridmet

        print(f"Fetching GridMET data from {start_date} to {end_date}...")
        
        # Define variables to fetch
        variables = ["pr", "tmmn", "tmmx", "srad", "vs", "sph", "pet"]
        
        # Fetch data using pygridmet
        ds = gridmet.get_bygeom(
            geometry=watershed_geom,
            dates=(start_date, end_date),
            variables=variables,
            crs="EPSG:4326",
        )
        
        print(f"✓ Retrieved {len(ds.time)} days of climate data")
        
        # Calculate spatial mean (watershed average)
        df_list = []
        
        for var in variables:
            if var in ds.data_vars:
                # Get spatial mean
                var_mean = ds[var].mean(dim=["lat", "lon"])
                series = var_mean.to_series()
                series.index = pd.to_datetime(series.index).tz_localize(None)
                df_list.append(series.rename(var))
        
        # Combine all variables
        df = pd.concat(df_list, axis=1)
        
        # Unit conversions
        df['tmmn'] = df['tmmn'] - 273.15  # K to °C
        df['tmmx'] = df['tmmx'] - 273.15  # K to °C
        df['tavg'] = (df['tmmn'] + df['tmmx']) / 2  # Average temperature
        
        # Rename columns to match CAMELS convention
        df = df.rename(columns={
            'pr': 'prcp_mm',
            'tmmn': 'tmin_C',
            'tmmx': 'tmax_C',
            'tavg': 'tavg_C',
            'srad': 'srad_Wm2',
            'vs': 'wind_ms',
            'sph': 'sph_kgkg',
            'pet': 'pet_mm'
        })
        
        df.index.name = 'date'
        df = df.reset_index()
        
        return df
        
    except Exception as e:
        print(f"✗ Error fetching GridMET data: {e}")
        return None


def calculate_pet_hargreaves(df: pd.DataFrame, latitude: float) -> pd.DataFrame:
    """
    Calculate PET using Hargreaves-Samani method.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with tmin_C, tmax_C, and srad_Wm2
    latitude : float
        Watershed centroid latitude
        
    Returns
    -------
    pd.DataFrame
        DataFrame with additional pet_hargreaves_mm column
    """
    try:
        # Hargreaves-Samani equation
        tavg = (df['tmin_C'] + df['tmax_C']) / 2
        tdiff = np.sqrt(df['tmax_C'] - df['tmin_C'])
        
        # Convert W/m² to MJ/m²/day (multiply by 0.0864)
        ra_approx = df['srad_Wm2'] * 0.0864 * 1.5  # rough approximation
        
        df['pet_hargreaves_mm'] = 0.0023 * ra_approx * (tavg + 17.8) * tdiff
        
        return df
        
    except Exception as e:
        print(f"✗ Error calculating Hargreaves PET: {e}")
        return df


def calculate_forcing_statistics(df: pd.DataFrame) -> dict:
    """
    Calculate climate statistics from forcing data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Climate forcing DataFrame
        
    Returns
    -------
    dict
        Dictionary of climate statistics
    """
    stats = {}
    
    # Basic statistics
    stats['mean_annual_precip_mm'] = df['prcp_mm'].sum() / (len(df) / 365.25)
    stats['mean_annual_pet_mm'] = df['pet_mm'].sum() / (len(df) / 365.25)
    stats['mean_annual_temp_C'] = df['tavg_C'].mean()
    
    if stats['mean_annual_precip_mm'] > 0:
        stats['aridity_index'] = stats['mean_annual_pet_mm'] / stats['mean_annual_precip_mm']
    else:
        stats['aridity_index'] = np.nan
    
    # Temperature extremes
    stats['mean_tmax_C'] = df['tmax_C'].mean()
    stats['mean_tmin_C'] = df['tmin_C'].mean()
    
    # Precipitation statistics
    stats['wet_days'] = (df['prcp_mm'] > 1.0).sum()
    stats['wet_day_frequency'] = stats['wet_days'] / len(df)
    
    # Snow fraction (approximate)
    snow_days = (df['tavg_C'] <= 0) & (df['prcp_mm'] > 0)
    total_precip = df['prcp_mm'].sum()
    if total_precip > 0:
        stats['snow_fraction'] = df.loc[snow_days, 'prcp_mm'].sum() / total_precip
    else:
        stats['snow_fraction'] = 0.0
    
    return stats


def get_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate monthly aggregated statistics.
    
    Parameters
    ----------
    df : pd.DataFrame
        Daily forcing DataFrame
        
    Returns
    -------
    pd.DataFrame
        Monthly summary with sum for precip/PET and mean for other variables
    """
    df_copy = df.copy()
    df_copy['year_month'] = pd.to_datetime(df_copy['date']).dt.to_period('M')
    
    monthly = df_copy.groupby('year_month').agg({
        'prcp_mm': 'sum',
        'pet_mm': 'sum',
        'tavg_C': 'mean',
        'tmax_C': 'mean',
        'tmin_C': 'mean',
        'srad_Wm2': 'mean'
    }).reset_index()
    
    monthly['year_month'] = monthly['year_month'].astype(str)
    
    return monthly


def calculate_water_balance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate annual water balance metrics.
    
    Parameters
    ----------
    df : pd.DataFrame
        Daily forcing DataFrame
        
    Returns
    -------
    pd.DataFrame
        Annual water balance summary
    """
    df_copy = df.copy()
    df_copy['year'] = pd.to_datetime(df_copy['date']).dt.year
    
    annual = df_copy.groupby('year').agg({
        'prcp_mm': 'sum',
        'pet_mm': 'sum'
    })
    
    annual['water_surplus_mm'] = annual['prcp_mm'] - annual['pet_mm']
    annual['aridity_index'] = annual['pet_mm'] / annual['prcp_mm']
    
    return annual
