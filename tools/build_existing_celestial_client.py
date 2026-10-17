"""Add the dial to the installed client's exact bytes, without deploying it.

Preserves existing imports, sections and overlay. The existing monster HUD's
position call is redirected through the same live spacing cell as fresh builds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import capstone
import pefile
from build_celestial_clients import ROOT, fixture, build

PREPARE=r'''/* Fixture-local incremental WENV registration; old peers remain intact. */
CelestialIncremental = function(_) {
	const n=AutoCombatUI.nativeHelpers;
	n.registerPacket0BF6=function(owner,protocol,handler) {
		if(protocol!=="wenv")throw Error("Incremental route accepts only WENV");
		const entry=n.packetTableEntryVir(0xBF6),phy=Exe.Vir2Phy(entry,CODE);
		if(Exe.GetUint32(phy)!==OLD_ROUTER)throw Error("Existing framed router changed");
		const a=n.asm();a.emit(0x9C,0x60,0xBE);a.dword(n.PacketBuffer);
		a.emit(0x66,0x81,0x3E);a.word(0xBF6);a.jcc(0x85,"stock");
		a.emit(0x66,0x83,0x7E,2,8);a.jcc(0x82,"stock");
		a.emit(0x81,0x7E,4);a.dword(0x564E4557);a.jcc(0x85,"stock");
		a.emit(0x61,0x9D);a.jmp(handler);
		a.label("stock");a.emit(0x61,0x9D);a.jmp(OLD_ROUTER);
		const router=n.allocateCode(a);Exe.SetUint32(phy,router.vir);
	};
	const owner=Exe.ActivePatch;
	Exe.SetActivePatch("CelestialDial");Warp.SetPatchState("CelestialDial",true);
	try {
		CelestialDial("CelestialDial");
		const c=CACHE.get("CelestialDial.Contract.v3");
		n.registerPacket0BF6("CelestialDial","wenv",c.receiver);
		if(Exe.GetHex(Exe.Vir2Phy(MONSTER_SITE),10).replace(/ /g,"").toLowerCase()!==MONSTER_BYTES.replace(/ /g,"").toLowerCase())
			throw Error("Existing monster HUD position changed");
		const a=n.asm();a.emit(0xFF,0x35);a.dword(c.top);a.emit(0x50,0x89,0xD9);a.call(0xA23450);a.emit(0xC3);
		const position=n.allocateCode(a);Exe.SetCALL(Exe.Vir2Phy(MONSTER_SITE),position.vir,0);Exe.SetNOPs(Exe.Vir2Phy(MONSTER_SITE+5),5);
		c.monsterPosition=position.vir;c.hooks.push({site:MONSTER_SITE,size:10});CACHE.put("CelestialDial.Contract.v3",c);
	} finally { Exe.ActivePatch=owner; }
	return true;
};
CelestialIncrementalProbe=function(_) {
	const f=new TextFile(MANIFEST,"w");if(!f.Valid)throw Error("Cannot write Celestial manifest");
	f.WriteLine(JSON.stringify(CACHE.get("CelestialDial.Contract.v3")));f.Close();return true;
};
'''

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=ROOT/'Outputs/CelestialDial/existing-client')
    args=ap.parse_args();source=args.source.resolve();out=args.output.resolve()
    original=source.read_bytes();old=pefile.PE(data=original);base=old.OPTIONAL_HEADER.ImageBase
    assert old.FILE_HEADER.Machine==0x14c and base==0x400000
    assert b'CelestialDial.v1\0' not in original and b'CelestialDial.v2\0' not in original and b'CelestialDial.v3\0' not in original,'dial already installed'
    target=lambda va:va+5+struct.unpack('<i',old.get_data(va-base+1,4))[0]
    monster=target(target(0xC76591));md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    instructions=list(md.disasm(old.get_data(monster-base+0x100,0x600),monster+0x100))
    sites=[]
    for i,ins in enumerate(instructions[:-3]):
        following=instructions[i:i+4]
        if [(x.mnemonic,x.op_str) for x in following]==[('push','0x18'),('push','eax'),('mov','ecx, ebx'),('call','0xa23450')]:
            assert sum(x.size for x in following)==10;sites.append(ins.address)
    assert len(sites)==1,'legacy monster position must have one exact match'
    site=sites[0];before=old.get_data(site-base,10)
    previous=struct.unpack('<I',old.get_data(0xCAD0EC-base,4))[0]
    assert previous!=0xCA0AAD and old.get_section_by_rva(previous-base).Characteristics&0x20000000
    out.mkdir(parents=True,exist_ok=False)
    (out/'before').mkdir();shutil.copy2(source,out/'before'/source.name)
    data=bytearray(original);prior=[s for s in old.sections if s.Name.rstrip(b'\0')==b'.xdiff'];assert len(prior)==1
    data[prior[0].get_file_offset():prior[0].get_file_offset()+8]=b'.cdprev\0'
    inp=out/'incremental-input.exe';inp.write_bytes(data)
    fx=fixture(out/'fixture');marker=out/'manifest.json'
    text=PREPARE.replace('OLD_ROUTER',str(previous)).replace('MONSTER_SITE',str(site)).replace('MONSTER_BYTES',json.dumps(before.hex(' '))).replace('MANIFEST',json.dumps(marker.as_posix()))
    (fx/'Scripts/Patches/CelestialIncremental.qjs').write_bytes(text.replace('\n','\r\n').encode('utf8'))
    with (fx/'Tables/Patch.yml').open('a') as f:f.write('\n65010 : CelestialIncremental\n65011 : CelestialIncrementalProbe\n')
    with (fx/'Patches/UI.yml').open('a') as f:
        f.write('\nCelestialFixture:\n    title: Celestial incremental adapter\n    patches:\n')
        for name in ['CelestialIncremental','CelestialIncrementalProbe']:
            f.write('        - '+name+':\n            title: '+name+'\n            recommend: no\n            author: WARP diagnostics\n            desc: Fixture-local adapter.\n')
    raw=out/'warp-raw.exe';build(fx,raw,['CelestialIncremental','CelestialIncrementalProbe'],source=inp)
    manifest=json.loads(marker.read_text());data=bytearray(raw.read_bytes());new=pefile.PE(data=bytes(data))
    extra=[s for s in new.sections if s.VirtualAddress not in {p.VirtualAddress for p in old.sections}];assert len(extra)==1
    extra=extra[0];actual=len(data)-extra.SizeOfRawData
    frame=manifest['frame'];off=actual+frame-base-extra.VirtualAddress
    assert data[off:off+3]==b'\x9c\x60\x53','new section raw position is not proven'
    struct.pack_into('<I',data,extra.get_file_offset()+20,actual)
    data[extra.get_file_offset():extra.get_file_offset()+8]=b'.celdial'
    table_end=max(s.get_file_offset()+40 for s in new.sections);align=new.OPTIONAL_HEADER.FileAlignment
    headers=(max(table_end,new.OPTIONAL_HEADER.SizeOfHeaders)+align-1)//align*align
    first_raw=min(s.PointerToRawData for s in new.sections if s.SizeOfRawData and s!=extra);assert headers<=first_raw
    struct.pack_into('<I',data,new.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfHeaders'),headers)
    new=pefile.PE(data=bytes(data));allowed={h['site']:h['size'] for h in manifest['hooks']}
    replacements={va:new.get_data(va-base,n) for va,n in allowed.items()}
    for prior in old.sections:
        current=next(s for s in new.sections if s.VirtualAddress==prior.VirtualAddress)
        assert (current.Misc_VirtualSize,current.SizeOfRawData,current.Characteristics)==(prior.Misc_VirtualSize,prior.SizeOfRawData,prior.Characteristics)
        data[current.get_file_offset():current.get_file_offset()+8]=prior.Name
        data[current.PointerToRawData:current.PointerToRawData+prior.SizeOfRawData]=prior.get_data()
    for va,replacement in replacements.items():
        off=new.get_offset_from_rva(va-base);data[off:off+len(replacement)]=replacement
    overlay=old.get_overlay() or b'';overlay_start=len(data);data.extend(overlay)
    cert=old.OPTIONAL_HEADER.DATA_DIRECTORY[4]
    if cert.Size:
        assert cert.VirtualAddress>=old.get_overlay_data_start_offset()
        struct.pack_into('<I',data,new.OPTIONAL_HEADER.DATA_DIRECTORY[4].get_file_offset(),overlay_start+cert.VirtualAddress-old.get_overlay_data_start_offset())
    final=pefile.PE(data=bytes(data));sections=[]
    for prior in old.sections:
        current=next(s for s in final.sections if s.VirtualAddress==prior.VirtualAddress)
        before_bytes,after=prior.get_data(),bytearray(current.get_data());changed=sum(a!=b for a,b in zip(before_bytes,after))
        assert current.Name==prior.Name
        for va,n in allowed.items():
            rel=va-base-prior.VirtualAddress
            if 0<=rel<=len(after)-n:after[rel:rel+n]=before_bytes[rel:rel+n]
        assert bytes(after)==before_bytes,('Unrelated existing bytes changed',prior.Name)
        sections.append({'name':prior.Name.decode().rstrip('\0'),'changed_bytes':changed})
    def imports(pe):return [(d.dll,[(i.name,i.ordinal,i.address) for i in d.imports]) for d in pe.DIRECTORY_ENTRY_IMPORT]
    assert imports(old)==imports(final),'import descriptors or IAT addresses changed'
    assert final.get_overlay()==overlay
    candidate=out/'release'/source.name;candidate.parent.mkdir();candidate.write_bytes(data)
    for name in ['boh_rain_prototype.bmp','boh_rain_ripple.bmp','boh_rain_wet.bmp']:
        texture=candidate.parent/'data/texture/effect'/name
        texture.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'Inputs/CelestialDial'/name,texture)
    sound=candidate.parent/'data/wav/boh_thunder_01.wav'
    sound.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'Inputs/CelestialDial/boh_thunder_01.wav',sound)
    report={'source':str(source),'source_sha256':digest(original),'candidate':str(candidate),'candidate_sha256':digest(data),
            'sections':sections,'allowed_hooks':{hex(va):n for va,n in allowed.items()},'previous_framed_router':hex(previous),
            'overlay_preserved':True,'imports_preserved':True,'weather_preserved':True,'live_accepted':False,'deployed':False}
    (out/'preservation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
