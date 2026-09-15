"""Verify package contents, cumulative upgrades, conflict rejection and reproducibility."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import zipfile
from package_louis_patches import build, ROOT


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("louis_installer", ROOT / "packaging/louis/install.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    packages = {}
    for name, features in (("ping", ["ping"]), ("combined", ["fps", "ping"])):
        archive = output / (name + ".zip")
        build(features, archive)
        duplicate = output / (name + "-repeat.zip")
        build(list(reversed(features)), duplicate)
        require(archive.read_bytes() == duplicate.read_bytes(), "archive is not deterministic")
        package = output / name
        with zipfile.ZipFile(archive) as z:
            z.extractall(package)
        packages[name] = package
    ping, combined = packages["ping"], packages["combined"]
    manifest = json.loads((ping / "package-manifest.json").read_text())
    require(set(manifest["managed_files"]) == {
        "Scripts/Patches/PingOverlay.qjs", "Scripts/Patches/CustomSlashCommand.qjs",
        "Scripts/Support/Class_NativeTelemetry.qjs", "Patches/LouisTelemetry.yml"}, "unexpected paid code in Ping ZIP")
    core = (ping / "Scripts/Support/Class_NativeTelemetry.qjs").read_text()
    require("StateFpsFrames" not in core and '"FPS: "' not in core, "FPS implementation leaked into core")
    for p in ping.rglob("*.qjs"):
        data = p.read_bytes()
        require(data.startswith(b"/*") and b"\n" not in data.replace(b"\r\n", b""), "invalid QJS encoding")
    warp = output / "warp"
    for directory in ("Scripts/Init", "Tables", "Patches"):
        (warp / directory).mkdir(parents=True)
    (warp / "Scripts/Init/Initializer.qjs").write_text("/* fixture */")
    (warp / "Patches.yml").write_text("# existing comment\ninclude:\n    - Patches/Base.yml\n")
    (warp / "Patches/Base.yml").write_text("Base:\n    title: Base\n    mutex: false\n    patches: []\n")
    (warp / "Tables/Patch.yml").write_text("# existing table\n1 : ExistingPatch\n")

    def snapshot():
        return {p.relative_to(warp).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in warp.rglob("*") if p.is_file()}

    def refused(package, expected):
        before = snapshot()
        try:
            installer.install(package, warp)
        except ValueError as error:
            require(expected in str(error), f"wrong refusal: {error}")
        else:
            raise RuntimeError("unsafe install was accepted")
        require(snapshot() == before, "refused install modified files")

    before = snapshot()
    installer.install(ping, warp, check=True)
    require(snapshot() == before, "check-only install wrote files")
    installer.install(ping, warp)
    require(not installer.install(ping, warp)["changes"], "reinstall changed files")
    require("1 : ExistingPatch" in (warp / "Tables/Patch.yml").read_text(), "existing table entry lost")
    require("Patches/Base.yml" in (warp / "Patches.yml").read_text(), "existing include lost")
    installer.install(combined, warp)
    require((warp / "Scripts/Patches/FpsOverlay.qjs").is_file(), "cumulative upgrade omitted FPS")
    require((warp / "Patches.yml").read_text().count("Patches/LouisTelemetry.yml") == 1, "duplicate include")
    refused(ping, "cumulative")

    lock_path = warp / installer.LOCK
    original_lock = lock_path.read_bytes()
    lock = json.loads(original_lock)
    lock["release"] = "2.0.0"
    lock_path.write_text(json.dumps(lock))
    refused(combined, "downgrade")
    lock_path.write_bytes(original_lock)

    helper = warp / "Scripts/Support/Class_NativeTelemetry.qjs"
    original_helper = helper.read_bytes()
    helper.write_bytes(original_helper + b"// local edit\r\n")
    refused(combined, "edited or removed")
    helper.write_bytes(original_helper)

    changed = output / "changed"
    shutil.copytree(combined, changed)
    changed_file = changed / "Scripts/Support/Class_NativeTelemetry.qjs"
    changed_file.write_bytes(changed_file.read_bytes() + b"// unversioned change\r\n")
    changed_manifest = json.loads((changed / "package-manifest.json").read_text())
    h = hashlib.sha256(changed_file.read_bytes()).hexdigest()
    changed_manifest["files"]["Scripts/Support/Class_NativeTelemetry.qjs"] = h
    changed_manifest["managed_files"]["Scripts/Support/Class_NativeTelemetry.qjs"] = h
    (changed / "package-manifest.json").write_text(json.dumps(changed_manifest))
    refused(changed, "version bump")

    tampered = combined / "runtime-options.lua"
    original = tampered.read_bytes()
    tampered.write_bytes(original + b"edit")
    refused(combined, "checksum")
    tampered.write_bytes(original)

    # Unmanaged installations reject collisions before touching any file.
    clean = output / "collision"
    shutil.copytree(warp, clean)
    (clean / installer.LOCK).unlink()
    (clean / "Scripts/Support/Class_NativeTelemetry.qjs").write_bytes(b"/* other implementation */\r\n")
    old_warp, warp = warp, clean
    refused(combined, "Unmanaged file conflict")
    warp = old_warp

    report = {"passed": True, "checks": [
        "deterministic archives", "Ping-only source closure", "QJS encoding", "dry-run",
        "idempotent install", "existing WARP registrations preserved", "cumulative upgrade",
        "partial upgrade refused", "downgrade refused", "local edits preserved",
        "shared version mismatch refused", "checksum failure refused", "unmanaged conflict refused"
    ]}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output.resolve())
