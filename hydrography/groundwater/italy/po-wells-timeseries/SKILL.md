---
name: po-wells-timeseries
description: >-
  Retrieve the per-well water-table-depth time series for 109 Piemonte
  groundwater monitoring wells as a pandas DataFrame, covering January
  2012 through August 2023 at 8-hour sampling cadence. Use whenever the
  user asks about how water tables changed over time — trends, seasonal
  cycles, drought / wet events, single-well histories, "when did X
  happen", "compare year Y to year Z", multi-year aggregates, or any
  question that mentions a specific date or time range in the Piemonte
  region. Loads a single bundled parquet file (no network at runtime)
  built from the per-well CSVs in github.com/rlsandovalp/Well_data_Po,
  with per-row provenance preserved.
---

# Po Wells — Piemonte Time-Series Skill

This skill exposes **968,862 water-table-depth observations** across
**109 groundwater wells in the Piemonte (Piedmont) region**, sampled at
8-hour intervals from **2012-01-01 through 2023-08-31**.

The data ships as a single bundled parquet file
(`data/piemonte_wtd_timeseries.parquet`, ~3 MB) consolidating 109
upstream per-well CSV files. The runtime loader reads the parquet
directly from disk — there is **no network dependency at query time**.

This skill is the **time-axis companion** to `po-wells`: where po-wells
returns one row per well with time-averaged mean and standard deviation,
this skill returns the underlying time-stamped observations and answers
questions about *when* and *how* water tables changed.

## What the data is

Each row is one **water-table-depth (WTD) measurement** taken at a
specific well at a specific timestamp:

- **`wtd`** is the depth from ground surface down to the water table, in
  meters. **Small values = water near the surface (wet conditions);
  large values = water deep below the surface (dry / heavily pumped).**
- **Negative `wtd` is valid.** In confined-aquifer wells, the
  piezometric head can rise *above* ground surface (artesian flow); the
  bundled data contains a few such observations.
- **8-hour cadence**: timestamps fall at 00:00, 08:00, and 16:00 each
  day — three observations per well per day.
- **11+ years of coverage** per well in most cases (some wells start or
  end mid-period; not every well has every timestamp).

The data covers 109 wells across the Piemonte region of northwest
Italy, within the Po River basin. Well coordinates are not part of this
skill — see `po-wells` for the well location, region tag, and
time-averaged summary statistics.

## The bundled parquet

The skill ships a single file:

```
skills/po-wells-timeseries/data/piemonte_wtd_timeseries.parquet
```

- Snappy-compressed, ~3 MB on disk
- Built from 109 per-well CSV files at
  `github.com/rlsandovalp/Well_data_Po/Piemonte/<well_id>.csv` plus
  the auxiliary `Piemonte/wellsSamplingDepth.txt`
- Sorted by `(well_id, date)` for efficient within-well range scans

The build script `build_parquet.py` (in this skill folder) documents
exactly how the parquet was produced and can be re-run if the upstream
source data is ever updated.

## Schema

| Column | Type | Meaning |
|--------|------|---------|
| `well_id` | string | Original Piemonte well identifier (11-digit numeric, e.g. `00100410001`) |
| `date` | datetime64[ns] | Observation timestamp (UTC-naive, 8-hour cadence) |
| `wtd` | float32 | Water-table depth in meters (negative = artesian) |
| `sampling_depth_m` | Int16 (nullable) | Static per-well sampling-tube depth, from `wellsSamplingDepth.txt` — same value across all rows of a given `well_id` |
| `source_file` | string | Original CSV path in the upstream repo (`Piemonte/<well_id>.csv`) — used for per-row provenance |

Row count: **968,862**. Unique wells: **109**.

## Standard loader

```python
import pandas as pd

PARQUET_PATH = "skills/po-wells-timeseries/data/piemonte_wtd_timeseries.parquet"

def load_piemonte_timeseries() -> pd.DataFrame:
    """Load the full Piemonte WTD time series as a pandas DataFrame.

    Returns ~969k rows × 5 columns; ~150 MB in memory. Sorted by
    (well_id, date). For large analyses, filter early with pyarrow
    predicates (see Performance below).
    """
    return pd.read_parquet(PARQUET_PATH)
```

A bare load takes ~200 ms. For most queries this is fine.

### Performance tip — filtering at read time

If a query only needs a subset (one well, one year, etc.), filter
during the parquet read instead of after — much faster and uses far
less memory:

```python
# Only one well
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001")],
)

# Only 2022. IMPORTANT: date filter values must be pd.Timestamp objects,
# not strings — pyarrow's filter pushdown will raise an
# `ArrowNotImplementedError` if you pass a string for a timestamp column.
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("date", ">=", pd.Timestamp("2022-01-01")),
             ("date", "<",  pd.Timestamp("2023-01-01"))],
)

# One well in one year
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001"),
             ("date", ">=", pd.Timestamp("2022-01-01")),
             ("date", "<",  pd.Timestamp("2023-01-01"))],
)
```

## Saving the result

This skill returns a tabular DataFrame, not a GeoDataFrame. Save the
result as CSV in `temp_dir` so the UI can render it:

```python
import os
os.makedirs(temp_dir, exist_ok=True)
df.to_csv(os.path.join(temp_dir, "well_timeseries.csv"), index=False)
```

You may additionally save a matplotlib PNG chart alongside the CSV if
a visualization helps the user — the UI will display it. Saving an
image is fine; **reading one back is not**.

> ⚠️ **DO NOT call `read_file` on any image you produce
> (`.png`, `.jpg`, `.pdf`, etc.).** The model has no vision capability:
> the read returns empty, typically triggering a wasteful retry loop
> that re-does the whole task from scratch. Write the file once, then
> finish your response — the UI handles display.

For map output (well locations on a basemap), use `po-wells` instead —
it provides geometries; this skill provides the time-axis values for
those same wells.

## Example queries

### Time series for a single well

```python
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001")],
)
df = df.sort_values("date")
df.to_csv(os.path.join(temp_dir, "well_00100410001_timeseries.csv"),
          index=False)
print(f"{len(df):,} observations from {df.date.min()} to {df.date.max()}")
print(f"WTD range: {df.wtd.min():.2f} to {df.wtd.max():.2f} m")
```

### When did a specific well have its lowest water table?

```python
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001")],
)
# Lowest water table = largest wtd value (water furthest below surface)
deepest = df.loc[df.wtd.idxmax()]
print(f"Deepest observation: {deepest.wtd:.2f} m on {deepest.date}")
print(f"Source: {deepest.source_file}")
```

### Daily mean WTD for one well (smooth out the 8-hour cadence)

```python
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001")],
)
daily = df.set_index("date").resample("D")["wtd"].mean().to_frame("daily_mean_wtd")
daily.to_csv(os.path.join(temp_dir, "00100410001_daily.csv"))
```

### Monthly seasonality across multiple years

```python
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001")],
)
df["month"] = df.date.dt.month
seasonal = df.groupby("month")["wtd"].agg(["mean", "min", "max", "std"]).round(2)
print(seasonal)
# Reveals seasonal cycle: shallow water tables in spring, deepest in late summer.
```

### Compare two years for the same well

```python
df = pd.read_parquet(
    PARQUET_PATH,
    filters=[("well_id", "==", "00100410001"),
             ("date", ">=", pd.Timestamp("2017-01-01")),
             ("date", "<",  pd.Timestamp("2023-01-01"))],
)
df["year"] = df.date.dt.year
annual = df.groupby("year")["wtd"].agg(["mean", "min", "max"]).round(2)
print(annual)
```

### Find the most volatile well basin-wide

```python
# Per-well standard deviation across the full time series
df = pd.read_parquet(PARQUET_PATH, columns=["well_id", "wtd"])
volatility = df.groupby("well_id")["wtd"].std().sort_values(ascending=False)
print(volatility.head(10))
```

### Detect the driest period across all 109 wells

```python
# Daily basin-wide mean WTD — when did Piemonte have the deepest average water table?
df = pd.read_parquet(PARQUET_PATH, columns=["date", "wtd"])
daily = df.set_index("date").resample("D")["wtd"].mean()
print(f"Driest day in 2012-2023: {daily.idxmax()} (mean WTD {daily.max():.2f} m)")
```

### Year-over-year basin average

```python
df = pd.read_parquet(PARQUET_PATH, columns=["date", "wtd"])
df["year"] = df.date.dt.year
annual = df.groupby("year")["wtd"].mean().round(2)
print(annual)
# Shows the multi-year basin-wide trend; rising values indicate drying.
```

### Compose with po-wells (cross-skill verification)

The 109 Piemonte well IDs in this skill are a subset of the 137
Piedmont+Emilia wells in po-wells. Their long-term mean WTD should
match the `wtd_m` value in po-wells:

```python
# This-skill mean WTD per well
ts = pd.read_parquet(PARQUET_PATH, columns=["well_id", "wtd"])
ts_mean = ts.groupby("well_id")["wtd"].mean().reset_index().rename(
    columns={"wtd": "ts_mean_wtd_m"})

# po-wells time-averaged value (load with the po-wells skill loader)
from po_wells_loader import load_po_wells   # or inline the loader
po = load_po_wells()[["well_id", "wtd_m"]]
po = po.rename(columns={"wtd_m": "po_mean_wtd_m"})

merged = ts_mean.merge(po, on="well_id", how="inner")
print(f"Matched {len(merged)} wells; mean absolute difference: "
      f"{(merged.ts_mean_wtd_m - merged.po_mean_wtd_m).abs().mean():.3f} m")
```

## Provenance — name the source file when reporting

Every row in this skill's data carries a **`source_file` column** that
names the upstream CSV the row came from. Use it directly when citing
provenance — do not derive the filename from `well_id` even though it
would match.

| What you report | File(s) to cite |
|-----------------|-----------------|
| A specific observation (one row: one `(well_id, date, wtd)`) | The value in the row's `source_file` column, e.g. `Piemonte/00100410001.csv` |
| An aggregate over one well (e.g. min/max/mean WTD across years) | The single `source_file` value for that well |
| An aggregate over multiple wells (e.g. basin-wide annual mean) | The list of source files involved, or describe as *"all 109 files under Piemonte/ in the source repo"* |
| A `sampling_depth_m` value | `Piemonte/wellsSamplingDepth.txt` (not the per-well CSV) |

Notes:

- Use the **bare filenames as they appear in the source repository**
  (`github.com/rlsandovalp/Well_data_Po`) — paths are relative to the
  repo root (e.g. `Piemonte/00100410001.csv`). Do not include the local
  `skills/po-wells-timeseries/data/...` path or the parquet filename
  in citations; the parquet is a local performance bundle, not a
  primary source.
- For convenience, the `source_file` column already contains the
  citation-form path. Read it directly from the result row.

Always include this provenance line in the final response whenever the
user asks where a value came from, asks about reproducibility, or asks
about data sources.

## Reporting tips

- WTD is in **meters**; smaller `wtd` = wetter (water closer to
  surface); larger `wtd` = drier (water deeper down).
- **Negative `wtd` values are real and meaningful**: they indicate
  artesian conditions where the piezometric head rises above ground
  surface. Mention this if it appears in the result; do not filter it
  out as bad data.
- The cadence is **8-hourly**, not daily. If asked about a "day" or a
  "month", resample with pandas (`.resample("D")`, `.resample("M")`)
  rather than counting raw rows.
- The data covers **only Piemonte wells**. For Lombardy or
  Emilia-Romagna time series, this skill cannot help — only static
  summaries are available for those regions in `po-wells` /
  `er-well-registry`.
- The time series ends at **2023-08-31**. Questions about more recent
  events cannot be answered from this dataset; say so explicitly.
- Use `pd.read_parquet(..., filters=[...])` for any query that doesn't
  need all 109 wells — much faster and uses far less memory than a
  full load followed by `.query()`.
