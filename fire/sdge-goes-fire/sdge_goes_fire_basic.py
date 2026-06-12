#!/usr/bin/env python3
"""
Fetch GOES fire detections (last 7 days) from SDG&E WIFIRE and save as GeoJSON.

Usage as a library:
    from sdge_goes_fire_basic import fetch_goes_fires
    gdf = fetch_goes_fires("fire_detections.geojson")

Usage as a script:
    python sdge_goes_fire_basic.py <output_file>
"""
import sys

import geopandas as gpd
import pandas as pd
import requests


def fetch_goes_fires(output_file: str) -> "gpd.GeoDataFrame":
    """Fetch GOES fire detections (last 7 days) from SDG&E WIFIRE.

    Writes a GeoJSON with fields: data_time, lon, lat, hours_ago.
    Returns the GeoDataFrame.
    """
    resp = requests.get("https://sdge.sdsc.edu/geoserver/ows", params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeName": "WIFIRE:view_wfabba_goes_last_7days",
        "outputFormat": "application/json",
    })
    resp.raise_for_status()
    gdf = gpd.GeoDataFrame.from_features(resp.json()["features"], crs="EPSG:4326")
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y
    gdf["data_time"] = pd.to_datetime(gdf["data_time"], utc=True)
    gdf["hours_ago"] = (gdf["seconds_ago"].astype(float) / 3600).round(1)

    gdf.to_file(output_file, driver="GeoJSON")
    print(f"Loaded {len(gdf)} fire detections")
    print(f"Date range: {gdf['data_time'].min()} to {gdf['data_time'].max()}")
    print(gdf[["data_time", "lon", "lat", "hours_ago"]].head(10).to_string(index=False))
    print(f"Saved to: {output_file}")
    return gdf


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sdge_goes_fire_basic.py <output_file>", file=sys.stderr)
        sys.exit(1)
    fetch_goes_fires(sys.argv[1])
