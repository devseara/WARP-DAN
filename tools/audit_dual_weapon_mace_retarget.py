"""Read-only exact-cell audit for a possible original mace donor.

This reports pixel-registration witnesses and native fallback semantics. It
does not infer hand/grip landmarks, emit replacement ACTs, or modify the EXE.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from audit_dual_weapon_asset_bridges import (
    Audit, ASSASSIN, compose, inverse, native_canvas_to_job, rounded,
)
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.rig_tables import parse_rig_bytes
from dual_weapon_formats.spr_reader import Spr

ROOT = Path(__file__).resolve().parents[1]


def native_fallback(exe):
    import capstone
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP,
    )
    raw = exe.read_bytes()
    pe = pefile.PE(data=raw)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    read = lambda va, size: pe.get_data(va-image_base, size)
    base, length, job_getter, stop = 0xD42790, 0x1F4, 0xC43230, 0x2200000
    code = read(base, length)
    if code[:13] != bytes.fromhex('55 8B EC 56 8B 75 08 57 6A FF 8B F9 E8'):
        raise ValueError('native weapon fallback profile does not match')
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(base & ~0xFFF, 0x1000)
    machine.mem_write(base, code)
    machine.mem_map(job_getter & ~0xFFF, 0x1000)
    machine.mem_map(stop, 0x1000)
    stack = 0x2300000
    machine.mem_map(stack, 0x10000)
    # Execute the actual PE branch/tables. Only the actor's job getter is an
    # ABI stub; no filesystem or rendering routine runs in this local emulator.
    current = {'job': 0}
    def hook(uc, address, size, user):
        if address == job_getter:
            uc.reg_write(UC_X86_REG_EAX, current['job'])
    machine.mem_write(job_getter, bytes.fromhex('C2 04 00'))
    machine.hook_add(UC_HOOK_CODE, hook)
    rows = []
    for job in (6, 12, 17, 4013, 4018, 4035, 4059, 4065, 4101, 4254, 1, 5):
        mapped = []
        current['job'] = job
        for view in range(1, 24):
            esp = stack+0x8000
            machine.mem_write(esp, struct.pack('<II', stop, view))
            machine.reg_write(UC_X86_REG_ESP, esp)
            machine.reg_write(UC_X86_REG_ECX, 0x2400000)
            machine.emu_start(base, stop, count=200)
            if machine.reg_read(UC_X86_REG_ESP) != esp+8:
                raise AssertionError('native thiscall ret4 stack mismatch')
            result = machine.reg_read(UC_X86_REG_EAX)
            if result != view:
                mapped.append({'input_view': view, 'output_view': result})
        rows.append({'job': job, 'changed_views': mapped})
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    branch = [{'VA': f'0x{i.address:08X}', 'hex': bytes(i.bytes).hex(' ').upper(),
               'instruction': f'{i.mnemonic} {i.op_str}'}
              for i in md.disasm(read(0xD427FE, 15), 0xD427FE)]
    extensions = []
    for index, expected_pointer, expected_name in ((0, 0x1011578, b'act'), (1, 0x1011ED8, b'spr')):
        address = 0x1227310 + 4 * index
        value = read(address, 4)
        pointer = struct.unpack('<I', value)[0]
        if pointer != expected_pointer or pe.get_string_at_rva(pointer-image_base) != expected_name:
            raise ValueError('native weapon extension table profile does not match')
        extensions.append({'index': index, 'table_VA': hex(address), 'bytes': value.hex(' '),
                           'string_VA': hex(pointer), 'extension': expected_name.decode('ascii')})
    return {
        'exe': str(exe), 'exe_sha256': hashlib.sha256(raw).hexdigest(),
        'machine': pe.FILE_HEADER.Machine, 'timestamp': pe.FILE_HEADER.TimeDateStamp,
        'function_VA': '0x00D42790', 'function_and_tables_sha256': hashlib.sha256(code).hexdigest(),
        'execution': 'actual native function and jump tables; C43230 actor-job ABI stub only',
        'matrix': rows, 'mace_branch': branch,
        'verified_extension_table': extensions,
        'equipment_path': {
            'scope': 'Solo original-resource acquisition. The native dual carrier follows a separate generic pair path.',
            'original_view_path_build': '0x00D40C3B', 'original_view_exists': '0x00D40C5A',
            'original_view_checked_extension': 'act',
            'filename_wrappers': {'0x00D8A010': 'act', '0x00D8A160': 'spr'},
            'original_view_missing_branch': '0x00D40C61',
            'view_remap_call_before_generic_path': '0x00D40D6A',
            'generic_path_build': '0x00D40D8E',
            'generic_exists': '0x00D40DAA',
            'original_view_suffix_lookup': '0x00D60DE0',
            'original_view_suffix_lookup_semantics':
                'ItemInfoGetter(itemID), read field +0x40, Lua ReqWeaponNameByClassNum(view). '
                'This is not an automatic decimal item-ID filename.',
            'mace_first_candidate': 'data/sprite/인간족/어세신/어세신_여_클럽.act',
            'mace_matching_sprite': 'data/sprite/인간족/어세신/어세신_여_클럽.spr',
            'mace_first_candidate_scope':
                'For observed item1504/view8 and female Assassin family. If present, '
                'the original-view ACT check succeeds before the 8-to-2 solo fallback. '
                'The matching SPR must also be provided; this does not change the separate native dual carrier.',
        },
    }


def run(coverage_file, exe, output):
    coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
    audit = Audit(Path(coverage['client']))
    parsed = {}
    source = (ROOT/'Scripts/Patches/AllowDualCustomWeaponSprites.qjs').read_text(encoding='utf-8')
    encoded = re.findall(r'const DualWeaponAuthoredRigHex = "([0-9A-Fa-f ]+)";', source)
    if len(encoded) != 1:
        raise ValueError('expected one accepted legacy rig')
    rig_bytes = bytes.fromhex(encoded[0])
    rig = parse_rig_bytes(rig_bytes)
    requirements = set()
    for row in rig['records']:
        if row['family'] or row['gender'] or row['state'] != 9:
            continue
        pose = row['transform']
        if pose.metadata & 8:
            continue
        requirements.add(((80 if row['phase'] or pose.metadata & 32 else 32)
                          + row['direction'], pose.flags & 31))
    # Undeclared custom swords may have copied ACTs across every job. They are
    # not silently promoted to stock hand-registration references.
    names = {r['resource_stem'] for r in coverage['views']+coverage['generic_types']
             if r.get('resource_stem') and r.get('kind') == 'single_weapon_view'}
    references = sorted(ASSASSIN+name for name in names
                        if ASSASSIN+name+'.act' in audit.corpus.keys
                        and ASSASSIN+name+'.spr' in audit.corpus.keys)
    mace = next(r for r in coverage['generic_types'] if r['view'] == 8)
    donors = mace['genders']['female']['alternate_job_assets']['paths']

    def cell(stem, action, frame):
        if stem not in parsed:
            ab, sb = audit.corpus.read(stem+'.act'), audit.corpus.read(stem+'.spr')
            parsed[stem] = (parse_act(ab), Spr(sb), hashlib.sha256(sb).hexdigest()) if ab and sb else None
        if parsed[stem] is None:
            return None
        act, spr, spr_hash = parsed[stem]
        if action >= len(act['actions']) or frame >= len(act['actions'][action].frames):
            return None
        layers = act['actions'][action].frames[frame].layers
        if len(layers) != 1 or layers[0].sprite_index < 0:
            return None
        layer = layers[0]
        if not layer.scale_x or not layer.scale_y:
            return None
        try:
            image = audit.image(spr, spr_hash, layer.sprite_index, layer.sprite_type)
        except (IndexError, ValueError):
            return None
        if not image or image['symmetric_canonical_choices'] != 1:
            return None
        return {**image, 'image': [layer.sprite_type, layer.sprite_index],
                'canonical_to_job': compose(native_canvas_to_job(layer, *image['dimensions']),
                                            inverse(image['to_canonical']))}

    results = []
    for path in donors:
        stem = path[:-4]
        job = stem.rsplit('_여_', 1)[0]+'_여_'
        rows, counts = [], Counter()
        for action, frame in sorted(requirements):
            destination = cell(stem, action, frame)
            row = {'action': action, 'frame': frame, 'witness_alternatives': []}
            if destination is None:
                row['status'] = 'missing_exact_mace_cell'
            else:
                row['mace_image'] = destination['image']
                row['mace_visible_rgba_D4_sha256'] = destination['canonical_visible_rgba_sha256']
                groups = {}
                for reference in references:
                    suffix = reference[len(ASSASSIN):]
                    a, b = cell(reference, action, frame), cell(job+suffix, action, frame)
                    if a and b and a['canonical_visible_rgba_sha256'] == b['canonical_visible_rgba_sha256']:
                        matrix = rounded(compose(a['canonical_to_job'], inverse(b['canonical_to_job'])))
                        groups.setdefault(matrix, []).append({
                            'reference_suffix': suffix, 'Assassin_image': a['image'],
                            'donor_image': b['image'],
                            'visible_rgba_D4_sha256': a['canonical_visible_rgba_sha256']})
                row['witness_alternatives'] = [{'donor_to_Assassin': list(matrix), 'witnesses': witnesses}
                                                for matrix, witnesses in sorted(groups.items())]
                row['status'] = ('no_exact_reference_bridge' if not groups else
                                 'conflicting_reference_bridges' if len(groups) > 1 else
                                 'one_exact_pixel_registration')
            counts[row['status']] += 1
            rows.append(row)
        results.append({'resource': stem, 'summary': dict(counts), 'cells': rows})
    results.sort(key=lambda row: (-row['summary'].get('one_exact_pixel_registration', 0), row['resource']))
    function_key = 'data/luafiles514/lua files/datainfo/weapontable_f.lub'
    function_bytes = audit.corpus.read(function_key)
    if not function_bytes or b'function ReqWeaponNameByClassNum(classNum)' not in function_bytes:
        raise ValueError('missing readable original-view weapon suffix function')
    result = {
        'schema': 'dual_weapon_mace_retarget_audit/v1',
        'audit_tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'coverage_sha256': hashlib.sha256(coverage_file.read_bytes()).hexdigest(),
        'accepted_rig_sha256': hashlib.sha256(rig_bytes).hexdigest(),
        'client': str(audit.corpus.client), 'source_requirements': sorted(requirements),
        'reference_resources': references, 'donors': results,
        'summary': {'donor_count': len(results), 'unique_source_cells': len(requirements),
                    'donors_with_all_cells_and_one_registration': sum(
                        r['summary'].get('one_exact_pixel_registration', 0) == len(requirements) for r in results)},
        'native_fallback': native_fallback(exe), 'sources': audit.corpus.sources,
        'limits': [
            'Exact visible RGBA correspondence proves only the registered reference image transform.',
            'It does not prove a mace grip shares the same point/axis or animation timing as that reference.',
            'Source requirements are the finite accepted female Assassin rig, not every native action/frame.',
            'No body-hand landmarks are inferred. No client resource or executable is modified.',
        ],
    }
    audit.corpus.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result['summary']))
    for row in results[:5]:
        print(row['resource'], row['summary'])
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coverage', type=Path, default=ROOT/'docs/evidence/dual-weapon-type-coverage.json')
    parser.add_argument('--exe', type=Path, default=Path(r'D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.exe'))
    parser.add_argument('--output', type=Path, default=ROOT/'docs/evidence/dual-weapon-mace-retarget-20260905.json')
    args = parser.parse_args()
    run(args.coverage, args.exe, args.output)
