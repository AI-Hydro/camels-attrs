# camels-attrs — Architecture

CONUS reference implementation of the 71 CAMELS catchment attributes for 671 USGS
gauges.  Used as the validation target for `aihydro-lsh` CONUS parity tests.

---

## Role in the ecosystem

```
   camels-attrs  (CONUS reference — read-only comparison target)
        │
        └── aihydro-lsh tests/test_conus_parity.py
                compare lsh.attributes(gauge_watershed) vs camels_attrs.get(gauge_id)
                tolerance: ±10 % topography / ±10 % climate / ±5 % geology
```

`camels-attrs` is a **standalone reference package**.  It is NOT imported by
`aihydro-lsh` at runtime — only in the `[validate]` optional dependency and in
`lsh_compare_to_ref` MCP tool.

---

## Module map

```
camels_attrs/
│
├── __init__.py          load_camels_attrs() — convenience loader
│
├── topology.py          area, perimeter, compactness, elongation, form_factor
├── climate.py           p_mean, pet_mean, aridity, p_seasonality, frac_snow, …
├── hydrology.py         q_mean, BFI, q5, q95, fdc_slope, q_half_flow_date, …
├── soil.py              sand_frac, clay_frac, silt_frac, soil_conductivity, …
├── vegetation.py        lai_max, lai_diff, gvf_max, forest_frac, …
└── geology.py           geol_1st_class, carbonate_rocks_frac, geol_porosity,
                         geol_permeability  (corrected: geol_porostiy typo fixed in 1.0.3)
```

---

## Data flow

```
import camels_attrs

# Load all 671 CONUS gauge attributes (pre-computed from CAMELS-US dataset)
df = camels_attrs.load_camels_attrs()   # pd.DataFrame (671 rows × 71 cols)

# Single gauge
row = df.loc["01638500"]                # Potomac at Point of Rocks
print(row["p_mean"])                    # 3.21 mm/day
```

The underlying data is the CAMELS-US dataset (Addor et al. 2017, Newman et al. 2015).
It is bundled as CSV/parquet in the package — no network required.

---

## Version history

| Version | Change |
|---|---|
| 1.0.0 | Initial PyPI release |
| 1.0.3 | `geol_porostiy` → `geol_porosity` typo fix (2026-06-20) |

Relocated from `site-packages` to `MCP/camels-attrs/` (Wave C0, 2026-06-20)
to make it a first-class ecosystem sibling with version control.

---

## Citation

Addor, N., Newman, A.J., Mizukami, N., & Clark, M.P. (2017). The CAMELS data set:
catchment attributes and meteorology for large-sample studies. *HESS*, 21, 5293–5313.
https://doi.org/10.5194/hess-21-5293-2017
