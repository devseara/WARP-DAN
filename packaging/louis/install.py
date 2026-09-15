"""Install an extracted Louis package without replacing WARP's existing patch lists."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import os

LOCK = "louis-package-lock.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, name):
    if "\\" in name or ":" in name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError(f"Invalid package path: {name}")
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path escapes destination: {name}")
    return path


def version(value):
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError(f"Invalid version: {value}")
    return tuple(map(int, value.split(".")))


def install(package: Path, warp: Path, check=False):
    package, warp = package.resolve(), warp.resolve()
    manifest = json.loads((package / "package-manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != 1:
        raise ValueError("Unsupported package schema")
    for name, expected in manifest["files"].items():
        if sha(safe(package, name).read_bytes()) != expected:
            raise ValueError(f"Package checksum mismatch: {name}")
    for name in ("Scripts/Init/Initializer.qjs", "Tables/Patch.yml", "Patches.yml"):
        if not safe(warp, name).is_file():
            raise ValueError(f"Not a WARP installation: missing {name}")
    lock_path = safe(warp, LOCK)
    previous = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else None
    if previous:
        if not set(previous["features"]) <= set(manifest["features"]):
            raise ValueError("Request a cumulative package containing every previously installed feature")
        if version(manifest["release"]) < version(previous["release"]):
            raise ValueError("Refusing to downgrade the customer package")
        for name, old_version in previous["modules"].items():
            new_version = manifest["modules"].get(name)
            if new_version is None or version(new_version) < version(old_version):
                raise ValueError(f"Missing or older shared module: {name}")
            if new_version == old_version:
                for file in previous["module_files"][name]:
                    if previous["managed_files"][file] != manifest["managed_files"].get(file):
                        raise ValueError(f"Shared module changed without a version bump: {name}")
        for name, expected in previous["managed_files"].items():
            target = safe(warp, name)
            if not target.is_file() or sha(target.read_bytes()) != expected:
                raise ValueError(f"Previously installed file was edited or removed: {name}")
    changes = {}
    for name, expected in manifest["managed_files"].items():
        if not name.startswith(("Scripts/", "Patches/", "Images/")):
            raise ValueError(f"Unexpected managed path: {name}")
        data = safe(package, name).read_bytes()
        if sha(data) != expected:
            raise ValueError(f"Managed checksum mismatch: {name}")
        target = safe(warp, name)
        if target.exists() and target.read_bytes() != data:
            if not previous or name not in previous["managed_files"]:
                raise ValueError(f"Unmanaged file conflict: {name}; use a clean WARP copy")
        changes[target] = data

    registrations = manifest["registrations"]
    patch_names = set(registrations.values())
    for metadata in (warp / "Patches").glob("*.yml"):
        if metadata.name == "LouisTelemetry.yml":
            continue
        names = set(re.findall(r"^\s*-\s*(\w+)\s*:", metadata.read_text(encoding="utf-8-sig"), re.M))
        if names & patch_names:
            raise ValueError(f"Existing patch registration in {metadata.name}: {sorted(names & patch_names)}")
    table_path = safe(warp, "Tables/Patch.yml")
    table = table_path.read_text(encoding="utf-8-sig")
    existing = dict(re.findall(r"^\s*(\d+)\s*:\s*(\w+)\s*(?:#.*)?$", table, re.M))
    for patch_id, name in registrations.items():
        if patch_id in existing and existing[patch_id] != name:
            raise ValueError(f"Patch ID {patch_id} is already owned by {existing[patch_id]}")
        other_ids = [key for key, value in existing.items() if value == name and key != patch_id]
        if other_ids:
            raise ValueError(f"Patch {name} already has another ID: {other_ids}")
        if patch_id not in existing:
            table = table.rstrip() + f"\n{patch_id} : {name}\n"
    changes[table_path] = table.replace("\n", "\r\n").encode("utf-8")
    tree_path = safe(warp, "Patches.yml")
    tree = tree_path.read_text(encoding="utf-8-sig")
    if not re.search(r"^include:\s*$", tree, re.M):
        raise ValueError("Unsupported Patches.yml include structure")
    include = "Patches/LouisTelemetry.yml"
    if include not in [line.lstrip()[1:].strip().strip(chr(34) + chr(39)) for line in tree.splitlines() if line.lstrip().startswith("-")]:
        if re.search(r"^(?!include:)[A-Za-z]\w*:", tree, re.M):
            raise ValueError("Patches.yml has additional root keys; merge the include manually")
        tree = tree.rstrip() + "\n    - " + include + "\n"
    changes[tree_path] = tree.replace("\n", "\r\n").encode("utf-8")
    changes[lock_path] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    changes = {path: data for path, data in changes.items() if not path.exists() or path.read_bytes() != data}
    result = {"features": manifest["features"], "check_only": check,
              "changes": [str(p.relative_to(warp)) for p in changes]}
    if check:
        return result

    originals = {p: p.read_bytes() if p.exists() else None for p in changes}

    def replace(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
        try:
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()

    written = []
    try:
        for path, data in changes.items():
            replace(path, data)
            written.append(path)
    except Exception:
        for path in reversed(written):
            if originals[path] is None:
                path.unlink()
            else:
                replace(path, originals[path])
        raise
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warp", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Validate the complete install without writing")
    args = parser.parse_args()
    try:
        print(json.dumps(install(Path(__file__).resolve().parent, args.warp, args.check), indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Installation refused: {error}\n")
