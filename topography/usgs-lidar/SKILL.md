---
name: usgs-lidar
description: "USGS 3DEP LiDAR point cloud data and forest / canopy metrics. Use when the user wants to: download LiDAR point clouds from USGS 3DEP / EPT (Entwine Point Tile) services; query the USGS 3DEP coverage catalog; visualize point clouds in 3D; save or read .las / .laz / .copc files; generate Digital Elevation Models (DEMs), Digital Surface Models (DSMs), or Canopy Height Models (CHMs); compute canopy metrics like PAD (Plant Area Density), PAI (Plant Area Index), FHD (Foliage Height Diversity), or canopy cover from ground-classified LiDAR returns. Pure data skill — Python functions only, no UI."
---

# usgs-lidar — Data Skill

This is a **data-only skill**. It exposes Python functions for fetching the
USGS 3DEP coverage catalog, filtering it by bounding box, downloading point
clouds, and rasterizing them to a DEM. It contains no widgets, maps, or
dropdowns and has no agent-runtime dependencies — usable from any Python
environment.

## ⚠️ Critical rule — NEVER plot 3DEP point cloud data on a Folium map

A single 3DEP LiDAR tile contains millions to billions of points. Rendering
them as point markers on a 2D Folium map will hang the browser, blow up
notebook size, and produce a meaningless dense blob.

- **Do NOT** save point cloud arrays (`pointclouds`, `X/Y/Z` arrays) as a
  GeoJSON of points and reference them with a `![...](...)` map tag.
- **Do NOT** convert decimated points to `Point` geometries for a Folium map.
- **Do NOT** include a 3DEP point file in a multi-layer map tag.

The only acceptable visualization for the point cloud itself is the Plotly
3D scatter in Step 4 (`fig.show()`). For 2D context on a Folium map, use
the **coverage tile footprint** (a polygon) from `fetch_coverage()`, not
the points. For a 2D raster, generate a DEM from the points and reference
the GeoTIFF instead.

## Required Libraries — call ensure_lidar_deps() before any lidar work

This skill needs `pdal` + Python bindings, plus `pyforestscan`, `laspy`,
`lazrs`, `geopandas`, `pyproj`, `rasterio`. PDAL is a native C++ library,
non-trivial to install on hosts that don't ship it (e.g. Colab).

**The helper module provides `ensure_lidar_deps()` — call it before any
import of pyforestscan, laspy, or pdal in your script.** This is the ONLY
correct way to install lidar dependencies for this skill. Do not run apt
or pip commands manually — the function handles everything.

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from usgs_lidar import ensure_lidar_deps, fetch_coverage, filter_by_bbox

ensure_lidar_deps()   # idempotent; <100 ms when deps already present
```

What it does per host:

| Host | Behaviour |
|---|---|
| Google Colab | Runs `apt-get install libpdal-dev pdal python3-pdal`, then `pip install pyforestscan laspy lazrs geopandas pyproj rasterio`, then patches `sys.path` so user-site installs are importable. ~2 min first time; <100 ms thereafter. |
| NRP JupyterHub | No-op (deps pre-installed in the image). |
| localhost / other | No-op if deps present; raises a clear `RuntimeError` with a `conda install ...` hint if not. |

If `ensure_lidar_deps()` raises, STOP and tell the user the exact error.
Do NOT try alternative install commands, version pins, or different
package names — the function already encodes the correct sequence.

## Helper module

The skill ships `usgs_lidar.py` next to this SKILL.md. Add the skill
directory to `sys.path` before importing:

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from usgs_lidar import ensure_lidar_deps, fetch_coverage, filter_by_bbox

ensure_lidar_deps()   # MUST call this before any pyforestscan / laspy import
```

Three public functions:

| Function                                       | Purpose                                                                       |
|------------------------------------------------|-------------------------------------------------------------------------------|
| `fetch_coverage(color_features=True)` | Downloads `https://usgs.entwine.io/boundaries/resources.geojson` and returns an in-memory `GeoDataFrame` in EPSG:4326 with `name`, `url`, `count`, `geometry`. Keep it in memory; do not write it to a file. |
| `filter_by_bbox(coverage, bbox, max_points)`   | Given the GeoDataFrame and a bbox tuple `(minx, miny, maxx, maxy)` in EPSG:4326, returns a list of dicts `[{"name", "url", "count", "est"}]` for intersecting datasets whose estimated bbox-clipped point count is below `max_points` (default 20 million). |

## Execution rules — read before writing any code

- Save every script to a `.py` file, then run it with `python /path/to/script.py`.
  Never use heredoc syntax (`python << 'EOF'`). Never chain commands with `&&`.
- Steps below depend on values produced by earlier steps (`coverage`,
  `bbox`, `ept_url`, `pointclouds`, `ept_srs`, `laz_path`, `arrays`). Each
  step's "Inputs" line names what it expects. Either combine related steps
  into one script so the values stay as local variables, or persist them
  between steps via files (e.g. save the LAZ in Step 6, reload it in Step 7).

---

## Step 1 — Fetch the USGS 3DEP coverage catalog

Pure data step. Produces:

| Variable    | Type            | Contents                                              |
|-------------|-----------------|-------------------------------------------------------|
| `coverage`  | GeoDataFrame    | One row per USGS 3DEP dataset; EPSG:4326              |

**DO NOT write the coverage to a file.** Specifically:
- Do NOT call `coverage.to_file(...)`, `coverage.to_json(...)` to a file,
  or otherwise save the catalog as `usgs_3dep_coverage.geojson` (or any name).
- Do NOT pass a file path string to a bbox-map overlay parameter — pass
  the in-memory `coverage` GeoDataFrame directly.
- Writing the catalog to disk can trigger a duplicate static map next to a
  live widget in some host frameworks. The widget renders the overlay from
  memory; no file is needed.

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from usgs_lidar import ensure_lidar_deps, fetch_coverage

ensure_lidar_deps()
coverage = fetch_coverage()
print(f"Loaded {len(coverage)} USGS 3DEP datasets.")
```

Keep `coverage` in memory only.

---

## Step 2 — Filter the catalog by a bounding box

Pure data step. Given a bbox in EPSG:4326 (e.g., from a UI widget or a
hardcoded value), return a list of intersecting datasets.

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from usgs_lidar import ensure_lidar_deps, filter_by_bbox

ensure_lidar_deps()
bbox = (-122.5, 37.7, -122.3, 37.9)   # (minx, miny, maxx, maxy) in EPSG:4326
datasets = filter_by_bbox(coverage, bbox, max_points=20_000_000)
print(f"{len(datasets)} dataset(s) intersect the bbox with under 20M estimated points.")
for d in datasets[:5]:
    est = f"~{d['est']:,} pts" if d['est'] else "?"
    print(f"  {d['name']}  ({est})")
```

`datasets` is a list of dicts with keys `name`, `url`, `count`, `est`.
Pick one (or let the user pick one via whatever picker your agent provides)
and pass its `url` and the bbox to Step 3.

---

## Step 3 — Download the selected point cloud

Given a bbox and an EPT endpoint URL, downloads the point cloud via
`pyforestscan`.

### pyforestscan imports — use these exact paths, do not guess

```python
from pyforestscan.handlers   import read_lidar, create_geotiff, write_las
from pyforestscan.calculate  import assign_voxels, calculate_pad, calculate_pai, calculate_fhd, calculate_chm
from pyforestscan.filters    import filter_hag
from pyforestscan.process    import process_with_tiles
from pyforestscan.utils      import get_srs_from_ept
```

`get_srs_from_ept` lives in `pyforestscan.utils`, not `pyforestscan.handlers`.
If it ever fails (package version mismatch, etc.), fall back to fetching the
EPT JSON directly:

```python
import requests
ept = requests.get(ept_url, timeout=30).json()
srs = ept.get("srs", {})
ept_srs = f"{srs.get('authority','EPSG')}:{srs.get('horizontal','3857')}"
```

### Step 3 script

**Inputs** (set at top of script, from Steps 1-2):
- `bbox` — 4-tuple `(minx, miny, maxx, maxy)` in EPSG:4326
- `ept_url` — EPT endpoint URL from Step 2's chosen dataset

**Outputs:** `pointclouds` (list of structured numpy arrays), `ept_srs` (string).

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from usgs_lidar import ensure_lidar_deps
ensure_lidar_deps()   # MUST be called before importing pyforestscan

import numpy as np
from pyproj import Transformer
from pyforestscan.handlers import read_lidar
from pyforestscan.utils import get_srs_from_ept

# Set from Step 1/2 selections
bbox    = (-122.5, 37.7, -122.3, 37.9)
ept_url = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/..."

ept_srs = get_srs_from_ept(ept_url)
transformer = Transformer.from_crs("EPSG:4326", ept_srs, always_xy=True)
minx, miny = transformer.transform(bbox[0], bbox[1])
maxx, maxy = transformer.transform(bbox[2], bbox[3])
bounds = ([minx, maxx], [miny, maxy])

print(f"Downloading point cloud from {ept_url} ...")
pointclouds = read_lidar(ept_url, ept_srs, bounds, hag=True)
print(f"Downloaded {len(pointclouds)} point arrays.")
```

`hag=True` computes Height Above Ground (normalized elevation relative to
ground). Set `hag=False` for raw absolute elevation.

---

## Step 4 — Interactive 3D visualization

Renders the point cloud as a Plotly 3D scatter plot colored by elevation.
Decimates to ~250,000 points for browser performance.

Call `fig.show()` directly — do NOT use a `![...](...)` map tag for Plotly figures.

**Inputs:** `pointclouds` from Step 3 (or `arrays` from Step 7).

```python
import plotly.graph_objects as go
import numpy as np

# pointclouds = <list of structured arrays from Step 3>

all_x, all_y, all_z = [], [], []
for pc in pointclouds:
    all_x.append(pc['X'] if 'X' in pc.dtype.names else pc.x)
    all_y.append(pc['Y'] if 'Y' in pc.dtype.names else pc.y)
    all_z.append(pc['Z'] if 'Z' in pc.dtype.names else pc.z)

x = np.concatenate(all_x); y = np.concatenate(all_y); z = np.concatenate(all_z)
x -= np.min(x); y -= np.min(y)

total = len(x)
step = max(1, total // 250_000)
x, y, z = x[::step], y[::step], z[::step]
print(f"Rendering {len(x):,} of {total:,} points (step={step})")

fig = go.Figure(data=[go.Scatter3d(
    x=x, y=y, z=z, mode='markers',
    marker=dict(size=1.5, color=z, colorscale='earth',
                colorbar=dict(title="Elevation", titleside="right"), opacity=1.0)
)])
fig.update_layout(margin=dict(l=0, r=0, b=0, t=0), scene=dict(aspectmode='data'))
fig.show()
```

`pointclouds` is a list of structured numpy arrays. Field names may be
uppercase (`X`, `Y`, `Z`) or lowercase depending on the dataset; the snippet
above handles both.

---

## Step 5 — 1-m DEM with hillshade overlay

Filters ground returns (LAS class 2), rasterises to a 1-m DEM, writes a
georeferenced GeoTIFF, and generates a hillshade via `gdaldem`. Also writes
a `hillshade.wms.json` sidecar for the combined Folium map.

**Input source — use whichever is available:**
- In-memory download: reads `pointclouds` set by Step 3.
- From a saved LAZ file: run Step 7 first to load the file into `arrays`,
  then this step reads `arrays`. Do NOT re-implement ground-point extraction
  or rasterisation from scratch — the code below handles both cases.

### Y-axis orientation — the classic rasterisation trap

`rasterio`'s `from_origin(min_x, max_y, dx, dy)` treats row 0 as `max_y`
(north-up). If you index the array with `y_idx = ((y - min_y) / dx).astype(int)`,
row 0 of the array is at `min_y` (south). Writing that array under a north-up
transform produces a **vertically flipped raster**. Use `y_idx` from `max_y`:

```python
y_idx = ((max_y - y) / 1.0).astype(int)   # row 0 = north
```

Verify by comparing the hillshade against Google Earth for the same bbox — a
correct hillshade with `-az 315` (NW lighting) has north-facing slopes in shadow.

### Step 5 script

**Inputs** (set at top of script):
- `pointclouds` — list of structured arrays from Step 3 (or `arrays` from Step 7)
- `ept_srs` — CRS string (from Step 3 or Step 7)
- `bbox` — optional, the original EPSG:4326 bbox for the WMS sidecar

**Outputs:** `dem_1m.tif`, `hillshade_1m.tif`, `hillshade.wms.json`.

```python
import numpy as np, json, subprocess
from pathlib import Path
import rasterio
from rasterio.transform import from_origin

# pointclouds = <list of arrays from Step 3 or Step 7>
ept_srs = "EPSG:3857"                 # from Step 3 or Step 7
bbox    = (-122.5, 37.7, -122.3, 37.9)  # optional, EPSG:4326

output_dir = Path(".")
output_dir.mkdir(parents=True, exist_ok=True)

# Extract ground-classified points (LAS class 2)
ground = []
for pc in pointclouds:
    cls_field = 'Classification' if 'Classification' in pc.dtype.names else 'classification'
    ground.append(pc[pc[cls_field] == 2])
all_ground = np.concatenate(ground)

x_field = 'X' if 'X' in all_ground.dtype.names else 'x'
y_field = 'Y' if 'Y' in all_ground.dtype.names else 'y'
z_field = 'Z' if 'Z' in all_ground.dtype.names else 'z'
x = all_ground[x_field]; y = all_ground[y_field]; z = all_ground[z_field]

min_x, max_x = float(np.min(x)), float(np.max(x))
min_y, max_y = float(np.min(y)), float(np.max(y))
grid_w = int(np.ceil(max_x - min_x)) + 1
grid_h = int(np.ceil(max_y - min_y)) + 1

# Rasterise with Y-flip-correct indexing
x_idx = ((x - min_x) / 1.0).astype(int)
y_idx = ((max_y - y) / 1.0).astype(int)   # row 0 = north
valid = (x_idx >= 0) & (x_idx < grid_w) & (y_idx >= 0) & (y_idx < grid_h)
cell = y_idx[valid] * grid_w + x_idx[valid]
z_ok = z[valid]
sum_z = np.bincount(cell, weights=z_ok, minlength=grid_w * grid_h)
cnt   = np.bincount(cell, minlength=grid_w * grid_h)
with np.errstate(divide='ignore', invalid='ignore'):
    dem = (sum_z / cnt).reshape((grid_h, grid_w))
dem[cnt.reshape((grid_h, grid_w)) == 0] = np.nan

# Write DEM
dem_tif = str(output_dir / "dem_1m.tif")
with rasterio.open(
    dem_tif, 'w', driver='GTiff',
    height=grid_h, width=grid_w, count=1, dtype=np.float32,
    crs=ept_srs, transform=from_origin(min_x, max_y, 1.0, 1.0),
    nodata=np.nan,
) as dst:
    dst.write(dem.astype(np.float32), 1)

# Local hillshade
hillshade_tif = str(output_dir / "hillshade_1m.tif")
subprocess.run(
    ["gdaldem", "hillshade", "-az", "315", "-alt", "45",
     "-compute_edges", dem_tif, hillshade_tif],
    check=True, capture_output=True, text=True,
)

# Register USGS 3DEP WMS as a wide-area context layer (only when bbox is known)
if bbox:
    wms_json = output_dir / "hillshade.wms.json"
    wms_json.write_text(json.dumps({
        "url": "https://elevation.nationalmap.gov/arcgis/services/3DEPElevation/ImageServer/WMSServer",
        "layers": "3DEPElevation:Hillshade Gray",
        "name": "USGS 3DEP Hillshade (Background)",
        "bbox": [bbox[1], bbox[0], bbox[3], bbox[2]],
        "opacity": 0.5,
    }, indent=2))
    print(f"Wrote {wms_json}")

print(f"Wrote {dem_tif}")
print(f"Wrote {hillshade_tif}")
```

### USGS 3DEP WMS layers — use these exact layer names

`3DEPElevation:Hillshade` (no qualifier) does NOT exist and renders blank
tiles. Valid names:

| Layer (use verbatim in `"layers"`)         | Visual                                              |
|--------------------------------------------|-----------------------------------------------------|
| `3DEPElevation:Hillshade Gray`             | Traditional single-source grayscale hillshade       |
| `3DEPElevation:Hillshade Gray-Stretch`     | Gray hillshade with contrast stretched              |
| `3DEPElevation:Hillshade Multidirectional` | Dramatic multi-source lighting                      |
| `3DEPElevation:Hillshade Elevation Tinted` | Hillshade colored by elevation                      |
| `3DEPElevation:Aspect Degrees`             | Aspect angle in degrees                             |
| `3DEPElevation:Slope Degrees`              | Slope angle in degrees                              |
| `3DEPElevation:Contour 25`                 | 25-unit contour lines                               |
| `3DEPElevation`                            | The raw DEM elevation grid                          |

URL for all of these: `https://elevation.nationalmap.gov/arcgis/services/3DEPElevation/ImageServer/WMSServer`.

---

## Step 6 — Save point cloud as LAZ file

`write_las(arrays, output_file, srs=None, compress=True)` writes the list
returned by `read_lidar` to a LAS or LAZ file. `compress=True` (the default)
produces a compressed `.laz` file. Pass the same SRS string used when
downloading.

**Inputs:** `pointclouds` from Step 3, `ept_url` from Step 2.

**Outputs:** `pointcloud.laz` on disk, plus `laz_path` and `ept_srs` strings
for use in Step 7.

```python
from pyforestscan.handlers import write_las
from pyforestscan.utils import get_srs_from_ept
from pathlib import Path

# pointclouds = <list from Step 3>
ept_url = "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/..."  # from Step 2

ept_srs = get_srs_from_ept(ept_url)
laz_path = str(Path("pointcloud.laz"))
write_las(pointclouds, laz_path, srs=ept_srs, compress=True)
print(f"Saved {laz_path}")
```

---

## Step 7 — Read a local LAZ/LAS file

**Use this step instead of Step 3 when a `.laz` file already exists on disk.**
A saved LAZ file lets you skip the EPT download entirely on subsequent runs —
useful when adding new analysis cells (e.g. CHM, PAD, PAI) without
re-downloading the point cloud.

**DO NOT reinvent CRS reading.** Specifically:
- Do NOT call `pdal info` + parse JSON/regex to extract the SRS string.
- Do NOT default to a hardcoded CRS like `"EPSG:3857"` if the read fails —
  a wrong CRS produces a wrong-georeferenced output silently.
- The canonical pattern is `laspy.open(path).header.parse_crs()` (shown
  below). Use `laspy.open()` not `laspy.read()` — `read()` decompresses
  point data and requires a LAZ backend (`lazrs`/`laszip`) which may not
  be installed in some environments. `open()` reads only the header.

`read_lidar` works for both EPT URLs (Step 3) and local `.las`/`.laz`/`.copc`
files. When reading a local file, `bounds` does not apply (EPT only). `srs`
is still required — read it from the EPT endpoint or from the LAZ header.

**Inputs:** `laz_path` (from Step 6 or known on disk).

**Outputs:** `arrays` (list of structured arrays), `ept_srs` (string).

```python
from pyforestscan.handlers import read_lidar

# Set from Step 6 output or known location
laz_path = "pointcloud.laz"

# Read CRS from the LAZ header WITHOUT decompressing point data.
# Use laspy.open() (streaming reader) — laspy.read() would decompress
# the whole file and requires a LAZ backend (lazrs/laszip), which may
# not be installed in some environments.
import laspy
with laspy.open(laz_path) as reader:
    crs = reader.header.parse_crs()
if crs is None:
    raise ValueError(f"Could not read CRS from {laz_path} — set ept_srs manually")
epsg = crs.to_epsg()
ept_srs = f"EPSG:{epsg}" if epsg else crs.to_wkt()
print(f"CRS read from file: {ept_srs}")

# hag=True adds HeightAboveGround field (needed for CHM and canopy metrics)
arrays = read_lidar(laz_path, ept_srs, hag=True)
print(f"Read {sum(len(a) for a in arrays):,} points from {laz_path}")
```

Supported formats: `.las`, `.laz`, `.copc`, `.copc.laz`, or `ept.json`.

---

## Step 8 — Canopy Height Model (CHM)

**"Generate a CHM" means save a georeferenced GeoTIFF (`chm_1m.tif`).** The
PNG is a preview image; the GeoTIFF is the data product downstream tools
load. Always write both.

**DO NOT reinvent CHM calculation.** Specifically:
- Do NOT compute CHM as DSM-minus-DEM by hand. `pyforestscan.calculate_chm`
  already does this correctly using the `HeightAboveGround` field.
- Do NOT use `cmap="Greens"`, `"YlGn"`, or any green-only colormap. The
  community standard for CHM visualization is **`viridis`** (matches the
  `plot_metric` default in `pyforestscan.visualize`). Other accepted
  scientific colormaps: `magma`, `plasma`, `inferno`. Never plain `Greens`.

Computes the CHM from a point cloud that has a `HeightAboveGround` field
(produced by `read_lidar(..., hag=True)`). Uses `filter_hag` to remove
below-ground noise, then `calculate_chm`.

`calculate_chm` takes a **single array** (`arrays[0]`), not the list.

`calculate_chm` returns `(chm, extent)` where `extent` is
`[x_min, x_max, y_min, y_max]` matching matplotlib's `imshow(..., origin="lower")`
convention (row 0 = south). For a north-up GeoTIFF, flip the array vertically
(`np.flipud`) and use `from_origin(x_min, y_max, ...)`.

**Inputs:** `arrays` from Step 7 (or `pointclouds` from Step 3 with `hag=True`),
`ept_srs` (from Step 3 or Step 7).

**Outputs:** `chm_1m.tif`, `chm.png`.

```python
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from rasterio.transform import from_origin
from pathlib import Path
from pyforestscan.filters   import filter_hag
from pyforestscan.calculate import calculate_chm

# arrays = <list of arrays from Step 7 or Step 3 (with hag=True)>
ept_srs    = "EPSG:3857"               # from Step 3 or Step 7
output_dir = Path(".")

# filter_hag removes points at or below ground (HeightAboveGround <= 0)
arrays = filter_hag(arrays)
points = arrays[0]

voxel_resolution = (1, 1, 1)   # (x_res, y_res, z_res) in data units (usually metres)
chm, extent = calculate_chm(points, voxel_resolution)
x_min, x_max, y_min, y_max = extent
x_res, y_res = voxel_resolution[0], voxel_resolution[1]
print(f"CHM shape: {chm.shape}, extent: {extent}")
print(f"Height range: {np.nanmin(chm):.1f} – {np.nanmax(chm):.1f} m")

# Save CHM as GeoTIFF — flip array so row 0 = north (rasterio convention)
chm_tif = str(output_dir / "chm_1m.tif")
chm_north_up = np.flipud(chm).astype(np.float32)
with rasterio.open(
    chm_tif, "w", driver="GTiff",
    height=chm_north_up.shape[0], width=chm_north_up.shape[1], count=1,
    dtype=np.float32, crs=ept_srs,
    transform=from_origin(x_min, y_max, x_res, y_res),
    nodata=np.nan,
) as dst:
    dst.write(chm_north_up, 1)
print(f"Wrote {chm_tif}")

# Save preview PNG (community-standard viridis colormap)
chm_png = str(output_dir / "chm.png")
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(chm, extent=extent, cmap="viridis", origin="lower")
plt.colorbar(im, ax=ax, label="Height (m)")
ax.set_title("Canopy Height Model")
plt.savefig(chm_png, dpi=150, bbox_inches="tight")
plt.close()
print(f"Wrote {chm_png}")
```

---

## Notes

- This skill describes data fetching, filtering, downloading, and processing.
  It contains no widgets, maps, or dropdowns. Pair it with whatever UI
  layer your agent provides for area selection and dataset picking.
- Steps 3–8 use placeholder variable names (`bbox`, `ept_url`, `pointclouds`,
  `arrays`, `ept_srs`, `laz_path`). Set them at the top of each script
  from the values your agent or host framework provides.
