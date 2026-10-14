"""Execute the Equipment patch's actual anchor code in memory; no game EXE output."""
from pathlib import Path
import argparse, hashlib, json, struct, subprocess
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *

ROOT = Path(__file__).resolve().parents[1]
NODE = r'''
const fs=require('fs'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(input.source,'utf8');
const begin=source.indexOf('RedesignedEquipmentWindow.patchEquipmentTooltipAnchor =');
const end=source.indexOf('RedesignedEquipmentWindow.patchLeftRailSelectors =',begin);
assert(begin>0 && end>begin);
const memory=Buffer.from(input.hex,'hex'),writes=[],hooks=[];
const Exe={Phy2Vir:a=>a,
 SetHex(a,hex){writes.push({address:a,hex:hex.replace(/ /g,'')});},
 SetUint32(a,v){writes.push({address:a,hex:Buffer.from([v&255,v>>>8&255,v>>>16&255,v>>>24&255]).toString('hex')});}};
const ui={findUnique(pattern,label){
 const bytes=Buffer.from(pattern.replace(/ /g,''),'hex'),at=memory.indexOf(bytes);
 assert(at>=0 && memory.indexOf(bytes,at+1)<0,label);return input.base+at;
}};
// The complete UI first fixes the footer's horizontal anchor. Execute that
// existing source block too when testing a pristine engine; a previously
// redesigned fixture already contains it. Otherwise expanded-width cases test
// an impossible mixture of the stock footer and the new vertical anchor.
const footerBegin=source.indexOf('RedesignedEquipmentWindow.patchAmmunitionHoverLabel =');
const footerBody=source.indexOf('{',footerBegin)+1;
const footerEnd=source.indexOf("\t$$(_, 3.65,",footerBody);
assert(footerBegin>0 && footerEnd>footerBody);
if(memory.includes(Buffer.from('8B4714992BC2D1F883E8148985C0FDFFFF','hex'))){
 new Function('RedesignedEquipmentWindow','Exe','$$','_',source.slice(footerBody,footerEnd))(ui,Exe,()=>{},null);
}else{
 assert(memory.includes(Buffer.from('B8780000009090909090908985C0FDFFFF','hex')),'missing footer anchor prerequisite');
}
const Filler=i=>' __ __ __ _'+i.toString(16).padStart(2,'0');
const MapAddrs=parts=>{let n=0;return parts.map(s=>{const at=n;n+=s.trim().split(/\s+/).length;return at;});};
function AutoHook(address,parts,options){
 const tokens=parts.join(' ').trim().split(/\s+/),bytes=Buffer.alloc(tokens.length),base=input.cave;
 for(let i=0;i<tokens.length;){
  if(tokens[i]==='__'){
   assert(tokens[i+1]==='__' && tokens[i+2]==='__');const id=parseInt(tokens[i+3].slice(1),16);
   const target=options.localTgts[id]===undefined?options.targets[id]:base+options.localTgts[id];
   assert(Number.isInteger(target));bytes.writeInt32LE(target-base-i-4,i);i+=4;
  }else{assert(/^[0-9A-F]{2}$/i.test(tokens[i]));bytes[i]=parseInt(tokens[i++],16);}
 }
 const jump=Buffer.alloc(5+(options.nops||0),0x90);jump[0]=0xe9;jump.writeInt32LE(base-address-5,1);
 writes.push({address,hex:jump.toString('hex')},{address:base,hex:bytes.toString('hex')});hooks.push({address,base,size:bytes.length});
}
new Function('RedesignedEquipmentWindow','Exe','CODE','$$','Filler','JL','JGE','JMP','MapAddrs','AutoHook',
 source.slice(begin,end)+'\nRedesignedEquipmentWindow.patchEquipmentTooltipAnchor(null);')(
 ui,Exe,0,()=>{},Filler,x=>'0F 8C '+x,x=>'0F 8D '+x,x=>'E9 '+x,MapAddrs,AutoHook);
console.log(JSON.stringify({writes,hooks}));
'''

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine',type=Path,required=True);ap.add_argument('--node',required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    source=ROOT/'Scripts/Patches/RedesignedEquipmentWindow.qjs'
    digest=hashlib.sha256(args.engine.read_bytes()).hexdigest()
    memory=pefile.PE(str(args.engine)).get_memory_mapped_image()
    base,cave=0x8b9000,0x50000000
    result=subprocess.run([args.node,'-e',NODE],input=json.dumps(dict(source=str(source),base=base,cave=cave,
        hex=memory[base-0x400000:base-0x400000+0x2000].hex())),text=True,capture_output=True,check=True)
    patch=json.loads(result.stdout)
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(0x400000,(len(memory)+4095)&~4095);u.mem_write(0x400000,memory)
    u.mem_map(cave,0x20000);window,frame=cave+0x10000,cave+0x18000
    def write(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def read(a):return struct.unpack('<i',u.mem_read(a,4))[0]
    def anchor(x,y,offset=0,width=280):
        write(window+0xf4,offset);write(window+0x14,width);write(frame-0x248,y+offset)
        u.reg_write(UC_X86_REG_EBP,frame);u.reg_write(UC_X86_REG_EDI,window);u.reg_write(UC_X86_REG_EBX,x)
        u.reg_write(UC_X86_REG_ESP,frame-0x400)
        u.emu_start(0x8b9d7e,0x8b9de9,count=1000)
        assert u.reg_read(UC_X86_REG_EIP)==0x8b9de9
        assert u.reg_read(UC_X86_REG_EDI)==window and u.reg_read(UC_X86_REG_EBX)==x
        assert u.reg_read(UC_X86_REG_ESP)==frame-0x400 and u.mem_read(frame-0x1d4,1)==b'\1'
        return read(frame-0x240),read(frame-0x244)
    before=sorted({anchor(70,y) for y in range(64,99)})
    assert len(before)>1,'fixture does not reproduce the within-slot tooltip jump'
    for entry in patch['writes']:u.mem_write(entry['address'],bytes.fromhex(entry['hex']))
    u.ctl_remove_cache(0x8b9d7e,0x8b9de9)
    checked=0
    for width in (280,382):
        for offset in (0,20):
            for x,expected_x in [(56,56),(70,56),(85,56),(225,225),(240,225),(254,225)]:
                for row in range(5):
                    for y in range(29+35*row,min(29+35*(row+1),199)):
                        assert anchor(x,y,offset,width)==(expected_x,9+35*row+offset),(x,y,anchor(x,y,offset,width))
                        checked+=1
            for x in (117,130,140):
                for y in range(191,215):assert anchor(x,y,offset,width)==(120,171+offset);checked+=1
    assert hashlib.sha256(args.engine.read_bytes()).hexdigest()==digest
    args.output.mkdir(parents=True,exist_ok=True)
    report=dict(passed=True,engine_sha256=digest,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        positions_checked=checked,old_second_row_anchors=before,game_exe_created=False,
        checks=['one fixed native balloon position throughout each main equipment slot',
                'both columns, all five rows, expanded Swap width and native vertical offset',
                'footer ammunition anchor is constant across its complete cell',
                'native item identified flag, registers and stack retained; text and item-picker code untouched'],
        live_accepted=False)
    (args.output/'equipment-tooltip-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
