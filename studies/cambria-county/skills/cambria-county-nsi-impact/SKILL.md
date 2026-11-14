---
name: cambria-county-nsi-impact
description: "Use this for questions about buildings, people and property in the simulated Cambria County South Fork Dam Breach Scenario (Cambria County, PA): population at risk (day/night, over 65, disabled), students, residential units, value of flooded buildings, building types (hospitals=COM6, schools=EDU1, nursing homes=RES6, mobile homes=RES2, churches=REL1, heavy industry=IND1), FEMA flood zones. Uses the National Structure Inventory 2026 (USACE). No employees, nursing-home residents, basements or own year built, and no dollar damage (only exposure)."
---

# Cambria County NSI Flood Impact Skill

## Description

Analyzes population exposure and the value of flooded buildings in the **simulated** Cambria County dam
breach (USACE HEC-RAS 2D, a hypothetical event, not a real flood), using USACE's National Structure
Inventory 2026 (NSI) for the study area. Reads the event's maximum flood depth at each building, then
aggregates people and building values.

**One event, no flow scenarios**: unlike the Kanawha study there is no flow (cfs) to choose.

**Exposure, not damage.** The data has no depth-damage functions, so dollar damage cannot be computed.
The sum of `val_struct + val_cont + val_vehic` of flooded buildings is the **value exposed** to the flood;
always call it exposure (or "value of flooded buildings"), never damage or losses.

**WFS layer `tiger:CambriaCounty_NSI2026_5070` (546,719 buildings in 8 counties; 44,113 inside the flood
grid). The geometry column is `geom`. Use ONLY these fields (lower case):**

| Field | Description |
|-------|-------------|
| `fd_id` | NSI structure id |
| `occtype` | Occupancy type code (table below); single-family codes add stories and basement, e.g. `RES1-1SNB` = 1 story, no basement, `RES1-2SWB` = 2 stories, with basement |
| `st_damcat` | Damage category: RES (homes and apartments), COM (businesses, plus agriculture AGR1, hotels RES4, dormitories RES5 and nursing homes RES6), IND, PUB (schools, colleges, government, churches). There is no GOV, EDU, REL or AGR category: filter building types by `occtype` |
| `bldgtype` | Construction: M (masonry), W (wood), H (manufactured), S (steel) |
| `found_type`, `found_ht` | Foundation type and height (ft) |
| `num_story`, `sqft` | Stories, floor area (sq ft) |
| `resunits` | Residential units |
| `students` | Students (schools, colleges) |
| `pop2amu65`, `pop2amo65` | Night-time population under / over 65 |
| `pop2pmu65`, `pop2pmo65` | Daytime population under / over 65 |
| `u65disable`, `o65disable` | Disabled population under / over 65 |
| `val_struct`, `val_cont`, `val_vehic` | Structure, contents and vehicle value (USD, 2026 price level) |
| `med_yr_blt` | Median year built of the census block (an area estimate, NOT this building's own year) |
| `ground_elv` | Ground elevation (ft, NAVD88) |
| `firmzone`, `zone_sub` | Estimated FEMA flood zone (X, AE, A, AO) and subtype as text |
| `cbfips` | Census block FIPS code |

**Not available** (unlike the Kanawha NSI): employees (`EMPNUM`), nursing-home residents (`NURSGHMPOP`),
basement flag (`BSMNT`; use the `occtype` RES1 suffix instead), the building's own year built (`YRBUILT`),
names and addresses. Hospital beds are in neither the NSI nor the CIKR data. Say so when asked. Fields
present but not documented by USACE (`depindex`, `crerank`, `creprcnt`, `novehprob`, `pctlowclr`,
`fullrep`, `vehperunit`, `static_bfe`, `source`, `ftprntsrc`) must not be used.

**occtype codes** (filter on the start of the code, e.g. `nsi.occtype.str.startswith("RES1")`):

| occtype | Description | occtype | Description |
|---------|-------------|---------|-------------|
| RES1 | Single-family residential | COM6 | Hospital |
| RES2 | Mobile home | COM7 | Medical office |
| RES3A–RES3F | Multi-family (2, 3–4, 5–9, 10–19, 20–49, 50+ units) | COM8 | Entertainment or recreation |
| RES4 | Hotel or motel | COM9 | Theater |
| RES5 | Institutional dormitory | COM10 | Parking garage |
| RES6 | Nursing home | IND1 | Heavy industrial |
| COM1 | Retail | IND2 | Light industrial |
| COM2 | Wholesale | IND3 | Food, drug or chemical processing |
| COM3 | Personal and repair services | IND4 | Metals or minerals processing |
| COM4 | Professional or technical services | IND5 | High technology |
| COM5 | Bank | IND6 | Construction |
| AGR1 | Agriculture | GOV1 | Government services |
| REL1 | Church or other religious building | GOV2 | Emergency response |
| EDU1 | School | EDU2 | College or university |

## When to Use

- User asks how many buildings or people are flooded in the Cambria County dam breach
- User asks about population at risk (day / night, elderly, disabled), students, residential units
- User asks about the value of flooded buildings, or about flooded buildings of a given type
- User asks for a comprehensive Cambria County flood impact report including people and property

## Example

### Buildings, people and value exposed to the Cambria County dam breach

```python
import json, os
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from rasterio.io import MemoryFile

OWS = "https://sparcal.sdsc.edu/geoserver/tiger/ows"
EXTENT = (1419345.95, 2043397.76, 1449566.93, 2066727.97)  # the flood grids, EPSG:5070 metres
DEPTH = "tiger__CambriaCounty_Depth_Max_5070"
FIELDS = ["fd_id", "occtype", "st_damcat", "bldgtype", "num_story", "sqft", "resunits", "students",
          "pop2amu65", "pop2amo65", "pop2pmu65", "pop2pmo65", "u65disable", "o65disable",
          "val_struct", "val_cont", "val_vehic", "firmzone"]

temp_dir = os.environ.get("TEMP_DIR", ".")


def sample_grid(points: gpd.GeoSeries, coverage: str, tile: float = 2000.0) -> np.ndarray:
    """The grid's value at each EPSG:5070 point (NaN outside the grid or where the grid has no value).
    The grids have 0.76 m cells, far too large to download whole: read 2 km tiles around the points."""
    xs, ys = points.x.to_numpy(), points.y.to_numpy()
    out = np.full(len(xs), np.nan)
    inside = (xs >= EXTENT[0]) & (xs <= EXTENT[2]) & (ys >= EXTENT[1]) & (ys <= EXTENT[3])
    tx, ty = np.floor(xs / tile).astype(int), np.floor(ys / tile).astype(int)

    def fetch(key):
        x0, y0 = key[0] * tile, key[1] * tile
        url = (f"{OWS}?service=WCS&version=2.0.1&request=GetCoverage&coverageId={coverage}"
               f"&format=image/tiff&SUBSET=X({x0},{x0 + tile})&SUBSET=Y({y0},{y0 + tile})"
               "&GEOTIFF:COMPRESSION=DEFLATE")
        r = requests.get(url, timeout=300)
        return key, (r.content if r.ok and r.content[:2] in (b"II", b"MM") else None)

    with ThreadPoolExecutor(6) as pool:
        for (kx, ky), data in pool.map(fetch, sorted(set(zip(tx[inside], ty[inside])))):
            if data is None:
                continue
            sel = np.flatnonzero(inside & (tx == kx) & (ty == ky))
            with MemoryFile(data) as mem, mem.open() as src:
                v = np.array([s[0] for s in src.sample(list(zip(xs[sel], ys[sel])))], dtype=float)
                if src.nodata is not None:
                    v[v == src.nodata] = np.nan
            out[sel] = v
    return out


def classify(d):
    if np.isnan(d): return "Not Flooded"
    if d <= 1:      return "Nuisance"
    if d <= 3:      return "Minor"
    if d <= 6:      return "Moderate"
    return "Severe"


# --- Step 1: Add the flood depth WMS layer to the map ---
with open(os.path.join(temp_dir, "cambria_county_flood_depth.wms.json"), "w") as f:
    json.dump({"url": "https://sparcal.sdsc.edu/geoserver/tiger/wms",
               "layers": "tiger:CambriaCounty_Depth_Max_5070",
               "name": "Cambria County Dam Breach: Max Flood Depth (simulated)",
               "opacity": 0.7, "bbox": [40.2168, -79.0759, 40.4701, -78.6732]}, f)

# --- Step 2: Fetch the buildings inside the flood grid (44,113; a few seconds) ---
wfs_url = (f"{OWS}?service=WFS&version=2.0.0&request=GetFeature"
           f"&typeNames=tiger:CambriaCounty_NSI2026_5070&outputFormat=application/json"
           f"&propertyName=geom,{','.join(FIELDS)}"
           f"&bbox={EXTENT[0]},{EXTENT[1]},{EXTENT[2]},{EXTENT[3]},EPSG:5070")
nsi = gpd.read_file(wfs_url)   # EPSG:5070
print(f"Buildings in the flood grid: {len(nsi):,}")

# --- Step 3: Read the maximum depth at each building (about 30 seconds) ---
nsi["depth_ft"] = sample_grid(nsi.geometry, DEPTH)
nsi.loc[~(nsi["depth_ft"] > 0), "depth_ft"] = np.nan   # depth 0 or no value = dry
flooded = nsi[nsi["depth_ft"].notna()].copy()
flooded["severity"] = flooded["depth_ft"].apply(classify)
print(f"Flooded buildings: {len(flooded):,}")

# --- Step 4: People and value exposed ---
flooded["pop_night"] = flooded.pop2amu65 + flooded.pop2amo65
flooded["pop_day"] = flooded.pop2pmu65 + flooded.pop2pmo65
flooded["value_total"] = flooded.val_struct + flooded.val_cont + flooded.val_vehic
pop_night, pop_day = flooded.pop_night.sum(), flooded.pop_day.sum()

by_cat = flooded.groupby("st_damcat").agg(
    buildings=("depth_ft", "size"),
    pop_night=("pop_night", "sum"),
    pop_day=("pop_day", "sum"),
    value_total=("value_total", "sum"),
).sort_values("buildings", ascending=False)
by_sev = flooded.groupby("severity").size().reindex(["Nuisance", "Minor", "Moderate", "Severe"], fill_value=0)

# --- Step 5: Choose the buildings to show on the map ---
# The summary above uses every flooded building; filter only what is drawn. Examples:
# display = flooded[flooded.occtype.str.startswith("RES6")]   # nursing homes
# display = flooded[flooded.occtype.str.startswith("RES2")]   # mobile homes
# display = flooded[flooded.students > 0]                     # schools and colleges
# display = flooded[flooded.severity == "Severe"]
display = flooded
cols = ["geometry", "fd_id", "occtype", "st_damcat", "depth_ft", "severity", "pop2amu65", "pop2amo65",
        "pop2pmu65", "pop2pmo65", "students", "resunits", "val_struct", "val_cont", "val_vehic"]
display[cols].to_crs(epsg=4326).to_file(os.path.join(temp_dir, "cambria_county_nsi_flooded.geojson"), driver="GeoJSON")
print(f"Saved {len(display):,} buildings to map layer cambria_county_nsi_flooded")

# --- Step 6: Save tables ---
by_cat.to_csv(os.path.join(temp_dir, "cambria_county_nsi_summary.csv"))
flooded.drop(columns="geometry").to_csv(os.path.join(temp_dir, "cambria_county_nsi_flooded.csv"), index=False)

# --- Step 7: Print the report ---
print("\n=== Cambria County simulated dam breach: buildings and people ===")
print(f"Flooded buildings: {len(flooded):,} of {len(nsi):,} in the flood grid")
print("By severity:", by_sev.to_dict())
print("\nPopulation in flooded buildings:")
print(f"  Night-time: {pop_night:,.0f} ({flooded.pop2amo65.sum():,.0f} over 65)")
print(f"  Daytime:    {pop_day:,.0f} ({flooded.pop2pmo65.sum():,.0f} over 65)")
print(f"  Disabled:   {flooded.u65disable.sum() + flooded.o65disable.sum():,.0f}")
print(f"  Students:   {flooded.students.sum():,.0f}")
print("\nValue exposed (not damage; 2026 USD):")
print(f"  Structures: ${flooded.val_struct.sum() / 1e6:,.1f}M")
print(f"  Contents:   ${flooded.val_cont.sum() / 1e6:,.1f}M")
print(f"  Vehicles:   ${flooded.val_vehic.sum() / 1e6:,.1f}M")
print(f"  Total:      ${flooded.value_total.sum() / 1e6:,.1f}M")
print("\nBy damage category:")
print(by_cat.assign(value_M=(by_cat.value_total / 1e6).round(1)).drop(columns="value_total").round(0).to_string())
```

## Notes

- **Simulated event**: always call it a simulated (hypothetical) dam failure, never a real flood.
- **Expected result**: about 2,590 flooded buildings, with about 5,750 people at night and 14,400 during
  the day.
- **Day and night**: night-time (AM) is where people sleep; daytime (PM) is where they work and study. Do
  not add the two.
- **Map display**: drawing all ~2,600 flooded buildings is fine; for bigger selections, filter first.
- **Only the flood grid is read**: buildings outside its extent are not fetched; they cannot be flooded in
  this event. Do not fetch all 546,719 buildings of the study area.
- **Other grids**: depth × velocity, velocity and arrival times can be read the same way with
  `sample_grid` (coverage ids in cambria-county-cikr-impact). Arrival times are hours after the dam failure (negative: before it).
- **CRS**: buildings and grids are both EPSG:5070 (metres); reproject the whole GeoDataFrame to EPSG:4326
  for latitude and longitude.
