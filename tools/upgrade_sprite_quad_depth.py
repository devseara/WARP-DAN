"""Upgrade an existing 2025-07-16 client without rebuilding unrelated features.

Produces a separate verified client only. Game deployment and paired Riftlock
signing remain an explicit release operation.
"""
from pathlib import Path
import argparse, hashlib, json, struct
import numpy as np
import pefile
from build_native_act_job_ui import ROOT
from verify_native_act_job_ui_warp import fixture_at, export
from verify_uniform_sprite_rhw import integration_gate, static_gate
from verify_floor_safe_sprite_depth import Image, emulate

LEGACY_SITE=0xC4A63E
LEGACY_STOCK=bytes.fromhex('8b45d80b8824010000')
LEGACY_PREFIX_BYTES=194
LEGACY_PREFIX_SHA='21c41deadc2e0e2c6930e38c51c21742e3dfdec11ea29733caa86827aa52b489'
KNOWN_WEATHER_CLIENT='5d1d4faf3065a27655e9404357af8beb697ede907959fa9c39ccc15aba3cbc36'
KNOWN_WEATHER_PLAYER_DRAW=0x0256D5A0

def sha(raw):return hashlib.sha256(raw).hexdigest()

def build(source,out):
    source=source.resolve();out=out.resolve()
    assert not out.exists(),'Use a fresh output folder to preserve previous evidence.'
    static_gate()
    before=source.read_bytes();original=Image(source);clean=bytearray(before)
    legacy=original.read(LEGACY_SITE,9)
    removed=False
    if legacy!=LEGACY_STOCK:
        assert legacy[0]==0xE9 and legacy[5:]==b'\x90'*4,'Unknown legacy hook'
        target=original.jmp_target(LEGACY_SITE)
        assert sha(original.read(target,LEGACY_PREFIX_BYTES))==LEGACY_PREFIX_SHA,'Unknown legacy cave'
        assert original.read(target+LEGACY_PREFIX_BYTES,9)==LEGACY_STOCK
        resume=target+LEGACY_PREFIX_BYTES+9
        assert original.jmp_target(resume)==LEGACY_SITE+9
        offset=original.pe.get_offset_from_rva(LEGACY_SITE-original.base)
        clean[offset:offset+9]=LEGACY_STOCK;removed=True
    out.mkdir(parents=True)
    seed=out/'source-with-legacy-hook-retired.exe';seed.write_bytes(clean)
    fixture=fixture_at(out)
    player_draw=original.u32(0x01094810+0x0C)
    if player_draw!=0x00D3A220:
        # Upgrade only the exact signed client audited for this release. Never
        # authorize an arbitrary vtable target or strip the weather wrapper.
        assert sha(before)==KNOWN_WEATHER_CLIENT and player_draw==KNOWN_WEATHER_PLAYER_DRAW,'Unprofiled player draw owner'
        patch=fixture/'Scripts/Patches/FloorSafeSpriteDepth.qjs'
        marker=b'\tconst self = FloorSafeSpriteDepth;'
        text=patch.read_bytes();assert text.count(marker)==1
        patch.write_bytes(text.replace(marker,
            b'\t// Exact-source upgrade adapter; existing weather owner retained.\r\n'
            b'\tCACHE.put("CelestialDial.Contract.v3", {playerDraw: 0x0256D5A0});\r\n'+marker,1))
    candidate=export(fixture,out/'candidate',seed,['UniformSpriteRHW','FloorSafeSpriteDepth'])
    image=Image(candidate)
    assert image.read(0xC4A5B1,5)==bytes.fromhex('0f1f440000')
    assert image.read(LEGACY_SITE,9)==LEGACY_STOCK
    emulation=emulate(candidate)
    cave=int(emulation['body_cave'],16)-16
    allowed=set(range(0xC4A5B1,0xC4A5B6))|set(range(0xC40F9F,0xC40FA4))|set(range(0xC49FEE,0xC4A004))|set(range(cave,cave+0xA0))
    if removed:allowed.update(range(LEGACY_SITE,LEGACY_SITE+9))
    # Compare all original section data, including existing custom-code caves,
    # weather payloads, imports and UI resources. Only the profiled hooks and
    # new floor-safe cave may change. No selective feature-name heuristic.
    changes=[]
    for section in original.pe.sections:
        old=section.get_data();new=image.pe.get_data(section.VirtualAddress,len(old))
        assert len(old)==len(new),'An existing section was truncated'
        offsets=np.flatnonzero(np.frombuffer(old,dtype=np.uint8)!=np.frombuffer(new,dtype=np.uint8))
        addresses=[original.base+section.VirtualAddress+int(i) for i in offsets]
        assert all(va in allowed for va in addresses),[hex(va) for va in addresses if va not in allowed][:20]
        changes.extend(addresses)
    assert image.pe.OPTIONAL_HEADER.AddressOfEntryPoint==original.pe.OPTIONAL_HEADER.AddressOfEntryPoint
    assert source.read_bytes()==before,'Input client changed during upgrade'
    report=dict(status='candidate_verified',source=str(source),source_sha256=sha(before),candidate=str(candidate),candidate_sha256=sha(candidate.read_bytes()),catalog=integration_gate(),legacy_clan_hook_removed=removed,weather_player_draw_preserved=image.u32(0x01094810+0x0C)==player_draw,all_other_existing_section_bytes_preserved=True,existing_section_changes=[hex(v) for v in changes],uniform_site=image.read(0xC4A5B1,5).hex(),floor_emulation=emulation,live_client_tested=False,installed=False)
    (out/'upgrade.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    seed.unlink()
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.source,a.out)
