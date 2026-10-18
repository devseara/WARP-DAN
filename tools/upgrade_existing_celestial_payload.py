"""Upgrade a validated v3 payload, extending its WARP section only if necessary."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path
import capstone,pefile
ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state frame reset receive draw hit destroy bridge receiver top vtable'.split()
EXPORTS=['CelestialApi','CelestialState','_CelestialFrame@4','_CelestialReset@0','_CelestialReceive@4','@CelestialDraw@8','@CelestialHit@16','@CelestialDestroy@12']
def sha(b):return hashlib.sha256(b).hexdigest()
def payload(path,base):
    raw=(path/'runtime.bin').read_bytes();meta=json.loads((path/'runtime.json').read_text())
    magic,version,size,count,api,api_size,packet_size,crc=struct.unpack_from('<8I',raw)
    assert magic==0x4c444543 and version==3 and api_size==20 and packet_size==80
    assert zlib.crc32(raw[32:])==crc and sha(raw)==meta['payload_sha256']
    body=bytearray(raw[32+count*4:]);assert len(body)==size==meta['size']
    for off in struct.unpack_from('<'+'I'*count,raw,32):
        target=struct.unpack_from('<I',body,off)[0];assert target<size
        struct.pack_into('<I',body,off,base+target)
    return body,meta
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=Path);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--old-payload',type=Path,default=ROOT/'Outputs/CelestialDial/rain-v3/clients/fixture/Inputs/CelestialDial')
    ap.add_argument('--new-payload',type=Path,default=ROOT/'Inputs/CelestialDial')
    args=ap.parse_args();original=args.source.read_bytes();data=bytearray(original);pe=pefile.PE(data=original);image=pe.get_memory_mapped_image();base=pe.OPTIONAL_HEADER.ImageBase
    marker=image.index(b'CelestialDial.v3\0');key=struct.pack('<I',base+marker);record=image.index(key)
    assert image.find(key,record+1)<0
    values=list(struct.unpack_from('<12I',image,record+4));contract=dict(zip(FIELDS,values))
    old_path=args.old_payload
    old_meta=json.loads((old_path/'runtime.json').read_text());codebase=contract['api']-old_meta['exports']['CelestialApi']
    oldbase=codebase
    old,old_meta=payload(old_path,codebase);new,new_meta=payload(args.new_payload,codebase)
    off=pe.get_offset_from_rva(codebase-base);current=original[off:off+len(old)]
    api=old_meta['exports']['CelestialApi']
    old[api:api+20]=current[api:api+20]
    assert bytes(old)==current,'Current injected runtime differs from the profiled earlier v3 payload'
    for name,address in zip(EXPORTS,values):assert address==codebase+old_meta['exports'][name]
    allowed=[];migrated=len(old)!=len(new) or api!=new_meta['exports']['CelestialApi']
    overlay=pe.get_overlay() or b'';overlay_start=pe.get_overlay_data_start_offset() or len(original)
    if migrated:
        align=lambda n,a:(n+a-1)//a*a
        sa=pe.OPTIONAL_HEADER.SectionAlignment;fa=pe.OPTIONAL_HEADER.FileAlignment
        # Extend the final WARP-owned section. No spare PE section-header slot
        # is assumed and no original section raw offsets or RVAs are shifted.
        tail=max(pe.sections,key=lambda s:s.VirtualAddress)
        assert tail.Name.rstrip(b'\0') in (b'.xdiff',b'.celdial')
        assert tail.PointerToRawData+tail.SizeOfRawData==overlay_start
        rva=tail.VirtualAddress+align(max(tail.Misc_VirtualSize,tail.SizeOfRawData),16)
        codebase=base+rva;new,new_meta=payload(args.new_payload,codebase)
        off=tail.PointerToRawData+rva-tail.VirtualAddress
        raw_size=align(off-tail.PointerToRawData+len(new),fa)
        new_overlay=tail.PointerToRawData+raw_size
        data=bytearray(original[:overlay_start]);data.extend(bytes(off-len(data)))
        data.extend(bytes(new_overlay-len(data)));data.extend(overlay)
        virtual_size=rva-tail.VirtualAddress+len(new)
        delta=raw_size-tail.SizeOfRawData
        fields=[(tail.get_file_offset()+8,4,virtual_size),(tail.get_file_offset()+16,4,raw_size),
                (tail.get_file_offset()+36,4,tail.Characteristics|0xE0000060),
                (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),4,align(rva+len(new),sa)),
                (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),4,pe.OPTIONAL_HEADER.SizeOfCode+delta),
                (pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfInitializedData'),4,pe.OPTIONAL_HEADER.SizeOfInitializedData+delta),
                (pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'),4,0)]
        cert=pe.OPTIONAL_HEADER.DATA_DIRECTORY[4]
        if cert.Size:
            assert cert.VirtualAddress>=overlay_start
            fields.append((cert.get_file_offset(),4,cert.VirtualAddress+new_overlay-overlay_start))
        for pos,size,value in fields:
            struct.pack_into('<H' if size==2 else '<I',data,pos,value);allowed.append((pos,size,'PE allocation metadata'))
    else:allowed.append((off,len(new),'owned native payload'))
    new_api=new_meta['exports']['CelestialApi'];new[new_api:new_api+20]=current[api:api+20]
    data[off:off+len(new)]=new
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    def replace_call(address,expected,target,size):
        ins=list(md.disasm(pe.get_data(address-base,size),address))
        matches=[i for i in ins if i.mnemonic=='call' and i.op_str==hex(expected)]
        assert len(matches)==1 and matches[0].bytes[0]==0xe8,(hex(address),hex(expected))
        site=matches[0].address;pos=pe.get_offset_from_rva(site-base)
        data[pos:pos+5]=b'\xe8'+struct.pack('<i',target-site-5);allowed.append((pos,5,'existing payload bridge'))
    replace_call(contract['bridge'],contract['frame'],codebase+new_meta['exports']['_CelestialFrame@4'],20)
    replace_call(contract['receiver'],contract['receive'],codebase+new_meta['exports']['_CelestialReceive@4'],80)
    if '@CelestialWeatherProcess@8' in new_meta['exports']:
        pos=pe.get_offset_from_rva(0xC74F71-base)
        expected=oldbase+old_meta['exports']['@CelestialWeatherProcess@8'] if '@CelestialWeatherProcess@8' in old_meta['exports'] else 0xC136A0
        assert original[pos]==0xe8 and 0xC74F76+struct.unpack_from('<i',original,pos+1)[0]==expected
        data[pos:pos+5]=b'\xe8'+struct.pack('<i',codebase+new_meta['exports']['@CelestialWeatherProcess@8']-0xC74F76)
        allowed.append((pos,5,'native weather post-process bridge'))
    shadow_calls={'@CelestialShadowProject@20':[(0xA59EF1,0x554380),(0xA5A66D,0x554380),(0xA5AF1C,0x554380)],
                  '@CelestialShadowSubmit@16':[(0xA5A484,0x550B10),(0xA5AD9D,0x550B10),(0xA5B0C9,0x550B10)]}
    for export,sites in shadow_calls.items():
        if export not in new_meta['exports']:continue
        for address,stock in sites:
            pos=pe.get_offset_from_rva(address-base)
            expected=oldbase+old_meta['exports'][export] if export in old_meta['exports'] else stock
            assert original[pos]==0xe8 and address+5+struct.unpack_from('<i',original,pos+1)[0]==expected
            data[pos:pos+5]=b'\xe8'+struct.pack('<i',codebase+new_meta['exports'][export]-address-5)
            allowed.append((pos,5,'scoped scenery shadow bridge'))
    if '@CelestialShadowActor@16' in new_meta['exports']:
        for table,stock in [(0x104D420,0xA59C30),(0x104D450,0xA59D20)]:
            pos=pe.get_offset_from_rva(table-base+7*4)
            expected=oldbase+old_meta['exports']['@CelestialShadowActor@16'] if '@CelestialShadowActor@16' in old_meta['exports'] else stock
            assert struct.unpack_from('<I',original,pos)[0]==expected
            struct.pack_into('<I',data,pos,codebase+new_meta['exports']['@CelestialShadowActor@16'])
            allowed.append((pos,4,'scenery model render slot'))
    if '@CelestialPlayerShadowDraw@12' in new_meta['exports']:
        pos=pe.get_offset_from_rva(0x1094810-base+3*4)
        export='@CelestialPlayerShadowDraw@12'
        expected=oldbase+old_meta['exports'][export] if export in old_meta['exports'] else 0xD3A220
        assert struct.unpack_from('<I',original,pos)[0]==expected
        struct.pack_into('<I',data,pos,codebase+new_meta['exports'][export])
        allowed.append((pos,4,'player draw scope'))
        pos=pe.get_offset_from_rva(0xC4A65E-base)
        export='CelestialSpriteSubmitBridge'
        expected=oldbase+old_meta['exports'][export] if export in old_meta['exports'] else 0x550B10
        assert original[pos]==0xe8 and 0xC4A663+struct.unpack_from('<i',original,pos+1)[0]==expected
        data[pos:pos+5]=b'\xe8'+struct.pack('<i',codebase+new_meta['exports'][export]-0xC4A663)
        allowed.append((pos,5,'scoped player silhouette submission'))
    for packet in [0x91,0x92]:
        entry=struct.unpack_from('<I',image,0xCAA2E0-base+(packet-0x73)*4)[0]
        replace_call(entry,contract['reset'],codebase+new_meta['exports']['_CelestialReset@0'],20)
    for index,name in enumerate(EXPORTS):
        pos=pe.get_offset_from_rva(record+4+index*4);struct.pack_into('<I',data,pos,codebase+new_meta['exports'][name]);allowed.append((pos,4,'dial contract'))
    for slot,name in [(0,EXPORTS[7]),(20,EXPORTS[5]),(50,EXPORTS[6])]:
        pos=pe.get_offset_from_rva(contract['vtable']-base+slot*4)
        assert struct.unpack_from('<I',data,pos)[0]==oldbase+old_meta['exports'][name]
        struct.pack_into('<I',data,pos,codebase+new_meta['exports'][name]);allowed.append((pos,4,'owned dial vtable'))
    restored=bytearray(data[:overlay_start] if migrated else data)
    for pos,size,_ in allowed:restored[pos:pos+size]=original[pos:pos+size]
    assert bytes(restored)==(original[:overlay_start] if migrated else original),'Unrelated client bytes changed'
    final=pefile.PE(data=bytes(data));assert (final.get_overlay() or b'')==overlay
    if not migrated:assert len(data)==len(original)
    args.output.parent.mkdir(parents=True,exist_ok=False);args.output.write_bytes(data)
    report={'source':str(args.source.resolve()),'source_sha256':sha(original),'target':str(args.output.resolve()),'sha256':sha(data),
        'runtime_base':hex(codebase),'unrelated_bytes_preserved':True,'size_preserved':not migrated,
        'owned_section_migration':migrated,'overlay_preserved':True,
        'allowed_ranges':[{'offset':hex(pos),'size':size,'purpose':purpose} for pos,size,purpose in allowed]}
    args.output.with_suffix('.upgrade.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='allowed_ranges'},indent=2))
if __name__=='__main__':main()
