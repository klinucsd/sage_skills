---
name: blake-ridge-hydrate
description: >-
  Gas-hydrate reservoir simulations for the Blake Ridge continental
  margin, offshore the southeastern United States — PFLOTRAN
  probabilistic models of methanogenesis and methane-hydrate formation
  in seafloor sediments across ~9,000 grid locations. Use when the user
  asks about gas hydrate, methane hydrate, hydrate saturation, hydrate
  mass, Blake Ridge, ODP Site 997, PFLOTRAN, methanogenesis, or how
  hydrate formation relates to water depth, seafloor temperature,
  sedimentation rate, TOC (total organic carbon), or heat flux —
  including the simulation outputs behind Eymold (2021, G-Cubed).
---

# Blake Ridge Gas-Hydrate PFLOTRAN Simulations

## Description

This skill covers the dataset published alongside Eymold, W. K. (2021),
*"Prediction of Gas Hydrate Formation at Blake Ridge using Machine
Learning and Probabilistic Reservoir Simulation"*, Geochemistry,
Geophysics, Geosystems (*G-Cubed*). The underlying simulations use
Sandia's PFLOTRAN subsurface flow / reactive transport code to model
methane generation from organic-matter decay (methanogenesis) and the
subsequent formation of solid gas hydrate in the sediment column across
the **Blake Ridge** continental margin (offshore US Southeast Atlantic).

The study area is a **108 × 84 rectangular grid** covering 9,072 map
locations. The 6,048 locations numbered `3025`–`9072` fall inside the
Blake Ridge study area and carry non-trivial simulation output; nodes
`1`–`3024` are outside the study area and are present only to fill the
rectangular grid.

The skill exposes three data files:

- A **per-node environmental attribute table** (`DataFile1_G3.txt`) —
  one row per grid location, with water depth, seafloor temperature,
  sedimentation rate, TOC, heat flux, and simulation summary
  statistics.
- A **per-node correlation table** (`DataFile2_G3.txt`) — the
  same grid, with correlation coefficients between hydrate formation
  and each of four environmental drivers.
- An **HDF5 archive** (`FigureData.h5`) of sediment-profile time series
  and hydrate-mass maps used to produce four figures in the paper.
  Groups are named `Figure_03`, `Figure_04`, `Figure_06`, `Figure_11`;
  each holds arrays of shape `(1000,)` (1000 depth points along a
  sediment column) or `(9072,)` (the full 108×84 spatial grid).

Semantics for every array and column below come from the SAND2021-2004
data-description report bundled with the dataset (`data/data_description.pdf`).

## Data

- **Source:** https://zenodo.org/records/4557948 (Zenodo DOI-backed record)
- **License:** CC-BY-4.0
- **Bundled files** (~10 MiB total, all included with the skill):
  - `data/DataFile1_G3.txt` — 12 columns × 6,048 rows, tab-delimited
  - `data/DataFile2_G3.txt` —  8 columns × 6,048 rows, tab-delimited
  - `data/FigureData.h5` — HDF5, 4 top-level groups
  - `data/data_description.pdf` — original description; bundled for provenance

Because the total size is under 11 MiB, all three data files are
cached with the skill; no lazy remote reads are needed.

## Grid geometry

- **Full grid:** 9,072 map locations arranged as a rectangular
  `108 × 84` array. The `Figure_06/Hydrate_Mass_NN` arrays index into
  this full grid; reshape via `arr.reshape((108, 84))` to plot.
- **Study area:** node IDs `3025`–`9072` (6,048 nodes). Only these
  carry simulation output in the tabular files. Outside the study
  area, values are 0 or NaN.

## Fields — tabular files

### `DataFile1_G3.txt` (per-node environmental attributes + summary)

| Column | Type | Meaning |
|---|---|---|
| `Node` | int | Grid node ID (1–9072; study-area range 3025–9072) |
| `Lon` | float | Longitude (decimal degrees, WGS84) |
| `Lat` | float | Latitude (decimal degrees, WGS84) |
| `Depth` | float | Seafloor water depth (metres, negative-down) |
| `Temp` | float | Seafloor temperature (°C) |
| `SedRate` | float | Sedimentation rate (typical units: cm/kyr) |
| `TOC` | float | Total organic carbon fraction (typical: mass fraction) |
| `Q` | float | Heat flux (typical units: mW/m²) |
| `Hmass` | float | Average hydrate mass formed across all Monte-Carlo simulations at this node |
| `Gmass` | float | Average free-gas mass formed across all simulations at this node |
| `G1%` | int | Count of simulations at this node where gas saturation reached 1% |
| `G2%` | int | Count of simulations at this node where gas saturation reached 2% |

Backs Figures 2, 5, 9, and 10 of the paper (map figures of geophysical
characteristics + average hydrate/gas formation).

### `DataFile2_G3.txt` (per-node correlation coefficients)

| Column | Type | Meaning |
|---|---|---|
| `Node` | int | Grid node ID (matches `DataFile1_G3.txt.Node` — this is the join key) |
| `Lon` | float | Longitude |
| `Lat` | float | Latitude |
| `SedRate` | float | Correlation coefficient: hydrate formation vs. sedimentation rate |
| `TOC` | float | Correlation coefficient: hydrate formation vs. TOC |
| `Q` | float | Correlation coefficient: hydrate formation vs. heat flux |
| `MRate` | float | Correlation coefficient: hydrate formation vs. methanogenesis rate |
| `MAX` | float | Maximum of the four correlation coefficients at this node |

Backs Figures 7 and 8 of the paper (map figures of correlation
coefficients). **Note:** the last five columns are **correlation
coefficients**, not raw variable values — a value of 0 means
"no simulation output at this node" (typical outside the study area)
or "no correlation."

## Arrays — HDF5 file (`FigureData.h5`)

The HDF5 file is a nested dictionary of `float64` NumPy arrays. Four
top-level groups, each corresponding to one figure in the paper:

### `Figure_03/` — 54-iteration sediment-profile ensemble at a single site (Profile 7675)

54 Monte-Carlo simulations at **one specific site** (node 7675) at the
crest of Blake Ridge. Each simulation is stored as a suite of 1D
profiles of length 1000 sampled along the sediment column depth axis:

| Dataset pattern | Shape | Physical meaning |
|---|---|---|
| `Gas_01` … `Gas_54` | `(1000,)` | Free-gas saturation as fraction of pore volume (0–1) at 1000 depth points along the sediment column |
| `Hydrate_01` … `Hydrate_54` | `(1000,)` | Solid gas-hydrate saturation as fraction of pore volume (0–1) |
| `MoleFraction_01` … `MoleFraction_54` | `(1000,)` | Aqueous methane mole fraction in the pore fluid |
| `Porosity_01` … `Porosity_54` | `(1000,)` | Sediment porosity (fraction, 0–1) |
| `Pressure_01` … `Pressure_54` | `(1000,)` | Pore pressure (units documented in the paper, typically MPa) |
| `Temperature_01` … `Temperature_54` | `(1000,)` | Sediment temperature (°C) at each depth point |

**324 datasets total** (6 quantities × 54 simulations). Index `_NN` is
the simulation index; profiles with the same index across quantities
correspond to the same PFLOTRAN run.

### `Figure_04/` — three-site profile ensembles with time evolution

Three specific sites (nodes 5233, 6576, and 8099), each with a
per-simulation ensemble of `Hydrate` and `Porosity` profiles. Number
of simulations per site varies:

- `Profile_5233/Hydrate_01`–`_100` and `Profile_5233/Porosity_01`–`_100` (100 sims)
- `Profile_6576/Hydrate_01`–`_96`  and `Profile_6576/Porosity_01`–`_96`  (96 sims)
- `Profile_8099/Hydrate_01`–`_89`  and `Profile_8099/Porosity_01`–`_89`  (89 sims)

All arrays are `(1000,)` — profiles along the sediment column.

### `Figure_06/` — hydrate-mass spatial maps across simulation sets

`Hydrate_Mass_01` … `Hydrate_Mass_12`, each shape `(9072,)`. Each is a
map of the total hydrate mass formed at every grid location for one of
12 different Monte-Carlo simulation ensembles.

**To plot as a map, reshape to (108, 84):**

```python
m = f["Figure_06/Hydrate_Mass_03"][:]      # length 9072
m_map = m.reshape((108, 84))               # spatial grid
```

### `Figure_11/` — ODP Site 997 profiles vs. Bhatnagar (2007) analytical solution

All arrays are under a `Bhatnagar/` subgroup:

- `Bhatnagar/Gas_01`–`_92` and `Bhatnagar/Hydrate_01`–`_92` (92 sims each) — PFLOTRAN Monte-Carlo runs at ODP Site 997, matched against the Bhatnagar et al. (2007) test case.
- `Bhatnagar/Exact_Gas` and `Bhatnagar/Exact_Hydrate` — analytical solutions from Bhatnagar's paper for comparison; all shape `(1000,)`.

## Cross-reference between HDF5 and tabular files

The `Profile_5233 / _6576 / _8099` group names in `Figure_04/` and the
implicit node 7675 backing `Figure_03/` are **grid node IDs** matching
the `Node` column in both `DataFile1_G3.txt` and `DataFile2_G3.txt`.
So the geographic coordinates and environmental attributes of any
HDF5-referenced profile can be looked up in the tabular files:

```python
grid.query("Node == 5233")   # → lon/lat, water depth, SedRate, TOC, Q for the Figure_04 Profile_5233 site
```

## How to Use

```python
from pathlib import Path
import numpy as np
import pandas as pd
import h5py

def _data_dir(skill_dir=None):
    if skill_dir is None:
        skill_dir = Path(__file__).parent
    return Path(skill_dir) / "data"

_NUMERIC_COLS_1 = ["Lon","Lat","Depth","Temp","SedRate","TOC","Q","Hmass","Gmass","G2%"]
_NUMERIC_COLS_2 = ["Lon","Lat","SedRate","TOC","Q","MRate","MAX"]

def _coerce(df, cols):
    """Coerce specified columns to numeric, turning malformed entries into NaN.
    The source files have a few whitespace-corrupted values (e.g. one Depth
    row reads '-4366.0 2.27') plus literal 'NaN' strings; this normalises
    both cases."""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def load_grid(skill_dir=None):
    """Load DataFile1_G3.txt as a DataFrame — per-node environmental
    attributes + simulation summary. 6,048 rows for the study area.

    Handles two data-quality issues in the source file: literal 'NaN'
    strings (outside the study area) and one whitespace-corrupted Depth
    value — both are coerced to proper NaN.
    """
    p = _data_dir(skill_dir) / "DataFile1_G3.txt"
    df = pd.read_csv(p, sep="\t", na_values=["NaN", "nan"], dtype=str)
    df["Node"] = df["Node"].astype(int)
    df["G1%"] = pd.to_numeric(df["G1%"], errors="coerce").astype("Int64")
    return _coerce(df, _NUMERIC_COLS_1)

def load_correlations(skill_dir=None):
    """Load DataFile2_G3.txt as a DataFrame — per-node correlation
    coefficients between hydrate formation and drivers.
    Same 'NaN' string + coercion handling as load_grid()."""
    p = _data_dir(skill_dir) / "DataFile2_G3.txt"
    df = pd.read_csv(p, sep="\t", na_values=["NaN", "nan"], dtype=str)
    df["Node"] = df["Node"].astype(int)
    return _coerce(df, _NUMERIC_COLS_2)

def open_h5(skill_dir=None):
    """Open FigureData.h5 read-only. Returns an h5py.File — caller is
    responsible for closing (or use as a context manager)."""
    p = _data_dir(skill_dir) / "FigureData.h5"
    return h5py.File(p, "r")

def load_hydrate_mass_map(sim_index, skill_dir=None):
    """Return the Figure_06 hydrate-mass map for one simulation set,
    reshaped to a (108, 84) spatial array ready to plot with imshow /
    pcolormesh. `sim_index` is 1..12."""
    with open_h5(skill_dir) as f:
        m = f[f"Figure_06/Hydrate_Mass_{sim_index:02d}"][:]
    return m.reshape((108, 84))

def load_profile(group, quantity, sim_index=None, subgroup=None, skill_dir=None):
    """Fetch one sediment-column profile.

    Examples:
      load_profile("Figure_03", "Hydrate", 1)                  # simulation 1 of the 54 at Profile 7675
      load_profile("Figure_04", "Hydrate", 42, subgroup="Profile_5233")
      load_profile("Figure_11", "Gas", 5, subgroup="Bhatnagar")
      load_profile("Figure_11", "Exact_Hydrate", subgroup="Bhatnagar")
    """
    with open_h5(skill_dir) as f:
        node = f[group]
        if subgroup:
            node = node[subgroup]
        name = quantity if sim_index is None else f"{quantity}_{sim_index:02d}"
        return node[name][:]
```

## Examples

```python
# 1. Where in the world is Blake Ridge?
grid = load_grid()
print(f"Longitude range: {grid['Lon'].min():.2f} to {grid['Lon'].max():.2f}")
print(f"Latitude  range: {grid['Lat'].min():.2f} to {grid['Lat'].max():.2f}")
print(f"Water depth range: {grid['Depth'].min():.0f} m to {grid['Depth'].max():.0f} m")

# 2. Where does the model predict the most hydrate?
top10 = grid.sort_values("Hmass", ascending=False).head(10)
print(top10[["Node", "Lon", "Lat", "Depth", "Hmass", "TOC", "Q"]])

# 3. What environmental factor most influences hydrate formation
#    across the study area?
corr = load_correlations()
mean_corr = corr[["SedRate", "TOC", "Q", "MRate"]].mean()
print("Mean absolute correlation coefficient across nodes:")
print(mean_corr.abs().sort_values(ascending=False))

# 4. Spatial map of hydrate mass from simulation set 3
import matplotlib.pyplot as plt
m = load_hydrate_mass_map(3)                         # (108, 84)
plt.imshow(m, origin="lower", cmap="viridis")
plt.colorbar(label="Hydrate mass")
plt.title("Blake Ridge — hydrate mass, simulation set 3")

# 5. Profile of hydrate saturation vs. depth at Profile 7675
#    (Figure_03), simulation index 1 out of 54
h = load_profile("Figure_03", "Hydrate", 1)           # (1000,)
plt.plot(h, np.arange(1000))
plt.gca().invert_yaxis()                              # depth increases downward
plt.xlabel("Hydrate saturation")
plt.ylabel("Depth index (0 = seafloor)")

# 6. Compare PFLOTRAN vs. Bhatnagar-analytical for hydrate at ODP Site 997
exact = load_profile("Figure_11", "Exact_Hydrate", subgroup="Bhatnagar")
sim_5 = load_profile("Figure_11", "Hydrate", 5, subgroup="Bhatnagar")
plt.plot(exact, np.arange(1000), label="Bhatnagar analytical")
plt.plot(sim_5, np.arange(1000), label="PFLOTRAN sim 5")
plt.legend()

# 7. Cross-file join: what are the geographic coordinates and
#    environmental attributes of the three Figure_04 sites?
sites = [5233, 6576, 8099]
grid.query("Node in @sites")[["Node", "Lon", "Lat", "Depth", "SedRate", "TOC", "Q"]]
```

## Caveats

- **Physical units** for `Depth`, `SedRate`, `TOC`, `Q`, `Pressure`,
  and `MoleFraction` are not spelled out in the bundled description
  PDF — they follow standard PFLOTRAN and marine-geoscience conventions
  (m, cm/kyr, mass fraction, mW/m², MPa, dimensionless respectively).
  When precise units matter (writing a paper, cross-comparing with
  other datasets), consult the source publication:
  Eymold (2021), *G-Cubed*, doi: 10.1029/2020GC009302.
- **`DataFile2_G3.txt` values are correlation coefficients**, not the
  underlying environmental values themselves. A 0 in the `TOC` column
  of DataFile2 does NOT mean zero organic carbon — it means "no
  computed correlation" (typically because the node is outside the
  study area). Environmental values live in `DataFile1_G3.txt`.
- **Study area vs. full grid.** The tabular files list 6,048 nodes
  (study area only). The `Figure_06` HDF5 arrays include 9,072
  positions (fills the rectangular grid to 108×84). Non-study-area
  positions in the maps carry zero or NaN.
- **Simulation index has no external meaning.** The `_NN` suffix on
  HDF5 datasets is just a Monte-Carlo iteration counter within one
  ensemble — index 5 in `Gas_05` and `Hydrate_05` of `Figure_03/`
  refer to the same simulation run, but there's no cross-simulation
  ordering to interpret.
