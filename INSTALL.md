# Installation Guide

## Standard Installation

The package can be installed directly from PyPI (once published):

```bash
pip install camels-attrs
```

## Development Installation

For development or to use the latest version:

```bash
git clone https://github.com/galib9690/camels-attrs.git
cd camels-attrs
pip install -e .
```

## Dependencies

All core dependencies will be installed automatically:

- **Core Libraries**: numpy, pandas, geopandas, xarray
- **Geospatial**: rioxarray, rasterio, shapely
- **HyRiver Ecosystem**: pynhd, py3dep, pygridmet, pygeohydro, pygeoutils
- **Remote Sensing**: pystac-client, planetary-computer
- **Scientific**: scipy, matplotlib
- **Hydrology**: built-in USGS Water Data API client (requests)

## Optional Dependencies

### Geological Attributes (pygeoglim)

If `pygeoglim` is not available on PyPI, install from source:

```bash
pip install git+https://github.com/hyriver/pygeoglim.git
```

If not installed, the package will gracefully return default values for geological attributes.

## Verifying Installation

Test your installation:

```bash
# Test CLI
camels-extract --version

# Test Python API
python -c "from camels_attributes import CamelsExtractor; print('Installation successful!')"
```

## Building from Source

To build the package for distribution:

```bash
pip install build
python -m build
```

This creates wheel and source distributions in the `dist/` directory.

## Troubleshooting

### Common Issues

1. **GDAL/Rasterio installation fails**:
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install gdal-bin libgdal-dev
   
   # On macOS
   brew install gdal
   ```

2. **HyRiver packages not found**:
   Ensure you have the latest versions:
   ```bash
   pip install --upgrade pynhd py3dep pygridmet pygeohydro pygeoutils
   ```

3. **Import errors**:
   Clear your Python cache:
   ```bash
   find . -type d -name __pycache__ -exec rm -r {} +
   pip install --force-reinstall camels-attributes
   ```

## System Requirements

- Python 3.8 or higher
- 4GB RAM minimum (8GB recommended for large watersheds)
- Internet connection (for data downloads)
