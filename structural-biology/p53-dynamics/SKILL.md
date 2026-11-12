---
name: p53-dynamics
description: Answer questions about the Amaro Lab full-length p53 tetramer Anton simulations — wild type against the G245S and Y220C cancer mutants, three replicas each, 7.5 microseconds, DNA-bound. Use for p53 dynamics, DNA-binding domain flexibility, RMSD, RMSF, mutation effects, tetramer motion, zinc sites, protein-DNA contacts, conformational comparison. Reads individual frames from the server with HTTP range requests, so a 10 GB trajectory is queried by moving tens of MB. Never downloads the 68 GB archive.
---

# Full-length p53 tetramer — Anton simulations

Nine trajectories: **wild type**, **G245S** and **Y220C** (two hotspot cancer
mutations), three replicas each, 7.5 µs per replica at 240 ps per frame, with
the DNA-binding domains aligned and solvent stripped.

## The one thing that makes this dataset different

**Every file is individually addressable and the server honours HTTP range
requests.** A trajectory is 10 GB, but you never download one. You read the
frames you need — a few hundred kilobytes each — straight out of the remote
file.

Work this way and a question costs tens of MB and about a minute:

| What you ask for | Bytes moved |
| --- | --- |
| Frame and atom counts | already in `catalog.json`, zero |
| 200 frames spread over the full 7.5 µs | ~66 MB |
| One replica in full | 10,245 MB — don't |

**Never download `fl_p53_Anton.tar.gz` (68 GB), and never fetch a whole
trajectory.** Both are in the catalogue only so you can recognise and avoid
them. `p53_fetch_frames` below enforces this; use it rather than writing your
own download.

## Step 1 — Read the catalogue

```python
import json
from pathlib import Path

def p53_catalog():
    """Load catalog.json from wherever this skill is installed."""
    roots = [Path.home() / ".deepagents/agent/skills/p53-dynamics",
             Path.cwd() / "private_skills/p53-dynamics",
             Path.cwd() / "p53-dynamics",
             Path.cwd()]
    for r in roots:
        if (r / "catalog.json").is_file():
            return json.loads((r / "catalog.json").read_text())
    for base in (Path.home() / ".deepagents/agent/skills", Path.cwd()):
        hits = sorted(base.glob("**/p53-dynamics/catalog.json"))
        if hits:
            return json.loads(hits[0].read_text())
    raise RuntimeError("catalog.json not found. Looked in: "
                       + ", ".join(str(r) for r in roots))

CAT = p53_catalog()
```

**Do not rewrite this to use `__file__`.** In a script you generate, `__file__`
is *your script's* directory, not the skill's, so the catalogue is not beside
it and the read fails. The helper above looks where the skill actually lives.
If you already know the absolute path of this `SKILL.md`, the catalogue sits
next to it and reading that path directly is also correct.

The catalogue holds every URL, frame count, atom count and byte offset you
need, all measured — so answer "how many frames / atoms / replicas" from it
without touching the network.

## Step 2 — Dependencies and the TLS fix, in one go

The server sends an incomplete certificate chain: it omits the InCommon
intermediate, so Python rejects it while browsers paper over it. The helper
repairs this by **adding** the missing intermediate to the trust store.
Certificate verification stays on. Do not disable verification, and do not
spend turns diagnosing the error — paste this and move on.

```python
import ssl, subprocess, sys, urllib.request
from pathlib import Path

CACHE = Path("/tmp/p53")            # pod-local scratch, cleared on restart

def ensure_p53_deps():
    """MDAnalysis, installed only if missing. Returns the module."""
    import importlib.util
    if importlib.util.find_spec("MDAnalysis") is None:
        print("Installing MDAnalysis …", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user",
                        "--quiet", "MDAnalysis"], check=True)
    import MDAnalysis
    return MDAnalysis

def p53_ssl_context():
    """A verifying context that also trusts this server's missing intermediate."""
    import certifi
    CACHE.mkdir(parents=True, exist_ok=True)
    bundle = CACHE / "ca_bundle.pem"
    if not bundle.exists():
        der = CACHE / "incommon.crt"
        urllib.request.urlretrieve(
            "http://crt.sectigo.com/InCommonRSAServerCA2.crt", der)
        pem = subprocess.run(["openssl", "x509", "-inform", "DER", "-in", str(der)],
                             capture_output=True, text=True, check=True).stdout
        bundle.write_text(Path(certifi.where()).read_text() + "\n" + pem)
    ctx = ssl.create_default_context(cafile=str(bundle))
    ctx.verify_mode = ssl.CERT_REQUIRED          # stays on, deliberately
    return ctx

mda = ensure_p53_deps()
SSL = p53_ssl_context()
```

## Step 3 — The topology (small, fetched once)

Each condition has its own PSF of about 2.6 MB. Fetch it normally; it is
cached after the first call.

```python
def p53_topology(cond):
    """Local path to this condition's PSF. cond is a dict from CAT['conditions']."""
    url = cond["topology"]["psf_url"]
    out = CACHE / cond["id"] / Path(url).name
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        with urllib.request.urlopen(url, timeout=300, context=SSL) as r, \
             open(out, "wb") as f:
            f.write(r.read())
    return out
```

Use the **PSF**, not the `.prmtop`. The PSF carries real segment names and
corrected residue numbers, which every selection below depends on.

## Step 4 — Frames, by range request

This is the heart of the skill. It reads chosen frames out of the remote DCD
and writes them to a small local DCD that MDAnalysis opens like any other.

```python
import struct

FRAME_BUDGET = 400          # a normal question's worth
FRAME_CEILING = 2000        # refuse past this unless told to proceed

def p53_fetch_frames(rep, start=0, stop=None, step=None, confirmed=False):
    """Range-read frames from a remote DCD into a small local DCD.

    rep is a replica dict from the catalogue. Returns (path, frame_indices).
    """
    stop = rep["frames"] if stop is None else min(stop, rep["frames"])
    if step is None:                      # default: spread FRAME_BUDGET over the range
        step = max(1, (stop - start) // FRAME_BUDGET)
    idx = list(range(start, stop, step))
    if len(idx) > FRAME_CEILING and not confirmed:
        raise RuntimeError(
            f"{len(idx)} frames is {len(idx)*rep['bytes_per_frame']/1e6:.0f} MB. "
            f"Tell the user the cost and let them decide; pass confirmed=True "
            f"only after they agree. A larger step answers most questions.")

    out = CACHE / rep["id"] / f"{rep['id']}_{start}_{stop}_{step}.dcd"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out, idx                   # cached: re-asking costs nothing

    def _range(a, b):
        rq = urllib.request.Request(rep["url"], headers={"Range": f"bytes={a}-{b}"})
        with urllib.request.urlopen(rq, timeout=300, context=SSL) as r:
            if r.status != 206:
                raise RuntimeError(f"expected 206, got {r.status} — stopping "
                                   f"rather than risk a whole-file download")
            return r.read()

    hdr = bytearray(_range(0, rep["header_bytes"] - 1))
    struct.pack_into("<i", hdr, 8, len(idx))          # NSET = frames we kept
    bpf = rep["bytes_per_frame"]
    tmp = out.with_suffix(".part")
    with open(tmp, "wb") as f:
        f.write(hdr)
        for n, k in enumerate(idx):
            off = rep["header_bytes"] + k * bpf
            blk = _range(off, off + bpf - 1)
            if len(blk) != bpf:
                raise RuntimeError(f"frame {k}: got {len(blk)} bytes, expected {bpf}")
            f.write(blk)
            if n and n % 100 == 0:
                print(f"  {n}/{len(idx)} frames", flush=True)
    tmp.rename(out)                                   # only a complete file is cached
    print(f"{len(idx)} frames, {len(idx)*bpf/1e6:.1f} MB moved "
          f"(the replica is {rep['bytes']/1e9:.1f} GB)")
    return out, idx
```

About 60 ms per frame, so 200 frames takes roughly a dozen seconds. Report the
MB moved when you tell the user what you did — it is the interesting part.

## Step 5 — Open it

```python
cond = next(c for c in CAT["conditions"] if c["id"] == "wt")
rep  = cond["replicas"][0]
dcd, frames = p53_fetch_frames(rep, 0, rep["frames"])     # 400 frames over 7.5 µs
u = mda.Universe(str(p53_topology(cond)), str(dcd))
```

Frame *i* of this subset is frame `frames[i]` of the original, at
`frames[i] * 240` ps. Say the real simulation time, not the subset index.

## Selections — verified, with three traps

Checked against the wild-type PSF with MDAnalysis 2.11.0. **Cut and paste
these; do not invent variants.** Always print the atom count and stop if it is
zero.

```python
ca_all   = u.select_atoms("name CA")                               # 1572
mon1     = u.select_atoms("segid MON1")                            # 6033 atoms, 393 res
dbd      = u.select_atoms("segid MON1 and name CA and resid 94:292")   # 199
dna      = u.select_atoms("segid DNA")                             # 3177 atoms, 100 res
zincs    = u.select_atoms("segid ZN1 ZN2 ZN3 ZN4")                 # 4
site245  = u.select_atoms("segid MON1 and resid 245")
```

Segments are `MON1`–`MON4` (the four monomers, 393 residues each), `DNA` (the
p21 response element), and `ZN1`–`ZN4` (one zinc each).

**Trap 1 — `protein` silently drops the residues these questions are about.**
It returns 23,944 atoms / 1,556 residues and omits 16: the ZAFF
zinc-coordinating residues, resnames `CY2` and `HE1`, four per monomer. They
sit in the DNA-binding domain beside the mutation sites. Select by `segid`
instead. `backbone` has the same gap for the same reason.

**Trap 2 — `resname ZN` returns zero atoms.** The zinc resname is `ZN2` while
the segids are `ZN1`–`ZN4`. Select the zincs by segid.

**Trap 3 — atom counts differ between conditions** (27,313 / 27,329 / 27,273),
because the mutations change atom composition. Never compare by atom index
across conditions. Compare by residue number, which is aligned: residue 245 is
residue 245 in all three.

## Comparing conditions

The dataset is built for this, and the comparison is the point of it: three
conditions × three replicas is a real design, so **use all three replicas per
condition and report the spread between them.** A difference smaller than the
replica-to-replica spread is not a result.

```python
from MDAnalysis.analysis import rms
import numpy as np

def dbd_rmsf(cond, rep, n_frames=200):
    dcd, _ = p53_fetch_frames(rep, 0, rep["frames"],
                              step=max(1, rep["frames"] // n_frames))
    u = mda.Universe(str(p53_topology(cond)), str(dcd))
    sel = u.select_atoms("segid MON1 and name CA and resid 94:292")
    if len(sel) == 0:
        raise RuntimeError("empty selection — check the segid names")
    return rms.RMSF(sel).run().results.rmsf       # one value per residue

for cond in CAT["conditions"]:
    per_rep = [dbd_rmsf(cond, r) for r in cond["replicas"]]
    m = np.mean(per_rep, axis=0)
    print(f"{cond['label']:<22} mean DBD RMSF {m.mean():.2f} Å "
          f"(replica spread {np.std([p.mean() for p in per_rep]):.2f})")
```

Work through the replicas one after another, as above. Do not spread them
across parallel workers — the server is a shared resource and the requests
rate-limit each other.

**Budget for a nine-replica comparison:** 100–200 frames per replica is enough
for RMSF and RMSD to settle, which is 300–600 MB and two to four minutes in
total. Say that total to the user before starting, and say it again afterwards
against the 92 GB the nine replicas hold — that contrast is the result as much
as the numbers are.

## What the lab already computed

`catalog.json` lists published derived products under
`derived_products_published_by_the_lab`: nine last-frame structures and
eighteen PCA extreme structures (PC1/PC2 minima and maxima per condition).
These are small PDBs. When a question is about the *extremes* of a motion or
the *final* state, fetch one of those rather than reading frames.

## Reporting

Give the simulation time, not frame indices: "over the last 2 µs", not "frames
25,000–31,250". Name the condition by what it is — "the G245S mutant" — and
say how many replicas are behind each number. When a comparison is close, say
so against the replica spread rather than quoting more decimal places. And
state what the answer cost: "read 198 MB out of 92 GB of trajectory" is the
sentence that shows the method working.
