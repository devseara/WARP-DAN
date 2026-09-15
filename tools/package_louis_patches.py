"""Build a deterministic customer ZIP from explicitly declared feature dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "packaging/louis/catalog.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve(catalog: dict, features: list[str]) -> list[str]:
    result, visiting = [], set()

    def visit(name: str):
        if name in visiting:
            raise ValueError(f"Dependency cycle: {name}")
        if name in result:
            return
        visiting.add(name)
        for dependency in catalog["modules"][name]["requires"]:
            visit(dependency)
        visiting.remove(name)
        result.append(name)

    for feature in features:
        for module in catalog["features"][feature]["requires"]:
            visit(module)
    return result


def build(features: list[str], output: Path) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    features = sorted(set(features))
    if not features or any(f not in catalog["features"] for f in features):
        raise ValueError("Select one or more registered features: " + ", ".join(catalog["features"]))
    modules = resolve(catalog, features)
    files = {}
    for spec in [catalog["modules"][m] for m in modules] + [catalog["features"][f] for f in features]:
        for name in spec["files"]:
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT):
                raise ValueError(f"Dependency path escapes repository: {name}")
            data = source.read_bytes()
            if name.endswith(".qjs"):
                data.decode("utf-8")
                if not data.startswith(b"/*") or b"\n" in data.replace(b"\r\n", b""):
                    raise ValueError(f"QJS must be UTF-8 without BOM and CRLF: {name}")
            files[name] = data
    rows = [catalog["features"][f] for f in features]
    metadata = "LouisTelemetry:\n    title: Louis T Steinhil - Telemetry\n    mutex: false\n    patches:\n"
    for row in rows:
        metadata += (f"        - {row['patch']}:\n"
                     f"            title: {json.dumps(row['title'])}\n"
                     "            recommend: no\n            author: Louis T Steinhil\n"
                     f"            desc: {json.dumps(row['description'])}\n")
    files["Patches/LouisTelemetry.yml"] = metadata.encode("utf-8")
    commands = [row["command"] for row in rows]
    files["runtime-options.lua"] = ("-- Optional: merge these entries into the existing savedata/OptionInfo.lua.\n"
        "-- Keep the existing CmdOnOffList table and all other player settings.\n" +
        "".join(f'CmdOnOffList["{cmd}"] = 1\n' for cmd in commands)).encode("utf-8")
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    files["install.py"] = (ROOT / "packaging/louis/install.py").read_bytes()
    readme = (f"Louis T Steinhil patches {catalog['release']}\n\n"
        "Purchased features: " + ", ".join(features) + "\n"
        "Target client: 2025-07-16 Ragexe only.\n\n"
        "1. Extract this ZIP to a separate folder. Close WARP.\n"
        '2. Run: python install.py --warp "C:/path/to/WARP" --check\n'
        "   Then run the same command without --check to install. Python 3.10+; no extra libraries.\n"
        "3. Open WARP, load your original client EXE, and select the purchased overlays.\n"
        "   Choose coordinates and an overlay font. Patch to a new EXE.\n\n"
        "Type " + " or ".join(commands) + " in game to toggle the purchased overlay.\n"
        "If initially hidden, type its command once. For enabled-by-default settings, merge\n"
        "runtime-options.lua into the existing savedata/OptionInfo.lua after its table definition.\n"
        "No replacement Game Settings Lua, custom DLL, server patch, or image assets are required.\n\n"
        "For additional purchases request one cumulative package containing all your features.\n"
        "The installer preserves WARP registrations and rejects older or conflicting managed files.\n"
        "It does not replace your client EXE, profiles, or player settings.\n"
        "This archive is a patch distribution, not a live-game acceptance certificate.\n")
    files["README.txt"] = readme.encode("utf-8")
    managed = {name: digest(data) for name, data in files.items() if name.startswith(("Scripts/", "Patches/"))}
    manifest = {
        "schema": 1, "release": catalog["release"], "features": features,
        "client_profiles": catalog["client_profiles"],
        "modules": {name: catalog["modules"][name]["version"] for name in modules},
        "module_files": {name: catalog["modules"][name]["files"] for name in modules},
        "registrations": {str(row["patch_id"]): row["patch"] for row in rows},
        "managed_files": managed, "files": {name: digest(data) for name, data in files.items()},
    }
    files["package-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an existing release archive.
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 9, 14, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP verification failed")
        for name, expected in manifest["files"].items():
            if digest(archive.read(name)) != expected:
                raise RuntimeError(f"ZIP hash mismatch: {name}")
    return {"archive": str(output.resolve()), "sha256": digest(output.read_bytes()),
            "features": features, "modules": modules, "managed_files": sorted(managed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", action="append", choices=["ping", "fps"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.feature, args.output), indent=2))


if __name__ == "__main__":
    main()
