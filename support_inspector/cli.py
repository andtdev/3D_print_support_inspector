#!/usr/bin/env python3
"""Find the parts of a sliced print that nothing holds up, and show them in a 3D viewer.

The inspector reads the G-code the slicer produced, because that is the only place where the supports
really are: painting an area or ticking "enable supports" does not mean a support ends up under it.
Every printed line of the model is cut into short pieces and each piece is checked against what lies
directly below it: the model's previous layer, or a support layer within the support gap. A piece with
nothing below it is reported, unless it is a short bridge held at both ends.

    support-inspector plate.gcode
    support-inspector project.gcode.3mf    (a sliced project exported from the slicer)
    support-inspector project.3mf          (not sliced yet: Bambu Studio or OrcaSlicer slices it first)

It prints a list of risk areas, writes NAME.support_report.html (the viewer) and exits with 1 when it
found any, so it can guard a build script.
"""
import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
import zipfile
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from . import __version__

HERE = os.path.dirname(os.path.abspath(__file__))
# Where the slicers that can slice a project from the command line usually are
SLICERS = [
    "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
    "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
    r"C:\Program Files\Bambu Studio\bambu-studio.exe",
    r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    "bambu-studio", "orca-slicer", "BambuStudio", "OrcaSlicer",
]


def default_slicer():
    """The first slicer found in its usual place or on the PATH, or None."""
    for s in SLICERS:
        if os.path.sep in s or "\\" in s:
            if os.path.exists(s):
                return s
        elif shutil.which(s):
            return shutil.which(s)
    return None

MODEL, SUPPORT, OTHER = 0, 1, 2      # what a printed line belongs to
OK, STEEP, HANGING, BRIDGE = 0, 1, 2, 3   # what the check says about a piece of a line
KIND = {STEEP: "steep", HANGING: "hanging", BRIDGE: "bridge"}

ARC_TOLERANCE = 0.02    # mm between an arc and the chords that stand in for it
BELOW_STEP = 0.1        # mm between the points that stand in for the lines below
Z_TOLERANCE = 0.03      # mm two layer heights may differ and still count as the same
CLOSED_PATH = 0.6       # mm between a loop's two ends: the slicer leaves a small gap at the seam
CLUSTER_XY, CLUSTER_Z = 1.0, 0.5   # mm: risky pieces closer than this form one area


def category(feature):
    """Whether a slicer feature is model, support or something that is neither."""
    f = feature.lower()
    if "support" in f:
        return SUPPORT
    if any(k in f for k in ("skirt", "brim", "tower", "custom", "ironing")):
        return OTHER
    return MODEL


def is_infill(feature):
    """Lines inside the part: they lie on the sparse infill by design, so they are not checked."""
    f = feature.lower()
    if f == "bridge infill":         # PrusaSlicer's bridges, over air as well as over the infill
        return False
    return "infill" in f or f == "fill" or "internal" in f or "floating vertical shell" in f


# --------------------------------------------------------------------------------------------- input

def find_gcode(path, plate, slicer, workdir):
    """The G-code to inspect: the file itself, the one inside a sliced 3MF, or a fresh slice."""
    if not os.path.isfile(path):
        sys.exit(f"{path}: no such file")
    if not zipfile.is_zipfile(path):
        return path
    name = f"Metadata/plate_{plate}.gcode"
    with zipfile.ZipFile(path) as z:
        if name in z.namelist():
            z.extract(name, workdir)
            return os.path.join(workdir, name)
    if not slicer or not (os.path.exists(slicer) or shutil.which(slicer)):
        sys.exit(f"{path} is not sliced, and no slicer was found to slice it: give Bambu Studio's or "
                 "OrcaSlicer's executable with --slicer, or export the sliced G-code and inspect that")
    print(f"slicing {os.path.basename(path)} ...", flush=True)
    done = subprocess.run([slicer, "--slice", str(plate), "--outputdir", workdir, path],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = os.path.join(workdir, f"plate_{plate}.gcode")
    if not os.path.exists(out):
        sys.exit(f"the slicer produced no G-code for plate {plate} (exit code {done.returncode})")
    return out


def parse_gcode(filename, default_height, default_width):
    """Every extruding move as a straight segment, with its layer, height, width, feature and path.

    Understands the comments of Bambu Studio ("; FEATURE:", "; Z_HEIGHT:") and those of PrusaSlicer,
    OrcaSlicer and Cura (";TYPE:", ";Z:", ";HEIGHT:", ";WIDTH:")."""
    X0, Y0, X1, Y1, SID = [], [], [], [], []
    states = []                      # (z, height, width, feature index, path) per run of segments
    features, feature_ix = [], {}
    x = y = z = 0.0
    z_comment = None
    height, width = default_height, default_width
    feat = None
    relative_xyz, relative_e, last_e = False, True, 0.0
    path = 0
    state_key, sid = None, -1
    extruding = False

    def segment(ax, ay, bx, by):
        nonlocal state_key, sid, extruding, path
        if not extruding:
            path += 1
            extruding = True
        key = (z if z_comment is None else z_comment, height, width, feat, path)
        if key != state_key:
            state_key = key
            states.append(key)
            sid = len(states) - 1
        X0.append(ax); Y0.append(ay); X1.append(bx); Y1.append(by); SID.append(sid)

    with open(filename, errors="replace") as f:
        for line in f:
            c = line[0]
            if c == "G":
                code = line[1:3]
                if code in ("1 ", "0 ", "2 ", "3 "):
                    nx, ny, nz, e, ci, cj = x, y, z, None, 0.0, 0.0
                    for w in line.split(";", 1)[0].split()[1:]:
                        k = w[0]
                        try:
                            v = float(w[1:])
                        except ValueError:
                            continue
                        if k == "X": nx = x + v if relative_xyz else v
                        elif k == "Y": ny = y + v if relative_xyz else v
                        elif k == "Z": nz = z + v if relative_xyz else v
                        elif k == "E": e = v
                        elif k == "I": ci = v
                        elif k == "J": cj = v
                    if e is not None and not relative_e:
                        e, last_e = e - last_e, e
                    if e is not None and e > 0 and feat is not None and (nx != x or ny != y or code[0] in "23"):
                        if code[0] in "23":
                            cx, cy = x + ci, y + cj
                            r = math.hypot(ci, cj)
                            a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
                            sweep = a1 - a0
                            if code[0] == "2":
                                sweep = sweep - 2 * math.pi if sweep >= 0 else sweep
                            else:
                                sweep = sweep + 2 * math.pi if sweep <= 0 else sweep
                            n = 1
                            if r > ARC_TOLERANCE:
                                n = max(1, min(360, math.ceil(abs(sweep) / (2 * math.acos(1 - ARC_TOLERANCE / r)))))
                            px, py = x, y
                            for i in range(1, n + 1):
                                a = a0 + sweep * i / n
                                qx, qy = (nx, ny) if i == n else (cx + r * math.cos(a), cy + r * math.sin(a))
                                segment(px, py, qx, qy)
                                px, py = qx, qy
                        else:
                            segment(x, y, nx, ny)
                    elif nx != x or ny != y or (e is not None and e < 0):
                        extruding = False
                    x, y, z = nx, ny, nz
                elif code == "90": relative_xyz = False
                elif code == "91": relative_xyz = True
                elif code == "92":
                    for w in line.split(";", 1)[0].split()[1:]:
                        if w[0] == "E":
                            last_e = float(w[1:] or 0)
            elif c == ";":
                if line.startswith("; FEATURE:") or line.startswith(";TYPE:"):
                    name = line.split(":", 1)[1].strip()
                    if name not in feature_ix:
                        feature_ix[name] = len(features)
                        features.append(name)
                    feat = feature_ix[name]      # a wall goes on as the same path when only its feature changes
                elif line.startswith("; Z_HEIGHT:") or line.startswith(";Z:"):
                    z_comment = float(line.split(":", 1)[1])
                    extruding = False
                elif line.startswith("; LAYER_HEIGHT:") or line.startswith(";HEIGHT:"):
                    height = float(line.split(":", 1)[1])
                elif line.startswith("; LINE_WIDTH:") or line.startswith(";WIDTH:"):
                    width = float(line.split(":", 1)[1])
            elif c == "M":
                if line.startswith("M83"): relative_e = True
                elif line.startswith("M82"): relative_e = False

    if not SID:
        sys.exit("no printed lines found: the G-code has no feature comments (; FEATURE: or ;TYPE:)")
    st = np.array(states, dtype=float)
    sid = np.array(SID, dtype=np.int64)
    return {
        "p0": np.column_stack((X0, Y0)), "p1": np.column_stack((X1, Y1)),
        "z": st[sid, 0], "h": st[sid, 1], "w": st[sid, 2],
        "feat": st[sid, 3].astype(int), "path": st[sid, 4].astype(np.int64),
        "features": features,
    }


# ------------------------------------------------------------------------------------------ analysis

def sample(p0, p1, step):
    """Cut segments into pieces no longer than step: (owner segment, piece number, pieces in the owner)."""
    length = np.hypot(*(p1 - p0).T)
    n = np.maximum(1, np.ceil(length / step)).astype(np.int64)
    owner = np.repeat(np.arange(len(n)), n)
    k = np.arange(len(owner)) - np.repeat(np.cumsum(n) - n, n)
    return owner, k, n[owner], (length / n)[owner]


def nearest(trees, pts, limit):
    """Distance from each point to the nearest point of any of the trees (inf beyond the limit), and that point."""
    d = np.full(len(pts), np.inf)
    q = np.full((len(pts), 2), np.nan)
    for t in trees:
        dt, i = t.query(pts, distance_upper_bound=limit)
        closer = dt < d
        d[closer] = dt[closer]
        q[closer] = t.data[i[closer]]
    return d, q


def inspect(g, a):
    """Check every piece of every checked line. Returns the risky pieces as arrays."""
    cat = np.array([category(f) for f in g["features"]])[g["feat"]]
    checked_feature = np.array([category(f) == MODEL and (a.check_infill or not is_infill(f))
                                for f in g["features"]])[g["feat"]]
    zkey = np.round(g["z"] * 1000).astype(np.int64)
    order = np.argsort(zkey, kind="stable")
    keys, starts = np.unique(zkey[order], return_index=True)
    layers = {k: order[s:e] for k, s, e in zip(keys, starts, list(starts[1:]) + [len(order)])}

    infill = np.array([category(f) == MODEL and is_infill(f) for f in g["features"]])[g["feat"]]
    model_keys = np.unique(zkey[cat == MODEL])
    trees = {}      # (layer key, kind) -> tree of the points standing in for that layer's lines

    def tree(key, kind):
        if (key, kind) not in trees:
            idx = layers[key]
            idx = idx[{"model": cat[idx] != SUPPORT, "support": cat[idx] == SUPPORT, "infill": infill[idx]}[kind]]
            t = None
            if len(idx):
                owner, k, n, _ = sample(g["p0"][idx], g["p1"][idx], BELOW_STEP)
                p0, p1 = g["p0"][idx][owner], g["p1"][idx][owner]
                t = cKDTree(p0 + (p1 - p0) * ((k + 0.5) / n)[:, None])
            trees[(key, kind)] = t
        return trees[(key, kind)]

    out = {k: [] for k in ("a", "b", "z", "status", "length")}
    first_top = None
    for key in keys:
        idx = layers[key]
        idx = idx[checked_feature[idx]]
        if not len(idx):
            continue
        z = key / 1000
        h = float(np.median(g["h"][idx]))
        # The layer rests on the model's layer before it. The lines' own height does not say where
        # that is when the slicer prints thick bridges, or when the G-code gives no height at all.
        before = model_keys[model_keys < key - round(Z_TOLERANCE * 1000)]
        if len(before) and z - before[-1] / 1000 <= max(float(g["h"][idx].max()), 0.6) + Z_TOLERANCE:
            h = z - before[-1] / 1000
        bottom = z - h
        if first_top is None:
            first_top = z
        if bottom <= Z_TOLERANCE or z <= first_top + Z_TOLERANCE:     # the first layer lies on the bed
            continue
        for old in [k for k in trees if k[0] < key - 5000]:
            del trees[old]
        lo, hi = round((bottom - Z_TOLERANCE) * 1000), round((bottom + Z_TOLERANCE) * 1000)
        model_below = [t for k in keys[(keys >= lo) & (keys <= hi)] if (t := tree(k, "model"))]
        infill_below = [] if a.check_infill else [t for k in keys[(keys >= lo) & (keys <= hi)] if (t := tree(k, "infill"))]
        lo = round((bottom - a.support_gap) * 1000)
        support_below = [t for k in keys[(keys >= lo) & (keys <= hi)] if (t := tree(k, "support"))]

        owner, k, n, piece = sample(g["p0"][idx], g["p1"][idx], a.resolution)
        p0, p1 = g["p0"][idx][owner], g["p1"][idx][owner]
        d = p1 - p0
        pa, pb = p0 + d * (k / n)[:, None], p0 + d * ((k + 1) / n)[:, None]
        mid = (pa + pb) / 2
        w = g["w"][idx][owner]
        d_model, q_model = nearest(model_below, mid, 2.0)
        d_support = nearest(support_below, mid, a.support_reach + 0.5)[0]

        steep_at = h * math.tan(math.radians(a.max_overhang_angle)) + 0.03
        status = np.where(d_model >= a.hang_fraction * w, HANGING, np.where(d_model > steep_at, STEEP, OK))
        # A line that lies between two lines of the layer below is as far from both as one that leans out
        # over an edge. Half a line width further out, the first finds the second line; the other nothing.
        steep = np.flatnonzero(status == STEEP)
        if len(steep):
            out_ = mid[steep] + (mid[steep] - q_model[steep]) / d_model[steep, None] * (w[steep, None] / 2)
            beyond = nearest(model_below, out_, 2.0)[0]
            status[steep[beyond < d_model[steep] + w[steep] / 2 - 0.05]] = OK
        status[d_support <= a.support_reach] = OK

        if (status == HANGING).any():
            on_infill = nearest(infill_below, mid, 1.0)[0] <= a.hang_fraction * w
            path = g["path"][idx][owner]
            bridges(status, piece, path, pa, pb, w, on_infill, a)
            # Cura fills a bridge with lines that end on the walls spanning the gap, not on the layer
            # below: what still hangs gets a second look, with the layer's own held lines as anchors.
            if (status == HANGING).any() and (status == OK).any():
                bridges(status, piece, path, pa, pb, w, on_infill, a, cKDTree(mid[status == OK]))
        risky = status != OK
        if risky.any():
            out["a"].append(pa[risky]); out["b"].append(pb[risky])
            out["z"].append(np.full(risky.sum(), z)); out["status"].append(status[risky])
            out["length"].append(piece[risky])
    if not out["a"]:
        return {"a": np.zeros((0, 2)), "b": np.zeros((0, 2)), "z": np.zeros(0),
                "status": np.zeros(0, dtype=int), "length": np.zeros(0)}
    return {k: np.concatenate(v) for k, v in out.items()}


def bridges(status, piece, path, pa, pb, w, on_infill, a, anchors=None):
    """Sort out the runs of hanging pieces along each printed path, in place.

    A run held at both ends is a bridge: fine up to --max-bridge, a risk of its own kind beyond, and
    fine at any length when an end rests on the infill, because then it is the skin over the infill
    inside the part. A run held at one end only may stick out by a line width or two. Everything else
    stays hanging.

    With anchors, a tree of the layer's held pieces, a run that reaches the end of its path is held
    there when the end lies against one of them."""
    hang = status == HANGING
    n = len(status)
    new_path = np.r_[True, path[1:] != path[:-1]]
    edge = np.r_[True, (hang[1:] != hang[:-1]) | new_path[1:]]
    starts = np.flatnonzero(edge)
    ends = np.r_[starts[1:], n]
    cum = np.r_[0, np.cumsum(piece)]
    path_start = np.flatnonzero(new_path)
    path_end = np.r_[path_start[1:], n]
    first_of = dict(zip(path[path_start].tolist(), path_start.tolist()))
    last_of = dict(zip(path[path_start].tolist(), path_end.tolist()))

    runs = [(int(s), int(e)) for s, e in zip(starts, ends) if hang[s]]
    done = set()
    for s, e in runs:
        if (s, e) in done:
            continue
        p = int(path[s])
        ps, pe = first_of[p], last_of[p]
        closed = np.hypot(*(pa[ps] - pb[pe - 1])) <= CLOSED_PATH
        parts = [(s, e)]
        held_start, held_end = s > ps, e < pe
        before, after = s - 1, e          # the pieces that hold the run's ends
        if closed and not (s == ps and e == pe):
            if s == ps:                      # the run wraps round the loop's seam
                if hang[pe - 1]:
                    other = next(r for r in runs if r[1] == pe)
                    parts.append(other); done.add(other)
                    before = other[0] - 1
                else:
                    before = pe - 1
                held_start = True
            elif e == pe:
                if hang[ps]:
                    other = next(r for r in runs if r[0] == ps)
                    parts.append(other); done.add(other)
                    after = other[1]
                else:
                    after = ps
                held_end = True
        length = sum(cum[e2] - cum[s2] for s2, e2 in parts)
        rests = (held_start and on_infill[before]) or (held_end and on_infill[after])
        if anchors is not None:
            held_start = held_start or anchors.query(pa[s])[0] <= w[s]
            held_end = held_end or anchors.query(pb[e - 1])[0] <= w[s]
        if held_start and held_end:
            new = OK if length <= a.max_bridge or rests else BRIDGE
        elif held_start or held_end:
            new = OK if length <= 2 * float(w[s]) else HANGING
        else:
            new = HANGING
        for s2, e2 in parts:
            status[s2:e2] = new


def regions(risk, a):
    """Group the risky pieces that touch into areas; drop the areas too small to matter."""
    n = len(risk["z"])
    if not n:
        return [], np.zeros(0, dtype=int)
    mid = (risk["a"] + risk["b"]) / 2
    cells = np.column_stack((np.floor(mid / CLUSTER_XY), np.floor(risk["z"] / CLUSTER_Z))).astype(np.int64)
    uniq, inverse = np.unique(cells, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    index = {tuple(c): i for i, c in enumerate(uniq.tolist())}
    parent = list(range(len(uniq)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    near = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) if (dx, dy, dz) > (0, 0, 0)]
    for c, i in index.items():
        for dx, dy, dz in near:
            j = index.get((c[0] + dx, c[1] + dy, c[2] + dz))
            if j is not None:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri
    root = np.array([find(i) for i in range(len(uniq))])[inverse]

    found = []
    for r in np.unique(root):
        m = root == r
        by_kind = {KIND[s]: float(risk["length"][m & (risk["status"] == s)].sum()) for s in KIND}
        total = sum(by_kind.values())
        if total < a.min_length:
            continue
        kind = "hanging" if by_kind["hanging"] >= a.min_length else max(by_kind, key=by_kind.get)
        pts = np.vstack((risk["a"][m], risk["b"][m]))
        zs = risk["z"][m]
        if kind == "steep" and zs.max() - zs.min() < a.min_steep_height - 1e-6:
            continue        # a rounded edge or the step above the first layer: steep, but only for a layer or two
        found.append({
            "kind": kind, "length": round(total, 1),
            "hanging": round(by_kind["hanging"], 1), "bridge": round(by_kind["bridge"], 1),
            "steep": round(by_kind["steep"], 1),
            "z": [round(float(zs.min()), 2), round(float(zs.max()), 2)],
            "min": [round(float(v), 2) for v in pts.min(axis=0)],
            "max": [round(float(v), 2) for v in pts.max(axis=0)],
            "center": [round(float(v), 2) for v in mid[m].mean(axis=0)] + [round(float(zs.mean()), 2)],
            "_mask": m,
        })
    rank = {"hanging": 0, "bridge": 1, "steep": 2}
    found.sort(key=lambda r: (rank[r["kind"]], -r["length"]))
    region_of = np.full(n, -1)
    for i, r in enumerate(found):
        region_of[r.pop("_mask")] = i
        r["id"] = i + 1
    return found, region_of


# -------------------------------------------------------------------------------------------- viewer

def pack(a, b, z, scale):
    """Segments as 16-bit integers (x0, y0, x1, y1, z), base64 encoded."""
    q = np.column_stack((a, b, z)) / scale
    return base64.b64encode(np.clip(np.round(q), 0, 65535).astype("<u2").tobytes()).decode()


def write_viewer(path, g, risk, region_of, found, a, source):
    cat = np.array([category(f) for f in g["features"]])[g["feat"]]
    shell = np.array([category(f) == MODEL and not is_infill(f) for f in g["features"]])[g["feat"]]
    if a.viewer_infill:
        shell = cat == MODEL
    origin = np.minimum(g["p0"].min(axis=0), g["p1"].min(axis=0))
    extent = max(float((np.maximum(g["p0"].max(axis=0), g["p1"].max(axis=0)) - origin).max()), float(g["z"].max()))
    scale = max(0.01, extent / 65000)
    layers = []
    for name, m in (("model", shell), ("support", cat == SUPPORT), ("other", cat == OTHER)):
        layers.append({"name": name, "count": int(m.sum()), "width": float(np.median(g["w"][m])) if m.any() else 0.4,
                       "data": pack(g["p0"][m] - origin, g["p1"][m] - origin, g["z"][m], scale)})
    keep = region_of >= 0
    for s, name in KIND.items():
        m = keep & (risk["status"] == s)
        layers.append({"name": name, "count": int(m.sum()), "width": 0.45,
                       "data": pack(risk["a"][m] - origin, risk["b"][m] - origin, risk["z"][m], scale)})
    data = {
        "source": os.path.basename(source), "source_path": os.path.abspath(source), "origin": origin.tolist(), "scale": scale,
        "zmax": float(g["z"].max()), "layer_height": float(np.median(g["h"])),
        "size": (np.maximum(g["p0"].max(axis=0), g["p1"].max(axis=0)) - origin).tolist(),
        "layers": layers, "regions": found,
        "settings": {k: getattr(a, k) for k in ("max_overhang_angle", "max_bridge", "support_gap",
                                                "support_reach", "min_length", "hang_fraction")},
    }
    with open(os.path.join(HERE, "viewer_template.html")) as f:
        html = f.read()
    with open(path, "w") as f:
        f.write(html.replace("/*DATA*/null", json.dumps(data)))


# ---------------------------------------------------------------------------------------------- main

def options():
    """The command line's options."""
    p = argparse.ArgumentParser(prog="support-inspector", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("file", help="G-code, a sliced .gcode.3mf, or a project .3mf to slice first")
    p.add_argument("--max-overhang-angle", type=float, default=45,
                   help="degrees from vertical a wall may lean out over the layer below before it counts as steep")
    p.add_argument("--max-bridge", type=float, default=5,
                   help="mm a line may span through the air when both its ends are held")
    p.add_argument("--support-gap", type=float, default=0.35,
                   help="mm a support's top may lie below a line and still hold it (the slicer's top z distance, with some slack)")
    p.add_argument("--support-reach", type=float, default=0.6,
                   help="mm a line may lie beside the nearest support line and still be held by it")
    p.add_argument("--hang-fraction", type=float, default=0.8,
                   help="a line hangs when it lies this fraction of its width, or more, beside the nearest line below")
    p.add_argument("--min-length", type=float, default=3,
                   help="mm of risky line an area needs to be reported")
    p.add_argument("--min-steep-height", type=float, default=0.6,
                   help="mm of height a steep overhang needs to be reported")
    p.add_argument("--resolution", type=float, default=0.2, help="mm, the length of the pieces the lines are checked in")
    p.add_argument("--check-infill", action="store_true", help="check the infill too, not only walls, surfaces and bridges")
    p.add_argument("--ignore-steep", action="store_true", help="do not report steep overhangs, only hanging lines and long bridges")
    p.add_argument("--layer-height", type=float, default=0.2, help="mm, when the G-code does not say")
    p.add_argument("--line-width", type=float, default=0.42, help="mm, when the G-code does not say")
    p.add_argument("--plate", type=int, default=1, help="plate of a 3MF to inspect")
    p.add_argument("--slicer", default=default_slicer(),
                   help="Bambu Studio's or OrcaSlicer's executable, to slice a project that is not sliced")
    p.add_argument("--version", action="version", version=f"support-inspector {__version__}")
    p.add_argument("-o", "--output", help="the viewer's HTML file (default: next to the input)")
    p.add_argument("--json", help="also write the list of areas to this file")
    p.add_argument("--viewer-infill", action="store_true", help="draw the infill in the viewer too (a bigger file)")
    p.add_argument("--no-open", action="store_true", help="do not open the viewer")
    p.add_argument("--no-viewer", action="store_true", help="only print the list")
    return p


def analyse(a):
    """Read the file and check it: the printed lines, the risky pieces, the area of each, the areas."""
    with tempfile.TemporaryDirectory() as work:
        gcode = find_gcode(a.file, a.plate, a.slicer, work)
        g = parse_gcode(gcode, a.layer_height, a.line_width)
    risk = inspect(g, a)
    if a.ignore_steep:
        risk = {k: v[risk["status"] != STEEP] for k, v in risk.items()}
    found, region_of = regions(risk, a)
    return g, risk, region_of, found


def main(argv=None):
    a = options().parse_args(argv)
    g, risk, region_of, found = analyse(a)

    print(f"{len(g['z'])} printed moves, {len(np.unique(np.round(g['z'], 3)))} layers")
    if found:
        print(f"{len(found)} risk areas (x, y on the plate, in mm):")
        for r in found:
            c = r["center"]
            print(f"  {r['id']:3d}  {r['kind']:8s} {r['length']:7.1f} mm of line   z {r['z'][0]:.2f} to {r['z'][1]:.2f}"
                  f"   at x {c[0]:.1f}, y {c[1]:.1f}   {r['max'][0] - r['min'][0]:.1f} x {r['max'][1] - r['min'][1]:.1f} mm")
    else:
        print("no risk areas: everything checked rests on the model or on a support")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"file": a.file, "regions": found}, f, indent=1)
    if not a.no_viewer:
        out = a.output or os.path.splitext(a.file)[0] + ".support_report.html"
        write_viewer(out, g, risk, region_of, found, a, a.file)
        print(f"viewer: {out}")
        if not a.no_open:
            webbrowser.open(Path(out).resolve().as_uri())
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
