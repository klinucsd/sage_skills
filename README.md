# sage_skills

A collection of domain-specific skills for [Sage (Science Agent for Jupyter)](https://github.com/klinucsd/sage). Each skill is a self-contained directory with a `SKILL.md` plus any helper Python modules or data files needed to use it.

Sage's `%%skill` cell magic installs skills directly from this repo into a user's notebook environment without rebuilding the Sage Docker image. See the [Sage README](https://github.com/klinucsd/sage) for how `%%skill` works and the security model around pinned commits and trust prompts.

## Quick install

In a Sage notebook, add a `%%skill` cell that pins to a specific commit:

```python
%%skill
https://github.com/klinucsd/sage_skills/tree/<COMMIT_SHA>/topography/usgs-lidar
https://github.com/klinucsd/sage_skills/tree/<COMMIT_SHA>/hydrography/nhd-rivers
```

Replace `<COMMIT_SHA>` with the 40-character commit hash from this repo. Branch refs (`main`, `master`, …) are rejected by `%%skill` for safety; tags are accepted with a warning.

## Repository layout

Skills are organized by discipline. Each top-level folder collects related domains; skills inside follow `kebab-case` naming.

| Discipline | Skills |
|---|---|
| `topography/` | Elevation, LiDAR point clouds, DEMs, canopy height. `usgs-lidar`, `gedi-l2a`, `cop30-topo`, `py3dep-dem`. |
| `hydrography/` | Rivers, floods, watershed analysis, Kanawha demo set, Po-basin groundwater wells. `nhd-rivers`, `kanawha-flood-depth`, `kanawha-reach-impact`, `kanawha-cikr-impact`, `kanawha-nsi-impact`. Italian groundwater (under `hydrography/groundwater/italy/`): `po-wells`, `po-wells-timeseries`, `er-well-registry`. |
| `remote-sensing/` | Satellite imagery and SAR. `sentinel1-sar`, `sentinel2-l2a`. |
| `fire/` | Wildfire detections, surface fuels, vegetation treatments. `sdge-goes-fire`, `sdge-surface-fuels`, `ca-vegetation-treatments`. |
| `hazards/` | Earthquakes and other natural hazards. `usgs-earthquake-events`. |
| `astronomy/` | Astronomical data products. `exoplanet-transits`. |

A skill that genuinely spans multiple disciplines is placed under its *primary* use; the categorization is a navigation aid, not a strict taxonomy.

## Skill structure

A skill folder contains at minimum:

```
<discipline>/<skill-name>/
├── SKILL.md           # human + agent-readable description and usage
├── *.py               # optional helper modules
├── *.csv / *.xlsx     # optional embedded reference data
└── requirements.txt   # optional Python dependencies for the skill
```

`SKILL.md` uses YAML frontmatter (`name`, `description`, optional `allowed-tools`) followed by free-form Markdown that the agent reads to decide when and how to invoke the skill. See any existing skill for a working example.

`requirements.txt` is honored by future versions of `%%skill` to install per-skill Python dependencies automatically — most skills here are pure-Python and don't need one. Skills requiring native libraries (e.g. PDAL for `usgs-lidar`) document the conda install in their `SKILL.md`.

## License

Each skill carries the license of its underlying data source where applicable. Unless otherwise noted, the skill code itself is provided as-is for non-commercial use.
