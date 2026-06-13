"""Build the Piemonte well time-series parquet bundle from the source GitHub repo.

This script is run *once* during development, not at runtime. It downloads the
109 per-well CSV files from `github.com/rlsandovalp/Well_data_Po/Piemonte/`
together with the auxiliary `wellsSamplingDepth.txt`, consolidates them into
a single parquet file with tight types and snappy compression, and writes
the result to `data/piemonte_wtd_timeseries.parquet`.

Re-run only when the upstream source data changes. The output parquet is
committed to the repo; the skill's runtime loader reads it directly from
disk without any network dependency.

Source attribution per row is preserved via the `source_file` column
(e.g. `Piemonte/00100410001.csv`), matching the directory structure in the
upstream repo so anyone re-tracing a value can find it.

Usage
-----
    cd skills/po-wells-timeseries
    python build_parquet.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

GITHUB_OWNER = "rlsandovalp"
GITHUB_REPO = "Well_data_Po"
GITHUB_BRANCH = "main"
PIEMONTE_DIR = "Piemonte"

RAW_BASE = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
    f"{GITHUB_BRANCH}/{PIEMONTE_DIR}"
)
API_LIST = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
    f"{PIEMONTE_DIR}?per_page=200"
)

HERE = Path(__file__).parent
OUT_PATH = HERE / "data" / "piemonte_wtd_timeseries.parquet"


def list_csv_filenames() -> list[str]:
    """Return the per-well CSV filenames under Piemonte/ via the GitHub API."""
    r = requests.get(API_LIST, timeout=30)
    r.raise_for_status()
    return sorted(
        entry["name"]
        for entry in r.json()
        if entry["type"] == "file" and entry["name"].endswith(".csv")
    )


def fetch_csv(filename: str) -> pd.DataFrame:
    """Download a single per-well CSV and return as a DataFrame.

    Source schema: `date,wtd` with 8-hour-interval timestamps in
    `YYYY/MM/DD HH:MM:SS` format and `wtd` as a float in meters.
    """
    url = f"{RAW_BASE}/{filename}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(
        io.StringIO(r.text),
        parse_dates=["date"],
        date_format="%Y/%m/%d %H:%M:%S",
    )
    return df


def fetch_sampling_depths() -> dict[str, int]:
    """Return the {well_id: sampling_depth_m} map from wellsSamplingDepth.txt.

    The file has lines of the form `<well_id> V <depth>` (one record per
    well, depth in meters).
    """
    url = f"{RAW_BASE}/wellsSamplingDepth.txt"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    depths: dict[str, int] = {}
    for line in r.text.strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            depths[parts[0]] = int(parts[2])
    return depths


def main() -> int:
    print("Listing Piemonte CSV filenames via GitHub API ...", flush=True)
    csv_files = list_csv_filenames()
    print(f"  found {len(csv_files)} CSVs", flush=True)

    print("Fetching wellsSamplingDepth.txt ...", flush=True)
    depths = fetch_sampling_depths()
    print(f"  parsed {len(depths)} (well_id -> depth) entries", flush=True)

    print(f"Downloading {len(csv_files)} per-well CSVs ...", flush=True)
    frames: list[pd.DataFrame] = []
    for i, fname in enumerate(csv_files, 1):
        well_id = fname.removesuffix(".csv")
        df = fetch_csv(fname)
        df["well_id"] = well_id
        df["source_file"] = f"{PIEMONTE_DIR}/{fname}"
        df["sampling_depth_m"] = depths.get(well_id, pd.NA)
        frames.append(df)
        if i % 25 == 0 or i == len(csv_files):
            print(f"  {i}/{len(csv_files)}  ({fname})", flush=True)

    print("Concatenating ...", flush=True)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["well_id", "date", "wtd",
                         "sampling_depth_m", "source_file"]]
    combined = combined.astype({
        "well_id":          "string",
        "wtd":              "float32",
        "sampling_depth_m": "Int16",   # nullable for any unmatched well
        "source_file":      "string",
    })
    combined = combined.sort_values(["well_id", "date"]).reset_index(drop=True)

    print(f"  total rows: {len(combined):,}")
    print(f"  unique wells: {combined['well_id'].nunique()}")
    print(f"  date range: "
          f"{combined['date'].min()} -> {combined['date'].max()}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet to {OUT_PATH} (snappy compression) ...", flush=True)
    combined.to_parquet(OUT_PATH, compression="snappy", index=False)

    sz = OUT_PATH.stat().st_size
    print(f"  wrote {sz:,} bytes ({sz / 1024 / 1024:.2f} MB)", flush=True)
    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
