---
name: amaro-datasets
description: Answer questions about Amaro Lab (UCSD) molecular dynamics datasets — SARS-CoV-2 nsp14 / nsp10 / RNA complexes, spike protein open and closed states, ACE2-RBD, HIV-1 Env trimer, and whole-virion influenza H1N1 structures. Use for questions about protein dynamics, RMSD, RMSF, flexibility, residue contacts, binding interfaces, glycans, zinc sites, active sites, atom and residue counts in these systems. Picks the right dataset from a catalog, asks before downloading, and caches under /tmp/amaro.
---

# Amaro Lab Datasets

## Never download without being told to

Reading the catalog is free. **Downloading is not, and you do not decide to do
it.** Before the first fetch of any dataset, say which dataset you need, how
many MB it is, and ask the user to confirm. Then stop and wait for their reply.

This holds even when the download looks small, and it holds when the user's
question clearly implies one — a question is not consent to spend their
bandwidth and disk. The full Amaro Lab collection runs to 7.9 TB and single
datasets reach 2.4 TB; the habit of fetching first is the thing that makes that
dangerous, not any one file's size.

If a question cannot be answered without data you have not been cleared to
fetch, say so and name the cost. That is a complete answer, not a failure.

Six published MD datasets from the Amaro Lab at UCSD, each small enough to
fetch on demand once cleared. The catalog beside this file (`catalog.json`) lists what each
one contains and, importantly, what it cannot answer.

## Step 1 — Read the catalog and pick a dataset

```python
import json, os
CATALOG = os.path.join(os.path.dirname(SKILL_PATH), "catalog.json")  # SKILL_PATH = this skill's folder
cat = json.load(open(CATALOG))
for d in cat["datasets"]:
    print(d["id"], "|", d["system"], "| dynamics:", d["has_dynamics"],
          "|", round(d["total_bytes"]/1e6), "MB")
```

Match the user's question to a dataset by its `system` and `answers` fields.
State which dataset you chose and why, in one line, before you fetch anything.

**Check `has_dynamics` before you promise an answer.** Three of these datasets
are a single structure, not a trajectory. If the user asks how something moves,
how flexible it is, or for an RMSD over time, and the best-matching dataset has
`has_dynamics: false`, say so plainly and offer the structural question you
*can* answer instead. Do not compute a time series from one frame, and do not
quietly switch to a different system than the one they asked about.

If the question needs a dataset that is not in the catalog, say which one it
would need and that it is not in this collection — the full Amaro Lab catalog
at <https://amarolab.ucsd.edu/data.php> runs to 7.9 TB and most of it is far
too large to fetch this way.

## Step 2 — Make sure the tools are installed

Run this before any analysis. It is a no-op once the packages are present.

```python
def ensure_amaro_deps():
    """MDAnalysis and its reader stack, installed only if missing."""
    import importlib.util, subprocess, sys
    missing = [p for p in ("MDAnalysis",) if importlib.util.find_spec(p) is None]
    if missing:
        print(f"Installing {', '.join(missing)} …", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user",
                        "--quiet", "--no-warn-script-location", *missing],
                       check=True)
    import MDAnalysis
    return MDAnalysis

mda = ensure_amaro_deps()
```

## Step 3 — Fetch the dataset (cached)

**Expect a TLS certificate error on the first request, and fix it with the
helper below — do not spend turns diagnosing it, and do not disable
verification.**

`amarolab.ucsd.edu` serves only its leaf certificate and omits the InCommon
intermediate, so Python, `curl` and `wget` all fail with "unable to get local
issuer certificate" while browsers paper over it. The certificate itself is
genuine. The fix is to fetch the 1.6 KB intermediate that the leaf's own
Authority Information Access extension points to and verify against it. This
is already known — there is nothing to investigate.

Cut and paste both helpers as-is. They cache under `/tmp/amaro/`, which is
pod-local and cleared on restart — never write these files to the persistent
volume, which has a small quota that one of these would fill.

```python
import json, os, gzip, shutil, ssl, subprocess, tarfile, urllib.request
from pathlib import Path

def amaro_ssl_context(cache_root="/tmp/amaro"):
    """A verifying SSL context that trusts this server's incomplete chain.

    Verification stays ON (CERT_REQUIRED). The bundle is built once and
    cached, so this costs one 1.6 KB download per pod.
    """
    import certifi
    ca_dir = Path(cache_root) / ".ca"
    ca_dir.mkdir(parents=True, exist_ok=True)
    bundle = ca_dir / "bundle.pem"
    if not bundle.exists():
        der = ca_dir / "incommon.der"
        urllib.request.urlretrieve(
            "http://crt.sectigo.com/InCommonRSAServerCA2.crt", der)
        pem = subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(der)],
                             capture_output=True, text=True, check=True).stdout
        bundle.write_text(Path(certifi.where()).read_text() + "\n" + pem)
    return ssl.create_default_context(cafile=str(bundle))

def amaro_urlretrieve(url, dest, ctx=None):
    """urlretrieve that works against this server's chain."""
    ctx = ctx or amaro_ssl_context()
    with urllib.request.urlopen(url, timeout=120, context=ctx) as r, \
         open(dest, "wb") as out:
        shutil.copyfileobj(r, out)
```

If you ever need `curl` here instead, pass the same bundle —
`curl --cacert /tmp/amaro/.ca/bundle.pem ...` — rather than `-k`.

```python
SIZE_LIMIT_BYTES = 1_073_741_824          # 1 GB -- the collection's own cut-off

def fetch_dataset(ds, cache_root="/tmp/amaro", confirmed=False):
    """Download + decompress a catalog dataset. Idempotent: a cached dataset
    is reused, so re-running costs nothing. Returns the dataset directory.

    Refuses to run unless the user has agreed to the download. Pass
    confirmed=True only after they have said yes to this specific dataset.
    """
    if "files" not in ds:
        raise RuntimeError(
            f"{ds.get('name', ds.get('id'))} is a reference-only entry, not a "
            f"fetchable dataset. It is listed so you can tell the user what "
            f"exists beyond this collection; point them at "
            f"https://amarolab.ucsd.edu/data.php.")
    if ds["total_bytes"] > SIZE_LIMIT_BYTES:
        raise RuntimeError(
            f"{ds['id']} is {ds['total_bytes']/1e9:.1f} GB, over this skill's "
            f"{SIZE_LIMIT_BYTES/1e9:.0f} GB limit. Tell the user the size and "
            f"let them decide how to obtain it.")
    out = Path(cache_root) / ds["id"]
    out.mkdir(parents=True, exist_ok=True)
    marker = out / ".complete"
    if marker.exists():
        # Already on disk: costs nothing, so no need to ask again.
        print(f"{ds['id']}: already cached at {out}")
        return out
    if not confirmed:
        raise RuntimeError(
            f"{ds['id']} is {ds['total_bytes']/1e6:.0f} MB and is not cached. "
            f"Tell the user the size and ask before downloading; call again "
            f"with confirmed=True once they agree.")

    total_mb = ds["total_bytes"] / 1e6
    print(f"{ds['id']}: fetching {total_mb:.0f} MB "
          f"({len(ds['files'])} file(s)) -> {out}", flush=True)

    ctx = amaro_ssl_context(cache_root)
    for f in ds["files"]:
        name = f["url"].split("/")[-1]
        dest = out / name
        if not dest.exists() or dest.stat().st_size != f["bytes"]:
            print(f"  downloading {name} ({f['bytes']/1e6:.0f} MB) …", flush=True)
            amaro_urlretrieve(f["url"], dest, ctx)
        got = dest.stat().st_size
        if got != f["bytes"]:
            raise RuntimeError(
                f"{name}: expected {f['bytes']} bytes, got {got} — "
                f"download incomplete, delete {out} and retry")
        # .gz single file -> decompress; .tar.gz -> extract
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            with tarfile.open(dest) as t:
                # filter="data" refuses absolute paths, ".." traversal and
                # special files. This archive comes off the internet, so it is
                # untrusted input; the filter is also the default from 3.14.
                try:
                    t.extractall(out, filter="data")
                except TypeError:            # Python < 3.12
                    t.extractall(out)
        elif name.endswith(".gz"):
            plain = out / name[:-3]
            if not plain.exists():
                with gzip.open(dest, "rb") as src, open(plain, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    marker.write_text("ok")
    on_disk = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{ds['id']}: ready at {out} ({on_disk/1e6:.0f} MB on disk)")
    return out
```

**Download size is not disk size.** The PSF/PDB bundles are text and compress
hard: `ace2-rbd` is a 23 MB download that becomes 184 MB extracted, an eight-
fold expansion. The DCD trajectories are binary and barely compress, so those
stay close to their download size. Report the on-disk figure the helper prints
rather than the catalog's `total_bytes` when telling the user what a fetch
cost them.

**A trajectory is useless without its topology.** Each dataset lists every file
it needs; always fetch the whole dataset, never a single file from it.

**A cached dataset costs nothing.** Check `/tmp/amaro/<id>/.complete` first; if
it is there, go straight to the analysis without asking.

**When the answer needs data this collection does not hold**, read the
dataset's `larger_alternatives`. Those entries record what the lab publishes
beyond the 1 GB cut-off — name, size and what it contains — so you can answer
precisely and without a download:

> This collection has only the spike *structures*. What you are asking needs a
> trajectory, and the lab does publish one: `TRAJECTORIES_spike_open_prot_glyc`,
> 33.1 GB, 6 replicas of protein + glycans. It is outside this skill's 1 GB
> limit, so it would have to be fetched another way.

That is the right answer. Do not substitute a different analysis and present it
as answering the question that was asked — if you offer one, say plainly that
it measures something else.

## Step 4 — Load and analyse

```python
import glob

def load_universe(path):
    """Build an MDAnalysis Universe from a fetched dataset directory."""
    tops = glob.glob(f"{path}/**/*.psf", recursive=True) + \
           glob.glob(f"{path}/**/*.pdb", recursive=True)
    trjs = sorted(glob.glob(f"{path}/**/*.dcd", recursive=True))
    if not tops:
        raise RuntimeError(f"no topology (.psf/.pdb) found under {path}")
    return mda.Universe(tops[0], *trjs) if trjs else mda.Universe(tops[0])

u = load_universe(fetch_dataset(ds))
print(f"{len(u.atoms)} atoms, {len(u.residues)} residues, "
      f"{len(u.trajectory)} frame(s)")
```

**Read the dataset's `topology` block before writing a selection.** These
files are not uniform: the apo `nsp14` PSF carries real segids and real
amino-acid resnames, while the two complexes have a blank segid column with
the chain label written into the resname field. On those, `protein`,
`backbone` and `segid N14` all return **zero atoms — silently, with no
error**, so an analysis built on them produces nothing or nonsense rather than
failing. Use the ready-made strings in `topology.select`:

```python
sel = ds["topology"]["select"]
ca = u.select_atoms(sel["ca"] if "ca" in sel else sel["nsp14_ca"])
print(f"{len(ca)} CA atoms selected")      # never proceed on an empty selection
```

Comparing the apo protein against a complex needs a *different* selection
string for each file — `segid N14` for one, `resname N14` for the other. The
resid numbering matches (2–526 in both), so per-residue comparison is valid
once each side is selected correctly.

Common analyses:

```python
# RMSD of the protein backbone over the trajectory
from MDAnalysis.analysis import rms
R = rms.RMSD(u, select="backbone").run()
times, rmsd = R.results.rmsd[:, 1], R.results.rmsd[:, 2]

# Per-residue flexibility (RMSF), after aligning to the average structure
from MDAnalysis.analysis import align, rms as _rms
align.AlignTraj(u, u, select="backbone", in_memory=True).run()
rmsf = _rms.RMSF(u.select_atoms("name CA")).run().results.rmsf

# Residues of chain A within 4 Å of chain B at the final frame
u.trajectory[-1]
iface = u.select_atoms("segid A and around 4.0 segid B").residues
```

Report the numbers you computed, and say how many frames they came from. A
value from a 3-replica concatenated trajectory is not a converged equilibrium
average — if the user's question implies one, say what you actually measured.

## What these datasets will not tell you

The nsp14 trajectories are **dry** — stripped of water and ions. Questions
about solvation, water-mediated hydrogen bonds, or ion binding cannot be
answered from them, and the absence of water is not evidence of its absence in
the simulation. Say so rather than computing something adjacent.

Timesteps and frame intervals are not published for these files, so frame
indices are reliable but wall-clock times are not. Report frames unless the
user confirms the timestep.
