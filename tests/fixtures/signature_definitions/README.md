# signature_definitions fixtures (Science Wave 3, PR-5)

Daily mean discharge (m3/s), WY1990-2009 (1989-10-01 .. 2009-09-30), 7305 days, no gaps. Public domain (USGS).
Byte-identical copies of `aihydro-watershed` `tests/fixtures/served_streamflow_*.csv` (branch
`vision2040/w3-watershed`, commit 6ba6615), which are in turn copies of
`docs/vision-2040/evidence/signature-definitions-1/data/` in the AI-Hydro workspace.

| File | Gauge | sha256 |
|---|---|---|
| `served_streamflow_01013500.csv` | USGS 01013500 (Fish River near Fort Kent, ME) | `683ccb1619efe82e3c124f8a540bdc9af93269af12efe5c3681d88d9438d359a` |
| `served_streamflow_01031500.csv` | USGS 01031500 (Piscataquis River near Dover-Foxcroft, ME) | `e01921cdd60e1750e3d27323aea4f8dc32632976c68fd0e961a3b64a444cbccc` |

`01031500` was written from the aihydro-data cache entry `b9d1de8bf04e2bf6f8b463ac` (NWIS_STREAMFLOW, fetched
2026-06-17); `01013500` is the series served in the watershed e2e proof 1. Source: USGS National Water
Information System, https://waterdata.usgs.gov/nwis.

Reference values (CAMELS attributes v2.0 `camels_hydro.txt`, Zenodo 15529996, md5 55ebdeb36c42ee7acdb998229c3edb3a):
01013500 slope_fdc 1.52821853538976, baseflow_index 0.585225955779508;
01031500 slope_fdc 1.49401920331253, baseflow_index 0.445090526012048.
