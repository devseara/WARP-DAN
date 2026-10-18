"""Upgrade an existing 2025-07-16 client without rebuilding unrelated features.

Produces a separate verified client only. Game deployment and paired Riftlock
signing remain an explicit release operation.
"""
from pathlib import Path
import argparse, hashlib, json, struct
import capstone
import numpy as np
import pefile
from build_native_act_job_ui import ROOT, ORIGINAL
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

def align(value,boundary):return (value+boundary-1)//boundary*boundary

def relocated_caves(template,old_base,new_base):
    """Relocate the exact QJS-emitted cave: four zero reads and two native jumps."""
    raw=bytearray(template.read(old_base,0xA0));md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);md.detail=True
    reads=jumps=0
    shadow=template.jmp_target(0xC49FEE)
    for start,stop in [(old_base+16,shadow),(shadow,old_base+0xA0)]:
        for ins in md.disasm(template.read(start,stop-start),start):
            offset=ins.address-old_base
            for operand in ins.operands:
                if operand.type==capstone.x86_const.X86_OP_MEM and operand.mem.base==0 and operand.mem.index==0 and operand.mem.disp==old_base:
                    assert ins.disp_size==4
                    struct.pack_into('<I',raw,offset+ins.disp_offset,new_base);reads+=1
            if ins.mnemonic=='jmp' and ins.operands[0].imm in [0xC40FA4,0xC4A004]:
                assert ins.imm_size==4
                target=ins.operands[0].imm;struct.pack_into('<I',raw,offset+ins.imm_offset,(target-(new_base+offset+ins.size))&0xffffffff);jumps+=1
                break
    assert reads==4 and jumps==2,(reads,jumps)
    return bytes(raw)

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
    fixture=fixture_at(out)
    player_draw=original.u32(0x01094810+0x0C)
    if player_draw!=0x00D3A220:
        # Upgrade only the exact signed client audited for this release. Never
        # authorize an arbitrary vtable target or strip the weather wrapper.
        assert sha(before)==KNOWN_WEATHER_CLIENT and player_draw==KNOWN_WEATHER_PLAYER_DRAW,'Unprofiled player draw owner'
    from verify_floor_safe_sprite_depth import qjs_constants
    body_sig,body_hex,shadow_sig,shadow_hex,actors=qjs_constants()
    assert original.read(body_sig,len(body_hex))==body_hex and original.read(shadow_sig,len(shadow_hex))==shadow_hex
    for name,vt,render in actors:
        assert original.u32(vt+0x24)==0xC40C20
        assert original.u32(vt+0x0C)==render or (name=='CPlayer' and sha(before)==KNOWN_WEATHER_CLIENT and player_draw==KNOWN_WEATHER_PLAYER_DRAW)
    # Generate code on the known native fixture; never let WARP allocate inside
    # an already-patched image's zero-filled runtime globals.
    template_path=export(fixture,out/'template',ORIGINAL,['UniformSpriteRHW','FloorSafeSpriteDepth'])
    template=Image(template_path);old_cave=template.jmp_target(0xC40F9F)-16
    pe=original.pe;sa=pe.OPTIONAL_HEADER.SectionAlignment;fa=pe.OPTIONAL_HEADER.FileAlignment
    rva=align(max(s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData) for s in pe.sections),sa)
    new_base=original.base+rva;raw_size=align(0xA0,fa)
    header=pe.sections[-1].get_file_offset()+40
    first_raw=min(s.PointerToRawData for s in pe.sections if s.SizeOfRawData)
    header_shift=max(0,align(header+40,fa)-first_raw)
    assert not getattr(pe,'DIRECTORY_ENTRY_DEBUG',[]),'Profile raw debug pointers before growing headers'
    assert not pe.FILE_HEADER.PointerToSymbolTable and not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].VirtualAddress,'Profile auxiliary raw-file pointers before growing headers'
    if header_shift:
        clean[first_raw:first_raw]=bytes(header_shift)
        for section in pe.sections:
            assert not section.PointerToRelocations and not section.PointerToLinenumbers
            if section.SizeOfRawData:
                struct.pack_into('<I',clean,section.get_field_absolute_offset('PointerToRawData'),section.PointerToRawData+header_shift)
        struct.pack_into('<I',clean,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfHeaders'),align(header+40,fa))
    raw_start=align(len(clean),fa)
    payload=relocated_caves(template,old_cave,new_base)
    clean+=bytes(raw_start-len(clean))+payload+bytes(raw_size-len(payload))
    # Preserve any WARP footer at EOF as well as its original prefix bytes.
    overlay=before[pe.get_overlay_data_start_offset():] if pe.get_overlay_data_start_offset() is not None else b''
    clean+=overlay
    clean[header:header+40]=struct.pack('<8sIIIIIIHHI',b'.rhwfix\0',0xA0,rva,raw_size,raw_start,0,0,0,0,0x60000020)
    struct.pack_into('<H',clean,pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),pe.FILE_HEADER.NumberOfSections+1)
    struct.pack_into('<I',clean,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),align(rva+0xA0,sa))
    struct.pack_into('<I',clean,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),pe.OPTIONAL_HEADER.SizeOfCode+raw_size)
    def patch(va,data):
        offset=pe.get_offset_from_rva(va-original.base)
        if offset>=first_raw:offset+=header_shift
        clean[offset:offset+len(data)]=data
    body=new_base+16;shadow=new_base+(template.jmp_target(0xC49FEE)-old_cave)
    patch(0xC4A5B1,bytes.fromhex('0f1f440000'))
    patch(0xC40F9F,b'\xe9'+struct.pack('<I',(body-0xC40FA4)&0xffffffff))
    patch(0xC49FEE,b'\xe9'+struct.pack('<I',(shadow-0xC49FF3)&0xffffffff)+b'\x90'*17)
    candidate=out/'candidate/client.exe';candidate.parent.mkdir();candidate.write_bytes(clean)
    image=Image(candidate)
    assert image.read(0xC4A5B1,5)==bytes.fromhex('0f1f440000')
    assert image.read(LEGACY_SITE,9)==LEGACY_STOCK
    emulation=emulate(candidate)
    cave=int(emulation['body_cave'],16)-16
    assert cave>=original.base+original.pe.OPTIONAL_HEADER.SizeOfImage,'Cave overlaps original mapped image'
    section=image.pe.get_section_by_rva(cave-image.base)
    assert section.Name.rstrip(b'\0')==b'.rhwfix' and section.Characteristics&0x20000000
    allowed=set(range(0xC4A5B1,0xC4A5B6))|set(range(0xC40F9F,0xC40FA4))|set(range(0xC49FEE,0xC4A004))
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
    report=dict(status='candidate_verified',source=str(source),source_sha256=sha(before),candidate=str(candidate),candidate_sha256=sha(candidate.read_bytes()),catalog=integration_gate(),legacy_clan_hook_removed=removed,weather_player_draw_preserved=image.u32(0x01094810+0x0C)==player_draw,all_other_existing_section_bytes_preserved=True,PE_header_growth=header_shift,original_mapped_image_end=hex(original.base+original.pe.OPTIONAL_HEADER.SizeOfImage),isolated_cave_section='.rhwfix',caves_outside_original_image=True,existing_section_changes=[hex(v) for v in changes],uniform_site=image.read(0xC4A5B1,5).hex(),floor_emulation=emulation,live_client_tested=False,installed=False)
    (out/'upgrade.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.source,a.out)
