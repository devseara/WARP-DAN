"""Upgrade a profiled AutoSupport or AutoCombat window in an isolated PE section.

The legacy-template manifest must be built with both original layouts, English.
Every reused renderer/input helper is compared in full after relocation. Existing
sections may change only at five settings vtable slots and four size immediates.
"""
from pathlib import Path
import argparse, hashlib, json, struct, zlib
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_CALL, CS_GRP_JUMP

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def align(n,a):return (n+a-1)//a*a

def build(source,template,out,feature='autosupport'):
    support=feature=='autosupport';prefix='AutoSupportCustom' if support else 'AutoHuntCustom'
    section_name=b'.asv1' if support else b'.ahv1'
    assert not out.exists(), 'Use a fresh output folder'
    raw=source.read_bytes();pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase
    assert pe.FILE_HEADER.Machine==0x14c and base==0x400000
    assert not pe.OPTIONAL_HEADER.DllCharacteristics&0x40, 'This static WARP profile requires ASLR disabled'
    assert not any(s.Name.startswith(section_name) for s in pe.sections), 'Already upgraded'
    marker=bytes.fromhex('C7 46 2C')+struct.pack('<I',0x3f6 if support else 0x3f0);site=raw.find(marker)
    assert site>=0 and raw.find(marker,site+1)<0, 'Unique AutoSupport window ID required'
    assert raw[site-23:site-21]==b'\xc7\x06' and raw[site-17]==0x68 and raw[site-12]==0x68
    assert raw[site+47:site+49]==b'\x89\x35'
    table=struct.unpack_from('<I',raw,site-21)[0];state=struct.unpack_from('<I',raw,site+49)[0]
    m=json.loads((template/'manifest.json').read_text())[feature];tp=pefile.PE(str(template/'autohunt.exe'))
    helpers=m['legacyHandlers'] if support else m['legacyHelpers']
    delta=table-m['vtableVir'];state_delta=state-m['stateVir']
    if support:assert state==m['stateVir']+delta
    begin=m['layoutContext']['paths']['titleBar']['vir']
    end=max(h['vir']+h['size'] for h in helpers.values())
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    immutable=[];mutable=[];resource_delta=delta;sender_delta=delta
    code_start=m['layoutContext']['scalarSender']['vir']
    if not support:
        def objects(obj):
            if isinstance(obj,dict):
                if 'vir' in obj and 'size' in obj:yield obj
                else:
                    for child in obj.values():yield from objects(child)
            elif isinstance(obj,list):
                for child in obj:yield from objects(child)
        for group in ['paths','strings']:immutable.extend(objects(m['layoutContext'][group]))
        mutable.extend(objects(m['layoutContext']['buffers']))
        for ptr,n in zip(m['layoutContext']['rows'],[800,384,384,48,144,384,192,192,128]):mutable.append({'vir':ptr,'size':n})
        for ptr,n in zip(m['layoutContext']['icons'],[256,256,32,96]):mutable.append({'vir':ptr,'size':n})
        h=helpers['draw'];original=tp.get_data(h['vir']-base,h['size']);actual=pe.get_data(h['vir']+delta-base,h['size'])
        basic=m['layoutContext']['paths']['basic']['vir'];deltas=[]
        for ins in md.disasm(original,h['vir']):
            if ins.imm_size==4 and struct.unpack_from('<I',original,ins.address-h['vir']+ins.imm_offset)[0]==basic:
                deltas.append(struct.unpack_from('<I',actual,ins.address-h['vir']+ins.imm_offset)[0]-basic)
        assert deltas and len(set(deltas))==1,'Resource anchor is ambiguous'
        resource_delta=deltas[0]
        # Independently validate every immutable resource/caption, including
        # those not referenced by the legacy draw path. No name guessing.
        for obj in immutable:
            expected=tp.get_data(obj['vir']-base,obj['size'])
            assert pe.get_data(obj['vir']+resource_delta-base,obj['size'])==expected,'Resource/caption layout differs'
        sender=m['layoutContext']['scalarSender'];h=helpers['down']
        a=tp.get_data(h['vir']-base,h['size']);b=pe.get_data(h['vir']+delta-base,h['size']);targets=[]
        for ins in md.disasm(a,h['vir']):
            if ins.group(CS_GRP_CALL) and ins.imm_size==4 and ins.operands[0].imm==sender['vir']:
                disp=struct.unpack_from('<i',b,ins.address-h['vir']+ins.imm_offset)[0]
                targets.append(ins.address+delta+ins.size+disp)
        assert targets and len(set(targets))==1,'Scalar sender anchor is ambiguous'
        sender_delta=targets[0]-sender['vir']
    # The full-profile client can allocate captions, writable snapshot buffers,
    # and code at separate offsets. Only exact typed spans may move separately.
    def address_of(value):
        sender=m['layoutContext']['scalarSender']
        if sender['vir']<=value<sender['vir']+sender['size']:return value+sender_delta
        if m['stateVir']<=value<m['stateVir']+(252 if support else 248):return state+value-m['stateVir']
        if not support:
            if any(o['vir']<=value<o['vir']+o['size'] for o in immutable):return value+resource_delta
            if any(o['vir']<=value<o['vir']+o['size'] for o in mutable):return value+state-m['stateVir']
            if code_start<=value<end:return value+delta
            assert not begin<=value<code_start,f'Unprofiled private data address: {value:#x}'
            return value
        return value+delta if begin<=value<end else value
    def relocate_code(h,function_delta=delta):
        original=tp.get_data(h['vir']-base,h['size']);code=bytearray(original)
        instructions=list(md.disasm(original,h['vir']));assert sum(i.size for i in instructions)==len(original)
        for ins in instructions:
            off=ins.address-h['vir']
            if (ins.group(CS_GRP_CALL) or ins.group(CS_GRP_JUMP)) and ins.imm_size==4:
                target=ins.operands[0].imm
                if h['vir']<=target<h['vir']+h['size']:destination=target+function_delta
                elif m['layoutContext']['scalarSender']['vir']<=target<m['layoutContext']['scalarSender']['vir']+m['layoutContext']['scalarSender']['size']:destination=target+sender_delta
                else:destination=target+delta if begin<=target<end else target
                struct.pack_into('<i',code,off+ins.imm_offset,destination-(ins.address+function_delta+ins.size))
                continue
            for pos,size in [(ins.imm_offset,ins.imm_size),(ins.disp_offset,ins.disp_size)]:
                if size==4:
                    value=struct.unpack_from('<I',original,off+pos)[0]
                    struct.pack_into('<I',code,off+pos,address_of(value))
        return bytes(code)
    sender=m['layoutContext']['scalarSender']
    assert pe.get_data(sender['vir']+sender_delta-base,sender['size'])==relocate_code(sender,sender_delta),'Scalar sender implementation differs'
    for name,h in helpers.items():
        expected=relocate_code(h);actual=pe.get_data(h['vir']+delta-base,h['size'])
        if actual!=expected:
            differences={i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b}
            evidence=[]
            for ins in md.disasm(expected,h['vir']+delta):
                off=ins.address-h['vir']-delta
                if any(i in differences for i in range(off,off+ins.size)):
                    evidence.append({'offset':off,'expected':expected[off:off+ins.size].hex(),'actual':actual[off:off+ins.size].hex(),'instruction':ins.mnemonic+' '+ins.op_str})
                    if len(evidence)==8:break
            raise AssertionError(f'Existing {feature} {name} differs from the profiled legacy implementation: {evidence}')
    slots={'draw':20,'down':25,'move':28,'up':31,'wheel':35}
    for name,slot in slots.items():assert struct.unpack('<I',pe.get_data(table-base+slot*4,4))[0]==helpers[name]['vir']+delta
    def rebase(value):
        if isinstance(value,dict):return {k:rebase(v) for k,v in value.items()}
        if isinstance(value,list):return [rebase(v) for v in value]
        return address_of(value) if isinstance(value,int) else value
    ctx=rebase(m['layoutContext']);s=ctx['strings'];p=ctx['paths'];v=lambda o:o['vir']
    title=b'AUTO SUPPORT SETTINGS\0' if support else b'AUTO HUNT SETTINGS\0'
    assert pe.get_data(v(s['windowTitle'])-base,len(title))==title
    stem='support-custom-v1' if support else 'custom-v1'
    blob=(ROOT/f'Inputs/AutoUI/{stem}.bin').read_bytes();meta=json.loads((ROOT/f'Inputs/AutoUI/{stem}.json').read_text())
    magic,version,size,count,imagebase,cfgsize,client,crc=struct.unpack_from('<8I',blob)
    assert (magic,version,cfgsize,client)==((0x31565341,1,648,20250716) if support else (0x31564341,2,620,20250716))
    assert zlib.crc32(blob[32:])==crc and sha(blob)==meta['payload_sha256']
    assert sha((ROOT/f'tools/native/{"autosupport" if support else "autohunt"}_custom_v1.cpp').read_bytes())==meta['source_sha256']
    start=32+count*4;payload=bytearray(blob[start:]);assert len(payload)==size
    sa,fa=pe.OPTIONAL_HEADER.SectionAlignment,pe.OPTIONAL_HEADER.FileAlignment
    rva=align(max(s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData) for s in pe.sections),sa);address=base+rva
    for n in range(count):
        off=struct.unpack_from('<I',blob,32+n*4)[0];old=struct.unpack_from('<I',payload,off)[0]
        assert imagebase<=old<imagebase+size;struct.pack_into('<I',payload,off,address+old-imagebase)
    def string(text):
        result=address+len(payload);payload.extend(text.encode('ascii')+b'\0');return {'vir':result}
    tabs=[string(t) for t in ['Overview','Party' if support else 'Targets','Combat','Recovery','Loot','Movement','Buff items']]
    custom=[string(t) for t in ['Support setup','Party master','Combat skills','Recovery rules','Loot rules','Movement & escape','Buff items','Core behavior','Stop & return rules','Advanced settings','General settings','Select party master','Return at weight limit','Enable Return','Use Token of Siegfried','Settings are saved automatically.','Collect categories','When inventory fills','Show empty slots','Hide empty slots','Equipment filters']]
    if not support:
        for index,text in [(0,'Hunt setup'),(1,'Monster selection'),(11,'Collect selected loot'),(13,'Return when buff items run out')]:custom[index]=string(text)
    labels=['windowTitle','reset','close','normalAttack','normalAttackHint','attackSettings','supportSettings','healSettings','statusSettings','registerItem','registerSkill','secondsSuffix','useLabel','weight','lootWeaponPrefix','lootArmorPrefix','lootOptionSuffix','lootSupportFirst','lootLootFirst','lootReturn','lootReturnHint','lootContinue','lootContinueHint','lootReturnHint','skillDelayHint','skillReject','itemReject','statusPotion']
    if not support:
        labels[17]='lootFightFirst';labels[19]='returnTown';labels[23]='itemReturnHint'
    controls=['sliderGaugeHp','sliderGaugeSp','sliderGaugeLoot','sliderThumbHp','sliderThumbSp','sliderLeft','sliderLeftOver','sliderLeftPressed','sliderRight','sliderRightOver','sliderRightPressed','scrollUp','scrollDown','scrollTrack','scrollThumbUp','scrollThumbMid','scrollThumbDown','checkboxOn','checkboxOff','lootDropdownArrow','skill3','potion1','looting1']
    cfg=[1 if support else 2,state,v(ctx['fillRect']),v(ctx['mouseDown']),v(ctx['sliderHover']),v(ctx['mouseUp']),0,0,helpers['blit']['vir']+delta,v(ctx['itemResolver']),v(p['skillIconFormat']),*ctx['rows'],*ctx['icons']]
    for seq in [tabs,s['headings'],s['subtitles'],s['basicOptions']+([s['basicOptions'][8]] if support else []),s['basicPrefixes'],s['basicSuffixes'],s['potionPanels'],s['lootOptions'],s['lootOptionChoices'],[s[k] for k in labels]+[s['headings'][1] if support else s['monsters'][0],s['teleport'],s['lootPriorityHeading']],[p[k] for k in controls]]:cfg.extend(v(a) for a in seq)
    cfg.extend([0,v(ctx['scalarSender']),v(ctx['mouseWheel']),*(v(a) for a in custom)])
    if support:cfg.extend([v(p['sysCloseOff']),v(p['sysCloseOn']),v(ctx['statusItemRow']),*(v(s[k]) for k in ['noMasterReject','masterOfflineReject','startPolicyReject','statusItemReject'])])
    assert len(cfg)*4==cfgsize
    struct.pack_into('<'+'I'*len(cfg),payload,meta['exports'][prefix+'Config'],*cfg)
    header=pe.sections[-1].get_file_offset()+40;first=min(s.PointerToRawData for s in pe.sections if s.SizeOfRawData)
    assert header+40<=first,'No PE section header room; do not shift unrelated raw data'
    assert not pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].VirtualAddress and not pe.FILE_HEADER.PointerToSymbolTable
    clean=bytearray(raw);raw_start=align(len(clean),fa);raw_size=align(len(payload),fa)
    clean.extend(bytes(raw_start-len(clean))+payload+bytes(raw_size-len(payload)))
    clean[header:header+40]=struct.pack('<8sIIIIIIHHI',section_name.ljust(8,b'\0'),len(payload),rva,raw_size,raw_start,0,0,0,0,0xE0000060)
    struct.pack_into('<H',clean,pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),pe.FILE_HEADER.NumberOfSections+1)
    struct.pack_into('<I',clean,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),align(rva+len(payload),sa))
    struct.pack_into('<I',clean,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),pe.OPTIONAL_HEADER.SizeOfCode+raw_size)
    allowed=set();writes=[]
    def put(off,expected,value):
        assert struct.unpack_from('<I',raw,off)[0]==expected
        struct.pack_into('<I',clean,off,value);allowed.update(range(off,off+4));writes.append({'offset':off,'before':expected,'after':value})
    entries={k:address+value for k,value in meta['exports'].items()}
    for name,slot in slots.items():put(pe.get_offset_from_rva(table-base+slot*4),helpers[name]['vir']+delta,entries[prefix+name.title()])
    for off,old,new in [(site-16,346,520),(site-11,470,760),(site+25,470,760),(site+38,346,520)]:put(off,old,new)
    out.mkdir(parents=True);candidate=out/'client.exe';candidate.write_bytes(clean);newpe=pefile.PE(str(candidate))
    for section in pe.sections:
        a=section.get_data();b=newpe.get_data(section.VirtualAddress,len(a));assert len(a)==len(b)
        for i,(old,new) in enumerate(zip(a,b)):
            if old!=new:assert section.PointerToRawData+i in allowed,'Unrelated section byte changed'
    custom_record={'entries':entries,'config':cfg,'payload':{'vir':address,'size':len(payload)},'source_sha256':meta['source_sha256']}
    m.update(customV1=custom_record,design='Custom AutoSupport UI v1' if support else 'Custom AutoHunt UI v1',windowSize=[760,520],stateVir=state,vtableVir=table,scalarSenderVir=v(ctx['scalarSender']),layoutContext=ctx)
    rebased_helpers={name:{**h,'vir':h['vir']+delta,'phy':pe.get_offset_from_rva(h['vir']+delta-base)} for name,h in helpers.items()}
    if support:m['legacyHandlers']=rebased_helpers
    else:m['legacyHelpers']=rebased_helpers;m['legacyHandlers']={name:h['vir'] for name,h in rebased_helpers.items()}
    m.update(drawVir=entries[prefix+'Draw'],mouseDownVir=entries[prefix+'Down'],mouseUpVir=entries[prefix+'Up'])
    (out/'autohunt.exe').write_bytes(clean) # Shared verifier convention; deployed name stays caller-selected.
    (out/'manifest.json').write_text(json.dumps({feature:m},indent=2)+'\n')
    report={'source':str(source),'source_sha256':sha(raw),'candidate':str(candidate),'candidate_sha256':sha(clean),'preserved_existing_sections':True,'legacy_helpers_compared':list(helpers),'scalar_sender_compared':True,'relocation_groups':{'code':delta,'resources':resource_delta,'state':state_delta,'scalar_sender':sender_delta,'immutable_spans_verified':len(immutable)},'section':section_name.decode(),'writes':writes,'live_accepted':False}
    (out/'upgrade.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=Path);ap.add_argument('--template',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--feature',choices=['autosupport','autohunt'],default='autosupport');a=ap.parse_args();build(a.source.resolve(),a.template.resolve(),a.output.resolve(),a.feature)
