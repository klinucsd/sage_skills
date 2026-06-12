---
name: exoplanet-transits
description: "Exoplanet transit data from NASA. Use when the user wants to: fetch transiting exoplanet metadata from the NASA Exoplanet Archive; download TESS or Kepler photometry from NASA MAST; phase-fold a light curve to reveal a transit; analyze transit depth, duration, or radius ratio; produce a transit summary plot. Pure data skill — Python functions only, no UI."
---

# exoplanet-transits — Data Skill

This skill provides **data only** — fetching from NASA APIs, processing photometry,
and computing transit parameters. It contains no UI logic and has no agent-runtime
dependencies — usable from any Python environment.

## Dependencies

```
pip install lightkurve astropy requests
```

(Some hosts pre-install `requests`; `lightkurve` and `astropy` are typically not.)

---

## Execution rules — read before writing any code

- Save every script to a `.py` file, then run it with `python /path/to/script.py`. Never use heredoc (`python << 'EOF'`). Never chain commands with `&&`.
- Never call `plt.show()` in scripts. Save to a PNG with `plt.savefig(...)` and print the path.
- Steps 2-4 below each have an "Inputs" section listing the values they need (planet name, period, etc.). Set those values at the top of your script — either by combining all steps into one script (simplest), or by carrying values across separate scripts via your framework's variable-passing mechanism.

---

## Step 1 — Fetch the transiting-exoplanet catalog

Pure data step. Produces one kernel variable:

| Variable  | Type            | Contents |
|-----------|-----------------|----------|
| `planets` | list of dicts   | Each dict has the NASA Exoplanet Archive fields below |

Each item has these keys: `pl_name`, `hostname`, `pl_orbper` (orbital period, days),
`pl_trandep` (transit depth, fraction), `pl_rade` (planet radius, R⊕),
`pl_bmasse` (planet mass, M⊕), `sy_vmag` (host star V magnitude),
`st_teff` (host star Teff, K), `st_rad` (host star radius, R☉).

Items are sorted alphabetically by `pl_name`.

```python
import requests

# Fallback list of well-known bright transiting exoplanets, used if the NASA
# Exoplanet Archive API is slow / unreachable. Each dict has the same keys as
# the live API.
_FALLBACK_PLANETS = [
    {"pl_name": "HD 209458 b",  "hostname": "HD 209458",  "pl_orbper": 3.52474,  "pl_trandep": 0.01478, "pl_rade": 15.59, "pl_bmasse": 219.5, "sy_vmag": 7.65,  "st_teff": 6117.0, "st_rad": 1.20},
    {"pl_name": "HAT-P-11 b",   "hostname": "HAT-P-11",   "pl_orbper": 4.88781,  "pl_trandep": 0.00330, "pl_rade":  4.36, "pl_bmasse":  26.0, "sy_vmag": 9.47,  "st_teff": 4780.0, "st_rad": 0.75},
    {"pl_name": "WASP-18 b",    "hostname": "WASP-18",    "pl_orbper": 0.94145,  "pl_trandep": 0.00960, "pl_rade": 13.40, "pl_bmasse": 3260.0,"sy_vmag": 9.29,  "st_teff": 6400.0, "st_rad": 1.24},
    {"pl_name": "WASP-76 b",    "hostname": "WASP-76",    "pl_orbper": 1.80988,  "pl_trandep": 0.01200, "pl_rade": 21.40, "pl_bmasse": 617.0, "sy_vmag": 9.52,  "st_teff": 6250.0, "st_rad": 1.76},
    {"pl_name": "WASP-121 b",   "hostname": "WASP-121",   "pl_orbper": 1.27492,  "pl_trandep": 0.01580, "pl_rade": 19.54, "pl_bmasse": 557.0, "sy_vmag": 10.44, "st_teff": 6460.0, "st_rad": 1.46},
    {"pl_name": "HAT-P-7 b",    "hostname": "HAT-P-7",    "pl_orbper": 2.20474,  "pl_trandep": 0.00640, "pl_rade": 15.97, "pl_bmasse": 510.0, "sy_vmag": 10.46, "st_teff": 6350.0, "st_rad": 1.84},
    {"pl_name": "GJ 436 b",     "hostname": "GJ 436",     "pl_orbper": 2.64390,  "pl_trandep": 0.00690, "pl_rade":  4.22, "pl_bmasse":  22.4, "sy_vmag": 10.61, "st_teff": 3416.0, "st_rad": 0.46},
    {"pl_name": "WASP-12 b",    "hostname": "WASP-12",    "pl_orbper": 1.09142,  "pl_trandep": 0.01450, "pl_rade": 19.40, "pl_bmasse": 447.0, "sy_vmag": 11.69, "st_teff": 6300.0, "st_rad": 1.60},
    {"pl_name": "WASP-39 b",    "hostname": "WASP-39",    "pl_orbper": 4.05528,  "pl_trandep": 0.02170, "pl_rade": 14.17, "pl_bmasse":  90.0, "sy_vmag": 12.09, "st_teff": 5400.0, "st_rad": 0.90},
    {"pl_name": "WASP-6 b",     "hostname": "WASP-6",     "pl_orbper": 3.36101,  "pl_trandep": 0.01650, "pl_rade": 13.39, "pl_bmasse": 171.0, "sy_vmag": 11.90, "st_teff": 5450.0, "st_rad": 0.87},
    {"pl_name": "WASP-17 b",    "hostname": "WASP-17",    "pl_orbper": 3.73548,  "pl_trandep": 0.01850, "pl_rade": 21.44, "pl_bmasse": 159.0, "sy_vmag": 11.60, "st_teff": 6650.0, "st_rad": 1.58},
    {"pl_name": "GJ 3470 b",    "hostname": "GJ 3470",    "pl_orbper": 3.33665,  "pl_trandep": 0.00580, "pl_rade":  4.75, "pl_bmasse":  14.0, "sy_vmag": 12.27, "st_teff": 3600.0, "st_rad": 0.48},
]

planets = []
print("Fetching transiting exoplanets from NASA Exoplanet Archive...")
try:
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
    query = (
        "SELECT pl_name, hostname, pl_orbper, pl_trandep, pl_rade, pl_bmasse, "
        "sy_vmag, st_teff, st_rad, ra, dec "
        "FROM pscomppars "
        "WHERE tran_flag=1 AND sy_vmag < 12.5 AND pl_orbper < 15 "
        "AND pl_orbper IS NOT NULL AND pl_rade IS NOT NULL AND sy_vmag IS NOT NULL "
        "ORDER BY pl_name ASC"
    )
    resp = requests.get(url, params={"query": query, "format": "json"}, timeout=60)
    resp.raise_for_status()
    rows = resp.json()
    planets = [p for p in rows if p.get("pl_orbper") and p.get("sy_vmag")]
    print(f"Got {len(planets)} planets from NASA Exoplanet Archive.")
except Exception as e:
    print(f"NASA Exoplanet Archive unavailable ({e}). Using built-in fallback list.")
    planets = list(_FALLBACK_PLANETS)

planets = sorted(planets, key=lambda p: p["pl_name"])
print(f"Catalog ready: {len(planets)} entries (sorted by planet name).")
```

After this script runs, `planets` holds the catalog. Pick a planet (interactively,
by name, or by index) and extract the fields Steps 2-4 need:

```python
chosen = planets[0]                       # or whichever row matches the user's choice
target_planet  = chosen["pl_name"]        # planet name
target_star    = chosen["hostname"]       # host star name
orbital_period = chosen["pl_orbper"]      # orbital period in days
planet_data    = chosen                   # full record, used in the summary card
```

Use these variable names in Steps 2-4 below, or rename them and update the
references consistently.

---

## Step 2 — Download a TESS / Kepler light curve

**Inputs** (set at top of script, from Step 1):
- `target_star` — host star name (e.g. `"HD 209458"`)
- `target_planet` — planet name for plot titles (e.g. `"HD 209458 b"`)

**Outputs:** `lc` (lightkurve `LightCurve`), `lc_mission` (str). Saves `lc_raw.csv`
and `lc_raw.png`.

```python
import lightkurve as lk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# Set from your Step 1 selection
target_star   = "HD 209458"
target_planet = "HD 209458 b"

print(f"Searching NASA MAST for {target_star} light curves...")
result  = lk.search_lightcurve(target_star, mission="TESS", exptime="short")
mission = "TESS"
if len(result) == 0:
    result, mission = lk.search_lightcurve(target_star, mission="Kepler", exptime="short"), "Kepler"
if len(result) == 0:
    result, mission = lk.search_lightcurve(target_star), "any"

print(f"Found {len(result)} sector(s) — mission: {mission}")
if len(result) == 0:
    raise RuntimeError(f"No light curves found for {target_star} on NASA MAST")

n_dl = min(3, len(result))
lc_coll = result[:n_dl].download_all()

from lightkurve import LightCurveCollection
lc = lc_coll.stitch() if isinstance(lc_coll, LightCurveCollection) else lc_coll
lc = lc.normalize().remove_outliers(sigma=5)
print(f"Light curve: {len(lc):,} points spanning "
      f"{lc.time.value[-1] - lc.time.value[0]:.1f} days")
lc_mission = mission

csv_path = "lc_raw.csv"
lc.to_pandas().to_csv(csv_path, index=False)
print(f"Saved raw light curve → {csv_path}")

fig, ax = plt.subplots(figsize=(12, 3))
ax.plot(lc.time.value, lc.flux.value, "k.", ms=0.8, alpha=0.35, rasterized=True)
ax.set_xlabel("Time (BTJD days)")
ax.set_ylabel("Normalized Flux")
ax.set_title(f"{target_planet} — Raw {mission} Light Curve ({len(lc):,} points)")
ax.set_ylim(
    float(lc.flux.value.mean()) - 5 * float(lc.flux.value.std()),
    float(lc.flux.value.mean()) + 5 * float(lc.flux.value.std()),
)
plt.tight_layout()
plt.savefig("lc_raw.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved plot → lc_raw.png")
```

If you run Steps 3-4 as separate scripts/processes, persist `lc` to disk
(`lc.write("lc.fits")` then `lc = lk.read("lc.fits")` in the next step), or
combine Steps 2-4 into a single script so `lc` stays a local variable.

---

## Step 3 — Phase-fold the light curve

**Inputs** (set at top of script):
- `lc` — the `LightCurve` from Step 2
- `orbital_period` — orbital period in days (from Step 1)
- `target_planet` — for plot titles

**Outputs:** `transit_depth`, `transit_duration` (days), `rp_rs`. Saves `lc_folded.png`.

**Critical rule:** use `lc.fold(period=orbital_period)` from lightkurve — do
not re-implement phase folding.

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# Inputs — carry `lc` from Step 2, set the rest from Step 1
# lc = <LightCurve from Step 2>
target_planet  = "HD 209458 b"
orbital_period = 3.52474       # days, from planets[i]["pl_orbper"]

print(f"Phase-folding {target_planet} at P = {orbital_period:.4f} days...")

folded = lc.fold(period=orbital_period)
binned = folded.bin(time_bin_size=0.004)
flux_arr = np.array(binned.flux.value, dtype=float)
time_arr = np.array(binned.time.value, dtype=float)

transit_depth    = float(1.0 - np.nanmin(flux_arr))
floor            = 1.0 - 0.5 * transit_depth
in_tr            = flux_arr < floor
transit_duration = float(np.sum(in_tr) * 0.004 * orbital_period) if np.any(in_tr) else float("nan")
rp_rs            = float(np.sqrt(max(transit_depth, 0.0)))

print(f"Transit depth:     {transit_depth*100:.4f}%")
print(f"Transit duration:  {transit_duration*24:.2f} h")
print(f"Rp/Rs estimate:    {rp_rs:.4f}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))
ax1.plot(np.array(folded.time.value), np.array(folded.flux.value),
         ".", ms=1.2, alpha=0.25, color="steelblue")
ax1.plot(time_arr, flux_arr, "r-", lw=1.8, label="Binned (0.4% phase)")
ax1.set_xlabel("Phase (days from transit center)")
ax1.set_ylabel("Normalized Flux")
ax1.set_title(f"{target_planet} — Phase-Folded Light Curve")
ax1.legend(fontsize=8)

zoom_half = max(3 * transit_duration, 0.05 * orbital_period) if not np.isnan(transit_duration) else 0.1 * orbital_period
mask = np.abs(time_arr) < zoom_half
if np.sum(mask) > 4:
    ax2.plot(time_arr[mask] * 24, flux_arr[mask], "r.-", lw=1.5, ms=4)
    ax2.set_xlabel("Hours from transit center")
    ax2.set_ylabel("Normalized Flux")
    ax2.set_title(f"Transit Zoom — depth={transit_depth*100:.3f}%, ~{transit_duration*24:.1f} h")
    ax2.axhline(1.0,                  color="gray",   ls="--", lw=0.8)
    ax2.axhline(1.0 - transit_depth,  color="orange", ls="--", lw=1.0,
                label=f"Depth = {transit_depth*100:.3f}%")
    ax2.legend(fontsize=8)
else:
    ax2.text(0.5, 0.5, "Insufficient data\nfor zoom",
             ha="center", va="center", transform=ax2.transAxes)

plt.tight_layout()
plt.savefig("lc_folded.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved plot → lc_folded.png")
```

---

## Step 4 — Transit summary card

**Inputs** (set at top of script):
- `lc` — the `LightCurve` from Step 2
- `target_planet`, `target_star` — names for labels
- `orbital_period` — from Step 1
- `transit_depth`, `transit_duration`, `rp_rs` — from Step 3
- `planet_data` — the full record from Step 1
- `lc_mission` — from Step 2 (e.g. "TESS", "Kepler")

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# Inputs — carry from Steps 1, 2, 3
# lc = <LightCurve from Step 2>
target_planet    = "HD 209458 b"
target_star      = "HD 209458"
orbital_period   = 3.52474
transit_depth    = 0.01478
transit_duration = 0.13         # days, from Step 3
rp_rs            = 0.1216
planet_data      = {}           # full row from Step 1
lc_mission       = "TESS"

folded = lc.fold(period=orbital_period)
binned = folded.bin(time_bin_size=0.003)
b_time = np.array(binned.time.value, dtype=float)
b_flux = np.array(binned.flux.value, dtype=float)

fig = plt.figure(figsize=(14, 5))
gs  = gridspec.GridSpec(1, 2, width_ratios=[1.8, 1.0], wspace=0.38)

ax = fig.add_subplot(gs[0])
ax.plot(np.array(folded.time.value) * 24, np.array(folded.flux.value),
        ".", ms=1.2, alpha=0.2, color="steelblue")
ax.plot(b_time * 24, b_flux, "r-", lw=2.0, zorder=5, label="Binned LC")
xlim_h = (4 * transit_duration * 24) if not np.isnan(transit_duration) else (0.08 * orbital_period * 24)
ax.set_xlim(-xlim_h, xlim_h)
ax.set_xlabel("Hours from Transit Center", fontsize=12)
ax.set_ylabel("Normalized Flux", fontsize=12)
ax.set_title(f"{target_planet} — Transit Light Curve", fontsize=13, fontweight="bold")
ax.axhline(1.0, color="gray", ls="--", lw=0.8)
if transit_depth > 0:
    ax.axhline(1.0 - transit_depth, color="orange", ls="--", lw=1.2,
               label=f"Depth = {transit_depth*100:.3f}%")
ax.legend(fontsize=9)

ax2 = fig.add_subplot(gs[1])
ax2.axis("off")
vmag_str  = f"{planet_data['sy_vmag']:.1f}"   if planet_data.get("sy_vmag") else "?"
teff_str  = f"{planet_data['st_teff']:.0f} K" if planet_data.get("st_teff") else "?"
rad_str   = f"{planet_data['pl_rade']:.2f} R⊕" if planet_data.get("pl_rade") else "?"
dur_str   = f"{transit_duration*24:.2f} h" if not np.isnan(transit_duration) else "?"
rp_str    = f"{rp_rs:.4f}"                 if not np.isnan(rp_rs)             else "?"
rows = [
    ("Planet",          target_planet),
    ("Host Star",       f"{target_star}  (V={vmag_str})"),
    ("Star T_eff",      teff_str),
    ("Orbital Period",  f"{orbital_period:.4f} days"),
    ("Transit Depth",   f"{transit_depth*100:.3f}%"),
    ("Duration (est.)", dur_str),
    ("Rp/Rs (est.)",    rp_str),
    ("Rp (archive)",    rad_str),
    ("Data source",     lc_mission),
]
ax2.set_title("Transit Parameters", fontsize=12, fontweight="bold", pad=10)
for i, (k, v) in enumerate(rows):
    y = 0.92 - i * 0.10
    ax2.text(0.03, y, f"{k}:", fontsize=10, fontweight="bold",
             transform=ax2.transAxes, va="top")
    ax2.text(0.44, y, str(v), fontsize=10, transform=ax2.transAxes, va="top")

plt.suptitle("Exoplanet Transit Explorer", fontsize=9, color="#888", y=0.01)
plt.savefig("transit_summary.png", dpi=150, bbox_inches="tight")
plt.close()
print("Summary saved → transit_summary.png")
```

---

## Notes

- First-run install of `lightkurve` and `astropy` is ~60s; cached afterwards.
- TESS short-cadence downloads can be 50–200 MB per sector. The script caps at 3 sectors.
- The NASA Exoplanet Archive TAP API requires no API key.
- For data sources with no live API, this skill ships a built-in fallback list of 12 well-known transiting exoplanets so the catalog is always available.
