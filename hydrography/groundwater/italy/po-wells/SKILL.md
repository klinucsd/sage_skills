---
name: po-wells
description: >-
  Retrieve Po River basin groundwater wells (northern Italy) as a GeoPandas
  GeoDataFrame in EPSG:4326. Use whenever the user asks about wells, water
  table depth (WTD), groundwater levels, well stability/fluctuation, where
  wells are located, or the Po / Lombardy / Piedmont / Emilia-Romagna well
  datasets. Loads the bundled CSVs, joins mean and standard deviation
  measurements, tags each well with its region, reprojects coordinates from
  ESRI:54012 to EPSG:4326, and returns one row per well with Point geometry
  — ready to filter, map, or save as GeoJSON.
---

# Po River Wells Skill

This skill loads **238 unique groundwater observation wells** across the Po
River plain in northern Italy and returns them as a single **GeoPandas
GeoDataFrame** in EPSG:4326 with Point geometries. Of those 238 wells,
**101 are in Lombardy** and **137 are in Piedmont + Emilia-Romagna**.
Filter, map, or save the result as GeoJSON.

## What the data is

Each well is a measurement station where the **water table depth** (WTD, in
meters) and its **standard deviation over time** (STD, in meters) are
recorded:

- **Small WTD** = water is near the surface (shallow well).
- **Large WTD** = water is deep underground.
- **Small STD** = water level is stable; **large STD** = it fluctuates (often
  from heavy pumping or strong seasonal effects).

All wells fall within northern Italy's Po plain — approximately 44.1–46.1°N
and 7.3–12.2°E.

## The four source CSVs and how they relate

The bundled CSVs are **not four independent datasets**. They are two
*paired* primary files plus two *Lombardy-subset* files of the same data:

| File | Rows | What it is |
|------|------|------------|
| `skills/po-wells/data/Steady_State_Leonardo.csv` | 238 | **Master inventory**: mean WTD for every well (all regions) |
| `skills/po-wells/data/Standard_Deviation_Leonardo.csv` | 238 | **Master inventory**: STD over time for every well (all regions) |
| `skills/po-wells/data/WTD_obs_lom_Leonardo.csv` | 101 | **Lombardy subset** of the master mean file (identical values) |
| `skills/po-wells/data/WTD_std_lom_Leonardo.csv` | 101 | **Lombardy subset** of the master STD file (identical values) |

The two Lombardy files exist only to identify which wells belong to
Lombardy — every Lombardy Well ID also appears in the master inventory
with the same coordinates and the same numeric values. Treat the master
files as the source of truth, and use one of the Lombardy files only to
tag the `region` column.

Two normalization quirks the loader handles:

1. **Different std-column names**: the master std file uses `STD`; the
   Lombardy std file uses `Standard Deviation WTD` (with spaces).
2. **Coordinates are projected, not lat/lon**: `X_54012`, `Y_54012` are
   meters in **ESRI:54012** (World Eckert IV). The loader reprojects them
   to **EPSG:4326** (WGS84 lon/lat) before returning, so the resulting
   GeoDataFrame is map-ready.

## Unified GeoDataFrame schema

After `load_po_wells()` runs, every well is one row:

| Column | Type | Meaning |
|--------|------|---------|
| `well_id` | str | Original well identifier |
| `wtd_m` | float | Mean water table depth, meters |
| `std_m` | float | Std-dev of water table depth over time, meters |
| `region` | str | `"Lombardy"` or `"Piedmont+Emilia"` |
| `geometry` | Point | Well location, EPSG:4326 (lon, lat) |

CRS: `EPSG:4326`. Total rows: **238** (101 Lombardy + 137 Piedmont+Emilia).

## Standard loader

```python
import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

SKILL_DATA = "skills/po-wells/data"

def load_po_wells() -> gpd.GeoDataFrame:
    """Load all 238 Po basin wells as a single GeoDataFrame in EPSG:4326."""
    # Master inventory: mean WTD + STD for every well across all regions.
    pe_mean = pd.read_csv(f"{SKILL_DATA}/Steady_State_Leonardo.csv")
    pe_std  = pd.read_csv(f"{SKILL_DATA}/Standard_Deviation_Leonardo.csv")
    df = pe_mean.merge(pe_std[["Well ID", "STD"]], on="Well ID")

    # The Lombardy mean file identifies which wells are in Lombardy.
    lo_mean = pd.read_csv(f"{SKILL_DATA}/WTD_obs_lom_Leonardo.csv")
    lombardy_ids = set(lo_mean["Well ID"])
    df["region"] = df["Well ID"].apply(
        lambda i: "Lombardy" if i in lombardy_ids else "Piedmont+Emilia"
    )

    df = df.rename(columns={"Well ID": "well_id",
                            "WTD":     "wtd_m",
                            "STD":     "std_m"})

    geom = [Point(x, y) for x, y in zip(df.X_54012, df.Y_54012)]
    gdf = gpd.GeoDataFrame(
        df[["well_id", "wtd_m", "std_m", "region"]],
        geometry=geom,
        crs="ESRI:54012",
    )
    return gdf.to_crs("EPSG:4326")
```

A single call to `load_po_wells()` returns the full 238-well GeoDataFrame.
Subsequent steps filter or aggregate it. The Lombardy std file
(`WTD_std_lom_Leonardo.csv`) is not read because its values duplicate the
master std file for the same 101 wells.

## Saving for the map

The WEN-OKN UI auto-loads any GeoJSON dropped into the session temp
directory. Always save the final result before reporting:

```python
import os
os.makedirs(temp_dir, exist_ok=True)
out = os.path.join(temp_dir, "po_wells.geojson")
gdf.to_file(out, driver="GeoJSON")
```

## Example queries (each returning a GeoDataFrame)

### Where is the water table shallowest?

```python
gdf = load_po_wells()
shallowest = gdf.nsmallest(5, "wtd_m")
shallowest.to_file(os.path.join(temp_dir, "shallowest_wells.geojson"),
                   driver="GeoJSON")
# Expect: MO-F08-00 (0.38 m, P+E), PO0170750RC536 (0.41 m, Lombardy),
#         MO-F02-00 (0.82 m, P+E), BO-F11-00 (1.12 m, P+E), …
```

### Which wells fluctuate the most?

```python
gdf = load_po_wells()
fluctuating = gdf.nlargest(10, "std_m")
fluctuating.to_file(os.path.join(temp_dir, "fluctuating_wells.geojson"),
                    driver="GeoJSON")
# Expect Bologna cluster (BO20-01, BO30-01, BO30-00, …) with ~20 m swings,
# all in Piedmont+Emilia.
```

### Stable wells in Lombardy (STD under 1 m)

```python
gdf = load_po_wells()
stable_lom = gdf[(gdf.region == "Lombardy") & (gdf.std_m < 1.0)]
stable_lom.to_file(os.path.join(temp_dir, "stable_lombardy_wells.geojson"),
                   driver="GeoJSON")
# Expect 56 of the 101 Lombardy wells.
```

### Deep wells (WTD > 30 m), all regions

```python
gdf = load_po_wells()
deep = gdf[gdf.wtd_m > 30]
deep.to_file(os.path.join(temp_dir, "deep_wells.geojson"), driver="GeoJSON")
```

### Wells within a bounding box (e.g. around Turin)

```python
gdf = load_po_wells()
turin_box = gdf.cx[7.5:8.2, 45.0:45.5]  # lon, lat
turin_box.to_file(os.path.join(temp_dir, "turin_wells.geojson"),
                  driver="GeoJSON")
```

### All wells, no filter (full inventory map)

```python
gdf = load_po_wells()
gdf.to_file(os.path.join(temp_dir, "all_po_wells.geojson"), driver="GeoJSON")
print(f"{len(gdf)} wells across {gdf.region.nunique()} regions")
# Expect 238 wells across 2 regions.
```

### Combined filter (region + WTD + STD together)

```python
gdf = load_po_wells()
# Shallow but jumpy Lombardy wells: WTD under 5 m AND STD over 2 m
mask = (gdf.region == "Lombardy") & (gdf.wtd_m < 5) & (gdf.std_m > 2)
result = gdf[mask]
result.to_file(os.path.join(temp_dir, "shallow_jumpy_lombardy.geojson"),
               driver="GeoJSON")
```

### Summary statistics by region

```python
gdf = load_po_wells()
summary = gdf.groupby("region").agg(
    n_wells=("well_id", "count"),
    mean_wtd_m=("wtd_m", "mean"),
    min_wtd_m=("wtd_m", "min"),
    max_wtd_m=("wtd_m", "max"),
    mean_std_m=("std_m", "mean"),
).round(2)
print(summary)
```

### Wells within N kilometers of a point

```python
gdf = load_po_wells()

# Project to a metric CRS for accurate distance (ESRI:54012 is fine —
# it's the same projection the source data was in, in meters).
gdf_m = gdf.to_crs("ESRI:54012")

# Target point: e.g. Milan city center (lon=9.19, lat=45.46)
from shapely.geometry import Point
target = gpd.GeoSeries([Point(9.19, 45.46)], crs="EPSG:4326").to_crs("ESRI:54012").iloc[0]

radius_km = 50
nearby = gdf_m[gdf_m.geometry.distance(target) <= radius_km * 1000]
nearby = nearby.to_crs("EPSG:4326")  # back to lon/lat for the map
nearby.to_file(os.path.join(temp_dir, "near_milan.geojson"), driver="GeoJSON")
print(f"{len(nearby)} wells within {radius_km} km of Milan")
# Expect 61 wells within 50 km of Milan.
```

### Find a specific well by ID

```python
gdf = load_po_wells()
single = gdf[gdf.well_id == "00100410001"]
print(single[["well_id", "wtd_m", "std_m", "region"]])
print(f"Location: {single.geometry.iloc[0]}")
```

### Spatial join with another GeoDataFrame

```python
# Example: wells inside any polygon GeoDataFrame `regions_gdf`
# (e.g. provinces fetched from another skill). Both must be in the same CRS.
gdf = load_po_wells()
regions_gdf = regions_gdf.to_crs("EPSG:4326")
wells_in_regions = gpd.sjoin(gdf, regions_gdf, predicate="within", how="inner")
wells_in_regions.to_file(os.path.join(temp_dir, "wells_by_region.geojson"),
                         driver="GeoJSON")
```

### Quick descriptive overview (no map output)

```python
gdf = load_po_wells()
print(f"Total wells: {len(gdf)}")
print(f"Regions: {gdf.region.value_counts().to_dict()}")
print(f"WTD range: {gdf.wtd_m.min():.2f} – {gdf.wtd_m.max():.2f} m")
print(f"STD range: {gdf.std_m.min():.2f} – {gdf.std_m.max():.2f} m")
print(f"Geographic bounds (W/S/E/N): {gdf.total_bounds.tolist()}")
# Expect: 238 wells; {'Piedmont+Emilia': 137, 'Lombardy': 101};
# WTD 0.38 – 54.54 m; bounds ~[7.31, 44.15, 12.24, 46.06].
```

## Provenance — name the source file when reporting

Every reported value should be traceable to a source CSV. Use the **bare
filenames as they appear in the original repository**
(`github.com/rlsandovalp/Well_data_Po`) — do not include the local
`skills/po-wells/data/` prefix in citations.

The data flow is uniform across all 238 wells, so the same column always
comes from the same file regardless of how the data is filtered, joined,
or aggregated:

| What you report | File to cite |
|-----------------|--------------|
| A WTD value (single well, filter result, or aggregate such as mean / min / max) | `Steady_State_Leonardo.csv` |
| A STD value (single well, filter result, or aggregate) | `Standard_Deviation_Leonardo.csv` |
| A `region` tag (`Lombardy` / `Piedmont+Emilia`) | derived from membership in `WTD_obs_lom_Leonardo.csv` |
| A geometry / coordinate | reprojected from the `X_54012`, `Y_54012` columns in `Steady_State_Leonardo.csv` |

Reporting rules:

- **Single-well questions** (e.g. *"which well is deepest, and where does that value come from?"*): name the file backing each cited quantity. *"The deepest well is `<well_id>` at `<wtd_m>` m; the WTD value is from `Steady_State_Leonardo.csv`."*
- **Aggregate questions** (e.g. *"average WTD in Lombardy"*): cite the file of the underlying column. *"Mean WTD across the 101 Lombardy wells, computed from `wtd_m` values in `Steady_State_Leonardo.csv`."*
- **Derived quantities** (e.g. a depth-to-fluctuation ratio): name the source files of each contributing column. *"Ratio of `wtd_m` (from `Steady_State_Leonardo.csv`) to `std_m` (from `Standard_Deviation_Leonardo.csv`)."*

Always include this provenance line in the final response whenever the user asks where a value came from, asks about reproducibility, or asks about data sources — even if the underlying question is otherwise about content.

## Reporting tips

- Always state the **region** in the answer (`Piedmont+Emilia`, `Lombardy`,
  or both).
- WTD and STD are in **meters**.
- "Stable / calm" → low `std_m`; "fluctuating / jumpy / volatile" → high
  `std_m`.
- "Shallowest" → smallest `wtd_m`; "deepest" → largest `wtd_m`.
- These are **time-averaged summaries** (one row per well), not time series
  — if asked for trends over time, note that this dataset only has per-well
  mean and standard deviation, not the underlying observations.
- Coordinates in the bundled CSVs are projected (ESRI:54012); the loader
  handles the reprojection to EPSG:4326, so downstream code should treat
  `geometry` as standard WGS84 lon/lat.
