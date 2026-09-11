"""Build both Auto UIs with real WARP and verify emitted text and copied assets.

Runs only in a fresh Outputs fixture; never edits the user's active profile.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
import tempfile

import pefile
import unicorn as uc
from unicorn import x86_const as x86

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = json.loads((ROOT / "Inputs/AutoUI/languages.json").read_text(encoding="ascii"))
CHINESE = "Traditional Chinese"
LEGACY_CHINESE = "Chinese Traditional (Big5 / CP950)"
CASES = {"default": ("English", "English", None),
         "chinese-legacy": (LEGACY_CHINESE, LEGACY_CHINESE, 950),
         "chinese-alias": ("Chinese Traditional", "Chinese Traditional", 65001),
         "mixed-asian": ("Thai", "Korean", 65001),
         "mixed-latin": ("Brazilian Portuguese", "Japanese", 65001),
         "mixed-english": ("English", "Filipino", 65001),
         "mixed-reverse": ("Indonesian", "English", 65001)}
for language, spec in LANGUAGES.items():
    if language != "English":
        CASES[spec["locale"] + "-stock"] = (language, language, None)
        CASES[spec["locale"] + "-utf8"] = (language, language, 65001)
PROBE = '''/* Isolated Auto UI language/export regression. */
TestAutoUIEnd = function(_) {
	const file = new TextFile(MARKER, "w");
	if (!file.Valid) throw Error("AutoUI probe marker unavailable");
	file.WriteLine(JSON.stringify({strings: typeof AutoUIProbeRows === "undefined" ? [] : AutoUIProbeRows, initializers: typeof AutoUIProbeInitializers === "undefined" ? {} : AutoUIProbeInitializers}));
	file.Close();
	return true;
};
TestAutoUIEnd.validate = () => true;
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_runtime(pe, probe, catalogs, configured):
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    base = pe.OPTIONAL_HEADER.ImageBase
    machine.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    machine.mem_write(base, pe.get_memory_mapped_image())
    stack, stop = 0x60000000, 0x70000000
    machine.mem_map(stack, 0x10000)
    machine.mem_map(stop, 0x1000)
    registers = [x86.UC_X86_REG_EAX, x86.UC_X86_REG_EBX, x86.UC_X86_REG_ECX,
                 x86.UC_X86_REG_EDX, x86.UC_X86_REG_ESI, x86.UC_X86_REG_EDI,
                 x86.UC_X86_REG_EBP]
    for name, initializer in probe["initializers"].items():
        if initializer is None:
            continue
        rows = [r for r in probe["strings"] if r["name"] == name]
        language = rows[0]["language"]
        spec = LANGUAGES[language]
        catalog = catalogs[language]
        assert initializer["count"] == len(rows)
        spans = [(row["vir"], row["vir"] + row["size"]) for row in rows]
        spans.append((initializer["cacheVir"], initializer["cacheVir"] + 4))
        for begin, end in spans:
            section = pe.get_section_by_rva(begin - base)
            assert section and section.Characteristics & 0x80000000, "text buffers must be writable"
            assert end - base <= section.VirtualAddress + section.Misc_VirtualSize
        mapper = bytes(machine.mem_read(0xA6F060, 12))
        for cp in (None, spec["codePage"], 65001, 1251, 65001):
            # Execute the actual generated x86 routine, varying the runtime
            # mapper to cover late selection/reapplication and safe fallback.
            machine.mem_write(0xA6F060, mapper if cp is None else b"\xb8" + struct.pack("<I", cp) + b"\xc3")
            resolved_cp = (configured or spec["codePage"]) if cp is None else cp
            machine.ctl_remove_cache(0xA6F060, 0xA6F066)
            for repeat in range(2):
                sp = stack + 0x8000
                machine.mem_write(sp, struct.pack("<I", stop))
                machine.reg_write(x86.UC_X86_REG_ESP, sp)
                expected_regs = [0x12340000 + i * 0x111 for i in range(len(registers))]
                for reg, value in zip(registers, expected_regs):
                    machine.reg_write(reg, value)
                machine.reg_write(x86.UC_X86_REG_EFLAGS, 0x602)  # Includes caller DF.
                writes = []
                hook = machine.hook_add(uc.UC_HOOK_MEM_WRITE,
                    lambda m, access, address, size, value, extra: writes.append((address, size)))
                machine.emu_start(initializer["vir"], stop, count=100000)
                machine.hook_del(hook)
                assert [machine.reg_read(r) for r in registers] == expected_regs
                assert machine.reg_read(x86.UC_X86_REG_ESP) == sp + 4
                assert machine.reg_read(x86.UC_X86_REG_EFLAGS) == 0x602
                for row in rows:
                    expected = (catalog[row["text"]].encode("utf-8" if resolved_cp == 65001 else spec["codec"])
                                if resolved_cp in (spec["codePage"], 65001) else row["text"].encode("ascii"))
                    data = bytes(machine.mem_read(row["vir"], row["size"]))
                    assert data.split(b"\0", 1)[0] == expected, (cp, row)
                for address, size in writes:
                    assert any(begin <= address and address + size <= end
                               for begin, end in spans + [(stack, stack + 0x10000)]), "write outside UI buffers"
                if repeat:
                    assert all(stack <= address < stack + 0x10000 for address, size in writes), "cached text copied again"
        machine.mem_write(0xA6F060, mapper)
        machine.ctl_remove_cache(0xA6F060, 0xA6F06C)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    source = args.source.resolve()
    output = Path(tempfile.mkdtemp(prefix="auto-ui-warp-", dir=ROOT / "Outputs"))
    fixture = output / "fixture"
    fixture.mkdir()
    for name in ("win32", "Scripts", "Tables", "Patches", "Inputs", "Languages", "Styles", "Assets"):
        shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "Patches.yml", fixture / "Patches.yml")
    with (fixture / "Tables/Patch.yml").open("a", encoding="utf-8") as f:
        f.write("\n65002 : TestAutoUIEnd\n")
    with (fixture / "Patches/Premium.yml").open("a", encoding="utf-8") as f:
        f.write("\nAutoUIProbe:\n    title: Auto UI probe\n    patches:\n")
        f.write("        - TestAutoUIEnd:\n            title: Auto UI probe\n            recommend: no\n"
                "            author: WARP diagnostics\n            desc: Isolated language verification.\n")
    # Instrument inside each patch's lexical scope; WARP isolates its const data.
    for name in ("AutoCombatUI", "AutoSupportUI"):
        script = fixture / f"Scripts/Patches/{name}.qjs"
        text = script.read_text(encoding="utf-8")
        c = name + "Static"
        original = f"""{c}.allocateUiString = function(text)
{{
	return AutoUILanguage.allocate({c}, text);
}};"""
        instrumented = f"""{c}.allocateUiString = function(text)
{{
	const result = AutoUILanguage.allocate({c}, text);
	if (typeof AutoUIProbeRows === "undefined") AutoUIProbeRows = [];
	AutoUIProbeRows.push({{name: "{name}", text, language: {c}.Language, fontSelector: {c}.FontSelector, vir: result.vir, size: result.size}});
	return result;
}};"""
        assert original in text
        text = text.replace(original, instrumented)
        marker = f"{c}.TextInitializer = AutoUILanguage.buildInitializer({c});"
        text = text.replace(marker, marker + f"""
	if (typeof AutoUIProbeInitializers === "undefined") AutoUIProbeInitializers = {{}};
	AutoUIProbeInitializers["{name}"] = {c}.TextInitializer;
""")
        script.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    catalogs = {name: json.loads((ROOT / f"Inputs/AutoUI/{spec['locale']}.json").read_text(encoding="utf-8"))
                for name, spec in LANGUAGES.items() if name != "English"}
    cases = CASES
    results = []
    for case in args.case or cases:
        folder = output / case
        folder.mkdir()
        target, marker = folder / "client.exe", folder / "strings.json"
        code = PROBE.replace("MARKER", json.dumps(marker.as_posix()))
        (fixture / "Scripts/Patches/AutoUIProbe.qjs").write_bytes(code.replace("\n", "\r\n").encode("utf-8"))
        inputs = {"$copyAutoSupportAssets": {"data": "", "display": "false", "type": 10}}
        for key, language in zip(("$autoCombatUILanguage", "$autoSupportUILanguage"), cases[case][:2]):
            if case != "default":
                inputs[key] = {"data": "", "display": language, "type": 10}
        code_page = cases[case][2]
        patches = ["AutoCombatUI", "AutoSupportUI", "TestAutoUIEnd"]
        if code_page:
            inputs["$customCodePage"] = {"data": code_page.to_bytes(4, "little").hex(),
                                        "display": code_page, "type": 2}
            patches.append("CustomCodePage")  # Deliberately listed after the UIs.
        profile = folder / "profile.yml"
        profile.write_text("from: " + json.dumps(str(source)) + "\nto: " + json.dumps(str(target)) +
                           "\ninputs: " + json.dumps(inputs) + "\npatches:\n" +
                           "".join("    - " + name + "\n" for name in patches),
                           encoding="utf-8")
        process = subprocess.run([str(fixture / "win32/WARP_console.exe"), "-using", str(profile)],
                                 cwd=fixture, capture_output=True, timeout=180,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        (folder / "warp.log").write_bytes(process.stdout + process.stderr)
        assert process.returncode == 0 and b"-E-" not in process.stdout + process.stderr and target.is_file() and marker.is_file(), f"WARP failed: {folder}"
        probe = json.loads(marker.read_text(encoding="utf-8"))
        records = probe["strings"]
        pe = pefile.PE(str(target))
        for record in records:
            expected_language = cases[case][0 if record["name"] == "AutoCombatUI" else 1]
            if expected_language in (LEGACY_CHINESE, "Chinese Traditional"):
                expected_language = CHINESE
            assert record["language"] == expected_language, record
            assert record["fontSelector"] == LANGUAGES[expected_language]["fontSelector"], record
            # Exported buffers start with readable English. Native UI entry
            # points select an encoding after all binary patches are applied.
            actual = pe.get_data(record["vir"] - pe.OPTIONAL_HEADER.ImageBase, record["size"])
            assert actual.split(b"\0", 1)[0] == record["text"].encode("ascii"), record
        verify_runtime(pe, probe, catalogs, code_page)
        assert len(records) > 200, "Probe did not capture both UIs"
        # Every AutoSupport BMP plus its native STR/TGA effect pack must deploy,
        # even though this profile retained the obsolete false copy preference.
        assets = ROOT / "Assets/AutoSupportUI/autosupport"
        ui_prefix = bytes.fromhex("C0 AF C0 FA C0 CE C5 CD C6 E4 C0 CC BD BA").decode("latin1")
        copied = 0
        for asset in assets.rglob("*"):
            if not asset.is_file() or asset.suffix not in (".bmp", ".tga", ".str", ".bson"):
                continue
            relative = asset.relative_to(assets)
            destination = (folder / "data/texture" / relative if relative.parts[0] == "effect"
                           else folder / "data/texture" / ui_prefix / "autosupport" / relative)
            assert destination.is_file() and sha(destination) == sha(asset), destination
            copied += 1
        # Only the explicitly selected existing CustomCodePage patch may alter
        # global encoding. The UI fix leaves shared draw/font code untouched.
        pristine = pefile.PE(str(source))
        mapper = pe.get_data(0xA6F060 - pe.OPTIONAL_HEADER.ImageBase, 12)
        if code_page:
            assert mapper[:6] == b"\xb8" + code_page.to_bytes(4, "little") + b"\xc3"
        else:
            assert mapper == pristine.get_data(0xA6F060 - pristine.OPTIONAL_HEADER.ImageBase, 12)
        for va, size in ((0x00A25A70, 160), (0x00A21C90, 190),
                         (0x005474A0, 350), (0x00547600, 250),
                         (0x011DCF30, 48), (0x00544BA0, 224)):
            rva = va - pe.OPTIONAL_HEADER.ImageBase
            assert pe.get_data(rva, size) == pristine.get_data(rva, size)
        row = {"case": case, "code_page": code_page, "passed": True, "strings": len(records), "copied_assets": copied,
               "sha256": sha(target), "output": str(target)}
        results.append(row)
        print(json.dumps(row), flush=True)
    (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: real WARP language/export matrix: {output}")


if __name__ == "__main__":
    main()
