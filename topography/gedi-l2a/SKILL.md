---
name: gedi-l2a
description: "Download NASA GEDI L2A canopy height data for a bounding box and time period. Use when the user asks for GEDI data, canopy height, forest height, tree height, or lidar canopy measurements. Requires EARTHDATA_USERNAME and EARTHDATA_PASSWORD credentials. Extracts quality-filtered shots with rh25–rh100, elev_highestreturn, elev_lowestmode, and sensitivity fields."
---

# gedi-l2a — GEDI L2A Canopy Height Download

Downloads NASA GEDI L2A data for a user-specified bounding box and time period.
Uses `earthaccess` for NASA Earthdata login, granule search, and batch download.
HDF5 files are downloaded to a temp directory, canopy-height fields extracted,
then deleted — no streaming (streaming via h5py remote is too slow).

## Quality filter applied per shot

```
quality_flag == 1  AND  degrade_flag == 0  AND  0 < rh98 < 130 m
```

## Dependencies

```
pip install earthaccess h5py python-dotenv
```

## Importing the helper

The helper module `gedi_l2a.py` lives next to this SKILL.md. Add the skill
directory to `sys.path` before importing:

```python
import sys
sys.path.insert(0, "/absolute/path/to/this/skill/directory")
from gedi_l2a import fetch_gedi_l2a
```

## API

```python
fetch_gedi_l2a(
    bbox,                  # (minx, miny, maxx, maxy) EPSG:4326
    output_path,           # destination CSV path
    earthdata_user=None,   # or set EARTHDATA_USERNAME env var
    earthdata_pass=None,   # or set EARTHDATA_PASSWORD env var
    year=None,             # e.g. 2024 — downloads the full calendar year
    start_date=None,       # "YYYY-MM-DD" — use instead of year for custom ranges
    end_date=None,         # "YYYY-MM-DD"
    batch_size=8,          # granules downloaded per batch
)
```

Returns a `pd.DataFrame` and writes a CSV to `output_path`.

### Output columns

| Column | Description |
|---|---|
| `latitude` / `longitude` | Shot ground location (EPSG:4326) |
| `elev_highestreturn` | Canopy top elevation, m above WGS84 ellipsoid |
| `elev_lowestmode` | Ground elevation, m above WGS84 ellipsoid |
| `rh25`, `rh50`, `rh75`, `rh95`, `rh98`, `rh100` | Relative height at percentile, m above ground |
| `sensitivity` | Canopy sensitivity (0–1) |
| `quality_flag` | 1 = good quality (all rows have 1 after filter) |
| `degrade_flag` | 0 = not degraded (all rows have 0 after filter) |
| `beam` | GEDI beam identifier |
| `shot_number` | Unique shot ID |
| `delta_time` | Seconds since 2018-01-01 00:00:00 UTC |

## Credentials

`fetch_gedi_l2a` requires `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`. Two
supported sources, in order — env vars first, interactive `earthaccess` login
as fallback. Never print credential values.

**1. Environment variables (preferred — non-interactive)**

Read from `.env` or the process environment:

```python
import os
try:
    from dotenv import load_dotenv
    if os.path.exists(".env"):
        load_dotenv(".env")
except ImportError:
    pass
earthdata_user = os.environ.get("EARTHDATA_USERNAME")
earthdata_pass = os.environ.get("EARTHDATA_PASSWORD")
```

**2. Interactive login (fallback)**

If env vars are missing, call `earthaccess.login(strategy="interactive")`. It
prompts for username + password and caches them in `~/.netrc`. Re-read into
env vars so `fetch_gedi_l2a` (which uses `strategy="environment"`) picks them
up:

```python
if not earthdata_user or not earthdata_pass:
    import earthaccess, netrc
    earthaccess.login(strategy="interactive", persist=True)
    auth = netrc.netrc().authenticators("urs.earthdata.nasa.gov")
    if auth:
        os.environ["EARTHDATA_USERNAME"], _, os.environ["EARTHDATA_PASSWORD"] = auth
        earthdata_user = os.environ["EARTHDATA_USERNAME"]
        earthdata_pass = os.environ["EARTHDATA_PASSWORD"]
```

## Full example

```python
import os, sys
from pathlib import Path

# Substitute the absolute path of the directory containing this SKILL.md
sys.path.insert(0, "/path/to/skills/gedi-l2a")
from gedi_l2a import fetch_gedi_l2a

# Load credentials
try:
    from dotenv import load_dotenv
    if os.path.exists(".env"):
        load_dotenv(".env")
except ImportError:
    pass
earthdata_user = os.environ.get("EARTHDATA_USERNAME")
earthdata_pass = os.environ.get("EARTHDATA_PASSWORD")

if not earthdata_user or not earthdata_pass:
    import earthaccess, netrc
    earthaccess.login(strategy="interactive", persist=True)
    auth = netrc.netrc().authenticators("urs.earthdata.nasa.gov")
    if auth:
        os.environ["EARTHDATA_USERNAME"], _, os.environ["EARTHDATA_PASSWORD"] = auth
        earthdata_user = os.environ["EARTHDATA_USERNAME"]
        earthdata_pass = os.environ["EARTHDATA_PASSWORD"]

bbox = (-122.71, 43.52, -122.56, 43.63)   # (minx, miny, maxx, maxy)
output_path = Path("gedi_canopy_2024.csv")

df = fetch_gedi_l2a(
    bbox=bbox,
    output_path=output_path,
    earthdata_user=earthdata_user,
    earthdata_pass=earthdata_pass,
    year=2024,
)
print(df.head())
print(f"Columns: {list(df.columns)}")
```

## Execution rules

- Save your script to a `.py` file, then run it with `python /path/to/script.py`.
- Always load credentials from `.env` / env vars first, with
  `earthaccess.login(strategy="interactive")` as the fallback. Do NOT hardcode
  or print credential values.
- Pick a descriptive output filename like `gedi_canopy_2024.csv`.
- Do NOT re-implement the download/extract logic. Call `fetch_gedi_l2a` and
  let it handle everything.
- `batch_size` controls memory pressure. Default (8) works for small bboxes.
  For very large bboxes (hundreds of granules), reduce to 4.
- The function prints progress per batch. Do NOT add your own download loops.
