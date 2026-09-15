"""Verify asset delivery and cumulative upgrades from telemetry to text products."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
from package_louis_patches import ROOT, build

def require(value, message):
    if not value: raise RuntimeError(message)

def run(out, previous):
    out.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("louis_install", ROOT / "packaging/louis/install.py")
    installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
    warp = out / "warp"
    for folder in ("Scripts/Init", "Tables", "Patches"): (warp / folder).mkdir(parents=True)
    (warp / "Scripts/Init/Initializer.qjs").write_text("/* unchanged WARP initializer */\n")
    (warp / "Tables/Patch.yml").write_text("1 : ExistingPatch\n")
    (warp / "Patches.yml").write_text("include:\n    - Patches/Existing.yml\n")
    (warp / "Patches/Existing.yml").write_text("Existing:\n    title: Existing\n    patches: []\n")
    initial = out / "previous"
    with zipfile.ZipFile(previous) as archive: archive.extractall(initial)
    installer.install(initial, warp)
    old_lock = json.loads((warp / installer.LOCK).read_text())
    require(old_lock["features"] == ["ping"] and old_lock["release"] == "1.0.0", "expected the tested Ping 1.0.0 release")

    features = ["ping", "fps", "emoji", "extended-names", "player-colors"]
    bundle = out / "all.zip"; result = build(features, bundle)
    again = out / "all-again.zip"; build(list(reversed(features)), again)
    require(bundle.read_bytes() == again.read_bytes(), "asset bundle is not deterministic")
    package = out / "package"
    with zipfile.ZipFile(bundle) as archive: archive.extractall(package)
    def hashes():
        return {p.relative_to(warp).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in warp.rglob("*") if p.is_file()}
    before = hashes()
    installer.install(package, warp, check=True)
    require(hashes() == before, "upgrade preflight wrote files")
    installer.install(package, warp)
    require(not installer.install(package, warp)["changes"], "cumulative install is not idempotent")
    lock = json.loads((warp / installer.LOCK).read_text())
    require(set(lock["features"]) == set(features), "upgrade lost a purchased feature")
    for file, expected in old_lock["managed_files"].items():
        if file.endswith(".qjs"): require(hashes()[file] == expected, "existing telemetry module changed")
    pngs = list((package / "Images/BohEmoji/fluent").glob("*.png"))
    require(len(pngs) > 3000, "emoji PNGs missing")
    for p in pngs:
        dest = warp / p.relative_to(package)
        require(dest.read_bytes() == p.read_bytes(), "asset install mismatch")
    require((warp / "Images/BohEmoji/fluent/LICENSE.Microsoft-Fluent-Emoji.txt").is_file(), "asset license missing")
    require("Patches/Existing.yml" in (warp / "Patches.yml").read_text(), "unrelated include lost")
    asset = warp / pngs[0].relative_to(package)
    original = asset.read_bytes(); asset.write_bytes(original + b"customer edit")
    altered = hashes()
    try: installer.install(package, warp)
    except ValueError as error: require("edited or removed" in str(error), str(error))
    else: raise RuntimeError("edited customer asset overwritten")
    require(hashes() == altered, "failed upgrade partially wrote files")
    report = {"passed": True, "previous_archive_sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
              "features": features, "png_files": len(pngs), "new_archive_sha256": result["sha256"],
              "checks": ["1.0.0 Ping to 1.1.0 cumulative upgrade", "unchanged existing telemetry modules",
                         "asset hashes and license", "deterministic asset archives", "dry-run upgrade",
                         "idempotent cumulative install", "existing registrations", "edited asset rejection without partial writes"]}
    (out / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-ping", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.previous_ping.resolve())
