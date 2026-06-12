"""
usgs_lidar — helpers for the USGS 3DEP LiDAR skill.

Public API:
  * ensure_lidar_deps() — idempotent installer for PDAL + pyforestscan +
    laspy + downstream Python deps. On Colab: runs apt + pip and patches
    sys.path. On other hosts where deps are already present: no-op.
  * fetch_coverage(output_path) — download the USGS 3DEP coverage GeoJSON,
    optionally save it to a file (so it can be used as a sage-bbox-map
    overlay), return a GeoDataFrame for in-memory queries.
  * filter_by_bbox(coverage, bbox, max_points) — given a GeoDataFrame and a
    bbox tuple, return a list of dicts describing the intersecting datasets.

The fetch / filter functions are GUI-free. They're imported by the
agent-generated scripts that compose this skill with sage-bbox-map (area
selection) and sage-dropdown (dataset selection).
"""

import json
import random
from pathlib import Path

import geopandas as gpd
import pyproj
import requests
from shapely.geometry import box


def ensure_lidar_deps(verbose=True):
    """Install PDAL + Python lidar deps if missing. Call BEFORE importing
    pyforestscan, laspy, etc. from any script.

    Idempotent — safe to call from every lidar script. After the first
    real install per session, subsequent calls are fast no-ops (<100 ms).

    Behaviour by host:
      * Colab — runs `apt-get install -y libpdal-dev pdal python3-pdal`,
        then `pip install --user pyforestscan laspy lazrs geopandas pyproj
        rasterio`, then patches sys.path so user-site installs are
        importable from subprocess Python. ~2 min first time.
      * NRP JupyterHub / other hosts with deps pre-installed — no-op.
      * Other hosts where deps are missing — raises RuntimeError with a
        clear conda command for the user.

    Args:
        verbose: if True, print progress lines during the install.

    Raises:
        RuntimeError: if deps cannot be installed (non-Colab host without
            them pre-present, or apt/pip failure on Colab).
    """
    import os
    import site
    import subprocess
    import sys

    # Always patch user-site onto sys.path — cheap, idempotent. Needed
    # because Colab's subprocess Python doesn't include it by default,
    # so pip --user installs from prior calls aren't otherwise findable.
    _user_site = site.getusersitepackages()
    if _user_site not in sys.path:
        sys.path.insert(0, _user_site)

    # Fast path: everything already importable. Return immediately.
    try:
        import pdal  # noqa: F401
        import pyforestscan  # noqa: F401
        import laspy  # noqa: F401
        return
    except ImportError:
        pass

    is_colab = "google.colab" in sys.modules or os.path.exists("/content")

    if not is_colab:
        raise RuntimeError(
            "Lidar dependencies (pdal, pyforestscan, laspy) are not "
            "installed and this host is not Colab. Install with conda:\n"
            "  conda install -c conda-forge pdal python-pdal "
            "pyforestscan laspy lazrs geopandas pyproj rasterio"
        )

    if verbose:
        print("[usgs-lidar] Refreshing apt index...", flush=True)
    subprocess.run(
        ["apt-get", "update", "-qq"],
        capture_output=True, text=True,
    )

    if verbose:
        print("[usgs-lidar] Installing PDAL 2.6.2 from UbuntuGIS PPA (~30s)...", flush=True)
    # Ubuntu 22.04 (jammy) main repo only has PDAL 2.3.0, too old for the
    # PyPI PDAL Python binding. UbuntuGIS PPA (typically pre-configured on
    # Colab) ships 2.6.2+ds-1~jammy0. Force that version explicitly so we
    # don't accidentally get the older one from main.
    apt = subprocess.run(
        ["apt-get", "install", "-y",
         "pdal=2.6.2+ds-1~jammy0",
         "libpdal-dev=2.6.2+ds-1~jammy0"],
        capture_output=True, text=True,
    )
    if apt.returncode != 0:
        raise RuntimeError(
            f"[usgs-lidar] apt-get install failed (exit {apt.returncode}):\n"
            f"{apt.stderr[-2000:]}"
        )

    if verbose:
        print("[usgs-lidar] Installing PDAL Python binding + deps via pip (~2-3 min)...", flush=True)
    # PyPI's PDAL 3.5.x requires PDAL C++ 2.7+, which UbuntuGIS doesn't
    # ship for jammy. Pin to PDAL Python <3.5 (the 3.4.x line) which is
    # compatible with PDAL C++ 2.6.x. Build is from source (no Python
    # 3.12 wheels), takes 1-2 min, but completes once PDAL 2.6 headers
    # are available from the apt step above.
    pip = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", "--quiet",
         "PDAL<3.5",
         "pyforestscan", "laspy", "lazrs", "geopandas", "pyproj", "rasterio"],
        capture_output=True, text=True,
    )
    if pip.returncode != 0:
        raise RuntimeError(
            f"[usgs-lidar] pip install failed (exit {pip.returncode}):\n"
            f"{pip.stderr[-2000:]}"
        )

    # Re-add user-site after install (in case it was empty and dropped)
    if _user_site not in sys.path:
        sys.path.insert(0, _user_site)

    # Clear stale import state. The fast-path `import pdal` at the top of
    # this function fails on first call (package not yet installed), and
    # importlib caches negative path-lookup results. Without these two
    # lines the verification below sees the cached "not found" instead of
    # the newly-installed package and raises spuriously.
    import importlib
    for _mod in list(sys.modules):
        if _mod == "pdal" or _mod.startswith("pdal."):
            del sys.modules[_mod]
        elif _mod == "pyforestscan" or _mod.startswith("pyforestscan."):
            del sys.modules[_mod]
        elif _mod == "laspy" or _mod.startswith("laspy."):
            del sys.modules[_mod]
    importlib.invalidate_caches()

    # Verify all imports succeed
    try:
        import pdal  # noqa: F401
        import pyforestscan  # noqa: F401
        import laspy  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            f"[usgs-lidar] install completed but import still fails: {e}"
        )

    if verbose:
        print("[usgs-lidar] lidar deps OK", flush=True)


# Reproducible 27-color categorical palette mirroring the USGS 3DEP web app.
# Used to color individual coverage polygons so the user can visually
# distinguish overlapping datasets when a sage-bbox-map overlay is rendered.
_COLORS = [
    "#8c510a", "#bf812d", "#c7eae5", "#80cdc1", "#35978f", "#01665e", "#762a83",
    "#9970ab", "#d9f0d3", "#a6dba0", "#5aae61", "#1b7837", "#b35806", "#e08214",
    "#fdb863", "#d8daeb", "#b2abd2", "#8073ac", "#542788", "#377eb8", "#4daf4a",
    "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999",
]


def fetch_coverage(color_features=True):
    """Download the USGS 3DEP coverage GeoJSON and return a GeoDataFrame.

    Returns the catalog as an in-memory GeoDataFrame only — no file is
    written. Pass the result directly to your bbox-map widget's overlay
    parameter. (Writing the catalog to disk can trigger a duplicate static
    map next to the live widget in some host frameworks.)

    Args:
        color_features: if True, write a reproducible random color into each
            feature's `properties._color`. sage-bbox-map honors this for
            per-feature coloring; without it the overlay would be a single
            color.

    Returns:
        GeoDataFrame in EPSG:4326 with one row per dataset. Important columns:
        `name` (dataset name), `url` (EPT endpoint), `count` (total point
        count for the dataset), `geometry` (Polygon or MultiPolygon).
    """
    resp = requests.get(
        "https://usgs.entwine.io/boundaries/resources.geojson", timeout=30
    )
    resp.raise_for_status()
    data = resp.json()

    if color_features:
        random.seed(42)
        for feat in data["features"]:
            feat.setdefault("properties", {})["_color"] = random.choice(_COLORS)

    gdf = gpd.GeoDataFrame.from_features(
        [f for f in data["features"]
         if f["geometry"]["type"] in ("Polygon", "MultiPolygon")],
        crs="EPSG:4326",
    )
    return gdf


def filter_by_bbox(coverage, bbox, max_points=20_000_000):
    """Return datasets intersecting `bbox` whose estimated point count is below max_points.

    The estimated point count for a clipped dataset is computed as
    `dataset_count * (clip_area / dataset_area)`, where the areas are computed
    on a WGS84 ellipsoid. Datasets above `max_points` are excluded so the user
    cannot accidentally request a download with hundreds of millions of
    points.

    Args:
        coverage: GeoDataFrame returned by `fetch_coverage()`.
        bbox: 4-tuple `(minx, miny, maxx, maxy)` in EPSG:4326.
        max_points: skip datasets whose estimated bbox-clipped point count
            exceeds this threshold (default 20 million).

    Returns:
        List of dicts: `[{"name", "url", "count", "est"}]`, where `count` is
        the dataset's total point count and `est` is the bbox-clipped
        estimate. Empty list if no datasets intersect (or all are too large).
    """
    if bbox is None:
        raise ValueError("filter_by_bbox: bbox is None — draw a rectangle first")
    minx, miny, maxx, maxy = bbox
    query_geom = box(minx, miny, maxx, maxy)

    intersecting = coverage[coverage.intersects(query_geom)]
    if intersecting.empty:
        return []

    geod = pyproj.Geod(ellps="WGS84")
    matches = []
    for _, row in intersecting.iterrows():
        url = row.get("url", "")
        name = row.get("name", "Unknown")
        if not url:
            continue
        count = row.get("count") or 0
        poly = row.geometry
        if count and poly and not poly.is_empty:
            dataset_area = abs(geod.geometry_area_perimeter(poly)[0])
            clip = query_geom.intersection(poly)
            clip_area = (abs(geod.geometry_area_perimeter(clip)[0])
                         if not clip.is_empty else 0)
            est = int(count * clip_area / dataset_area) if dataset_area > 0 else 0
        else:
            est = 0
        if est > max_points:
            continue
        matches.append({
            "name": name,
            "url": url,
            "count": int(count) if count else 0,
            "est": est,
        })
    return matches
