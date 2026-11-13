---
name: clm-fire-rasters
description: California Landscape Metrics fire rasters served by WCS — annual burn probability, wildfire ignition counts by cause (all, human, lightning), predicted ignition cause, and probability of low/moderate/high fire severity, statewide at 30 m. Use for burn probability, ignition density, fire severity likelihood, wildfire risk along roads or inside polygons. Reads only the window a question needs, so a corridor-sized zonal statistic moves about a megabyte instead of the 4.3 GB statewide raster.
---

# California Landscape Metrics — fire rasters

Ten fire coverages from the California Regional Resource Kits, served from SDSC's
GeoServer as WCS 2.0.1. Native CRS **EPSG:3310**, mostly 30 m.

**Endpoint:** `https://sparcal.sdsc.edu/geoserver/rrk/wcs`

| Key | What it is | Resolution |
| --- | --- | --- |
| `annual_burn_probability` | modelled annual probability of burning | 30 m |
| `ignitions_all_causes` | observed ignition counts 1992–2020 | 30 m |
| `ignitions_human` | human-caused subset | 30 m |
| `ignitions_lightning` | lightning-caused subset | 30 m |
| `pred_ignition_human` | predicted human ignition cause 1992–2015 | **1000 m** |
| `pred_ignition_lightning` | predicted lightning ignition cause | **1000 m** |
| `fire_severity_prob_high` / `_mod` / `_low` | probability of each severity class | 30 m |
| `fire_severity_class_max` | max observed severity class 2012–2021 | **unusable, see trap 1** |

## Why windowed reads

The statewide 30 m grid is 30,469 × 35,325 float32 — **about 4.3 GB per layer.**
A WCS subset of a 43 × 5 km corridor window is **1.08 MB.** Never fetch a whole
coverage; request the window the question needs.

| What you ask for | Bytes moved | Time |
| --- | --- | --- |
| Coverage extent, CRS, resolution, nodata | already in `catalog.json`, zero | 0 s |
| One corridor + 500 ft buffer, 30 m | ~1 MB | <1 s |
| 35 corridors, **one window each** | 134 MB | **8.7 s** |
| 35 corridors, one window spanning all of them | 969 MB | 31 s |
| A whole coverage | ~4,300 MB — don't | — |

**Fetch one window per feature.** Linear features scattered across a region share a
bounding box far larger than themselves — the 35 SCIRP corridors occupy a tiny
fraction of their 211,317 km² shared box, so a single window moves 7× more data for
the same answer. `clm_zonal` below already does this; keep that shape if you write
your own.

## Step 1 — Read the catalogue

```python
import json
from pathlib import Path

def clm_catalog():
    """Load catalog.json from wherever this skill is installed."""
    roots = [Path.home() / ".deepagents/agent/skills/clm-fire-rasters",
             Path.cwd() / "_skills_/clm-fire-rasters",            # %%skill --notebook
             Path.cwd() / "private_skills/clm-fire-rasters",
             Path.cwd() / "clm-fire-rasters",
             Path.cwd()]
    for r in roots:
        if (r / "catalog.json").is_file():
            return json.loads((r / "catalog.json").read_text())
    for base in (Path.home() / ".deepagents/agent/skills", Path.cwd()):
        hits = sorted(base.glob("**/clm-fire-rasters/catalog.json"))
        if hits:
            return json.loads(hits[0].read_text())
    raise RuntimeError("catalog.json not found. Looked in: "
                       + ", ".join(str(r) for r in roots))

CLM = clm_catalog()
```

**Do not rewrite this to use `__file__`.** In a script you generate, `__file__` is
*your script's* directory, not the skill's. Note too that `"__file__" in dir()` is
always true at script top level, so guarding on it does not help.

Every extent, resolution and nodata value in `catalog.json` was measured from
`DescribeCoverage`, not assumed. Read them from there rather than hardcoding.

## Step 2 — Check coverage before computing anything

This is the step that keeps the answers honest. The collection mixes statewide and
regional products, and a zonal statistic over a partly-covered geometry returns a
perfectly plausible number computed from whatever happened to be inside.

```python
from shapely.geometry import box

def clm_crs(key):
    """The CRS the pixels are actually in (not always what the server declares)."""
    info = CLM["coverages"][key]
    if info.get("data_crs"):
        return info["data_crs"]
    return "EPSG:" + info["srs"].rstrip("/").split("/")[-1]

def clm_coverage_fraction(gdf, key):
    """Fraction of gdf's area that falls inside this coverage's extent."""
    info = CLM["coverages"][key]
    lo, hi = info["lower_corner"], info["upper_corner"]
    extent = box(lo[0], lo[1], hi[0], hi[1])
    g = gdf.to_crs(clm_crs(key))
    total = g.geometry.area.sum()
    if total <= 0:                      # lines or points: fall back to bounds
        g = g.copy()
        g["geometry"] = g.geometry.buffer(1)
        total = g.geometry.area.sum()
    inside = g.geometry.intersection(extent).area.sum()
    return float(inside / total) if total else 0.0

def clm_require_coverage(gdf, key, allow_partial=False):
    """Refuse a partly-covered query unless partial coverage is asked for."""
    info = CLM["coverages"][key]
    if not info.get("usable", True):
        raise RuntimeError(f"{key} is marked unusable: {info.get('note')}")
    frac = clm_coverage_fraction(gdf, key)
    if frac < 0.999 and not allow_partial:
        raise RuntimeError(
            f"{key} covers only {frac:.1%} of the query area. Any statistic would "
            f"describe that fraction only. Coverage extent is "
            f"{info['lower_corner']} .. {info['upper_corner']} in {clm_crs(key)}. "
            "Pass allow_partial=True to proceed and report the fraction alongside "
            "the result.")
    return frac
```

## Step 3 — Read a window and compute a zonal statistic

```python
import numpy as np
import requests
from rasterio.io import MemoryFile
from rasterio.mask import mask

FEET = 0.3048

def clm_window(gdf, key, buffer_m=0):
    """GeoTIFF bytes for the window covering gdf, from the WCS."""
    info = CLM["coverages"][key]
    g = gdf.to_crs(clm_crs(key))
    minx, miny, maxx, maxy = g.total_bounds
    minx, miny, maxx, maxy = (minx - buffer_m, miny - buffer_m,
                              maxx + buffer_m, maxy + buffer_m)
    ax = info["axis_labels"] or ["X", "Y"]
    r = requests.get(CLM["endpoint"], timeout=600, params={
        "service": "WCS", "version": CLM["wcs_version"],
        "request": "GetCoverage", "coverageId": info["coverage_id"],
        "format": "image/tiff",
        "subset": [f"{ax[0]}({minx},{maxx})", f"{ax[1]}({miny},{maxy})"]})
    r.raise_for_status()
    if "xml" in (r.headers.get("content-type") or ""):
        raise RuntimeError("WCS returned an exception: " + r.text[:400])
    return r.content

def clm_zonal(gdf, key, feet=500, allow_partial=False,
              keep=("corridor_fid", "Corridor_N", "Zone")):
    """Per-feature statistics of `key` within `feet` of each feature in gdf.

    Any column named in `keep` that exists on `gdf` is copied into the result, so
    the output is self-describing and cannot be re-attached to the wrong feature
    by row position later.

    Fetches **one window per feature**, not one window spanning them all. For
    linear features this matters enormously: the 35 SCIRP corridors share a
    bounding box of 211,317 km², so a single window is 969 MB and 31 s, while
    their own boxes total 134 MB and 8.7 s for the same answers — 7× less data.
    The gap widens the further apart the features are.

    Returns a DataFrame indexed like gdf, carrying `coverage` and
    `coverage_fraction` as columns so they survive joins and show up in output.
    """
    zone = gdf.to_crs(clm_crs(key)).copy()
    zone["geometry"] = zone.geometry.buffer(feet * FEET)
    frac = clm_require_coverage(zone, key, allow_partial=allow_partial)

    rows = []
    for idx, geom in zip(zone.index, zone.geometry):
        one = gpd.GeoDataFrame(geometry=[geom], crs=zone.crs)
        try:
            tif = clm_window(one, key)
        except Exception as exc:
            rows.append({"index": idx, "n_px": 0, "mean": np.nan,
                         "median": np.nan, "max": np.nan, "note": str(exc)[:80]})
            continue
        with MemoryFile(tif) as mf, mf.open() as src:
            nodata = src.nodata
            try:
                arr, _ = mask(src, [geom], crop=True, filled=False)
            except ValueError:               # geometry outside the window
                rows.append({"index": idx, "n_px": 0, "mean": np.nan,
                             "median": np.nan, "max": np.nan})
                continue
            v = arr[0].compressed().astype("float64")
            if nodata is not None:
                v = v[~np.isclose(v, nodata)]
            v = v[np.isfinite(v)]
        rows.append({"index": idx, "n_px": int(v.size),
                     "mean": float(v.mean()) if v.size else np.nan,
                     "median": float(np.median(v)) if v.size else np.nan,
                     "max": float(v.max()) if v.size else np.nan})
    import pandas as pd
    out = pd.DataFrame(rows).set_index("index")
    out["coverage"] = key
    out["coverage_fraction"] = frac
    carry = [c for c in keep if c in gdf.columns]
    if carry:
        out = out.join(gdf[carry])
    return out
```

Report `coverage_fraction` whenever it is below 1.0. A statistic over 70% of a
corridor is a statistic about 70% of a corridor.

**The fraction is a column, not metadata, on purpose.** `DataFrame.attrs` is
dropped by `join`, `merge` and `concat`, so a fraction stored there disappears at
exactly the moment you combine these results with anything else — and the result
then looks fully covered. A column survives those operations and prints with the
table.

## Never re-join results by position

Every function here returns a frame **indexed like the input**, and that index is only
meaningful while you still hold the original rows. Writing results to GeoJSON or CSV and
re-reading them does not preserve order, and re-attaching names by row position then
silently mislabels everything: the numbers stay internally consistent, the labels shift,
and nothing in the output looks wrong.

**Carry an identifier column through instead.** The SCIRP corridors ship with
`corridor_fid` for exactly this purpose.

```python
summary = <summary_function>(corridors, ...)          # indexed like corridors
summary = summary.join(corridors[["corridor_fid", "Corridor_N"]])   # join while in hand
summary.to_csv(path, index=False)                     # now self-describing
```

Do not write an intermediate file that drops the identifying columns and then map row
numbers back to names afterwards.

## Traps

**1. `fire_severity_class_max` is served in the wrong CRS.** The server declares
EPSG:3310, but its extent is `[-2614584, 1212364 .. -1482324, 2458714]`, which is
not California in 3310 — it is California in **CONUS Albers, EPSG:5070**. A correct
3310 query returns nothing; a naive reprojection returns garbage. The catalogue
marks it `usable: false` and `clm_require_coverage` refuses it. Use the three
`fire_severity_prob_*` layers instead, which are correctly georeferenced.

**2. Statewide and regional products are mixed in this collection.** The fire
layers here are statewide, but CLM also publishes regional Tier 2 products — for
example *Southern CA Cost of Potential Treatments*, which stops at
`[-120.675, 32.497, -115.775, 35.287]` in WGS84. The SCIRP corridors reach
−121.913 west and 36.404 north, so PCH Big Sur and the Central Coast fall outside
it entirely. **Always call `clm_require_coverage` before computing.** If you add a
coverage to this skill, measure its extent with `DescribeCoverage` first.

**3. The two `pred_ignition_*` layers are 1000 m, not 30 m.** A 500 ft buffer is
152 m — smaller than a single pixel — so a zonal statistic over it is a point
sample wearing a mean's clothing. Either aggregate over a long stretch of road or
say plainly that the value is one pixel.

**4. nodata is not consistent.** Most layers use `-3.4e38`, the ignition count
layers use `-128`, and **`ignitions_lightning` declares nodata as `15.0`** — a
value inside the plausible data range rather than a sentinel. Masking it may drop
real pixels; not masking it may admit fill. Check the histogram before trusting a
mean from that layer.

**5. `annual_burn_probability` is not pixel-aligned with the other 30 m layers.**
Its extent differs by 11–15 m, so cell-by-cell arithmetic across layers needs
resampling first. Per-layer zonal statistics are unaffected.

**6. Work in the coverage's own CRS.** `clm_crs(key)` returns it, including the
corrected CRS where the server is wrong. Reproject your geometry to the raster
rather than the raster to your geometry.

## Dependencies

```python
def ensure_clm_deps():
    """rasterio, geopandas, numpy, pandas, requests — installed only if missing."""
    import importlib.util, subprocess, sys
    missing = [p for p in ("rasterio", "geopandas", "numpy", "pandas", "requests")
               if importlib.util.find_spec(p) is None]
    if missing:
        print(f"Installing {', '.join(missing)} …", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user",
                        "--quiet", *missing], check=True)
    import rasterio
    return rasterio
```

## Regenerating the catalogue

`catalog.json` is produced by `clm_inventory.py` in the SCIRP working folder, which
reads `DescribeCoverage` for every coverage and records the extents, resolutions,
nodata values and known issues. Re-run it if the server's holdings change.
