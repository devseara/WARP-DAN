"""Inventory every declared weapon type/view for Assassin resource prefixes.

Reads loose files and active DATA.INI archives. Unreadable archives prevent an
absolute absence claim. Tests exact source-cell availability and transform
compatibility; it does not infer missing frames, hand landmarks, or job poses.
"""
from __future__ import annotations
import argparse
from collections import Counter
import configparser
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.grf_reader import GrfFile
from dual_weapon_formats.rig_tables import parse_rig_bytes
from dual_weapon_formats.spr_reader import Spr
from dual_weapon_formats.weapontable_lua import lua_block, parse_expansions, parse_ids, parse_names

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "data/sprite/인간족/어세신/어세신_"
TABLE = "data/luafiles514/lua files/datainfo/weapontable.lub"
CLS = "data/luafiles514/lua files/cls/weapontable.lub"
GENDERS = {"female": "여", "male": "남"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Corpus:
    def __init__(self, client):
        self.client, self.archives, self.unreadable, self.sources = client, [], [], {}
        self.archive_profiles = []
        ini = configparser.ConfigParser()
        ini.read(client / "DATA.INI")
        self.priority = [client / value for _, value in sorted(ini["Data"].items(), key=lambda x: int(x[0]))]
        self.keys = set()
        for path in self.priority:
            try:
                archive = GrfFile(path)
                self.archives.append((path, archive))
                self.keys.update(archive.entries)
                self.archive_profiles.append({"path": str(path), "format": archive.format,
                    "version": archive.version, "entry_count": archive.file_count,
                    "ACT_entries": sum(key.endswith('.act') for key in archive.entries),
                    "SPR_entries": sum(key.endswith('.spr') for key in archive.entries)})
            except (ValueError, OSError) as error:
                self.unreadable.append({"path": str(path), "reason": str(error)})
        loose = client / "data"
        if loose.is_dir():
            self.keys.update(p.relative_to(client).as_posix().lower() for p in loose.rglob("*") if p.is_file())

    def read(self, key):
        key = key.lower()
        path = self.client / Path(key)
        data, source = (path.read_bytes(), path) if path.is_file() else (None, None)
        if data is None:
            for path, archive in self.archives:
                data = archive.read(key)
                if data is not None:
                    source = path
                    break
        if data is not None:
            self.sources[key] = {"source": str(source), "bytes": len(data), "sha256": sha(data)}
        return data

    def absent_status(self):
        return "not_found_in_readable_sources_unreadable_archive_remains" if self.unreadable else "absent"

    def close(self):
        for _, archive in self.archives:
            archive.close()


def run(client, output):
    corpus = Corpus(client)
    standard, cls = corpus.read(TABLE), corpus.read(CLS)
    assert standard and cls, "missing source weapon table"
    assert not standard.startswith(b"\x1bLua") and not cls.startswith(b"\x1bLua"), "compiled Lua needs a bytecode parser"
    standard, cls = standard.decode("cp949"), cls.decode("cp949")
    ids = parse_ids(lua_block(standard, "Weapon_IDs")) | parse_ids(lua_block(cls, "Weapon_IDs_CLS"))
    names = parse_names(lua_block(standard, "WeaponNameTable")) | parse_names(lua_block(cls, "WeaponNameTable_CLS"))
    expansions = parse_expansions(lua_block(standard, "Expansion_Weapon_IDs")) | parse_expansions(lua_block(cls, "Expansion_Weapon_IDs_CLS"))
    source = (ROOT / "Scripts/Patches/AllowDualCustomWeaponSprites.qjs").read_text(encoding="utf-8")
    embedded = re.findall(r'const DualWeaponAuthoredRigHex = "([0-9A-Fa-f ]+)";', source)
    assert len(embedded) == 1
    rig_bytes = bytes.fromhex(embedded[0])
    requirements = {hand: set() for hand in (0, 1)}
    for row in parse_rig_bytes(rig_bytes)["records"]:
        if row["family"] or row["gender"] or row["state"] != 9:
            continue
        pose = row["transform"]
        if pose.metadata & 8:
            continue
        action = (80 if row["phase"] or pose.metadata & 32 else 32) + row["direction"]
        requirements[row["hand"]].add((action, pose.flags & 31))

    assets, parsed = {}, {}

    def layer(asset, action, frame):
        if asset is None:
            return None
        act, spr = asset
        if action >= len(act["actions"]) or frame >= len(act["actions"][action].frames):
            return None
        layers = act["actions"][action].frames[frame].layers
        if not layers:
            return None
        result = layers[0]
        images = [im for im in spr.images if im.is_indexed == (result.sprite_type == 0)]
        if result.sprite_type not in (0, 1) or not 0 <= result.sprite_index < len(images):
            return None
        return result, images[result.sprite_index], len(layers)

    def load(stem):
        if stem in assets:
            return parsed.get(stem)
        act_bytes, spr_bytes = corpus.read(stem + ".act"), corpus.read(stem + ".spr")
        entry = {"ACT": corpus.sources.get((stem + ".act").lower()), "SPR": corpus.sources.get((stem + ".spr").lower())}
        assets[stem] = entry
        if act_bytes is None or spr_bytes is None:
            entry.update(status=corpus.absent_status(), missing_extensions=[e for e, b in ((".act", act_bytes), (".spr", spr_bytes)) if b is None])
            return None
        try:
            pair = parse_act(act_bytes), Spr(spr_bytes)
        except Exception as error:
            entry.update(status="parse_failed", reason=str(error))
            return None
        parsed[stem] = pair
        act, spr = pair
        entry.update(status="resolved", actions=len(act["actions"]), indexed_images=spr.n_indexed8, rgba_images=spr.n_bgra32)
        groups = {}
        for label, base in (("held32", 32), ("solo_attack80", 80)):
            directions = []
            for direction in range(8):
                action = base + direction
                frames = act["actions"][action].frames if action < len(act["actions"]) else []
                visible, multi, nonidentity = [], [], []
                for frame, frame_data in enumerate(frames):
                    cell = layer(pair, action, frame)
                    if not cell:
                        continue
                    l, im, count = cell
                    visible.append(frame)
                    if count != 1:
                        multi.append(frame)
                    if l.rotation or l.scale_x != 1 or l.scale_y != 1:
                        nonidentity.append({"frame": frame, "angle": l.rotation, "scale": [l.scale_x, l.scale_y]})
                directions.append({"direction": direction, "frame_count": len(frames), "visible_layer0_frames": visible,
                                   "visible_multilayer_frames": multi, "nonidentity_source_transforms": nonidentity})
            groups[label] = directions
        entry["action_coverage"] = groups
        return pair

    for gender in GENDERS.values():
        load(PREFIX + gender + "_13412")
        load(PREFIX + gender + "_1238")

    def compare(candidate, reference, hand):
        absent, mismatch, multi, offsets = [], [], [], []
        for action, frame in sorted(requirements[hand]):
            a, b = layer(candidate, action, frame), layer(reference, action, frame)
            if not a or not b:
                absent.append({"action": action, "frame": frame, "candidate_visible": bool(a), "reference_visible": bool(b)})
                continue
            ca, ci, cn = a
            ra, ri, rn = b
            ct, rt = [ca.rotation, ca.scale_x, ca.scale_y, ca.mirror], [ra.rotation, ra.scale_x, ra.scale_y, ra.mirror]
            if ct != rt:
                mismatch.append({"action": action, "frame": frame, "candidate": ct, "reference": rt})
            if cn != 1 or rn != 1:
                multi.append([action, frame, cn, rn])
            cx = ca.x - (ci.width + 1) // 2 + ci.width / 2
            cy = ca.y - (ci.height + 1) // 2 + ci.height / 2
            rx = ra.x - (ri.width + 1) // 2 + ri.width / 2
            ry = ra.y - (ri.height + 1) // 2 + ri.height / 2
            offsets.append({"action": action, "frame": frame, "delta_native_image_centers": [cx - rx, cy - ry],
                            "candidate_image": [ca.sprite_type, ca.sprite_index], "candidate_dimensions": [ci.width, ci.height]})
        return {"required_visible_source_cells": len(requirements[hand]), "missing_cells": absent,
                "transform_mismatches": mismatch, "multi_layer_cells": multi,
                "source_cells_compatible": not absent and not mismatch and not multi,
                "physical_grip_registration_verified": False, "center_correspondences": offsets}

    def alternatives(suffix, gender):
        # Inventory only: another job's ACT registration is not an Assassin socket.
        ending = "_" + gender + suffix + ".act"
        matches = sorted(k for k in corpus.keys if k.startswith("data/sprite/인간족/") and
                         k.endswith(ending) and k[:-4] + ".spr" in corpus.keys and not k.startswith(PREFIX))
        return {"matching_ACT_SPR_pairs_in_readable_sources": len(matches), "paths": matches,
                "Assassin_registration_verified": False}

    views, generic = [], []
    for symbol, view in sorted(ids.items(), key=lambda row: (row[1], row[0])):
        suffix = names.get(symbol)
        base_symbol = expansions.get(symbol, symbol)
        base_type = ids.get(base_symbol)
        row = {"view": view, "symbol": symbol, "base_type": base_type, "base_symbol": base_symbol,
               "suffix": suffix, "resource_stem": suffix.lstrip("_") if suffix else suffix,
               "kind": "none_or_marker" if view in (0, 24) else "combined_pair" if 25 <= view <= 30 else "single_weapon_view"}
        views.append(row)
        if 1 <= view <= 23:
            generic.append(row)
        if not suffix or row["kind"] == "none_or_marker":
            continue
        row["genders"] = {}
        for label, gender in GENDERS.items():
            stem = PREFIX + gender + suffix
            candidate = load(stem)
            result = {"resource": stem, "status": assets[stem]["status"],
                      "reference_pose_acceptance": "female_Assassin_pair28_only" if label == "female" else "male_pose_not_accepted",
                      "combined_art_requires_pixel_review": base_type == 16 or row["kind"] == "combined_pair"}
            if candidate:
                result["relative_to_sword_hand"] = compare(candidate, load(PREFIX + gender + "_13412"), 0)
                result["relative_to_dagger_hand"] = compare(candidate, load(PREFIX + gender + "_1238"), 1)
                result["registration_status"] = "source_center_correspondence_only_not_body_hand_proof"
            else:
                result["alternate_job_assets"] = alternatives(suffix, gender)
            row["genders"][label] = result

    summary = {}
    for label in GENDERS:
        weapon_rows = [r for r in views if r["kind"] == "single_weapon_view" and label in r.get("genders", {})]
        resolved = [r for r in weapon_rows if r["genders"][label]["status"] == "resolved"]
        summary[label] = {"declared_weapon_views": len(weapon_rows), "resolved_views": len(resolved),
                          "resolved_generic_types": [r["view"] for r in generic if r["genders"][label]["status"] == "resolved"],
                          "unresolved_generic_types": [r["view"] for r in generic if r["genders"][label]["status"] != "resolved"],
                          "source_compatible_sword_role_views": [r["view"] for r in resolved if r["genders"][label]["relative_to_sword_hand"]["source_cells_compatible"]],
                          "source_compatible_dagger_role_views": [r["view"] for r in resolved if r["genders"][label]["relative_to_dagger_hand"]["source_cells_compatible"]],
                          "missing_registration_is_not_implied_compatible": True}
    result = {"schema": "dual_weapon_type_coverage/v1", "client": str(client),
              "audit_tool_sha256": sha(Path(__file__).read_bytes()),
              "DATA_INI_sha256": sha((client / "DATA.INI").read_bytes()),
              "archive_priority": [str(p) for p in corpus.priority], "unreadable_archives": corpus.unreadable,
              "archive_profiles": corpus.archive_profiles,
              "table_sources": {k: corpus.sources[k] for k in (TABLE, CLS)}, "legacy_reference_rig_sha256": sha(rig_bytes),
              "summary": summary, "generic_types": generic, "views": views, "assets": assets,
              "limits": ["Source compatibility is not anatomical grip registration or live placement acceptance.",
                         "Alternate job resource paths are inventory only; they do not prove Assassin-body hand placement.",
                         "Male source-cell checks do not supply accepted male body poses.",
                         "Layer0 source selection follows the current compositor. Multi-layer art is flagged rather than silently accepted.",
                         "A complete view/item database is not inferred from numeric resource stems; this covers declared Weapon_IDs and CLS entries.",
                         ("Unresolved names may still exist in unreadable active archives." if corpus.unreadable else
                          "Every active archive was parsed; absent expected paths are missing from the active archives and loose files."),
                         "No frames or files are synthesized."]}
    corpus.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "unreadable_archives": corpus.unreadable,
                      "declared_ids": len(ids), "unique_expected_resources": len(assets)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/dual-weapon-type-coverage.json")
    args = parser.parse_args()
    run(args.client, args.output)
