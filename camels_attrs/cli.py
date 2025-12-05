"""
Command-line interface for CAMELS attributes extraction
"""

import argparse
import sys
from .extractor import CamelsExtractor, extract_multiple_gauges
from .timeseries import get_monthly_summary, calculate_water_balance
from . import __version__


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract CAMELS-like catchment attributes for USGS gauge sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract attributes for a single gauge
  camels-extract 01031500 -o attributes.csv
  
  # Extract for multiple gauges
  camels-extract 01031500 02177000 06803530 -o combined.csv
  
  # Specify custom date ranges
  camels-extract 01031500 --climate-start 2010-01-01 --climate-end 2020-12-31
  
  # Output as JSON
  camels-extract 01031500 -o attributes.json -f json
        """
    )
    
    parser.add_argument(
        "gauge_ids",
        nargs="+",
        help="USGS gauge ID(s) to process"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="camels_attributes.csv",
        help="Output file path (default: camels_attributes.csv)"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)"
    )
    
    parser.add_argument(
        "--climate-start",
        default="2000-01-01",
        help="Climate data start date (default: 2000-01-01)"
    )
    
    parser.add_argument(
        "--climate-end",
        default="2020-12-31",
        help="Climate data end date (default: 2020-12-31)"
    )
    
    parser.add_argument(
        "--hydro-start",
        default="2000-01-01",
        help="Streamflow data start date (default: 2000-01-01)"
    )
    
    parser.add_argument(
        "--hydro-end",
        default="2020-12-31",
        help="Streamflow data end date (default: 2020-12-31)"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress messages"
    )
    
    parser.add_argument(
        "--timeseries",
        action="store_true",
        help="Extract hydrometeorological timeseries data (in addition to static attributes)"
    )
    
    parser.add_argument(
        "--timeseries-only",
        action="store_true",
        help="Extract only timeseries data (skip static attributes)"
    )
    
    parser.add_argument(
        "--monthly",
        action="store_true",
        help="Also output monthly aggregated data (requires --timeseries)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    args = parser.parse_args()
    
    try:
        # Single gauge
        if len(args.gauge_ids) == 1:
            gauge_id = args.gauge_ids[0]
            if not args.quiet:
                print(f"Extracting CAMELS data for gauge {gauge_id}...\n")
            
            extractor = CamelsExtractor(
                gauge_id,
                climate_start=args.climate_start,
                climate_end=args.climate_end,
                hydro_start=args.hydro_start,
                hydro_end=args.hydro_end
            )
            
            # Extract static attributes unless timeseries-only
            if not args.timeseries_only:
                attributes = extractor.extract_all(verbose=not args.quiet)
                extractor.save(args.output, format=args.format)
                
                if not args.quiet:
                    print(f"\n✓ Static attributes complete! {len(attributes)} attributes extracted.")
                    print(f"  Output: {args.output}")
            
            # Extract timeseries if requested
            if args.timeseries or args.timeseries_only:
                if not args.quiet:
                    print(f"\nExtracting hydrometeorological timeseries...")
                
                forcing_df = extractor.extract_timeseries()
                
                # Save timeseries
                ts_output = args.output.replace('.csv', '_timeseries.csv').replace('.json', '_timeseries.csv')
                forcing_df.to_csv(ts_output, index=False)
                
                if not args.quiet:
                    print(f"✓ Timeseries data saved: {ts_output}")
                
                # Save monthly data if requested
                if args.monthly:
                    monthly_df = get_monthly_summary(forcing_df)
                    monthly_output = args.output.replace('.csv', '_monthly.csv').replace('.json', '_monthly.csv')
                    monthly_df.to_csv(monthly_output, index=False)
                    
                    if not args.quiet:
                        print(f"✓ Monthly data saved: {monthly_output}")
                
                # Calculate and save forcing statistics
                forcing_stats = extractor.get_forcing_statistics(forcing_df)
                stats_output = args.output.replace('.csv', '_forcing_stats.csv').replace('.json', '_forcing_stats.csv')
                import pandas as pd
                pd.DataFrame([forcing_stats]).to_csv(stats_output, index=False)
                
                if not args.quiet:
                    print(f"✓ Forcing statistics saved: {stats_output}")
        
        # Multiple gauges
        else:
            if not args.quiet:
                print(f"Extracting CAMELS attributes for {len(args.gauge_ids)} gauges...\n")
            
            df = extract_multiple_gauges(
                args.gauge_ids,
                climate_start=args.climate_start,
                climate_end=args.climate_end,
                hydro_start=args.hydro_start,
                hydro_end=args.hydro_end
            )
            
            if args.format == "csv":
                df.to_csv(args.output, index=False)
            else:
                df.to_json(args.output, orient="records", indent=2)
            
            if not args.quiet:
                print(f"\n✓ Complete! Processed {len(df)} gauges.")
                print(f"  Output: {args.output}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    
    except Exception as e:
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
