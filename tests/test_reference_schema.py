from __future__ import annotations

from camels_attrs.geology import extract_geological_attributes
from camels_attrs.hydrology import HYDRO_SIGNATURE_UNITS
from camels_attrs.soil import SOIL_ATTRIBUTE_UNITS


EXPECTED_HYDRO_SIGNATURES = {
    "q_mean",
    "q_std",
    "q5",
    "q95",
    "q_median",
    "baseflow_index",
    "runoff_ratio",
    "stream_elas",
    "high_q_freq",
    "high_q_dur",
    "low_q_freq",
    "low_q_dur",
    "zero_q_freq",
    "flow_variability",
    "hfd_mean",
    "half_flow_date_std",
    "slope_fdc",
}

EXPECTED_SOIL_ATTRIBUTES = {
    "soil_porosity",
    "available_water_capacity",
    "field_capacity",
    "sand_frac",
    "silt_frac",
    "clay_frac",
    "soil_depth_statsgo",
    "max_water_content",
    "soil_conductivity",
}

EXPECTED_GEOLOGY_ATTRIBUTES = {
    "geol_1st_class",
    "geol_2nd_class",
    "glim_1st_class_frac",
    "glim_2nd_class_frac",
    "carbonate_rocks_frac",
    "geol_permeability",
    "geol_porosity",
}


def test_hydrology_units_cover_reference_signature_schema():
    assert set(HYDRO_SIGNATURE_UNITS) == EXPECTED_HYDRO_SIGNATURES
    assert all(HYDRO_SIGNATURE_UNITS[name] for name in EXPECTED_HYDRO_SIGNATURES)


def test_soil_units_cover_reference_schema():
    assert set(SOIL_ATTRIBUTE_UNITS) == EXPECTED_SOIL_ATTRIBUTES
    assert all(SOIL_ATTRIBUTE_UNITS[name] for name in EXPECTED_SOIL_ATTRIBUTES)


def test_geology_fallback_schema_is_stable_without_network():
    attrs = extract_geological_attributes(watershed_gdf=None)

    assert set(attrs) == EXPECTED_GEOLOGY_ATTRIBUTES
    assert "geol_porostiy" not in attrs
    assert "geol_porosity" in attrs
