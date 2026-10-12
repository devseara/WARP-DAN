"""Build isolated customer packages with real WARP and execute the generated x86."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid
import zipfile
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
from package_louis_patches import build, ROOT

SOURCE_NAME = "2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe"
CASES = {
    "ping-only": (["ping"], 'apply("PingOverlay");'),
    "fps-only": (["fps"], 'apply("FpsOverlay");'),
    "fps-ping": (["fps", "ping"], 'apply("FpsOverlay"); apply("PingOverlay");'),
    "ping-fps": (["fps", "ping"], 'apply("PingOverlay"); apply("FpsOverlay");'),
    "remove-fps": (["fps", "ping"], 'apply("FpsOverlay"); apply("PingOverlay"); remove("FpsOverlay");'),
    "remove-ping": (["fps", "ping"], 'apply("PingOverlay"); apply("FpsOverlay"); remove("PingOverlay");'),
    "reapply-ping": (["fps", "ping"], 'apply("FpsOverlay"); apply("PingOverlay"); remove("PingOverlay"); apply("PingOverlay");'),
    "remove-all": (["fps", "ping"], 'apply("PingOverlay"); apply("FpsOverlay"); remove("PingOverlay"); remove("FpsOverlay");'),
    "reapply-all": (["fps", "ping"], 'apply("PingOverlay"); remove("PingOverlay"); apply("FpsOverlay"); apply("PingOverlay");'),
    "failed-ping": (["fps", "ping"], 'apply("FpsOverlay"); failPing();'),
}
PROBE = r'''/*
 * Disposable 2025-07-16 telemetry lifecycle probe.
 */
TestTelemetry = function(_) {
    const probeOwner = Exe.ActivePatch;
    const events = [];
    const expectedActive = {fps: false, ping: false};
    const feature = name => name === "PingOverlay" ? PingOverlay : FpsOverlay;
    const snapshot = function() {
        return JSON.parse(JSON.stringify({
            state: CACHE.get("NativeTelemetryOverlay.State") ?? null,
            active: expectedActive,
            selection: {fps: Warp.GetPatchState("FpsOverlay"), ping: Warp.GetPatchState("PingOverlay")},
            commands: CACHE.get("CustomSlashCommand.RegistryByOwner") ?? {}
        }));
    };
    const apply = function(name) {
        Exe.SetActivePatch(name); Warp.SetPatchState(name, true);
        try { feature(name)(name); expectedActive[name === "PingOverlay" ? "ping" : "fps"] = true; }
        finally { Exe.ActivePatch = probeOwner; }
        events.push(snapshot());
    };
    const remove = function(name) {
        Exe.SetActivePatch(name); feature(name).cleanup(name);
        Exe.ClearPatch(); Warp.SetPatchState(name, false); Exe.ActivePatch = probeOwner;
        expectedActive[name === "PingOverlay" ? "ping" : "fps"] = false;
        events.push(snapshot());
    };
    const failPing = function() {
        const saved = NativeTelemetryOverlay.installPingCapture;
        NativeTelemetryOverlay.installPingCapture = function() { throw Error("injected capture failure"); };
        let caught = false;
        try { apply("PingOverlay"); }
        catch (error) { caught = String(error).includes("injected capture failure"); }
        finally {
            NativeTelemetryOverlay.installPingCapture = saved;
            Exe.SetActivePatch("PingOverlay"); Exe.ClearPatch();
            if (Warp.GetPatchState("PingOverlay")) Warp.SetPatchState("PingOverlay", false);
            Exe.ActivePatch = probeOwner;
        }
        if (!caught) throw Error("failure injection did not run");
        expectedActive.ping = false; // UI selection is not proof of successful installation.
        events.push(snapshot());
    };
    ACTION
    const result = snapshot(); result.events = events; result.token = TOKEN;
    result.loadedChannels = Object.keys(NativeTelemetryOverlay.Channels);
    const file = new TextFile(MARKER, "w");
    if (!file.Valid) throw Error("marker open failed");
    file.WriteLine(JSON.stringify(result)); file.Close();
    return true;
};
TestTelemetry.validate = function() { return true; };
TelemetryProbe = TestTelemetry;
'''

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def fixture_from(base, fixture):
    fixture.mkdir(parents=True)
    for directory in ("win32", "Tables", "Languages", "Styles", "Fonts", "Inputs", "Scripts/Init", "Scripts/Support"):
        shutil.copytree(base / directory, fixture / directory)
    (fixture / "Scripts/Patches").mkdir()
    (fixture / "Patches").mkdir()
    (fixture / "Patches.yml").write_text("include:\n", encoding="utf-8")

def inputs():
    result = {
        "$telemetryFontName": {"data": "417269616c00", "display": "Arial", "type": 10},
        "$telemetryFontSize": {"data": "0e000000", "display": 14, "type": 2},
    }
    for name, y in (("ping", 66), ("fps", 50)):
        result["$" + name + "OverlayXY"] = {
            "data": struct.pack("<hh", -195, y).hex(),
            "display": [{"type": 2, "value": -195}, {"type": 2, "value": y}],
        }
    return result

class Machine:
    def __init__(self, path):
        self.pe = pefile.PE(str(path))
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095
        self.uc.mem_map(0x400000, size)
        self.uc.mem_write(0x400000, self.pe.get_memory_mapped_image())
        for base, size in ((0x28000000, 0x100000), (0x29000000, 0x100000), (0x2A000000, 0x10000)):
            self.uc.mem_map(base, size)
        self.options = {10002: 1, 10003: 1}
        self.tick, self.draws, self.dc_balance, self.color = 1000, [], 0, 0xFFFFFF
        self.callbacks = {}
        self.uc.hook_add(UC_HOOK_CODE, self.hook)
        self.stub(0x68EA70, 0, lambda a: self.options.get(self.u32(self.uc.reg_read(UC_X86_REG_ESP) + 4), 0))
        self.stub(0x68FD50, 0, self.set_option)
        self.import_stub(0xFC120C, 0, lambda a: self.tick)
        self.import_stub(0xFC1268, 4, lambda a: 1)
        self.import_stub(0xFC1390, 8, lambda a: 0x2A00F000)
        self.stub(0x2A00F000, 8, self.release_dc)
        self.import_stub(0xFC16B8, 8, self.client_rect)
        self.import_stub(0xFC16D8, 4, self.get_dc)
        self.import_stub(0xFC10E8, 8, lambda a: 1)
        self.import_stub(0xFC1114, 56, lambda a: 0x700)
        self.import_stub(0xFC1120, 8, lambda a: 0x701)
        self.import_stub(0xFC10E0, 8, self.set_color)
        self.import_stub(0xFC10D8, 20, self.text_out)

    def u32(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def put(self, address, value):
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def stub(self, address, pop, callback):
        self.callbacks[address] = (pop, callback)
        self.uc.mem_write(address, b"\xC3")

    def import_stub(self, iat, pop, callback):
        address = 0x2A000000 + len(self.callbacks) * 0x100
        self.stub(address, pop, callback)
        self.put(iat, address)

    def hook(self, uc, address, size, user):
        if address in self.callbacks:
            pop, callback = self.callbacks[address]
            sp = uc.reg_read(UC_X86_REG_ESP)
            value = callback([self.u32(sp + 4 + off) for off in range(0, pop, 4)])
            uc.reg_write(UC_X86_REG_EAX, value or 0)
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, self.u32(sp))

    def set_option(self, args):
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        self.options[self.u32(sp + 4)] = self.u32(sp + 8)
        return 1

    def client_rect(self, args):
        self.uc.mem_write(args[1], struct.pack("<iiii", 0, 0, 1280, 720))
        return 1

    def get_dc(self, args):
        self.dc_balance += 1
        return 0x600

    def release_dc(self, args):
        self.dc_balance -= 1
        return 1

    def set_color(self, args):
        old, self.color = self.color, args[1]
        return old

    def text_out(self, args):
        self.draws.append({"text": bytes(self.uc.mem_read(args[3], args[4])).decode("ascii"),
                          "x": args[1], "y": args[2], "color": self.color})
        return 1

    def run(self, start, stop, eax=0x12345678):
        registers = [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                     UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP]
        values = [eax, 0x1234, 0x2345, 0x3456, 0x29000000, 0x4567, 0x28008000, 0x28008000]
        for register, value in zip(registers, values):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_X86_REG_EFLAGS, 0x202)
        self.put(0x29000000, 0x555)
        self.uc.emu_start(start, stop, count=100000)
        require(self.uc.reg_read(UC_X86_REG_EIP) == stop, "execution did not reach native continuation")
        return values, [self.uc.reg_read(r) for r in registers]

    def toggle(self, address, option):
        before = self.options[option]
        self.put(0x28008000, 0x2A00FF00)
        self.run(address, 0x2A00FF00)
        require(self.options[option] == 1 - before, "slash toggle did not invert native option")

    def dispatch(self, command, settings=False):
        # Stock unknown-command suffix: POP EDI; MOV EAX,3, then POP ESI.
        sp, bp, caller, text = 0x28007F00, 0x28008000, 0x28008200, 0x29002000
        self.uc.mem_write(text, command.encode("ascii") + b"\0")
        self.put(sp, 0x4567)
        self.put(bp, caller)
        self.put(bp + 8, text)
        self.put(caller + 4, 0x68FCE8 if settings else 0x500000)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_EBP, bp)
        self.uc.emu_start(0xD5CDF4, 0xD5CDFA, count=100000)
        require(self.uc.reg_read(UC_X86_REG_EIP) == 0xD5CDFA, "command dispatcher missed stock continuation")
        require(self.uc.reg_read(UC_X86_REG_ESP) == sp + 4, "command dispatcher stack mismatch")
        require(self.uc.reg_read(UC_X86_REG_EDI) == 0x4567, "command dispatcher lost saved EDI")
        return self.uc.reg_read(UC_X86_REG_EAX)

def verify_pe(path, snapshot, original):
    pe = pefile.PE(str(path))
    active = snapshot["active"]
    def data(va, size):
        return pe.get_data(va - 0x400000, size)
    def imports(image):
        return [(d.dll, tuple((e.name, e.ordinal) for e in d.imports)) for d in image.DIRECTORY_ENTRY_IMPORT]
    require(imports(pe) == imports(original), "telemetry changed the import table")
    for site, size, enabled in ((0x543441, 6, any(active.values())), (0xC9E8F8, 5, active["ping"])):
        require((data(site, size) != original.get_data(site - 0x400000, size)) == enabled, f"hook ownership mismatch: {site:x}")
    commands = [entry for group in snapshot["commands"].values() for entry in group]
    require(sorted(e["command"] for e in commands) == sorted("/" + n for n, yes in active.items() if yes),
            "removed command remains registered")
    require(original.get_data(0xD5CDF4 - 0x400000, 6) == bytes.fromhex("5F B8 03 00 00 00"),
            "unsupported command suffix profile")
    machine = Machine(path)
    for name, option in (("fps", 10002), ("ping", 10003)):
        before = machine.options.copy()
        require(machine.dispatch("/" + name, settings=True) == (option if active[name] else 3),
                "command option lookup is stale")
        require(machine.options == before, "settings lookup toggled an option")
        require(machine.dispatch("/" + name) == (0 if active[name] else 3),
                "removed command still executes")
        require(machine.options[option] == (0 if active[name] else 1), "command route toggled wrong option")
    require(machine.dispatch("/not_louis") == 3, "unknown command fallback changed")
    if not any(active.values()):
        require(snapshot["state"] is None, "removed shared state remains cached")
        return {"restored_stock": True, "removed_commands_inert": True}
    state = snapshot["state"]
    require(data(0x543441, 1) == b"\xE9", "missing Present JMP")
    target = 0x543446 + struct.unpack("<i", data(0x543442, 4))[0]
    require(target == state["presentVir"], "Present target is stale")
    require(data(target, 6) == bytes.fromhex("89 86 8C 06 00 00"), "stock store not replayed")
    machine.options = {10002: 1, 10003: 1}
    state_va = state["stateVir"]
    require(machine.u32(state_va) == int(active["fps"]), "FPS installed flag mismatch")
    require(machine.u32(state_va + 4) == int(active["ping"]), "Ping installed flag mismatch")
    if active["ping"]:
        before, after = machine.run(0xC9E8F8, 0xC9E8FD, 72)
        require(machine.u32(state_va + 36) == 72 and after[2] == 0x15FA3C0, "Ping capture/stock ECX mismatch")
        require(before[:2] + before[3:] == after[:2] + after[3:], "Ping capture corrupted registers")
    for tick in (1000, 1500, 2000):
        machine.tick = tick
        before, after = machine.run(0x543441, 0x543447)
        require(before == after and machine.uc.reg_read(UC_X86_REG_EFLAGS) == 0x202, "Present corrupted CPU state")
        require(machine.u32(0x2900068C) == before[0], "Present store was lost")
    require(machine.dc_balance == 0, "GetDC/ReleaseDC imbalance")
    texts = [d["text"] for d in machine.draws]
    require(any(t == "Ping: 72 ms" for t in texts) == active["ping"], "Ping draw mismatch")
    require(any(t == "FPS: 3" for t in texts) == active["fps"], "FPS sampling mismatch")
    require(machine.u32(state_va + 32) == (3 if active["fps"] else 0), "disabled FPS was sampled")
    if active["ping"]:
        require(any(d == {"text": "Ping: 72 ms", "x": 1085, "y": 66, "color": 0xFFFF}
                    for d in machine.draws), "Ping coordinates/color changed")
        for value, expected in ((50, 0xFF00), (100, 0xFFFF), (101, 0xFF)):
            machine.put(state_va + 36, value)
            machine.draws.clear()
            machine.run(0x543441, 0x543447)
            require(any(d["text"] == f"Ping: {value} ms" and d["color"] == expected for d in machine.draws),
                    "Ping threshold color mismatch")
    for entry in commands:
        machine.toggle(entry["targetVir"], entry["optionId"])
    machine.draws.clear()
    machine.run(0x543441, 0x543447)
    require(not machine.draws and machine.dc_balance == 0, "disabled overlays still draw")
    return {"channels": state["channels"], "registers_preserved": True, "draw_and_toggle_passed": True}

def run(base, source, output, selected=None):
    output.mkdir(parents=True, exist_ok=False)
    original = pefile.PE(str(source))
    packages, fixtures = {}, {}
    for features in (["ping"], ["fps"], ["fps", "ping"]):
        key = "-".join(sorted(features))
        archive = output / f"Louis-{key}-1.0.0.zip"
        packages[key] = build(features, archive)
        package = output / f"package-{key}"
        with zipfile.ZipFile(archive) as z:
            z.extractall(package)
        spec = importlib.util.spec_from_file_location("louis_install", package / "install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        fixture = output / f"warp-{key}"
        fixture_from(base, fixture)
        require(installer.install(package, fixture, check=True)["changes"], "dry run is empty")
        require(not (fixture / "louis-package-lock.json").exists(), "dry run mutated installation")
        installer.install(package, fixture)
        require(not installer.install(package, fixture)["changes"], "install is not idempotent")
        expected = {"CustomSlashCommand.qjs"} | {f.title() + "Overlay.qjs" for f in features}
        require({p.name for p in (fixture / "Scripts/Patches").glob("*.qjs")} == expected, "unpurchased scripts present")
        with (fixture / "Tables/Patch.yml").open("a") as f:
            f.write("\n65010 : TestTelemetry\n")
        with (fixture / "Patches/LouisTelemetry.yml").open("a") as f:
            f.write("\nTelemetryTest:\n    title: Verification\n    patches:\n        - TestTelemetry:\n"
                    "            title: Probe\n            recommend: no\n            author: Louis T Steinhil\n"
                    "            desc: Disposable lifecycle probe.\n")
        fixtures[key] = fixture
    results = []
    for name in selected or CASES:
        features, action = CASES[name]
        fixture = fixtures["-".join(sorted(features))]
        marker, target = output / f"{name}.json", output / f"{name}.exe"
        token = uuid.uuid4().hex
        code = PROBE.replace("ACTION", action).replace("TOKEN", json.dumps(token)).replace("MARKER", json.dumps(marker.as_posix()))
        (fixture / "Scripts/Patches/TelemetryProbe.qjs").write_bytes(code.replace("\n", "\r\n").encode("utf-8"))
        profile = output / f"{name}.yml"
        profile.write_text(f"from: {json.dumps(str(source))}\nto: {json.dumps(str(target))}\n"
                           f"inputs: {json.dumps(inputs())}\npatches:\n    - TestTelemetry\n", encoding="utf-8")
        process = subprocess.run([str(fixture / "win32/WARP_console.exe"), "-using", str(profile)],
                                 cwd=fixture, capture_output=True, timeout=90)
        log = process.stdout + process.stderr
        (output / f"{name}.log").write_bytes(log)
        row = {"case": name, "passed": False}
        try:
            errors = [line for line in log.decode(errors="replace").splitlines() if "-E-" in line]
            expected_errors = ["-E- Patch Error : 'PingOverlay' : Error: injected capture failure"] if name == "failed-ping" else []
            require(process.returncode == 0 and errors == expected_errors and b"Cancelled" not in log
                    and marker.is_file() and target.is_file(), "WARP probe failed; inspect case log")
            snapshot = json.loads(marker.read_text(encoding="utf-8"))
            require(snapshot["token"] == token, "stale marker")
            row["verification"] = verify_pe(target, snapshot, original)
            row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            row["passed"] = True
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)
        print(json.dumps(row), flush=True)
    report = {"passed": all(row["passed"] for row in results), "source": str(source),
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "base": str(base), "packages": packages, "cases": results, "live_visual_accepted": False}
    (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["passed"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / SOURCE_NAME)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    sys.exit(0 if run(args.base.resolve(), args.source.resolve(), args.output.resolve(), args.case) else 1)
