---
name: sdge-goes-fire
description: Retrieve GOES satellite fire detections for Southern California from SDG&E WIFIRE. Use for questions about recent wildfires, active fire hotspots, satellite-detected fires, fire radiative power, and fire activity trends in the San Diego and Southern California region.
license: Apache-2.0
---

# SDG&E GOES Fire Detection Skill

Fetches GOES satellite fire detections (last 7 days) from the SDG&E WIFIRE
GeoServer. Data is updated in near real-time.

## Dependencies

```
pip install requests geopandas pandas
```

## Importing the helper

The helper module `sdge_goes_fire_basic.py` lives next to this SKILL.md.
Add the skill directory to `sys.path` before importing:

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from sdge_goes_fire_basic import fetch_goes_fires
```

## API

```python
fetch_goes_fires(output_file)   # destination GeoJSON path
```

Returns a `GeoDataFrame` and writes a GeoJSON with fields:

| Field | Description |
|---|---|
| `data_time` | UTC timestamp of the detection |
| `lon` / `lat` | Detection location (EPSG:4326) |
| `hours_ago` | Hours elapsed since the detection (derived from `seconds_ago`) |

## Full example

```python
import sys

# Substitute the absolute path of the directory containing this SKILL.md
sys.path.insert(0, "/path/to/skills/sdge-goes-fire")
from sdge_goes_fire_basic import fetch_goes_fires

output_file = "fire_detections.geojson"
gdf = fetch_goes_fires(output_file)
print(f"{len(gdf)} fire detections")
```

## Analysis tips

- `hours_ago` — how many hours since the detection
- `data_time` — UTC timestamp of the detection
- Group detections by date: `gdf.groupby(gdf["data_time"].dt.date).size()`
- Filter to a county: use the `us-counties` skill to get county geometry,
  then spatial join
- To color fire points by fuel moisture risk, use the `sdge-surface-fuels`
  skill
