"""Verify text customer packages against a committed baseline using real WARP."""
from __future__ import annotations
import argparse
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import uuid
import zipfile
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
from package_louis_patches import ROOT, build
from verify_telemetry_packages import inputs as telemetry_inputs, verify_pe as verify_telemetry

FEATURES = {"ping": "PingOverlay", "fps": "FpsOverlay", "emoji": "FluentEmoji", "player-colors": "CustomPlayerNameColor", "extended-names": "CustomExtName"}
CASES = {
    "emoji": ["emoji"], "player-colors": ["player-colors"], "extended-names": ["extended-names"],
    "emoji-colors": ["emoji", "player-colors"], "colors-emoji": ["player-colors", "emoji"],
    "emoji-names": ["emoji", "extended-names"], "names-emoji": ["extended-names", "emoji"],
    "names-colors": ["extended-names", "player-colors"], "colors-names": ["player-colors", "extended-names"],
    "all": ["emoji", "extended-names", "player-colors"],
    "complete-bundle": ["ping", "fps", "emoji", "extended-names", "player-colors"],
    "production-bundle": ["emoji", "extended-names", "fps", "ping", "player-colors"],
}
PROBE = r'''/* Isolated text package state recorder. */
TestTextPackage = function(_) {
 const f = new TextFile(MARKER, "w");
 if (!f.Valid) throw Error("cannot write text package marker");
 f.WriteLine(JSON.stringify({
  token: TOKEN, text: CACHE.get("ExtNameTextStatic.State"),
  emoji: CACHE.get("FluentEmojiStatic.State") ?? null,
  routes: CACHE.get("CustomPacketDispatch.Routes") ?? null,
  telemetry: CACHE.get("NativeTelemetryOverlay.State") ?? null,
  commands: CACHE.get("CustomSlashCommand.RegistryByOwner") ?? {}
 })); f.Close(); return true;
};
TestTextPackage.validate = function() { return true; };
TextPackageProbe = TestTextPackage;
'''

def require(value, message):
    if not value:
        raise RuntimeError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def common(base, destination):
    destination.mkdir(parents=True)
    for folder in ("win32", "Tables", "Inputs", "Languages", "Styles", "Fonts", "Scripts/Support", "Scripts/Init"):
        shutil.copytree(base / folder, destination / folder)
    (destination / "Scripts/Patches").mkdir()
    (destination / "Patches").mkdir()
    (destination / "Patches.yml").write_text("include:\n", encoding="utf-8")

def reference(base, destination, ref):
    common(base, destination)
    archive = subprocess.check_output(["git", "archive", "--format=tar", ref, "Scripts"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream.getmembers():
            if not member.isfile():
                continue
            target = (destination / member.name).resolve()
            require(target.is_relative_to(destination), "archive path escapes fixture")
            data = stream.extractfile(member).read()
            if target.suffix == ".qjs":
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    shutil.copytree(ROOT / "Images/BohEmoji/fluent", destination / "Images/BohEmoji/fluent")

def configure(fixture, order, marker, token, preserve_products=False):
    tree = "TextProducts:\n    title: Text verification\n    mutex: false\n    patches:\n"
    for name in ([] if preserve_products else order) + ["TestTextPackage"]:
        tree += (f"        - {name}:\n            title: {name}\n            recommend: no\n"
                 "            author: Louis T Steinhil\n            desc: Isolated test.\n")
    (fixture / "Patches/TextProducts.yml").write_text(tree, encoding="utf-8")
    include = "include:\n" + ("    - Patches/LouisTelemetry.yml\n" if preserve_products else "")
    (fixture / "Patches.yml").write_text(include + "    - Patches/TextProducts.yml\n", encoding="utf-8")
    table = (fixture / "Tables/Patch.yml").read_text(encoding="utf-8")
    if "65011 : TestTextPackage" not in table:
        (fixture / "Tables/Patch.yml").write_text(table.rstrip() + "\n65011 : TestTextPackage\n")
    code = PROBE.replace("MARKER", json.dumps(marker.as_posix())).replace("TOKEN", json.dumps(token))
    (fixture / "Scripts/Patches/TextPackageProbe.qjs").write_bytes(code.replace("\n", "\r\n").encode())

def warp_build(fixture, source, target, order, preserve_products=False):
    marker = target.with_suffix(".json")
    token = uuid.uuid4().hex
    configure(fixture, order, marker, token, preserve_products)
    profile = target.with_suffix(".yml")
    profile.write_text("from: " + json.dumps(str(source)) + "\nto: " + json.dumps(str(target)) +
                       "\ninputs: " + json.dumps(telemetry_inputs()) + "\npatches:\n" +
                       "".join("    - " + p + "\n" for p in order + ["TestTextPackage"]), encoding="utf-8")
    run = subprocess.run([str(fixture / "win32/WARP_console.exe"), "-using", str(profile)], cwd=fixture,
                         capture_output=True, timeout=120)
    log = run.stdout + run.stderr
    target.with_suffix(".log").write_bytes(log)
    require(run.returncode == 0 and b"-E-" not in log and b"Cancelled" not in log and marker.is_file(),
            f"WARP failed: {target.with_suffix('.log')}")
    snapshot = json.loads(marker.read_text(encoding="utf-8"))
    require(snapshot["token"] == token, "stale marker")
    return snapshot

class TextMachine:
    def __init__(self, pe):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.uc.mem_write(0x400000, pe.get_memory_mapped_image())
        self.uc.mem_map(0x28000000, 0x100000)
        self.uc.mem_map(0x29000000, 0x100000)
        self.color, self.draws, self.hooks = 0xFFFFFF, [], {}
        self.uc.hook_add(UC_HOOK_CODE, self.hook)
        self.iat(0xFC1204, 32, self.wide_to_multi)
        self.iat(0xFC1200, 24, self.multi_to_wide)
        self.iat(0xFC10E0, 8, self.set_color)
        self.iat(0xFC10DC, 20, self.text_out)

    def u32(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def wide(self, address):
        out = bytearray()
        for i in range(1024):
            pair = bytes(self.uc.mem_read(address + i * 2, 2))
            if pair == b"\0\0": break
            out.extend(pair)
        return out.decode("utf-16le")

    def ansi(self, address):
        out = bytearray()
        for i in range(2048):
            b = bytes(self.uc.mem_read(address + i, 1))
            if b == b"\0": break
            out.extend(b)
        return out.decode("utf-8")

    def stub(self, address, pop, function):
        self.hooks[address] = (pop, function)
        self.uc.mem_write(address, b"\xc3")

    def iat(self, cell, pop, function):
        address = 0x290F0000 + len(self.hooks) * 0x100
        self.stub(address, pop, function)
        self.uc.mem_write(cell, struct.pack("<I", address))

    def hook(self, uc, address, size, user):
        if address not in self.hooks: return
        sp = uc.reg_read(UC_X86_REG_ESP)
        pop, function = self.hooks[address]
        args = [self.u32(sp + 4 + i) for i in range(0, pop, 4)]
        result = function(args)
        uc.reg_write(UC_X86_REG_EAX, result or 0)
        uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, self.u32(sp))

    def wide_to_multi(self, args):
        text = self.wide(args[2]) + "\0" if args[3] == 0xFFFFFFFF else bytes(self.uc.mem_read(args[2], args[3] * 2)).decode("utf-16le")
        raw = text.encode("utf-8")
        if len(raw) > args[5]: return 0
        self.uc.mem_write(args[4], raw)
        return len(raw)

    def multi_to_wide(self, args):
        text = self.ansi(args[2]) + "\0" if args[3] == 0xFFFFFFFF else bytes(self.uc.mem_read(args[2], args[3])).decode("utf-8")
        raw = text.encode("utf-16le")
        if len(raw) // 2 > args[5]: return 0
        self.uc.mem_write(args[4], raw)
        return len(raw) // 2

    def set_color(self, args):
        previous, self.color = self.color, args[1]
        return previous

    def text_out(self, args):
        self.draws.append((bytes(self.uc.mem_read(args[3], args[4] * 2)).decode("utf-16le"), self.color))
        return 1

    def call(self, address, args):
        sp, stop = 0x28080000, 0x290FF000
        registers = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]
        initial = [0x1234, 0x2345, 0x3456, 0x4567]
        for reg, value in zip(registers, initial): self.uc.reg_write(reg, value)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.mem_write(sp, struct.pack("<" + "I" * (len(args) + 1), stop, *args))
        self.uc.emu_start(address, stop, count=500000)
        require(self.uc.reg_read(UC_X86_REG_EIP) == stop, "function missed return")
        require(self.uc.reg_read(UC_X86_REG_ESP) == sp + 4 + len(args) * 4, "stdcall stack mismatch")
        require([self.uc.reg_read(r) for r in registers] == initial, "callee-saved registers corrupted")
        return self.uc.reg_read(UC_X86_REG_EAX)

def verify(path, state, features, original):
    pe = pefile.PE(str(path))
    expected = (4 if "emoji" in features else 0) | (2 if "player-colors" in features else 0) | (1 if "extended-names" in features else 0)
    text = state["text"]
    raw = pe.get_data(text["stateVir"] - 0x400000 + 4, 4)
    require(int.from_bytes(raw, "little") == expected, "unexpected active text features")
    def imports(image):
        return [(d.dll, [(entry.name, entry.ordinal) for entry in d.imports]) for d in image.DIRECTORY_ENTRY_IMPORT]
    require(imports(pe) == imports(original), "custom imports added")
    stock_name = original.get_data(0xC14866 - 0x400000, 14)
    require((pe.get_data(0xC14866 - 0x400000, 14) != stock_name) == bool(expected & 1), "unselected name packets modified")
    require(bool(state["routes"]) == bool(expected & 3), "unexpected packet routes")
    m = TextMachine(pe)
    if expected & 4:
        emoji = state["emoji"]
        for token in [":red_heart:", "@red_heart@", "\u2764\ufe0f"]:
            raw = token.encode("utf-16le")
            m.uc.mem_write(0x29001000, raw + b"\0\0")
            row = m.call(emoji["matchVir"], [0x29001000, len(raw) // 2])
            require(row != 0 and m.wide(m.u32(row + 8)) == "red_heart.png", "emoji token lookup mismatch")
        raw = ":not_a_real_emoji:".encode("utf-16le")
        m.uc.mem_write(0x29001000, raw + b"\0\0")
        require(m.call(emoji["matchVir"], [0x29001000, len(raw) // 2]) == 0, "unknown emoji matched")
        # Test text policy with emoji declining the ordinary name label.
        m.stub(emoji["drawVir"], 24, lambda args: 0)
    if expected & 3:
        short, long = "Louis_Test", "Louis_Test_" + "Extended_Name_" * 5
        m.uc.mem_write(0x29002000, short.encode() + b"\0")
        m.uc.mem_write(0x29003000, long.encode() + b"\0")
        m.call(text["putVir"], [0x29002000, 0x29003000, 0, 0, 0x33CC66])
        row = m.call(text["lookupVir"], [0x29002000])
        require(row and m.ansi(row + 144) == long and m.u32(row + 12) == 0x33CC66, "entity map mismatch")
        raw = short.encode("utf-16le")
        m.uc.mem_write(0x29004000, raw + b"\0\0")
        for color in [0xFFFFFF, 0]:
            m.color, m.draws = color, []
            m.call(text["textOutVir"], [1, 20, 30, 0x29004000, len(raw) // 2])
            expected_color = 0x33CC66 if expected & 2 and color else color
            require(m.draws == [(long if expected & 1 else short, expected_color)], "text policy/dark pass changed")
            require(m.color == color, "HDC color was not restored")
    result = {"features": expected, "generated_code_execution": True, "imports_unchanged": True}
    if "ping" in features or "fps" in features:
        result["telemetry"] = verify_telemetry(path, {
            "state": state["telemetry"], "active": {"fps": "fps" in features, "ping": "ping" in features},
            "commands": state["commands"]}, original)
    return result

def run(args):
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    base, source = args.base.resolve(), args.source.resolve()
    baseline = out / "baseline"; reference(base, baseline, args.reference_ref)
    original = pefile.PE(str(source))
    results, packages = [], {}
    for case in args.case or CASES:
        features = CASES[case]
        key = "+".join(sorted(features))
        print("BUILD " + case, flush=True)
        if key not in packages:
            archive = out / (key + ".zip")
            package = build(features, archive)
            package["managed_file_count"] = len(package.pop("managed_files"))
            extracted = out / ("package-" + key)
            with zipfile.ZipFile(archive) as z: z.extractall(extracted)
            fixture = out / ("warp-" + key); common(base, fixture)
            installed = subprocess.run([sys.executable, str(extracted / "install.py"), "--warp", str(fixture)],
                                       capture_output=True)
            require(installed.returncode == 0, installed.stderr.decode(errors="replace"))
            manifest = json.loads((extracted / "package-manifest.json").read_text())
            packaged_scripts = {p.relative_to(fixture).as_posix() for p in (fixture / "Scripts/Patches").glob("*.qjs")}
            require(packaged_scripts == {p for p in manifest["managed_files"] if p.startswith("Scripts/Patches/")}, "unlisted patch files")
            if "extended-names" not in features:
                require(not (fixture / "Scripts/Patches/CustomExtName.qjs").exists() and
                        not (fixture / "Scripts/Patches/NamePackets128Static.qjs").exists(), "unpaid name adapters present")
            if features == ["emoji"]:
                require(packaged_scripts == {"Scripts/Patches/FluentEmoji.qjs", "Scripts/Patches/ExtNameTextStatic.qjs"}, "emoji includes unrelated feature code")
            packages[key] = {"archive": package, "fixture": fixture}
        fixture = packages[key]["fixture"]
        order = [FEATURES[f] for f in features]
        before, after = out / (case + "-before.exe"), out / (case + "-after.exe")
        warp_build(baseline, source, before, order)
        snapshot = warp_build(fixture, source, after, order, preserve_products=case == "production-bundle")
        row = {"case": case, "passed": False}
        try:
            require(before.read_bytes() == after.read_bytes(), "full PE differs from pre-extraction baseline")
            row.update(verification=verify(after, snapshot, features, original), sha256=sha(after), identical_to_baseline=True, passed=True)
            if case == "production-bundle":
                lock = json.loads((fixture / "louis-package-lock.json").read_text())
                require(sha(fixture / "Patches/LouisTelemetry.yml") == lock["managed_files"]["Patches/LouisTelemetry.yml"], "production metadata was modified")
                row["production_metadata_unchanged"] = True
            if "emoji" in features:
                delivered = after.parent / "BohEmoji/fluent"
                pngs = list((fixture / "Images/BohEmoji/fluent").glob("*.png"))
                require(all((delivered / p.name).is_file() and sha(delivered / p.name) == sha(p) for p in pngs),
                        "runtime emoji assets missing or changed")
                row["runtime_pngs_verified"] = len(pngs)
        except Exception as exc:
            row.update(passed=False, error=str(exc))
        results.append(row); print(json.dumps(row), flush=True)
    report = {"passed": all(r["passed"] for r in results), "client_profile": 20250716,
              "source_sha256": sha(source), "reference_ref": args.reference_ref, "cases": results,
              "packages": {k: v["archive"] for k, v in packages.items()}, "live_visual_accepted": False}
    (out / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["passed"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe")
    parser.add_argument("--reference-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    sys.exit(0 if run(args) else 1)
