/* Execute current QJS against the original PE with explicit WARP API doubles.
 * Produces private test bytes, never an installable client executable. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(__dirname,'../..'),original=fs.readFileSync(process.argv[2]);
const out=process.argv[3];fs.mkdirSync(out,{recursive:true});
const extraBase=0x2800000,data=Buffer.alloc(original.length+0x40000);original.copy(data);
const pe=data.readUInt32LE(0x3c),opt=pe+24,base=data.readUInt32LE(opt+28);
const table=opt+data.readUInt16LE(pe+20),sections=[];
for(let i=0;i<data.readUInt16LE(pe+6);i++){
    const at=table+i*40;sections.push([base+data.readUInt32LE(at+12),data.readUInt32LE(at+20),data.readUInt32LE(at+16)]);
}
function off(va){
    for(const [start,raw,size] of sections)if(va>=start&&va<start+size)return raw+va-start;
    if(va>=extraBase&&va<extraBase+0x40000)return original.length+va-extraBase;
    return -1;
}
function address(at){
    for(const [start,raw,size] of sections)if(at>=raw&&at<raw+size)return start+at-raw;
    return extraBase+at-original.length;
}
let next=original.length;const writes=[];
function write(at,bytes){assert(at>=0&&at+bytes.length<=data.length);writes.push([at,bytes.length]);bytes.copy(data,at);}
function branch(at,target,op){const b=Buffer.alloc(5);b[0]=op;b.writeInt32LE(target-address(at)-5,1);write(at,b);}
const Exe={BuildDate:20250716,ActivePatch:'test',Vir2Phy:off,
    GetUint8:at=>data[at],GetUint32:at=>data.readUInt32LE(at),
    GetHex:(at,n)=>data.subarray(at,at+n).toString('hex').match(/../g).join(' '),
    SetHex:(at,hex)=>write(at,Buffer.from(hex.replace(/\s/g,''),'hex')),
    SetUint32:(at,n)=>{const b=Buffer.alloc(4);b.writeUInt32LE(n>>>0);write(at,b);},
    SetNOPs:(at,n)=>write(at,Buffer.alloc(n,0x90)),
    SetCALL:(at,target)=>branch(at,target,0xE8),SetJMP:(at,target)=>branch(at,target,0xE9),
    Allocate:(size,align)=>{next=Math.ceil(next/align)*align;const at=next;next+=size;return[at,address(at)];},
    ActivateGlobal(){this.ActivePatch='global';},SetActivePatch(name){this.ActivePatch=name;}
};
const cache=new Map(),events=[];
const CACHE={get:k=>cache.get(k),put:(k,v)=>cache.set(k,v),has:k=>cache.has(k),del:k=>cache.delete(k)};
const context=vm.createContext({Exe,CACHE,CODE:1,Warp:{TestMode:true,GetPatchState:()=>true},$$:()=>{},
    PatchDiagnostics:{add:(topic,value)=>events.push({topic,value})},
    MakeMap:(...xs)=>new Map(xs.flatMap((x,i)=>i%2?[]:[[x,xs[i+1]]]))});
for(const name of ['AutoCombatUI','NewButtonVisibility','ROGlobalZeroMenu','VipUI']){
    const s=fs.readFileSync(path.join(root,'Scripts/Patches/'+name+'.qjs'),'utf8');
    assert(!s.replace(/\r\n/g,'').includes('\n'),name+' CRLF');vm.runInContext(s,context);
}
const s=vm.runInContext('MenuZeroStatic',context),vip=vm.runInContext('VipUIStatic',context),nb=context.NewButtonVis;
const dummy=s.allocateBytes(Array(256).fill(0));
const theme=s.allocateBytes([1,0,0,0]),load=s.allocateCode((()=>{const a=s.asm();a.emit(0xC3);return a;})());
CACHE.put('ROGlobalZeroUITheme.State',{stateVir:theme.vir,loadVir:load.vir});
const routes={};for(const label of ['Auto Hunt','Item Collection','AutoSupport','Bestiary']){
    routes[label]=nb.publishCustomButton(label,{requestVir:load.vir,toggleVir:load.vir});
}
const refs={packetCtorA:0x60000300,packetSend:0x60000310},close=0x60000320;
const sender=s.allocateCode(vip.menuToggle(close,refs));
routes.VIP=nb.publishCustomButton('VIP',{requestVir:sender.vir,toggleVir:sender.vir});
assert(context.ROGlobalZeroMenu(10001));
const menu=events.find(e=>e.topic==='ROGlobalZeroMenu.QjsOnly').value;
assert.equal(menu.vip.windowId,0x3FE);assert.equal(menu.backgroundPathVirs.renewal.length,7);
assert.equal(menu.backgroundPathVirs.classic.length,7);
// The former roulette dispatch and all shared Battle Pass/Gacha packet tables
// are outside these menu writes. Verify the original roulette bytes explicitly.
assert(data.subarray(off(0x916A16),off(0x916A16)+7).equals(original.subarray(off(0x916A16),off(0x916A16)+7)));
const cell=routes.VIP.requestCellPhy;
nb.applyCustomVisibility('VIP',0);assert.equal(data.readUInt32LE(cell+4),0);
nb.applyCustomVisibility('VIP',1);assert.equal(data.readUInt32LE(cell+4),1);
assert.equal(nb.customRoute('VIP').requestCellPhy,cell);
fs.writeFileSync(path.join(out,'bytes.bin'),data.subarray(0,next));
fs.writeFileSync(path.join(out,'state.json'),JSON.stringify({originalLength:original.length,extraBase,menu,routes,refs,close,sender,dummy,treeOffsets:s.TreeOffsets,commandGrid:s.CommandGrid},null,2));
console.log('PASS: actual QJS profile checks, VIP registration/visibility, seven-row assets, independent roulette route; emitted bytes ready for native execution');
