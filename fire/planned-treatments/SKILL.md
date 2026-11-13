---
name: planned-treatments
description: Planned and proposed California wildfire-resilience work that the completed-treatment record does not contain — 20,110 Caltrans ONRM fuel-reduction work areas with Planned/Proposed/Complete status, and Regional Priority Plan project layers from Inland Empire RCD, Santa Monica Mountains Conservancy and TEAMS RCD with project type and lead agency. Use for planned fuels projects, proposed treatments, upcoming vegetation management, pipeline of funded or identified wildfire projects, project proponent and lead agency.
---

# Planned and proposed treatments

The statewide completed-treatment record (ITS) contains **only finished and active
work** — no planned or proposed activity at all. Anything asking about *planned or
implemented* treatments needs this skill for the first half of that phrase.

```python
ARC = "https://services1.arcgis.com/8CpMUd3fdw6aXef7/arcgis/rest/services/"

ONRM_WORK_AREAS = ARC + "OVWM_Fuel_Reduction_Service_Contract_Web_Services_Public_View/FeatureServer/1"
ONRM_HIGHWAY    = ARC + "OVWM_Fuel_Reduction_Service_Contract_Web_Services_Public_View/FeatureServer/0"
ONRM_ACTIVITY   = ARC + "OVWM_Fuel_Reduction_Service_Contract_Web_Services_Public_View/FeatureServer/2"
ONRM_TREES      = ARC + "OVWM_Fuel_Reduction_Service_Contract_Web_Services_Public_View/FeatureServer/3"

RPP_INLAND_EMPIRE = ARC + "Inland_Empire_RCD_Regional_Priority_Plan_Projects/FeatureServer/0"
RPP_SMMC          = ARC + "SMMC_MRCA/FeatureServer/0"
RPP_TEAMS         = ARC + "Potential_Fire_Break_Areas/FeatureServer/3"
```

## What each source gives you

### Caltrans ONRM fuel-reduction contracts — the useful one

Caltrans Office of Natural Resource Management, vegetation management along state
highways. **Native SR 3857 (Web Mercator)** — not 3310, not 26911.

| Layer | Geometry | Records | Notes |
| --- | --- | --- | --- |
| Work Area Boundaries (`/1`) | Polygon | **20,110** | **carries `Status`** — the planned/proposed pipeline |
| Project Highway Location (`/0`) | Polyline | 382 | contract and project names, postmile ranges |
| Treatment Activity Acres (`/2`) | Polygon | 170 | activity detail, all `Complete` |
| Tree Treatment (`/3`) | Point | 466 | per-tree, includes genus |

`Status` on the work areas, measured:

| Status | Count |
| --- | --- |
| Complete | 10,966 |
| **Planned** | **5,150** |
| **Proposed** | **3,856** |
| Active | 136 |
| Cancelled | 2 |

So 9,006 polygons describe work that has not happened yet. That is the half of
"planned or implemented" that the completed record cannot answer.

### Regional Priority Plan project layers

Projects identified through CAL FIRE block-grantee Regional Priority Plans.
Inclusion does **not** mean approved, funded or implemented — these are candidate
projects, which is exactly what makes them "planned".

| Layer | Records | Attributes |
| --- | --- | --- |
| Inland Empire RCD (`RPP_INLAND_EMPIRE`) | **39** polygons | `PrjName`, **`PrjType`**, **`Lead`**, `Acres`, `Miles` |
| Santa Monica Mountains Conservancy (`RPP_SMMC`) | **1** polygon | `Name`, `Grantee`, `acres`, `miles` |
| TEAMS RCD (`RPP_TEAMS`) | **28** polygons | `BUFF_DIST`, `ORIG_FID` only — **no project attributes** |

Inland Empire is the only one with a usable breakdown:

- `PrjType`: Hazardous Fuels Reduction 25 · Community Programs 5 · Fuel Break 5 ·
  Restoration 2 · Plan Development 1 · Research 1
- `Lead`: SBNF 12 · CAL FIRE 10 · TBD 8 · CAL FIRE/SBNF 2 · Mountain Rim FSC 2 ·
  SBVMWD 2 · Inland Empire RCD 1 · TreePeople 1 · Wildlands Conservancy 1

## Step 1 — Query helper

```python
import geopandas as gpd
import pandas as pd
import requests

FEET = 0.3048

def arc_query(url, where="1=1", envelope=None, in_sr=None, out_sr=3310,
              out_fields="*", page=2000):
    """Paged ArcGIS query -> GeoDataFrame in out_sr. Always sends inSR and outSR.

    `envelope` must be given in `in_sr`. These layers have three different native
    SRs (3857, 26911, 3310); with a non-4326 geometry and no inSR, ArcGIS returns
    zero features and no error.
    """
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
```

## Step 2 — Planned work near a set of features

```python
PLANNED_STATUSES = ("Planned", "Proposed")

def onrm_near(gdf, feet=1000, statuses=PLANNED_STATUSES):
    """ONRM work areas within `feet` of any feature in gdf, filtered by Status."""
    target = gdf.to_crs(3310)
    pad = feet * FEET
    minx, miny, maxx, maxy = target.total_bounds
    where = "1=1" if not statuses else \
        "Status IN (" + ",".join(f"'{s}'" for s in statuses) + ")"
    areas = arc_query(ONRM_WORK_AREAS, where=where,
                      envelope=(minx - pad, miny - pad, maxx + pad, maxy + pad),
                      in_sr=3310, out_sr=3310)
    if areas.empty:
        return areas
    zone = gpd.GeoDataFrame(geometry=target.geometry.buffer(pad), crs="EPSG:3310")
    zone["target_index"] = target.index
    return gpd.sjoin(areas, zone, predicate="intersects", how="inner")


def rpp_near(gdf, feet=1000):
    """Regional Priority Plan candidate projects near gdf, from all three layers."""
    target = gdf.to_crs(3310)
    pad = feet * FEET
    minx, miny, maxx, maxy = target.total_bounds
    env = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    parts = []
    for url, label in [(RPP_INLAND_EMPIRE, "inland_empire"),
                       (RPP_SMMC, "smmc"), (RPP_TEAMS, "teams")]:
        g = arc_query(url, envelope=env, in_sr=3310, out_sr=3310)
        if g.empty:
            continue
        # Normalise the three different schemas onto common columns.
        g = g.assign(
            source=label,
            project_name=g.get("PrjName", g.get("Name", pd.Series(index=g.index, dtype=object))),
            project_type=g.get("PrjType", pd.Series(index=g.index, dtype=object)),
            lead=g.get("Lead", g.get("Grantee", pd.Series(index=g.index, dtype=object))))
        parts.append(g[["source", "project_name", "project_type", "lead", "geometry"]])
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:3310")
    rpp = pd.concat(parts, ignore_index=True).pipe(gpd.GeoDataFrame, crs="EPSG:3310")
    zone = gpd.GeoDataFrame(geometry=target.geometry.buffer(pad), crs="EPSG:3310")
    zone["target_index"] = target.index
    return gpd.sjoin(rpp, zone, predicate="intersects", how="inner")


def planned_summary(gdf, feet=1000):
    """Per-feature count of planned ONRM work areas and RPP candidate projects."""
    onrm = onrm_near(gdf, feet=feet)
    rpp = rpp_near(gdf, feet=feet)
    target = gdf.to_crs(3310)
    rows = []
    for idx in target.index:
        o = onrm[onrm.target_index == idx] if len(onrm) else onrm
        r = rpp[rpp.target_index == idx] if len(rpp) else rpp
        rows.append({
            "index": idx,
            "onrm_planned_areas": len(o),
            "onrm_planned": int((o.Status == "Planned").sum()) if len(o) else 0,
            "onrm_proposed": int((o.Status == "Proposed").sum()) if len(o) else 0,
            "rpp_projects": len(r),
            "rpp_types": ",".join(sorted(set(r.project_type.dropna()))) if len(r) else "",
            "rpp_leads": ",".join(sorted(set(r.lead.dropna()))) if len(r) else "",
        })
    return pd.DataFrame(rows).set_index("index")
```

## How fast this should be

Everything here is **seconds**. If your code is taking minutes, it is the code, not
the service.

| Operation | Measured |
| --- | --- |
| Fetch ONRM planned/proposed work areas across a 211,317 km² box | 4,581 polygons in **7.1 s** |
| Fetch all three RPP layers over the same box | 68 polygons in **1.8 s** |
| Match either against 35 buffered corridors with `sjoin` | well under a second |
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

**1. Three sources, three native SRs.** ONRM is **EPSG:3857**, the RPP layers are
**EPSG:26911**, Caltrans vulnerability is **EPSG:3310**. Always send `inSR` matching
the geometry you pass and `outSR` for what you want back. With a non-4326 geometry
and no `inSR`, ArcGIS returns **zero features and no error**.

**2. The three RPP layers do not share a schema.** Inland Empire has `PrjName` /
`PrjType` / `Lead`; SMMC has `Name` / `Grantee`; TEAMS has **neither** — only a
buffer distance and a source id. A "breakdown by project type and proponent" is
available for Inland Empire, partially for SMMC, and **not at all for TEAMS**. Say
which layers a breakdown covers.

**3. SMMC contains a single polygon.** Treat a hit on it as "inside the SMMC
regional plan area", not as one project.

**4. RPP inclusion is not approval.** The publishers state that inclusion does not
indicate project approval, funding or implementation. These are candidates.

**5. ONRM `Activity_Description` is a comma-separated multi-value string**, e.g.
`"Chipping,Mastication,Pruning,ManualThinning,MechanicalThinning"` — 70-odd distinct
combinations across 170 rows. Split on commas before counting activity types, or
counts will be meaningless.

**6. Only the work-area layer carries planned status.** The activity-acres layer
(`/2`) is entirely `Complete`, so it cannot answer a planned-work question.

## Dependencies

```python
def ensure_planned_deps():
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
