"""
Enhanced watershed visualization with comprehensive information display
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import contextily as ctx
from pynhd import NLDI
import py3dep
import cartopy.crs as ccrs
import cartopy.feature as cfeature


def create_comprehensive_watershed_map(
    watershed_gdf,
    watershed_geom,
    metadata,
    attributes=None,
    gauge_id=None,
    save_path=None
):
    """
    Create a comprehensive multi-panel watershed visualization with rich information.
    
    Parameters
    ----------
    watershed_gdf : gpd.GeoDataFrame
        Watershed boundary GeoDataFrame
    watershed_geom : shapely.geometry
        Watershed geometry
    metadata : dict
        Gauge metadata
    attributes : dict, optional
        Extracted CAMELS attributes for annotation
    gauge_id : str, optional
        USGS gauge ID
    save_path : str, optional
        Path to save the figure
    
    Returns
    -------
    matplotlib.figure.Figure
        The created figure
    """
    
    # Create figure with multiple panels
    fig = plt.figure(figsize=(20, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.35)
    
    # ========================================
    # MAIN MAP: Watershed with topography
    # ========================================
    ax_main = fig.add_subplot(gs[:2, :2])
    
    try:
        # Get DEM for background
        dem = py3dep.get_dem(watershed_geom, resolution=90)
        dem_proj = dem.rio.reproject("EPSG:3857")
        
        # Plot DEM
        dem_plot = dem_proj.plot(
            ax=ax_main,
            cmap='terrain',
            alpha=0.7,
            add_colorbar=False
        )
        
        # Add colorbar
        cbar = plt.colorbar(dem_plot, ax=ax_main, fraction=0.046, pad=0.04)
        cbar.set_label('Elevation (m)', rotation=270, labelpad=20, fontsize=10)
        
    except Exception as e:
        print(f"Could not load DEM: {e}")
    
    # Plot watershed boundary
    watershed_gdf_proj = watershed_gdf.to_crs("EPSG:3857")
    watershed_gdf_proj.boundary.plot(
        ax=ax_main,
        edgecolor='red',
        linewidth=3,
        label='Watershed Boundary'
    )
    
    # Try to add stream network
    try:
        nldi = NLDI()
        flowlines = nldi.navigate_byid(
            fsource="nwissite",
            fid=f"USGS-{gauge_id}",
            navigation="upstreamTributaries",
            source="flowlines",
            distance=500
        )
        if flowlines is not None and not flowlines.empty:
            flowlines_proj = flowlines.to_crs("EPSG:3857")
            flowlines_proj.plot(
                ax=ax_main,
                color='blue',
                linewidth=1.5,
                alpha=0.8,
                label='Stream Network'
            )
    except:
        pass
    
    # Plot gauge location
    gauge_lat = metadata.get('gauge_lat', 0)
    gauge_lon = metadata.get('gauge_lon', 0)
    if gauge_lat and gauge_lon:
        from shapely.geometry import Point
        import geopandas as gpd
        gauge_point = gpd.GeoDataFrame(
            geometry=[Point(gauge_lon, gauge_lat)],
            crs="EPSG:4326"
        ).to_crs("EPSG:3857")
        gauge_point.plot(
            ax=ax_main,
            color='yellow',
            edgecolor='black',
            markersize=200,
            marker='*',
            label='USGS Gauge',
            zorder=10
        )
    
    # Add basemap
    try:
        ctx.add_basemap(
            ax_main,
            source=ctx.providers.OpenStreetMap.Mapnik,
            alpha=0.3
        )
    except:
        pass
    
    ax_main.set_title(
        f'Watershed Map - USGS {gauge_id}\n{metadata.get("gauge_name", "Unknown")}',
        fontsize=14,
        fontweight='bold',
        pad=15
    )
    ax_main.legend(loc='upper right', fontsize=9, framealpha=0.9)
    ax_main.set_xlabel('Easting (m)', fontsize=10)
    ax_main.set_ylabel('Northing (m)', fontsize=10)
    
    # Add scale bar
    add_scale_bar(ax_main, watershed_gdf_proj)
    
    # Add north arrow
    add_north_arrow(ax_main)
    
    # ========================================
    # PANEL 2: Location Context Map
    # ========================================
    ax_context = fig.add_subplot(gs[0, 2], projection=ccrs.PlateCarree())
    
    # Show location in USA context with state boundaries
    try:
        import geopandas as gpd
        
        # Add USA features (states, borders, coastlines)
        ax_context.add_feature(cfeature.STATES.with_scale('110m'), 
                              edgecolor='gray', facecolor='lightgray', linewidth=0.5)
        ax_context.add_feature(cfeature.BORDERS.with_scale('110m'), 
                              linewidth=1, edgecolor='black')
        ax_context.coastlines(resolution='110m', linewidth=0.8)
        
        # Watershed location point
        centroid = watershed_gdf.geometry.centroid.iloc[0]
        ax_context.plot(centroid.x, centroid.y, 
                       marker='o', color='red', markersize=5, 
                       markeredgecolor='darkred', markeredgewidth=1.5,
                       zorder=5, transform=ccrs.PlateCarree())
        
        # Set CONUS extent
        ax_context.set_extent([-125, -66, 24, 50], crs=ccrs.PlateCarree())
        ax_context.set_title('Location in USA', fontsize=11, fontweight='bold')
        ax_context.gridlines(draw_labels=False, alpha=0.3, linestyle='--')
        
    except Exception as e:
        print(f"Could not create USA context map: {e}")
        ax_context.text(0.5, 0.5, 'Location map\nunavailable', 
                       ha='center', va='center', transform=ax_context.transAxes)
        ax_context.set_title('Location Context', fontsize=11, fontweight='bold')
    
    # ========================================
    # PANEL 3: Key Statistics
    # ========================================
    ax_stats = fig.add_subplot(gs[1, 2])
    ax_stats.axis('off')
    
    # Compile statistics text
    stats_text = f"📍 WATERSHED INFORMATION\n"
    stats_text += "="*33 + "\n\n"
    
    stats_text += f"🆔 Gauge ID: {metadata.get('gauge_id', 'N/A')}\n"
    stats_text += f"📌 HUC02: {metadata.get('huc_02', 'N/A')}\n"
    stats_text += f"📍 Location: ({gauge_lat:.3f}°N, {gauge_lon:.3f}°W)\n\n"
    
    if attributes:
        stats_text += f"📐 TOPOGRAPHY\n"
        stats_text += f"  • Area: {attributes.get('area_geospa_fabric', 0):.1f} km²\n"
        stats_text += f"  • Elev (mean): {attributes.get('elev_mean', 0):.1f} m\n"
        stats_text += f"  • Elev (range): {attributes.get('elev_min', 0):.0f}-{attributes.get('elev_max', 0):.0f} m\n"
        stats_text += f"  • Slope (mean): {attributes.get('slope_mean', 0):.1f} m/km\n\n"
        
        stats_text += f"🌦️ CLIMATE\n"
        stats_text += f"  • Precip: {attributes.get('p_mean', 0):.2f} mm/day\n"
        stats_text += f"  • Temp: {attributes.get('temp_mean', 0):.1f}°C\n"
        stats_text += f"  • Aridity: {attributes.get('aridity', 0):.2f}\n"
        stats_text += f"  • Snow frac: {float(str(attributes.get('frac_snow', 0))):.2f}\n\n"
        
        stats_text += f"🌲 VEGETATION\n"
        stats_text += f"  • Forest: {attributes.get('frac_forest', 0)*100:.1f}%\n"
        stats_text += f"  • Cropland: {attributes.get('frac_cropland', 0)*100:.1f}%\n"
        stats_text += f"  • LAI (max): {attributes.get('lai_max', 0):.1f}\n"
        stats_text += f"  • Dominant: {attributes.get('dom_land_cover', 'N/A')}\n\n"
        
        stats_text += f"💧 HYDROLOGY\n"
        stats_text += f"  • Q (mean): {attributes.get('q_mean', 0):.2f} mm/day\n"
        stats_text += f"  • Runoff ratio: {attributes.get('runoff_ratio', 0):.2f}\n"
        stats_text += f"  • Baseflow idx: {attributes.get('baseflow_index', 0):.2f}\n"
    
    ax_stats.text(
        0.05, 0.98,
        stats_text,
        transform=ax_stats.transAxes,
        fontsize=8.5,
        verticalalignment='top',
        fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    )
    
    # ========================================
    # PANEL 4: Elevation Profile
    # ========================================
    ax_elev = fig.add_subplot(gs[2, 0])
    
    if attributes:
        try:
            elev_data = [
                attributes.get('elev_min', 0),
                attributes.get('elev_mean', 0),
                attributes.get('elev_max', 0)
            ]
            ax_elev.bar(['Min', 'Mean', 'Max'], elev_data, color=['lightblue', 'blue', 'darkblue'])
            ax_elev.set_ylabel('Elevation (m)', fontsize=10)
            ax_elev.set_title('Elevation Statistics', fontsize=11, fontweight='bold')
            ax_elev.grid(True, alpha=0.3, axis='y')
            ax_elev.tick_params(labelsize=9)
        except:
            ax_elev.text(0.5, 0.5, 'Elevation data\nunavailable',
                        ha='center', va='center', transform=ax_elev.transAxes)
    
    # ========================================
    # PANEL 5: Land Cover Pie Chart
    # ========================================
    ax_lc = fig.add_subplot(gs[2, 1])
    
    if attributes:
        try:
            frac_forest = attributes.get('frac_forest', 0)
            frac_crop = attributes.get('frac_cropland', 0)
            water_frac = attributes.get('water_frac', 0)
            other = max(0, 1 - frac_forest - frac_crop - water_frac)
            
            sizes = [frac_forest, frac_crop, water_frac, other]
            labels = ['Forest', 'Cropland', 'Water', 'Other']
            colors = ['green', 'gold', 'blue', 'lightgray']
            
            ax_lc.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                     startangle=90, textprops={'fontsize': 9})
            ax_lc.set_title('Land Cover Distribution', fontsize=11, fontweight='bold')
        except:
            ax_lc.text(0.5, 0.5, 'Land cover data\nunavailable',
                      ha='center', va='center', transform=ax_lc.transAxes)
    
    # ========================================
    # PANEL 6: Climate Summary
    # ========================================
    ax_climate = fig.add_subplot(gs[2, 2])
    
    if attributes:
        try:
            p_mean = attributes.get('p_mean', 0)
            pet_mean = attributes.get('pet_mean', 0)
            
            ax_climate.bar(['Precipitation', 'PET'], [p_mean, pet_mean],
                          color=['blue', 'orange'])
            ax_climate.set_ylabel('mm/day', fontsize=10)
            ax_climate.set_title('Water Balance Components', fontsize=11, fontweight='bold')
            ax_climate.grid(True, alpha=0.3, axis='y')
            ax_climate.tick_params(labelsize=9)
            
            # Add aridity annotation
            aridity = attributes.get('aridity', 0)
            ax_climate.text(0.5, 0.95, f'Aridity Index: {aridity:.2f}',
                           transform=ax_climate.transAxes,
                           ha='center', fontsize=9,
                           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))
        except:
            ax_climate.text(0.5, 0.5, 'Climate data\nunavailable',
                           ha='center', va='center', transform=ax_climate.transAxes)
    
    # Overall title
    fig.suptitle(
        f'Comprehensive Watershed Analysis - USGS {gauge_id}',
        fontsize=16,
        fontweight='bold',
        y=0.98
    )
    
    # Save if requested
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Comprehensive map saved: {save_path}")
    
    return fig


def add_scale_bar(ax, gdf, location='lower left', length_km=None):
    """Add a scale bar to the map."""
    try:
        from matplotlib.patches import Rectangle
        from matplotlib.lines import Line2D
        
        # Get map bounds
        bounds = gdf.total_bounds
        width = bounds[2] - bounds[0]
        
        # Auto-calculate scale bar length if not provided
        if length_km is None:
            length_km = round(width / 5000) * 1000  # Round to nice number
            if length_km == 0:
                length_km = 1000
        
        length_m = length_km
        
        # Position
        x_pos = bounds[0] + width * 0.05 if 'left' in location else bounds[2] - width * 0.15
        y_pos = bounds[1] + (bounds[3] - bounds[1]) * 0.05 if 'lower' in location else bounds[3] - (bounds[3] - bounds[1]) * 0.1
        
        # Draw scale bar
        line = Line2D([x_pos, x_pos + length_m], [y_pos, y_pos],
                     color='black', linewidth=3)
        ax.add_line(line)
        
        # Add text
        ax.text(x_pos + length_m / 2, y_pos + (bounds[3] - bounds[1]) * 0.02,
               f'{length_km/1000:.0f} km',
               ha='center', fontsize=9, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    except:
        pass


def add_north_arrow(ax):
    """Add a north arrow to the map."""
    try:
        # Get axis limits
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
        # Position in top right
        x = xlim[1] - (xlim[1] - xlim[0]) * 0.08
        y = ylim[1] - (ylim[1] - ylim[0]) * 0.08
        
        # Draw arrow
        ax.annotate('N', xy=(x, y), xytext=(x, y - (ylim[1] - ylim[0]) * 0.05),
                   arrowprops=dict(arrowstyle='->', lw=2, color='black'),
                   fontsize=12, fontweight='bold', ha='center',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    except:
        pass
