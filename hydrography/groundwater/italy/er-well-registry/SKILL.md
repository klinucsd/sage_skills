---
name: er-well-registry
description: >-
  Retrieve the Emilia-Romagna groundwater well registry (Anagrafica) as a
  GeoPandas GeoDataFrame in EPSG:4326. Use whenever the user asks about
  well metadata in Emilia-Romagna — well depth, ground elevation, filter
  intervals, aquifer / groundwater body, station type, municipality, or
  province — for example "how deep is well X", "which wells are in
  Bologna", "wells screened in the confined aquifer", "deepest wells in
  Emilia-Romagna", or "how was the well drilled". Loads the latest
  bundled Anagrafica file (2020), reprojects UTM-ETRS89 coordinates to
  EPSG:4326, and returns one row per well with Point geometry — ready to
  filter, map, save as GeoJSON, or spatially join with other skills'
  outputs (e.g. po-wells WTD measurements).
---

# Emilia-Romagna Well Registry Skill

This skill loads the Emilia-Romagna regional groundwater observation
registry (the *Anagrafica*) from a bundled Excel file and returns it as a
**GeoPandas GeoDataFrame** in EPSG:4326 with Point geometries. The 2020
edition covers **447 wells** distributed across 9 provinces.

The registry is **complementary to the po-wells skill**: po-wells
provides the time-averaged water-table-depth values (WTD, STD) for 238
basin wells; this skill provides the **per-well static metadata** —
depth, ground elevation, filter intervals, aquifer assignment, station
type — for the Emilia-Romagna subset. Only ~23 wells appear in both;
the remaining ~424 registry wells are not in po-wells (no time-averaged
WTD published), and most po-wells P+E wells are in Piemonte (not
covered here).

## What the data is

The Anagrafica is a yearly snapshot maintained by the Emilia-Romagna
regional environmental agency. Each row describes one **observation
station** (typically a `Pozzo` — well — but a few are `Piezometro` or
`Sorgente` / spring) with its administrative location, the aquifer it
samples, and its construction details.

- **`station_type`**: `Pozzo` (well), `Piezometro` (piezometer), or
  `Sorgente` (spring).
- **`well_depth_m`**: total depth of the borehole, in meters.
- **`ground_elevation_m`**: ground surface elevation at the well head
  (m above sea level).
- **`filter_top_m`** / **`filter_bottom_m`** / **`filter_count`**: the
  intake screen (filter) intervals through which water enters the well.
- **`aquifer_name`** / **`aquifer_code`**: the regional groundwater body
  (`Corpo Idrico Sotterraneo`, GWB) the well samples — typically named
  by the aquifer type (e.g. `Pianura Alluvionale Appenninica -
  confinato superiore` = "Apennine alluvial plain — upper confined").

## The source files

Nine yearly Anagrafica files ship with this skill, named
`Anagrafica<year>.xlsx` for years 2012–2020. They live at
`skills/er-well-registry/data/`. The loader uses **2020 as the primary
inventory** because it has the richest metadata (LAT/LON columns, GWB
naming aligned with the 2015–2021 regional classification) and reflects
the currently-monitored network.

Earlier years are bundled for two reasons: (1) historical-coverage
questions ("when was this well first registered?"), and (2) some wells
retired before 2020 are only present in earlier files. Load them by
year as needed; the column set varies between years and a normalization
helper would be required for cross-year joins.

## Known source-data quirks

- **`LAT` and `LON` columns are swapped** in the 2020 file (and others):
  the column labeled `LAT` actually contains *longitude* values
  (~10–13°E), and the column labeled `LON` contains *latitude* values
  (~44–45°N). The loader **ignores both** and reprojects from the
  unambiguous UTM-ETRS89 (zone 32) coordinates instead.
- The depth column header is `Profondità (m)` in proper Italian, but in
  the xlsx it reads as `Profondit� (m)` due to a character-encoding
  issue. The loader detects the column by its `Profondit` prefix.
- Column names vary across years (e.g., 2012–2014 use UTM-ED50, later
  years use UTM-ETRS89). The loader handles only the 2020 schema by
  default.

## Unified GeoDataFrame schema

After `load_er_well_registry()` runs, every well is one row:

| Column | Type | Meaning |
|--------|------|---------|
| `well_id` | str | Original well identifier (`Codice`) |
| `station_type` | str | `Pozzo`, `Piezometro`, or `Sorgente` |
| `province` | str | 2-letter Italian province code (BO, MO, FE, …) |
| `municipality` | str | Italian comune (uppercase, e.g. `SAN PIETRO IN CASALE`) |
| `aquifer_code` | str | Regional groundwater-body code (`Codice_GWB_2015-2021`) |
| `aquifer_name` | str | Human-readable aquifer name |
| `ground_elevation_m` | float | Ground surface elevation, m above sea level |
| `well_depth_m` | float | Total borehole depth, m |
| `filter_position` | str | Filter placement description (often NaN) |
| `filter_count` | int | Number of screen intervals |
| `filter_top_m` | float | Top of shallowest filter, m below ground |
| `filter_bottom_m` | float | Bottom of deepest filter, m below ground |
| `geometry` | Point | Well location, EPSG:4326 (lon, lat) |

CRS: `EPSG:4326`. Total rows: **447** (2020 snapshot).

### Province codes

`BO` Bologna · `FC` Forlì-Cesena · `FE` Ferrara · `MO` Modena · `PC`
Piacenza · `PR` Parma · `RA` Ravenna · `RE` Reggio Emilia · `RN` Rimini.

Well IDs sometimes include a third letter (e.g. `BOA-12`, `PRC-05`)
indicating a sub-category within the province; the loader still
classifies these by the first two letters.

## Standard loader

```python
import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

SKILL_DATA = "skills/er-well-registry/data"

def load_er_well_registry(year: int = 2020) -> gpd.GeoDataFrame:
    """Load the Emilia-Romagna well registry as a GeoDataFrame in EPSG:4326.

    Default is the 2020 snapshot (447 wells, richest metadata). Other years
    (2012-2019) have variable schemas and are not normalized by this loader.
    """
    df = pd.read_excel(f"{SKILL_DATA}/Anagrafica{year}.xlsx", sheet_name=0)

    # The depth column header has a character-encoding artifact in the
    # source; detect it by prefix rather than literal match.
    depth_col = next(c for c in df.columns if c.lower().startswith("profondit"))

    df = df.rename(columns={
        "Codice":                       "well_id",
        "Tipologia stazione":           "station_type",
        "Comune":                       "municipality",
        "Codice_GWB_2015-2021":         "aquifer_code",
        "Nome_GWB_2015-2021":           "aquifer_name",
        "Quota PC (m)":                 "ground_elevation_m",
        depth_col:                      "well_depth_m",
        "Posizione filtri":             "filter_position",
        "N tot filtri":                 "filter_count",
        "Inizio filtri: da m":          "filter_top_m",
        "Fine filtri: a m":             "filter_bottom_m",
    })
    df["province"] = df["well_id"].astype(str).str[:2]

    # Use UTM-ETRS89 (zone 32, EPSG:25832) to build the geometry — the
    # raw LAT/LON columns in the source are swapped and unreliable.
    geom = [
        Point(x, y)
        for x, y in zip(df["XUTM-ETRS89 (fuso 32)"], df["YUTM-ETRS89 (fuso 32)"])
    ]
    gdf = gpd.GeoDataFrame(
        df[["well_id", "station_type", "province", "municipality",
            "aquifer_code", "aquifer_name", "ground_elevation_m",
            "well_depth_m", "filter_position", "filter_count",
            "filter_top_m", "filter_bottom_m"]],
        geometry=geom,
        crs="EPSG:25832",
    )
    return gdf.to_crs("EPSG:4326")
```

A single call returns the full 447-well GeoDataFrame for the 2020
inventory.

## Saving for the map

```python
import os
os.makedirs(temp_dir, exist_ok=True)
out = os.path.join(temp_dir, "er_wells.geojson")
gdf.to_file(out, driver="GeoJSON")
```

## Example queries (each returning a GeoDataFrame)

### Look up a specific well

```python
gdf = load_er_well_registry()
single = gdf[gdf.well_id == "BO03-01"]
print(single[["well_id", "municipality", "well_depth_m", "aquifer_name"]])
```

### Deepest wells in Emilia-Romagna

```python
gdf = load_er_well_registry()
deepest = gdf.nlargest(10, "well_depth_m")
deepest.to_file(os.path.join(temp_dir, "deepest_er_wells.geojson"),
                driver="GeoJSON")
# Expect MO16-00 (~538 m, in Ravarino) as the deepest.
```

### Wells in a specific province

```python
gdf = load_er_well_registry()
bologna = gdf[gdf.province == "BO"]
bologna.to_file(os.path.join(temp_dir, "bologna_wells.geojson"),
                driver="GeoJSON")
```

### Wells screened in confined aquifers

```python
gdf = load_er_well_registry()
confined = gdf[gdf.aquifer_name.str.contains("confinato", case=False, na=False)]
confined.to_file(os.path.join(temp_dir, "confined_aquifer_wells.geojson"),
                 driver="GeoJSON")
```

### Distribution of well depth by province

```python
gdf = load_er_well_registry()
summary = gdf.groupby("province").agg(
    n_wells=("well_id", "count"),
    mean_depth_m=("well_depth_m", "mean"),
    median_depth_m=("well_depth_m", "median"),
    max_depth_m=("well_depth_m", "max"),
).round(1).sort_values("max_depth_m", ascending=False)
print(summary)
```

### Wells in a bounding box (e.g., around Modena)

```python
gdf = load_er_well_registry()
modena_box = gdf.cx[10.8:11.2, 44.5:44.8]  # lon, lat
modena_box.to_file(os.path.join(temp_dir, "modena_box_wells.geojson"),
                   driver="GeoJSON")
```

### Wells near a point (within N kilometers)

```python
gdf = load_er_well_registry()
gdf_m = gdf.to_crs("EPSG:25832")  # metric CRS for distance

from shapely.geometry import Point
target = gpd.GeoSeries([Point(11.34, 44.49)], crs="EPSG:4326").to_crs("EPSG:25832").iloc[0]  # Bologna

radius_km = 30
nearby = gdf_m[gdf_m.geometry.distance(target) <= radius_km * 1000]
nearby = nearby.to_crs("EPSG:4326")
nearby.to_file(os.path.join(temp_dir, "near_bologna_wells.geojson"),
               driver="GeoJSON")
```

### Cross-skill spatial join — registry × po-wells WTD

```python
# Combine static metadata (this skill) with time-averaged WTD (po-wells)
# on Well ID, for the ~23 wells in both.
gdf = load_er_well_registry()
from po_wells_loader import load_po_wells  # or replicate the loader here
po = load_po_wells()
joined = gdf.merge(
    po[["well_id", "wtd_m", "std_m"]],
    on="well_id", how="inner",
)
joined.to_file(os.path.join(temp_dir, "er_wells_with_wtd.geojson"),
               driver="GeoJSON")
print(f"{len(joined)} ER wells with WTD measurements")
```

## Provenance — name the source file when reporting

Every reported value should be traceable to a source xlsx. Use the
**bare filenames as they appear in the original repository**
(`github.com/rlsandovalp/Well_data_Po`) — do not include the local
`skills/er-well-registry/data/` prefix in citations.

For the 2020 loader (the default), all metadata columns come from a
single file:

| What you report | File to cite |
|-----------------|--------------|
| Any registry attribute (depth, elevation, filters, aquifer, station type, municipality, province, geometry) | `Anagrafica2020.xlsx` |

If you load a different year, cite the corresponding file (e.g.
`Anagrafica2017.xlsx`). For cross-skill joins (e.g., registry × po-wells),
cite both files — the registry's `Anagrafica<year>.xlsx` for the
metadata columns and the relevant po-wells CSV for any WTD/STD values
(see po-wells SKILL.md for its column-to-file map).

Always include this provenance line in the final response whenever the
user asks where a value came from, asks about reproducibility, or asks
about data sources.

## Reporting tips

- Always state the **province** (and where relevant, the municipality)
  in the answer.
- Depths and elevations are in **meters**; depths are below ground,
  elevations are above sea level.
- "Confined aquifer" → look for `confinato` in `aquifer_name`;
  "unconfined / phreatic" → look for `freatico` / unconfined contexts.
- The 2020 snapshot covers only the **currently-monitored** 447 wells;
  for historical or retired wells, load an earlier `Anagrafica<year>`.
- Station type matters: `Pozzo` (well) is the common case; `Piezometro`
  (piezometer) wells are dedicated monitoring boreholes; `Sorgente`
  (spring) entries do not have a well depth in the conventional sense.
- This skill covers Emilia-Romagna only. Lombardia and Piemonte wells
  are not in the registry; for those, see the po-wells skill for
  coordinates and (where available) time-averaged WTD.
