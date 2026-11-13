---
name: roadside-vegetation
description: Roadside vegetation assessment of Southern California highways — 23,453 polygons in a 30 ft buffer along priority roads, classifying non-native annual cover, vegetation cover type and ground surface, with acreage. Use for roadside fuels, non-native grass cover, invasive annual cover along highways, vegetation type beside roads, roadside treatment need. Covers Priority 1 and Priority 2 road networks assessed for the USFS and Caltrans.
---

# Roadside vegetation, 30 ft buffer

Field-verified vegetation mapping in a 30 ft buffer along Southern California
priority highways, produced from aerial imagery plus field collection.

| Layer | Polygons | Native SR |
| --- | --- | --- |
| Priority 1 — `…/Roadside_buffer_30ft_Priority_1/FeatureServer/0` | **12,279** | EPSG:26911 |
| Priority 2 — `…/SCRIP_Roadside_Assessment_Priorities/FeatureServer/2` | **11,174** | EPSG:26911 |

```python
ARC = "https://services1.arcgis.com/8CpMUd3fdw6aXef7/arcgis/rest/services/"
VEG_P1 = ARC + "Roadside_buffer_30ft_Priority_1/FeatureServer/0"
VEG_P2 = ARC + "SCRIP_Roadside_Assessment_Priorities/FeatureServer/2"
```

**Only Priority 1 is in the Commons catalog.** Priority 2 exists in the same
ArcGIS organisation and roughly doubles the covered network. Decide which you are
using and say so — "roadside vegetation" over Priority 1 alone describes about half
the assessed roads.

## The classification, and the trap inside it

`NonNative_Cover` is described by the publisher as *"absolute cover of non-native
annual"*. It is a **coded class, not a percentage**:

| Code | Meaning | Priority 1 count |
| --- | --- | --- |
| 1 | <10% | 2,771 |
| 2 | 10–50% | 5,847 |
| 3 | 50–75% | 2,615 |
| 4 | 75–100% | 419 |
| **5** | **Urban** | **627** |

**Code 5 is not a cover percentage.** It is a land-cover category that happens to
sort last numerically. So a threshold of "more than 50% non-native cover" is
**codes 3 and 4 only**:

```python
OVER_50_PCT = (3, 4)      # 50-75% and 75-100%
URBAN = 5                 # not a percentage - exclude from cover thresholds

over_50 = veg[veg.NonNative_Cover.isin(OVER_50_PCT)]        # correct
over_50_wrong = veg[veg.NonNative_Cover >= 3]               # sweeps in 627 Urban
```

Writing `>= 3` inflates the result and the error is invisible in the output.

### Which acres go in the denominator

`veg_summary` divides by **all assessed acres, including Urban-coded ones**. That
treats an Urban polygon as assessed and not above the threshold, which is the
conservative reading.

The alternative — dividing by vegetated acres only — is also defensible, and the
difference is material enough to reorder a ranking:

| Corridor | Urban acres | Share incl. Urban | Share excl. Urban |
| --- | --- | --- | --- |
| SR-38 Redlands–Big Bear | 17.8 | 8.1% | **10.4%** |
| SR-138 Cajon–Silverwood | 10.5 | 20.5% | **25.9%** |

```python
share_incl = over_acres / total_acres                    # what veg_summary returns
share_excl = over_acres / (total_acres - urban_acres)    # vegetated acres only
```

**State which denominator you used.** `veg_summary` returns `acres_urban_class`
precisely so the other figure can be computed and the choice made explicit.

The other two coded fields:

| `Cover_Type` | 1 Conifer Forest · 2 Oak Woodland · 3 Mixed Conifer/Hardwood · 4 Riparian · 5 Shrubland · 6 Grassland · 7 Urban · 8 Rock/Barren |
| `GroundSurface` | 1 Native · 2 Cut Slope · 3 Fill Slope · 4 Urban |

`Acres` holds polygon area; `Delivery_Area` names the road the polygon belongs to
(39 named roads in Priority 1, e.g. `Ortega Hwy`, `Rim of the World Hwy`, `CA-38`).
`FOREST_GRASSLANDNAME` gives the administering national forest or grassland.

These codes are published as ArcGIS coded-value domains, so they are also readable
from the layer metadata at `?f=json` under each field's `domain` — the copy in
`catalog.json` beside this skill was taken from there.

## Step 1 — Load the codebook

```python
import json
from pathlib import Path

def veg_catalog():
    """Load catalog.json from wherever this skill is installed."""
    roots = [Path.home() / ".deepagents/agent/skills/roadside-vegetation",
             Path.cwd() / "_skills_/roadside-vegetation",            # %%skill --notebook
             Path.cwd() / "private_skills/roadside-vegetation",
             Path.cwd() / "roadside-vegetation",
             Path.cwd()]
    for r in roots:
        if (r / "catalog.json").is_file():
            return json.loads((r / "catalog.json").read_text())
    for base in (Path.home() / ".deepagents/agent/skills", Path.cwd()):
        hits = sorted(base.glob("**/roadside-vegetation/catalog.json"))
        if hits:
            return json.loads(hits[0].read_text())
    raise RuntimeError("catalog.json not found. Looked in: "
                       + ", ".join(str(r) for r in roots))

VEG = veg_catalog()
```

Do not rewrite this with `__file__`; in a generated script that is the script's own
directory, and `"__file__" in dir()` is always true at top level so guarding on it
does not help.

## Step 2 — Fetch and summarise along a set of features

```python
import geopandas as gpd
import pandas as pd
import requests

FEET = 0.3048

def arc_query(url, where="1=1", envelope=None, in_sr=None, out_sr=3310,
              out_fields="*", page=2000):
    """Paged ArcGIS query -> GeoDataFrame in out_sr. Sends inSR and outSR both."""
    base = {"where": where, "outFields": out_fields, "f": "geojson",
            "outSR": out_sr, "returnGeometry": "true"}
    if envelope is not None:
        if in_sr is None:
            raise ValueError("pass in_sr whenever you pass an envelope")
        base.update({"geometry": ",".join(str(v) for v in envelope),
                     "geometryType": "esriGeometryEnvelope",
                     "spatialRel": "esriSpatialRelIntersects", "inSR": in_sr})
    out, offset = [], 0
    while True:
        r = requests.get(url + "/query",
                         params=dict(base, resultOffset=offset, resultRecordCount=page),
                         timeout=300)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RuntimeError(f"ArcGIS error: {j['error']}")
        feats = j.get("features", [])
        if not feats:
            break
        out.extend(feats)
        if len(feats) < page:
            break
        offset += page
    if not out:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{out_sr}")
    return gpd.GeoDataFrame.from_features(out, crs=f"EPSG:{out_sr}")


def veg_near(gdf, feet=100, include_priority_2=True):
    """Roadside vegetation polygons within `feet` of any feature in gdf."""
    target = gdf.to_crs(3310)
    pad = feet * FEET
    minx, miny, maxx, maxy = target.total_bounds
    env = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    urls = [VEG_P1] + ([VEG_P2] if include_priority_2 else [])
    parts = []
    for u, label in zip(urls, ["priority_1", "priority_2"]):
        g = arc_query(u, envelope=env, in_sr=3310, out_sr=3310)
        if not g.empty:
            parts.append(g.assign(priority=label))
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:3310")
    veg = pd.concat(parts, ignore_index=True).pipe(gpd.GeoDataFrame, crs="EPSG:3310")
    zone = gpd.GeoDataFrame(geometry=target.geometry.buffer(pad), crs="EPSG:3310")
    zone["target_index"] = target.index
    return gpd.sjoin(veg, zone, predicate="intersects", how="inner") \
              .rename(columns={"index_right": "_dropped"})


def veg_summary(gdf, feet=100, include_priority_2=True,
                keep=("corridor_fid", "Corridor_N", "Zone")):
    """Per-feature roadside vegetation summary, acre-weighted.

    Any column named in `keep` that exists on `gdf` is copied into the result, so
    the output is self-describing and cannot be re-attached to the wrong feature
    by row position later.
    """
    hit = veg_near(gdf, feet=feet, include_priority_2=include_priority_2)
    target = gdf.to_crs(3310)
    # One grouped pass, so this is as fast for 1,600 segments as for 35 corridors.
    if len(hit):
        h = hit.assign(
            over=hit.Acres.where(hit.NonNative_Cover.isin(VEG["nonnative_over_50pct_codes"]), 0.0),
            urban=hit.Acres.where(hit.NonNative_Cover == VEG["urban_code"], 0.0))
        g = h.groupby("target_index").agg(veg_polygons=("Acres", "size"), veg_acres=("Acres", "sum"),
                                          acres_over_50pct_nonnative=("over", "sum"),
                                          acres_urban_class=("urban", "sum"))
    else:
        g = pd.DataFrame(columns=["veg_polygons", "veg_acres",
                                  "acres_over_50pct_nonnative", "acres_urban_class"])
    out = g.reindex(target.index)
    out["veg_polygons"] = out.veg_polygons.fillna(0).astype(int)
    for c in ("veg_acres", "acres_over_50pct_nonnative", "acres_urban_class"):
        out[c] = out[c].fillna(0.0).astype(float)
    out["share_over_50pct_nonnative"] = (out.acres_over_50pct_nonnative / out.veg_acres).where(out.veg_acres > 0)
    out["assessed"] = out.veg_polygons > 0
    out = out[["veg_polygons", "veg_acres", "acres_over_50pct_nonnative",
               "share_over_50pct_nonnative", "acres_urban_class", "assessed"]]
    carry = [c for c in keep if c in gdf.columns]
    if carry:
        out = out.join(gdf[carry])
    return out
```

`assessed` matters: this mapping covers *priority* roads, not all roads, so a
corridor with no polygons has **not been assessed** — which is different from
having no non-native cover. Never report 0% non-native for an unassessed corridor.

### One function at every level, so the levels agree

Use `veg_summary` for whatever you are scoring — whole corridors, half-mile segments,
anything else — and pass the identifiers through `keep`:

```python
by_corridor = veg_summary(corridors, keep=("corridor_fid", "Corridor_N"))
by_segment  = veg_summary(segments,  keep=("segment_id", "corridor_fid", "Corridor_N"))
```

Do not write a second join for segments. Two methods give two different answers for
the same question, and the reader sees both. With one function the levels are
consistent by construction: **a corridor is assessed exactly when at least one of its
segments is**, so these two counts must match, and checking them is a quick test of
your own code:

```python
n_corr = int(by_corridor.assessed.sum())
n_from_segs = by_segment[by_segment.assessed].corridor_fid.nunique()
assert n_corr == n_from_segs, (n_corr, n_from_segs)
```

A statistic you compute only where a corridor has enough assessed segments — a spread
or concentration measure that needs at least three, say — is a *different* count from
"corridors with vegetation data". Name it for what it is ("12 corridors have the three
assessed segments a spread measure needs"), never as the number assessed.

## How fast this should be

Everything here is **seconds**. If your code is taking minutes, it is the code, not
the service.

| Operation | Measured |
| --- | --- |
| Fetch Priority 1 + Priority 2 across a 211,317 km² box | 23,453 polygons in **16.1 s** |
| Match them against 35 buffered corridors with `sjoin` | well under a second |
| The same match as a nested distance loop | minutes to hours |

**Never measure distance in a Python loop.** `point.distance(line)` costs ~24 µs, so
40,000 features against 1,700 targets is 68 million calls — about half an hour. Buffer
the targets once and use `gpd.sjoin`, which is spatially indexed and returns the same
answer in a fraction of a second regardless of how many targets there are.

```python
zone = targets.to_crs(3310).copy()
zone["geometry"] = zone.geometry.buffer(feet * 0.3048)
hits = gpd.sjoin(features, zone, predicate="intersects", how="inner")   # fast
```

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

**1. `NonNative_Cover == 5` means Urban, not "most non-native".** Use
`isin((3, 4))` for a >50% threshold, never `>= 3`.

**2. Native SR is 26911 (UTM zone 11N), not 3310 or 4326.** Send `inSR` with any
spatial query; without it an ArcGIS query returns zero features and no error.

**3. Only Priority 1 is catalogued.** `include_priority_2=True` is the default here
because the pair is the full assessed network; set it to `False` only to match a
Commons-catalogue-only analysis, and say which you used.

**4. Absence means unassessed.** See `assessed` above.

**5. Weight by `Acres`, not polygon count.** Polygons vary widely in size, so a
plain mean of class codes is meaningless.

**6. The line must be on the road.** These polygons are a 30 ft strip along the actual
pavement, and a 100 ft buffer only reaches them if your line follows the road closely.
A hand-drawn or generalised line a few hundred feet off finds few polygons, or polygons
from a different stretch, and returns a share computed on the wrong ground — with no
error, and with `assessed` still True. Before measuring, know how far your geometry is
from the real road: use centerlines from a road network where you have them, and if
you only have sketched lines, say in the answer that the roadside measures depend on
their accuracy.

## Dependencies

```python
def ensure_veg_deps():
    import importlib.util, subprocess, sys
    missing = [p for p in ("geopandas", "pandas", "requests")
               if importlib.util.find_spec(p) is None]
    if missing:
        print(f"Installing {', '.join(missing)} …", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user",
                        "--quiet", *missing], check=True)
    import geopandas
    return geopandas
```
