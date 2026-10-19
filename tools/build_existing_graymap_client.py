"""Add GrayMap to a previously patched client without rebuilding its features.

Uses an isolated real WARP fixture, chains the existing static slash dispatcher,
repairs WARP's section-header growth bug, then verifies all old mapped bytes.
This tool builds a candidate only; it never changes the game installation.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import pefile
from build_graymap import ROOT

PREPARE = r'''/* Incremental GrayMap dispatcher adapter; fixture-local. */
GrayMapChainPrepare = function(_) {
	CustomSlashCommand.register = function(owner, spec) {
		if (spec.command !== "/graymap" || !Number.isInteger(spec.targetVir))
			throw Error("Incremental adapter accepts only /graymap");
		const b = [], fixups = [], labels = {};
		const emit = (...values) => b.push(...values);
		const u32 = v => emit(v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255);
		const rel = (op, target) => { emit(...op); fixups.push({at:b.length, target}); u32(0); };
		emit(0x9C, 0x60, 0x8B, 0x7D, 8); // save flags/all regs, command=[EBP+8]
		for (let i = 0; i <= spec.command.length; i++) {
			const value = i === spec.command.length ? 0 : spec.command.charCodeAt(i);
			if (i === 0) emit(0x80, 0x3F, value);
			else emit(0x80, 0x7F, i, value);
			rel([0x0F, 0x85], "fallback");
		}
		// The settings parser asks for a command's option ID; do not toggle.
		emit(0x8B, 0x45, 0, 0x81, 0x78, 4); u32(0x0068FCE8);
		rel([0x0F, 0x84], "fallback");
		emit(0x61, 0x9D);
		rel([0xE8], spec.targetVir);
		emit(0x5F, 0x33, 0xC0); // stock suffix's saved EDI, TT_OK
		rel([0xE9], 0x00D5CDFA);
		labels.fallback = b.length;
		emit(0x61, 0x9D);
		rel([0xE9], PREVIOUS_TARGET);
		const [phy, vir] = Exe.Allocate(b.length, 0x10);
		for (const f of fixups) {
			const target = typeof f.target === "string" ? vir + labels[f.target] : f.target;
			const v = (target - (vir + f.at + 4)) >>> 0;
			for (let i = 0; i < 4; i++) b[f.at+i] = (v >>> (8*i)) & 255;
		}
		Exe.SetHex(phy, b.map(v => v.toString(16).padStart(2,"0")).join(" "));
		Exe.SetJMP(Exe.Vir2Phy(0x00D5CDF4, CODE), vir, 0);
		const m = CACHE.get("GrayMap.Native.v1");
		m.dispatch = {phy, vir, size:b.length, site:0x00D5CDF4, previousVir:PREVIOUS_TARGET};
		CACHE.put("GrayMap.Native.v1", m);
		return true;
	};
	// WARP reloads script globals between top-level patch applications. Apply
	// the feature in this same evaluation so the adapter owns registration.
	const owner = Exe.ActivePatch;
	Exe.SetActivePatch("GrayMap"); Warp.SetPatchState("GrayMap", true);
	try { GrayMap("GrayMap"); }
	finally { Exe.ActivePatch = owner; }
	return true;
};
'''


def digest(b):
    return hashlib.sha256(b).hexdigest()


def build(source, out):
    original = source.read_bytes()
    old = pefile.PE(data=original)
    assert old.FILE_HEADER.Machine == 0x14C and old.OPTIONAL_HEADER.ImageBase == 0x400000
    site = 0xD5CDF4
    off = old.get_offset_from_rva(site - 0x400000)
    assert original[off] == 0xE9, 'expected an existing static slash dispatcher'
    previous = site + 5 + struct.unpack_from('<i', original, off + 1)[0]
    prior_dispatch_section = old.get_section_by_rva(previous - 0x400000)
    assert prior_dispatch_section and prior_dispatch_section.Characteristics & 0x20000000
    assert original[off + 5] == 0, 'unsupported native command suffix'
    out.mkdir(parents=True, exist_ok=False)
    (out / 'before').mkdir()
    shutil.copy2(source, out / 'before' / source.name)
    data = bytearray(original)
    prior_diff = [s for s in old.sections if s.Name.rstrip(b'\0') == b'.xdiff']
    assert len(prior_diff) == 1
    assert not any(s.Name.rstrip(b'\0') in (b'.gmprev', b'.graymap') for s in old.sections)
    data[prior_diff[0].get_file_offset() : prior_diff[0].get_file_offset() + 8] = b'.gmprev\0'
    inp = out / 'incremental-input.exe'
    inp.write_bytes(data)
    fixture = out / 'warp-fixture'
    fixture.mkdir()
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Languages', 'Styles'):
        shutil.copytree(ROOT / name, fixture / name)
    (fixture / 'Inputs').mkdir()
    shutil.copytree(ROOT / 'Assets/GrayMap', fixture / 'Assets/GrayMap')
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    (fixture / 'Scripts/Patches/GrayMapChainPrepare.qjs').write_bytes(
        PREPARE.replace('PREVIOUS_TARGET', str(previous)).replace('\n', '\r\n').encode()
    )
    marker = out / 'manifest.json'
    probe = '''/* Incremental GrayMap manifest. */
GrayMapChainProbe = function(_) {
    const f = new TextFile(MARKER, "w");
    if (!f.Valid) throw Error("Cannot open GrayMap manifest");
    f.WriteLine(JSON.stringify({graymap:CACHE.get("GrayMap.Native.v1")}));
    f.Close(); return true;
};
'''.replace(
        'MARKER', json.dumps(marker.as_posix())
    )
    (fixture / 'Scripts/Patches/GrayMapChainProbe.qjs').write_bytes(
        probe.replace('\n', '\r\n').encode()
    )
    with (fixture / 'Tables/Patch.yml').open('a') as f:
        f.write('\n65004 : GrayMapChainPrepare\n65005 : GrayMapChainProbe\n')
    with (fixture / 'Patches/Data.yml').open('a') as f:
        f.write('\nGrayMapIncremental:\n    title: Incremental GrayMap\n    patches:\n')
        for patch in ('GrayMapChainPrepare', 'GrayMapChainProbe'):
            f.write(
                f'        - {patch}:\n            title: {patch}\n            recommend: no\n'
                '            author: WARP diagnostics\n            desc: Isolated incremental adapter.\n'
            )
    raw_path = out / 'warp-raw.exe'
    profile = out / 'incremental.yml'
    profile.write_text(
        'from: '
        + json.dumps(inp.as_posix())
        + '\nto: '
        + json.dumps(raw_path.as_posix())
        + '\ninputs: {}\npatches:\n    - GrayMapChainPrepare\n    - GrayMapChainProbe\n'
    )
    run = subprocess.run(
        [str(fixture / 'win32/WARP_console.exe'), '-using', str(profile)],
        cwd=fixture,
        capture_output=True,
        timeout=180,
    )
    (out / 'build.log').write_bytes(run.stdout + run.stderr)
    assert (
        run.returncode == 0 and b'-E-' not in run.stdout + run.stderr and marker.is_file()
    ), 'WARP failed; see build.log'
    manifest = json.loads(marker.read_text())
    assert manifest.get('graymap') and manifest['graymap'].get(
        'dispatch'
    ), 'GrayMap or chained dispatcher was not installed'
    data = bytearray(raw_path.read_bytes())
    new = pefile.PE(data=bytes(data))
    extra = [
        s for s in new.sections if s.VirtualAddress not in {p.VirtualAddress for p in old.sections}
    ]
    assert len(extra) == 1 and extra[0].Name.startswith(b'.xdiff')
    extra = extra[0]
    # WARP places new allocation bytes at EOF but can report the wrong raw
    # pointer when adding a tenth section expands the PE section table.
    actual = len(data) - extra.SizeOfRawData
    first_code = manifest['graymap']['toggle']
    toggle_offset = actual + first_code['vir'] - 0x400000 - extra.VirtualAddress
    assert (
        data[toggle_offset : toggle_offset + 3] == b'\x9c\x83\x35'
    ), 'new section location is not proven'
    struct.pack_into('<I', data, extra.get_file_offset() + 20, actual)
    data[extra.get_file_offset() : extra.get_file_offset() + 8] = b'.graymap'
    table_end = max(s.get_file_offset() + 40 for s in new.sections)
    align = new.OPTIONAL_HEADER.FileAlignment
    headers = (max(table_end, new.OPTIONAL_HEADER.SizeOfHeaders) + align - 1) // align * align
    first_raw = min(s.PointerToRawData for s in new.sections if s.SizeOfRawData and s != extra)
    assert headers <= first_raw
    struct.pack_into(
        '<I', data, new.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfHeaders'), headers
    )
    new = pefile.PE(data=bytes(data))
    allowed = {h['site']: h.get('size', 5) for h in manifest['graymap']['hooks']}
    allowed[site] = 5
    replacements = {va: bytes(new.get_data(va - 0x400000, size)) for va, size in allowed.items()}
    # Restore all pre-existing mapped bytes, retaining only the six new hooks.
    for prior in old.sections:
        current = next(s for s in new.sections if s.VirtualAddress == prior.VirtualAddress)
        assert (current.Misc_VirtualSize, current.SizeOfRawData, current.Characteristics) == (
            prior.Misc_VirtualSize,
            prior.SizeOfRawData,
            prior.Characteristics,
        )
        data[current.get_file_offset() : current.get_file_offset() + 8] = prior.Name
        data[current.PointerToRawData : current.PointerToRawData + prior.SizeOfRawData] = (
            prior.get_data()
        )
    for va, code in replacements.items():
        offset = new.get_offset_from_rva(va - 0x400000)
        data[offset : offset + len(code)] = code
    overlay = old.get_overlay() or b''
    overlay_start = len(data)
    data.extend(overlay)
    cert = old.OPTIONAL_HEADER.DATA_DIRECTORY[4]
    if cert.Size:
        assert cert.VirtualAddress >= old.get_overlay_data_start_offset()
        struct.pack_into(
            '<I',
            data,
            new.OPTIONAL_HEADER.DATA_DIRECTORY[4].get_file_offset(),
            overlay_start + cert.VirtualAddress - old.get_overlay_data_start_offset(),
        )
    final = pefile.PE(data=bytes(data))
    sections = []
    for prior in old.sections:
        current = next(s for s in final.sections if s.VirtualAddress == prior.VirtualAddress)
        before, after = prior.get_data(), bytearray(current.get_data())
        assert current.Name == prior.Name
        changes = sum(a != b for a, b in zip(before, after))
        for va, size in allowed.items():
            rel = va - 0x400000 - prior.VirtualAddress
            if 0 <= rel <= len(after) - size:
                after[rel : rel + size] = before[rel : rel + size]
        assert bytes(after) == before, f'unrelated mapped bytes changed: {prior.Name}'
        sections.append(dict(name=prior.Name.decode().rstrip('\0'), changed_bytes=changes))

    def imports(pe):
        return [
            (d.dll, [(i.name, i.ordinal, i.address) for i in d.imports])
            for d in pe.DIRECTORY_ENTRY_IMPORT
        ]

    assert imports(old) == imports(final), 'imports changed'
    assert (final.get_overlay() or b'') == overlay, 'overlay changed'
    manifest['commands'] = {'GrayMap': [{'command': '/graymap'}]}
    manifest['source'] = str(out / 'before' / source.name)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    release = out / 'release'
    release.mkdir()
    candidate = release / source.name
    candidate.write_bytes(data)
    if (out / 'data').is_dir():
        shutil.copytree(out / 'data', release / 'data')
    # Existing verifier accepts a conventional graymap.exe in the build dir.
    shutil.copy2(candidate, out / 'graymap.exe')
    report = dict(
        source=str(source),
        candidate=str(candidate),
        source_sha256=digest(original),
        candidate_sha256=digest(data),
        sections=sections,
        permitted_hooks=[hex(v) for v in allowed],
        previous_dispatch=hex(previous),
        overlay_preserved=True,
        imports_preserved=True,
        header_growth_repaired=True,
        live_accepted=False,
    )
    (out / 'preservation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    build(args.source.resolve(), args.output.resolve())
