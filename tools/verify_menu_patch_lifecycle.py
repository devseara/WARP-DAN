"""Build menu lifecycle cases with real WARP in an isolated repository copy.

The exported PE, not CACHE alone, must retain valid custom button callbacks.
No live client is started and no production source or user session is changed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import uuid

import pefile

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "baseline": "",
    "hide-show": 'apply("HideNewButtons"); apply("ShowNewButtons");',
    "hide-before-menu": 'remove("ROGlobalZeroMenu"); apply("HideNewButtons"); apply("ROGlobalZeroMenu");',
    "reapply-autohunt": 'remove("AutoCombatUI"); apply("AutoCombatUI");',
    "reapply-autosupport": 'remove("AutoSupportUI"); apply("AutoSupportUI");',
    "disable-autohunt": 'remove("AutoCombatUI");',
    "disable-autosupport": 'remove("AutoSupportUI");',
    "disable-item": 'remove("ItemCollectionUI");',
    "disable-all": 'remove("AutoSupportUI"); remove("AutoCombatUI"); remove("ItemCollectionUI");',
    "show-disabled": 'remove("AutoSupportUI"); remove("AutoCombatUI"); remove("ItemCollectionUI"); apply("ShowNewButtons");',
    "reapply-item": 'remove("ItemCollectionUI"); apply("ItemCollectionUI");',
    "reapply-all": 'remove("AutoSupportUI"); remove("AutoCombatUI"); remove("ItemCollectionUI"); apply("ItemCollectionUI"); apply("AutoCombatUI"); apply("AutoSupportUI");',
    "reapply-both": 'remove("AutoSupportUI"); remove("AutoCombatUI"); apply("AutoCombatUI"); apply("AutoSupportUI");',
}

PROBE = r'''/*
 * Description: Isolated 2025-07-16 native WARP menu lifecycle probe.
 */
TestMenuLifecycle = function(_) {
	const probeOwner = Exe.ActivePatch;
	const functions = {AutoCombatUI, AutoSupportUI, ROGlobalZeroUITheme,
		ItemCollectionUI, ROGlobalZeroMenu, HideNewButtons, ShowNewButtons};
	const apply = function(name) {
		Exe.SetActivePatch(name);
		Warp.SetPatchState(name, true);
		functions[name].call(functions[name], name);
		Exe.ActivePatch = probeOwner;
	};
	const remove = function(name) {
		Exe.SetActivePatch(name);
		if (typeof functions[name].cleanup === "function") functions[name].cleanup(name);
		Exe.ClearPatch();
		Warp.SetPatchState(name, false);
		Exe.ActivePatch = probeOwner;
	};
	let constructionError = null;
	let before = null;
	try {
		before = JSON.parse(JSON.stringify({
			hunt: CACHE.get("AutoCombatUI.MenuButton.v1"),
			support: CACHE.get("AutoSupportUI.MenuButton.v1")
		}));
		ACTION
	} catch (error) { constructionError = String(error); }
	const marker = new TextFile(MARKER, "w");
	if (!marker.Valid) throw Error("menu lifecycle marker unavailable");
	marker.WriteLine(JSON.stringify({
		token: TOKEN, constructionError, before,
		hunt: CACHE.get("AutoCombatUI.MenuButton.v1"),
		support: CACHE.get("AutoSupportUI.MenuButton.v1"),
		item: CACHE.get("ItemCollectionUI.MenuButton.v1"),
		visibility: CACHE.get("NewButtonVisibility.CustomVisibility.v1"),
		peer: CACHE.get("AutoCombatUI.LifecycleHooks.v1"),
		events: CACHE.get("PatchDiagnostics.Events")
	}));
	marker.Close(); Exe.ActivePatch = probeOwner; return true;
};
TestMenuLifecycle.validate = function() { return true; };
MenuLifecycleProbe = TestMenuLifecycle;
'''


def check_pe(path, state, case):
    pe = pefile.PE(str(path), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase

    def read(va, length):
        try:
            return pe.get_data(va - base, length)
        except pefile.PEFormatError:
            return b""

    def u32(va):
        raw = read(va, 4)
        return struct.unpack("<I", raw)[0] if len(raw) == 4 else 0

    menu = next(e["value"] for e in reversed(state["events"])
                if e["topic"] == "ROGlobalZeroMenu.QjsOnly")
    if u32(menu["drawVtableVir"]) != menu["drawWrapperVir"]:
        raise RuntimeError("Exported menu draw vtable does not target the recorded menu generation")
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EAX

    def execute_route(entry, target, pop_bytes):
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        mapped = pe.get_memory_mapped_image()
        u.mem_map(base, (len(mapped) + 4095) & ~4095)
        u.mem_write(base, mapped)
        stack, stop = 0x60000000, 0x60001000
        u.mem_map(stack, 0x4000)
        esp = stack + 0x800
        u.mem_write(esp, struct.pack('<I', stop) + b'A' * pop_bytes)
        u.reg_write(UC_X86_REG_ESP, esp)
        u.reg_write(UC_X86_REG_EBP, 0x12345678)
        hits = []
        if target:
            u.mem_write(target, b'\xc2' + struct.pack('<H', pop_bytes if entry == state['peer']['scalarSenderVir'] else 0))
        def step(uc, address, size, user):
            if address == target: hits.append(address)
            if address == stop: uc.emu_stop()
        u.hook_add(UC_HOOK_CODE, step)
        u.emu_start(entry, 0, count=1000)
        assert u.reg_read(UC_X86_REG_ESP) == esp + 4 + pop_bytes, 'callback stack imbalance'
        assert u.reg_read(UC_X86_REG_EBP) == 0x12345678, 'callback frame clobbered'
        assert len(hits) == bool(target), 'callback did not call exactly the published target'
        return True

    disabled = {
        'disable-autohunt': {'hunt'}, 'disable-autosupport': {'support'},
        'disable-item': {'item'}, 'disable-all': {'hunt','support','item'},
        'show-disabled': {'hunt','support','item'}
    }.get(case, set())
    peer = state['peer']['scalarSenderVir']
    peer_target = u32(peer - 4)
    assert (peer_target == 0) == ('hunt' in disabled), 'peer callback retained a removed producer'
    assert read(peer, 7) == b'\xa1' + struct.pack('<I', peer-4) + b'\x85\xc0', 'peer thunk address changed'
    if peer_target: assert read(peer_target, 8) != bytes(8), 'peer points to cleared code'
    execute_route(peer, peer_target, 12)
    rows = []
    # Derive all three cloned child vtables from their emitted ensure checks.
    import re
    raw = path.read_bytes()
    children = {}
    for match in re.finditer(rb"\x81\x3F(....)\x0F\x85....\x81\x7F\x2C(....)", raw, re.DOTALL):
        va = base + pe.get_rva_from_offset(match.start())
        if not menu["autoHunt"]["ensureVir"] <= va < menu["reflowVir"]:
            continue
        vt, child = struct.unpack("<I", match[1])[0], struct.unpack("<I", match[2])[0]
        if child in (0x3F2, 0x3F4, 0x3F5):
            if child in children:
                raise RuntimeError(f"Ambiguous child {child:#x}")
            children[child] = vt
    for label, key, child in (("Auto Hunt", "hunt", 0x3F2),
                              ("AutoSupport", "support", 0x3F5),
                              ("Item Collection", "item", 0x3F4)):
        bridge = state[key]
        mouse_up = u32(children[child] + 31 * 4)
        head = read(mouse_up, 24)
        if head.startswith(bytes.fromhex("55 8b ec e8")):
            target = mouse_up + 8 + struct.unpack_from("<i", head, 4)[0]
        elif head.startswith(bytes.fromhex("55 8b ec a1")):
            target = u32(struct.unpack_from("<I", head, 4)[0])
        else:
            raise RuntimeError(f"Unknown {label} mouse-up ABI at {mouse_up:#x}")
        target_head = read(target, 25)
        if child == 0x3F4:
            valid_entry = target_head.startswith(bytes.fromhex("9c 60 6a 00 6a 00 6a 00 6a 01 e8"))
        else:
            valid_entry = bool(re.fullmatch(
                rb"\xFF\x15....\x83\xC0.\xA3....\xC7\x05....\x01\0\0\0\xC3",
                target_head, re.DOTALL))
        if key in disabled:
            valid_entry = target == 0
        expected_visible = 0 if case == "hide-before-menu" or (key in disabled and case != "show-disabled") else 1
        execute_route(mouse_up, target, 8)
        actual_visible = u32(bridge["visibleVir"])
        rows.append({"button": label, "child": hex(child), "mouse_up": hex(mouse_up),
                     "emitted_target": hex(target), "published_target": hex(bridge["requestVir"]),
                     "target_bytes": target_head.hex(), "entry_valid": valid_entry,
                     "target_matches_current": target == (0 if key in disabled else bridge["requestVir"]),
                     "visible": actual_visible, "expected_visible": expected_visible})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    # A fresh output directory prevents old exports/markers being accepted.
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / "warp-fixture"
    fixture.mkdir()
    for name in ("win32", "Scripts", "Tables", "Patches", "Inputs", "Languages", "Styles"):
        shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "Patches.yml", fixture / "Patches.yml")
    shutil.copytree(ROOT / "Assets", fixture / "Assets")
    with (fixture / "Tables/Patch.yml").open("a", encoding="utf-8") as stream:
        stream.write("\n65001 : TestMenuLifecycle\n")
    with (fixture / "Patches/Premium.yml").open("a", encoding="utf-8") as stream:
        stream.write("\nMenuLifecycleProbe:\n    title: Menu lifecycle probe\n    patches:\n"
                     "        - TestMenuLifecycle:\n            title: Test menu lifecycle\n"
                     "            recommend: no\n            author: WARP diagnostics\n"
                     "            desc: Isolated menu lifecycle regression.\n")
    results = []
    for case in args.case or CASES:
        print("BUILD " + case, flush=True)
        target, marker = output / f"{case}.exe", output / f"{case}-state.json"
        token = uuid.uuid4().hex
        code = PROBE.replace("ACTION", CASES[case]).replace("TOKEN", json.dumps(token))
        code = code.replace("MARKER", json.dumps(marker.as_posix()))
        (fixture / "Scripts/Patches/MenuLifecycleProbe.qjs").write_bytes(code.replace("\n", "\r\n").encode("utf-8"))
        hidden = ["Battleground", "Twitter (SNS)", "Booking"]
        if case == "hide-before-menu":
            hidden += ["Auto Hunt", "AutoSupport", "Item Collection"]
        inputs = {
            "$copyAutoSupportAssets": {"data": "", "display": "false", "type": 10},
            "$copyItemCollectionAssets": {"data": "", "display": "false", "type": 10},
            "$newHiddenButtons": {"data": "", "display": [{"type": 10, "value": x} for x in hidden]},
            "$newShownButtons": {"data": "", "display": [{"type": 10, "value": x} for x in ("Auto Hunt", "AutoSupport", "Item Collection")]},
        }
        profile = output / f"{case}.yml"
        patches = ["AutoCombatUI", "AutoSupportUI", "ROGlobalZeroUITheme", "ItemCollectionUI"]
        patches += ["ROGlobalZeroMenu", "TestMenuLifecycle"]
        profile.write_text("from: " + json.dumps(str(source)) + "\nto: " + json.dumps(str(target)) +
                           "\ninputs: " + json.dumps(inputs) + "\npatches:\n" +
                           "".join("    - " + name + "\n" for name in patches), encoding="utf-8")
        process = subprocess.run([str(fixture / "win32/WARP_console.exe"), "-using", str(profile)],
                                 cwd=fixture, capture_output=True, timeout=180)
        (output / f"{case}.log").write_bytes(process.stdout + process.stderr)
        row = {"case": case, "returncode": process.returncode, "passed": False}
        if process.returncode == 0 and marker.is_file() and target.is_file():
            state = json.loads(marker.read_text(encoding="utf-8"))
            if state["token"] != token:
                raise RuntimeError("Stale WARP marker")
            row["construction_error"] = state["constructionError"]
            if state["constructionError"] is None:
                try:
                    row["buttons"] = check_pe(target, state, case)
                    row["passed"] = all(b["entry_valid"] and b["target_matches_current"] and
                                        b["visible"] == b["expected_visible"] for b in row["buttons"])
                except (KeyError, RuntimeError, StopIteration, AssertionError) as exc:
                    row["inspection_error"] = str(exc)
                row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        results.append(row)
        print(json.dumps(row), flush=True)
    report = {"source": str(source), "cases": results,
              "passed": all(r["passed"] for r in results)}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
