"""Read-only proof of exact weapon-art bridges between female job ACT spaces.

This establishes pixel correspondences, not anatomical hilt landmarks or live
acceptance. It never synthesizes missing pixels/frames or modifies client data.
Only the actual held cell (32 + direction, frame 0) is compared. Transparent
padding is retained in each affine witness; alpha-zero RGB is visually inert.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from audit_dual_weapon_type_coverage import Corpus
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr

ROOT = Path(__file__).resolve().parents[1]
ASSASSIN = "data/sprite/인간족/어세신/어세신_여_"
IDENTITY = (1., 0., 0., 1., 0., 0.)


def compose(a, b):
    """a(b(point)), affine tuple a,b,c,d,tx,ty."""
    return (a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3],
            a[2]*b[0]+a[3]*b[2], a[2]*b[1]+a[3]*b[3],
            a[0]*b[4]+a[1]*b[5]+a[4], a[2]*b[4]+a[3]*b[5]+a[5])


def inverse(a):
    det = a[0]*a[3]-a[1]*a[2]
    r = (a[3]/det, -a[1]/det, -a[2]/det, a[0]/det, 0., 0.)
    return (*r[:4], -r[0]*a[4]-r[1]*a[5], -r[2]*a[4]-r[3]*a[5])


def point(a, p):
    return [a[0]*p[0]+a[1]*p[1]+a[4], a[2]*p[0]+a[3]*p[1]+a[5]]


def rounded(a):
    return tuple(round(v, 7) for v in a)


def native_canvas_to_job(layer, width, height):
    """Native continuous pixel centers before common raster far-edge +1.

    Canvas boundary coordinates: first pixel center (0.5, 0.5). Actual loader
    uses ceil(imageDimension/2), including odd dimensions. Native ACT rotation
    is about the image center; source offsets are not themselves rotated.
    """
    x = (layer.x-(width+1)//2+width/2)*layer.scale_x
    y = (layer.y-(height+1)//2+height/2)*layer.scale_y
    co, si = math.cos(math.radians(layer.rotation)), math.sin(math.radians(layer.rotation))
    mx = -1 if layer.mirror else 1
    a = (co*layer.scale_x*mx, -si*layer.scale_y,
         si*layer.scale_x*mx, co*layer.scale_y, 0., 0.)
    return (*a[:4], x-a[0]*width/2-a[1]*height/2,
            y-a[2]*width/2-a[3]*height/2)


class Audit:
    def __init__(self, client):
        self.corpus = Corpus(client)
        self.image_cache = {}
        self.cell_cache = {}
        self.errors = []

    def image(self, spr, digest, index, kind):
        key = digest, index, kind
        if key in self.image_cache:
            return self.image_cache[key]
        raw, width, height = spr.get_rgba(index, kind)
        rgba = bytearray(raw)
        for i in range(0, len(rgba), 4):
            if rgba[i+3] == 0:
                rgba[i:i+4] = bytes(4)
        visible = [(x, y) for y in range(height) for x in range(width) if rgba[(y*width+x)*4+3]]
        if not visible:
            self.image_cache[key] = None
            return None
        bbox = (min(x for x, y in visible), min(y for x, y in visible),
                max(x for x, y in visible)+1, max(y for x, y in visible)+1)
        crop = [bytes(rgba[(y*width+x)*4:(y*width+x+1)*4])
                for y in range(bbox[1], bbox[3]) for x in range(bbox[0], bbox[2])]
        variants = []
        for mirror in (0, 1):
            cw, ch = bbox[2]-bbox[0], bbox[3]-bbox[1]
            pixels = [crop[y*cw+cw-1-x] for y in range(ch) for x in range(cw)] if mirror else crop
            matrix = (-1., 0., 0., 1., float(cw), 0.) if mirror else IDENTITY
            for quarter in range(4):
                digest2 = hashlib.sha256(struct.pack("<II", cw, ch)+b"".join(pixels)).hexdigest()
                full_to_canonical = compose(matrix, (1., 0., 0., 1., -bbox[0], -bbox[1]))
                variants.append((digest2, mirror, quarter, full_to_canonical))
                matrix = compose((0., -1., 1., 0., float(ch), 0.), matrix)
                pixels = [pixels[(ch-1-x)*cw+y] for y in range(cw) for x in range(ch)]
                cw, ch = ch, cw
        variants.sort()
        best = variants[0]
        result = {"canonical_visible_rgba_sha256": best[0], "dimensions": [width, height],
                  "alpha_bbox": list(bbox), "to_canonical": best[3],
                  "canonical_d4": [best[1], best[2]],
                  "symmetric_canonical_choices": sum(v[0] == best[0] for v in variants)}
        self.image_cache[key] = result
        return result

    def load(self, stem):
        if stem in self.cell_cache:
            return self.cell_cache[stem]
        cells = []
        try:
            act_bytes, spr_bytes = self.corpus.read(stem+".act"), self.corpus.read(stem+".spr")
            if not act_bytes or not spr_bytes:
                return []
            act, spr = parse_act(act_bytes), Spr(spr_bytes)
            digest = hashlib.sha256(spr_bytes).hexdigest()
            for direction in range(8):
                action = 32+direction
                if action >= len(act["actions"]) or not act["actions"][action].frames:
                    continue
                frame = act["actions"][action].frames[0]
                # A multilayer image cannot serve as a single-bitmap affine witness.
                if len(frame.layers) != 1:
                    continue
                layer = frame.layers[0]
                if layer.sprite_index < 0 or layer.sprite_type not in (0, 1) or not layer.scale_x or not layer.scale_y:
                    continue
                try:
                    image = self.image(spr, digest, layer.sprite_index, layer.sprite_type)
                except (IndexError, ValueError):
                    continue
                if not image or image["symmetric_canonical_choices"] != 1:
                    continue
                to_job = native_canvas_to_job(layer, *image["dimensions"])
                cells.append({"resource": stem, "job": stem.rsplit("_여_", 1)[0]+"_여_",
                    "direction": direction, "action": action, "frame": 0,
                    "image": [layer.sprite_type, layer.sprite_index],
                    "raw_layer": {"xy": [layer.x, layer.y], "scale": [layer.scale_x, layer.scale_y],
                                  "mirror": layer.mirror, "angle": layer.rotation},
                    **image, "canvas_to_job": to_job,
                    "canonical_to_job": compose(to_job, inverse(image["to_canonical"]))})
        except Exception as error:
            self.errors.append({"resource": stem, "error": str(error)})
        self.cell_cache[stem] = cells
        return cells


def run(coverage_path, output):
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    audit = Audit(Path(coverage["client"]))
    names = {r["resource_stem"] for r in coverage["views"]
             if r.get("resource_stem") and r.get("kind") == "single_weapon_view"}
    names.update(r["resource_stem"] for r in coverage["generic_types"] if r.get("resource_stem"))
    # Every declared original view can transmit an exact bridge once its job
    # space is connected. This is the closure, not just the initial 17 seeds.
    stems = sorted(key[:-4] for key in audit.corpus.keys if key.endswith(".act")
                   and "_여_" in key and key.rsplit("_여_", 1)[1][:-4] in names
                   and key[:-4]+".spr" in audit.corpus.keys)
    cells = [cell for stem in stems for cell in audit.load(stem)]
    for cell_id, cell in enumerate(cells):
        cell["id"] = cell_id
    by_hash = defaultdict(list)
    by_job = defaultdict(list)
    for cell in cells:
        by_hash[cell["direction"], cell["canonical_visible_rgba_sha256"]].append(cell)
        by_job[cell["direction"], cell["job"]].append(cell)
    candidates = defaultdict(dict)
    for (direction, pixel_hash), members in by_hash.items():
        for a, b in itertools.combinations(members, 2):
            if a["job"] == b["job"]:
                continue
            if a["job"] > b["job"]:
                a, b = b, a
            b_to_a = compose(a["canonical_to_job"], inverse(b["canonical_to_job"]))
            key = (direction, a["job"], b["job"])
            transform = rounded(b_to_a)
            group = candidates[key].setdefault(transform, {"count": 0, "witness_cells": [a["id"], b["id"]]})
            group["count"] += 1
    edges, adjacency, strict_adjacency = [], defaultdict(list), defaultdict(list)
    for (direction, a, b), transforms in sorted(candidates.items()):
        # All alternatives stay visible. No majority vote silently establishes
        # a universal job transform when independent weapon references disagree.
        ordered = sorted(transforms.items(), key=lambda pair: (-pair[1]["count"], pair[0]))
        entry = {"direction": direction, "job_a": a, "job_b": b,
                 "consistent_across_all_visible_reference_matches": len(ordered) == 1,
                 "transform_alternatives": [{"b_to_a": matrix, **data} for matrix, data in ordered]}
        edge_id = len(edges)
        edges.append(entry)
        for alternative, (matrix, data) in enumerate(ordered):
            adjacency[direction, a].append((b, matrix, edge_id, alternative))
            adjacency[direction, b].append((a, inverse(matrix), edge_id, alternative))
            if len(ordered) == 1:
                strict_adjacency[direction, a].append((b, matrix, edge_id, alternative))
                strict_adjacency[direction, b].append((a, inverse(matrix), edge_id, alternative))

    def traverse(graph, direction):
        reached = {ASSASSIN: {"to_assassin": IDENTITY, "edge_path": []}}
        queue = deque([ASSASSIN])
        contradictions = []
        for_current = set()
        while queue:
            job = queue.popleft()
            current = reached[job]
            for neighbor, to_current, edge_id, alternative in graph[direction, job]:
                transform = compose(current["to_assassin"], to_current)
                if neighbor not in reached:
                    reached[neighbor] = {"to_assassin": rounded(transform), "edge_path": current["edge_path"]+[
                        {"edge": edge_id, "alternative": alternative, "child_job": neighbor}]}
                    queue.append(neighbor)
                else:
                    error = max(abs(x-y) for x, y in zip(transform, reached[neighbor]["to_assassin"]))
                    if error > 1e-5 and edge_id not in for_current:
                        contradictions.append({"edge": edge_id, "maximum_affine_coefficient_difference": error})
                        for_current.add(edge_id)
        return reached, contradictions

    closures = []
    for direction in range(8):
        reached, contradictions = traverse(adjacency, direction)
        strict, strict_contradictions = traverse(strict_adjacency, direction)
        closures.append({"direction": direction, "pixel_correspondence_graph": reached,
                         "pixel_graph_cycle_disagreements": contradictions,
                         "pairwise_consistent_graph": strict,
                         "pairwise_graph_cycle_disagreements": strict_contradictions})
    types = []
    for row in coverage["generic_types"]:
        name = row["resource_stem"]
        donors = []
        for stem in stems:
            if stem.rsplit("_여_", 1)[1] != name:
                continue
            source = audit.load(stem)
            matches = []
            for cell in source:
                d, job = cell["direction"], cell["job"]
                proof = closures[d]["pixel_correspondence_graph"].get(job)
                strict = closures[d]["pairwise_consistent_graph"].get(job)
                if proof:
                    matches.append({"direction": d, "target_cell": cell["id"], "path": proof,
                        "pairwise_consistent_path": strict,
                        "target_canvas_to_assassin": rounded(compose(proof["to_assassin"], cell["canvas_to_job"]))})
            donors.append({"resource": stem, "matched_directions": [x["direction"] for x in matches],
                           "cells": matches})
        types.append({"view": row["view"], "symbol": row["symbol"], "resource_stem": name,
                      "any_exact_bridge_directions": sorted({d for x in donors for d in x["matched_directions"]}),
                      "full_eight_direction_donors": sum(len(x["matched_directions"]) == 8 for x in donors),
                      "donors": donors})
    report = {"schema": "dual-weapon-exact-art-bridge-audit-v1", "client": coverage["client"],
        "scope": {"gender": "female", "action_base": 32, "frame": 0,
                  "source_names": "all declared single weapon views plus generic type names",
                  "method": "Exact visible RGBA with alpha-zero RGB canonicalized, transparent crop offsets retained, lossless horizontal reflection and quarter-turn permutations only.",
                  "coordinate_model": "Native ACT image edges use ceil(width/2), ceil(height/2); continuous pixel centers before camera scaling and native far-edge +1 raster term.",
                  "acceptance": "Read-only candidate registration audit. A pixel-identity path proves shared art, not a universal anatomical grip transform. Conflicting paths are explicit; no runtime or client assets generated.",
                  "unverified": ["Attack frames and held frames beyond zero", "Male sprites", "Physical hilt/body contact", "Native +1 raster rounding after retargeting", "Live rendering"]},
        "summary": {"resources": len(stems), "usable_held_cells": len(cells), "job_spaces": len({x["job"] for x in cells}),
                    "edges": len(edges), "inconsistent_edges": sum(not x["consistent_across_all_visible_reference_matches"] for x in edges),
                    "type_count": len(types), "types_with_all_eight_pixel_bridge_directions": sum(len(x["any_exact_bridge_directions"]) == 8 for x in types)},
        "types": types, "closures": closures, "edges": edges, "cells": cells,
        "sources": audit.corpus.sources, "unreadable_archives": audit.corpus.unreadable,
        "parse_errors": audit.errors}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    audit.corpus.close()
    print(json.dumps(report["summary"]))
    print(json.dumps([{k: r[k] for k in ("view", "symbol", "any_exact_bridge_directions", "full_eight_direction_donors")} for r in types]))
    print("Report: "+str(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, default=ROOT/"docs/evidence/dual-weapon-type-coverage.json")
    parser.add_argument("--output", type=Path, default=ROOT/"docs/evidence/dual-weapon-exact-art-bridges-20260905.json")
    args = parser.parse_args()
    run(args.coverage, args.output)
