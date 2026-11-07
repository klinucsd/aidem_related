---
name: cambria-county-cikr-impact
description: Flood impact of the simulated Cambria County South Fork Dam Breach Scenario (Johnstown, PA) on critical facilities (schools, hospitals, EMS, fire stations, police, prisons, substations, power plants, wastewater plants, airports, terminals, broadcast) with their names and addresses. Use instead of any generic school/hospital/infrastructure skill for Johnstown. Returns flooded facilities by severity, depth, flood force and arrival time.
---

# Cambria County CIKR Impact Skill

## Description

Analyzes the impact of the **simulated** Cambria County dam breach (USACE HEC-RAS 2D, a hypothetical event,
not a real flood) on critical infrastructure (CIKR). Reads the event's maximum flood depth at each
facility, classifies severity, saves the facilities as a map layer and prints a summary.

**One event, no flow scenarios**: unlike the Kanawha study there is no flow (cfs) to choose. If the user
gives a flow, explain that the Cambria County study has a single dam-failure scenario.

**Severity classification (maximum depth above the ground):**
| Severity | Depth |
|----------|-------|
| Not Flooded | 0 ft |
| Nuisance | 0 – 1 ft |
| Minor | 1 – 3 ft |
| Moderate | 3 – 6 ft |
| Severe | > 6 ft |

**WFS layer `tiger:CambriaCounty_CIKR_Points_5070`: ONLY these fields exist:**
- `NAME` (string): facility name
- `Address` (string): street address
- `Point_Type` (string): facility type; use it for all filtering and grouping
- `id` (string): GeoServer feature id, not a name

There is no county, city, capacity, bed count, enrollment or phone field. Do not access other columns.

**Point_Type values:**
Airports, Broadcast Communication, Colleges and Universities, Correctional Facilities, EMS,
Electric Power Generation, Electric Substations, Fire Stations, Fire Stations EMS, Heliports, Hospitals,
Gas-Fired Power Plant, Hydroelectric Power Generation, Intermodal Terminal Facilities, Law Enforcement, Natural Gas Storage,
Petroleum Terminals, Schools, Wastewater Treatment Plants

("Gas-Fired Power Plant" is Franklin Power Ventures, a hypothetical plant the AidEM team added to the
scenario. Note: "Wastewater Treatment Plants" here, "Waste Water Treatment Plants" in the Kanawha data.)

**Other values that can be read at each facility (the `GRIDS` dict in the example):**
| Key | Grid | Units |
|-----|------|-------|
| `depth_ft` | Maximum flood depth | ft |
| `dxv` | Maximum depth × velocity: the force of the water (structures and people) | ft²/s |
| `velocity` | Maximum flow velocity (values up to about 280 ft/s in a few places may be model artefacts) | ft/s |
| `arrival_wet_h` | Arrival time, first wet | hours after the dam failure |
| `arrival_2ft_h` | Arrival time, 2 ft deep (the team's failure criterion for facilities) | hours after the dam failure |
| `arrival_max_h` | Arrival time, maximum depth | hours after the dam failure |

Arrival times are **hours after the dam failure** (negative: before it, flooded by non-failure flows).
The 18 h simulation starts 8.83 h before the failure, so values run from −8.83 (wet from the start) to
about 9. Report them as hours after the dam failure, and say "before the failure" for negative values.

## When to Use

- User asks which / how many facilities are flooded in the Cambria County dam breach
- User asks "which schools / fire stations / police stations get wet, and how deep?"
- User asks which facilities get wet first, or how strong the flood is at them
- User asks for a Cambria County flood impact report on critical infrastructure

## When NOT to Use

This skill has facility locations, names, types and flood values only. For people, students, building
values or building types, use **cambria-county-nsi-impact**. Hospital beds, enrollment and employees are not in
either dataset: tell the user this information is not available.

## Example

### Show all flooded schools, with depth and arrival time

Substitute `filter_type` (None for all types) and `extra` (other grids to read; [] for depth only).

```python
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from rasterio.io import MemoryFile

OWS = "https://sparcal.sdsc.edu/geoserver/tiger/ows"
EXTENT = (1419345.95, 2043397.76, 1449566.93, 2066727.97)  # the flood grids, EPSG:5070 metres
GRIDS = {
    "depth_ft": "tiger__CambriaCounty_Depth_Max_5070",
    "dxv": "tiger__CambriaCounty_DxV_Max_5070",
    "velocity": "tiger__CambriaCounty_Velocity_Max_5070",
    "arrival_wet_h": "tiger__CambriaCounty_Arrival_Wet_5070",
    "arrival_2ft_h": "tiger__CambriaCounty_Arrival_2ft_5070",
    "arrival_max_h": "tiger__CambriaCounty_Arrival_MaxDepth_5070",
}

# ← substitute from user's request
# Single type: "Schools"  |  Multiple types: ["Schools", "Hospitals"]  |  All: None
filter_type = "Schools"
extra = ["arrival_wet_h"]   # any of: "dxv", "velocity", "arrival_wet_h", "arrival_2ft_h", "arrival_max_h"

temp_dir = os.environ.get("TEMP_DIR", ".")


def sample_grid(points: gpd.GeoSeries, coverage: str, tile: float = 1000.0) -> np.ndarray:
    """The grid's value at each EPSG:5070 point (NaN outside the grid or where the grid has no value).
    The grids have 0.76 m cells, far too large to download whole: read 1 km tiles around the points."""
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
import json
with open(os.path.join(temp_dir, "cambria_county_flood_depth.wms.json"), "w") as f:
    json.dump({"url": "https://sparcal.sdsc.edu/geoserver/tiger/wms",
               "layers": "tiger:CambriaCounty_Depth_Max_5070",
               "name": "Cambria County Dam Breach: Max Flood Depth (simulated)",
               "opacity": 0.7, "bbox": [40.2168, -79.0759, 40.4701, -78.6732]}, f)

# --- Step 2: Fetch the facilities inside the flood grid (169 of the study's 2,047) ---
wfs_url = (f"{OWS}?service=WFS&version=2.0.0&request=GetFeature"
           f"&typeNames=tiger:CambriaCounty_CIKR_Points_5070&outputFormat=application/json")
bbox = f"BBOX(the_geom,{EXTENT[0]},{EXTENT[1]},{EXTENT[2]},{EXTENT[3]},'EPSG:5070')"
if filter_type:
    types = filter_type if isinstance(filter_type, list) else [filter_type]
    cql = bbox + " AND Point_Type IN (" + ", ".join("'" + t.replace("'", "''") + "'" for t in types) + ")"
else:
    cql = bbox
cikr = gpd.read_file(wfs_url + "&CQL_FILTER=" + quote(cql))   # EPSG:5070
print(f"Facilities in the flood grid: {len(cikr)} ({filter_type or 'all types'})")

# --- Step 3: Read the flood grids at each facility ---
for col in ["depth_ft"] + [e for e in extra if e != "depth_ft"]:
    cikr[col] = sample_grid(cikr.geometry, GRIDS[col])
cikr.loc[~(cikr["depth_ft"] > 0), "depth_ft"] = np.nan   # depth 0 or no value = dry
dry = cikr["depth_ft"].isna()
for col in extra:   # other grids only count where the place gets wet
    cikr.loc[dry, col] = np.nan
cikr["severity"] = cikr["depth_ft"].apply(classify)

# --- Step 4: Save the facilities as a map layer (WGS84) ---
if filter_type is None:
    label = "all_cikr"
elif isinstance(filter_type, list):
    label = "_".join(t.split()[0].lower() for t in filter_type)
else:
    label = filter_type.lower().replace(" ", "_")
flooded = cikr[~dry].copy()
flooded.to_crs(epsg=4326).to_file(os.path.join(temp_dir, f"cambria_county_{label}_flooded.geojson"), driver="GeoJSON")
print(f"Saved {len(flooded)} flooded facilities to map layer cambria_county_{label}_flooded")

# --- Step 5: Print the summary ---
print("\n=== Cambria County simulated dam breach: CIKR impact ===")
print(f"Facilities in the flood grid: {len(cikr)}   flooded (any depth): {len(flooded)}")
for sev in ["Nuisance", "Minor", "Moderate", "Severe"]:
    print(f"  {sev}: {(cikr['severity'] == sev).sum()}")
cols = ["NAME", "Point_Type", "Address", "depth_ft", "severity"] + extra
print("\nFlooded facilities (deepest first):")
print(flooded.sort_values("depth_ft", ascending=False)[cols].round(2).to_string(index=False))
if extra and any(c.startswith("arrival") for c in extra):
    print("\nArrival times: hours after the dam failure (negative: before it).")

pivot = (flooded.groupby(["Point_Type", "severity"]).size().unstack(fill_value=0)
         .reindex(columns=["Nuisance", "Minor", "Moderate", "Severe"], fill_value=0))
pivot["Total"] = pivot.sum(axis=1)
print("\nBy facility type:")
print(pivot.to_string())
pivot.to_csv(os.path.join(temp_dir, f"cambria_county_cikr_summary_{label}.csv"))
flooded.drop(columns="geometry").to_csv(os.path.join(temp_dir, f"cambria_county_{label}_flooded.csv"), index=False)
```

## Notes

- **Simulated event**: always call it a simulated (hypothetical) dam failure, never a real flood.
- **Expected result (all types)**: 24 facilities get wet: 6 schools, 5 fire stations, 3 police
  departments, 2 EMS, 1 Fire Stations EMS, 2 intermodal terminals (Amtrak station, Greyhound stop),
  1 hospital (Crichton Rehabilitation Center), 1 prison (Johnstown CCC), 1 broadcast station (WLKJ-FM1),
  1 wastewater plant (Dornick Point WWTP) and the hypothetical Franklin Power Ventures (10.4 ft). All CIKR
  electric substations stay dry. 22 of them reach 2 ft, the team's failure criterion (two schools get
  less than 0.2 ft).
- **Duplicate**: Forest Hills Area Ambulance Association is listed twice (as EMS and as Fire Stations EMS):
  count it once when counting distinct places.
- **Only the flood grid is read**: facilities outside the grid's extent are not fetched; they cannot be
  flooded in this event. The study area (8 counties) holds 2,047 facilities in all.
- **Speed**: about 10 seconds for all facilities (more with each extra grid).
- **CRS**: CIKR points and grids are both EPSG:5070 (metres); reproject the whole GeoDataFrame
  (`gdf.to_crs(epsg=4326)`), never a single geometry, to print latitude and longitude.
