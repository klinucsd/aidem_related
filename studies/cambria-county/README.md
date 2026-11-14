# Cambria County study skills

Skills for the **Cambria County South Fork Dam Breach Scenario**: USACE's simulated dam failure
in Cambria County, PA (December demo data; not a real event), built like the Kanawha
skills (`kanawha-flood-depth`, `kanawha-cikr-impact`, `kanawha-nsi-impact`). Each skill (in `skills/`) is one
`SKILL.md` whose example code reads the study's layers from the SDSC GeoServer
(`https://sparcal.sdsc.edu/geoserver/tiger`, layers `CambriaCounty_*`; facilities updated 2026-11-13
with the team's v3: schools, hospitals and power only), so no data has to be installed.

| Skill | Kanawha counterpart | What it does |
|---|---|---|
| `cambria-county-flood-depth` | kanawha-flood-depth | Shows the maximum flood depth grid (WMS) |
| `cambria-county-cikr-impact` | kanawha-cikr-impact | Flooded critical facilities, with names and addresses: depth, severity, and optionally force (depth × velocity), velocity and arrival times |
| `cambria-county-nsi-impact` | kanawha-nsi-impact | Flooded buildings (NSI 2026): people by day and night, over 65, disabled, students, value exposed, by building type |

**Not built: reach impact.** The Cambria County study has no reaches or gauges (USACE delivered an
8-county study area instead), so there is no counterpart of `kanawha-reach-impact`.

## Differences from the Kanawha skills

- **One event, no flows.** The study is a single simulated dam failure: there is no flow (cfs) to
  choose. The skills say so if a user gives one.
- **Facilities have names and addresses** (`NAME`, `Address`), unlike the Kanawha CIKR points.
- **Different NSI fields.** NSI 2026, lower-case field names; no employees, nursing-home residents,
  basement flag or own year built. The skill lists the fields that exist and says what is missing.
- **Exposure, not damage.** The NSI skill reports the value of flooded buildings as *exposure*; dollar
  damage needs depth-damage functions, which the data does not include.
- **Arrival times** are hours after the dam failure (negative: before it, from non-failure flows). The
  18 h simulation starts 8.83 h before the failure.
- **Facilities: schools, hospitals and power only** (the team's v3). Three are hypothetical, placed by
  the AidEM team: Franklin Power Ventures (a flooded power plant), Franklin Memorial Medical Center and
  Franklin K-12.
- **Only the flood grid is read.** The grids have 0.76 m cells, too large to download whole, so the code
  fetches only facilities and buildings inside the flood grid and reads the grid in 1–2 km tiles
  around them (WCS).

## Conventions to adapt

Like the Kanawha skills, the code writes its outputs to the folder in the `TEMP_DIR` environment
variable (here it falls back to the current folder):

- `*.wms.json`: a WMS layer to add to the map (`url`, `layers`, `name`, `opacity`, `bbox` as
  [south, west, north, east])
- `*.geojson`: a vector layer to add to the map (EPSG:4326)
- `*.csv`: tables

If your system adds map layers another way, change those few lines.

Python packages: geopandas, numpy, pandas, requests, rasterio.

## Tests

`tests/test_skills.py` runs each skill's example code exactly as written in its `SKILL.md`
(plus variants: all facility types, two types) and checks the files it writes and the numbers it
prints. Rerun it after changing a skill or the GeoServer layers (network access needed, about 1 minute):

```bash
pip install geopandas numpy pandas requests rasterio pytest
pytest -v studies/cambria-county/tests
```

Results (2026-11-14, `CambriaCounty_*` layers, facilities v3):

| Skill | Result | Time |
|---|---|---|
| flood-depth | WMS layer shows the flood along the Little Conemaugh, Stonycreek and Conemaugh | instant |
| cikr-impact, all types | 50 facilities in the flood grid, 9 flooded (with Franklin Power Ventures and Franklin K-12) | about 6 s |
| cikr-impact, schools + arrival time | 7 flooded schools | about 6 s |
| nsi-impact | 44,113 buildings in the grid, 2,588 flooded; 5,752 people at night, 14,367 by day | about 33 s |

These match the cascade analysis (9 wet facilities; 2,587 buildings: one building at the flood's edge
differs because the GeoServer grids were reprojected to EPSG:5070).
