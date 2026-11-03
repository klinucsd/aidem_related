---
name: johnstown-flood-depth
description: Display the maximum flood depth of the simulated Johnstown, PA dam failure (USACE HEC-RAS 2D, not a real event) as a map layer served from GeoServer WMS. Use when the user asks to show the Johnstown flood, flood area or flood depth.
---

# Johnstown Flood Depth Skill

## Description

Displays the USACE HEC-RAS 2D maximum flood depth grid of the **simulated** Johnstown dam failure as a
WMS overlay on the map.

**This is one hypothetical event, not a real flood and not a set of flow scenarios.** Unlike the Kanawha
study, there is no flow (cfs) to choose: the grid holds the deepest water each place reaches during the
event. If the user gives a flow, explain that the Johnstown study has a single dam-failure scenario.

- Grid: maximum depth above the ground, in feet, at 2.5 ft (0.762 m) cells
- Flood extent: about 30 km along the South Fork Little Conemaugh, the Little Conemaugh, the Stonycreek
  and the Conemaugh rivers through Johnstown (Cambria County, PA)
- The style on GeoServer uses the same depth classes and colours as the Kanawha layers

## When to Use

- User asks to show / display / visualize the Johnstown flood, flood area or flood depth
- User asks "what does the Johnstown dam failure flood look like?"

## Example

### Show the Johnstown flood depth

```python
import json, os

temp_dir = os.environ.get("TEMP_DIR", ".")

wms_layer = {
    "url": "https://sparcal.sdsc.edu/geoserver/tiger/wms",
    "layers": "tiger:Johnstown_Depth_Max_5070",
    "name": "Johnstown Dam Failure: Max Flood Depth (simulated)",
    "opacity": 0.7,
    "bbox": [40.2168, -79.0759, 40.4701, -78.6732],   # [south, west, north, east]: the flood grid
}
with open(os.path.join(temp_dir, "johnstown_flood_depth.wms.json"), "w") as f:
    json.dump(wms_layer, f)
print(f"WMS layer added: {wms_layer['name']}")
```

## Notes

- **Simulated event**: always describe it as a simulated (hypothetical) dam failure, never as a real flood.
- **Other grids**: GeoServer also serves the event's maximum depth × velocity (`tiger:Johnstown_DxV_Max_5070`,
  ft²/s), maximum velocity (`tiger:Johnstown_Velocity_Max_5070`, ft/s) and arrival times
  (`tiger:Johnstown_Arrival_Wet_5070`, `..._Arrival_2ft_5070`, `..._Arrival_MaxDepth_5070`). They currently
  carry the depth style on GeoServer, so do not show them on the map with this skill. Their values can be
  read at facilities and buildings with johnstown-cikr-impact and johnstown-nsi-impact.
- **Arrival times** are in model hours whose time zero USACE has not confirmed (values run from about
  −9.8 to 7.5). Never present them as hours after the dam failure.
- **Data source**: USACE HEC-RAS 2D model, December demo data package. CRS EPSG:5070; GeoServer reprojects
  for WMS display.
- **Depth units**: feet above the ground surface.
