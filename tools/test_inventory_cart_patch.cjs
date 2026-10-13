/* WARP source reads + separately serialized patch/global records, entirely in memory.
 * BeginTag replaces prior tagged writes (CHANGELOG.md, Exe.BeginTag API notes).
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),source=process.argv[2],output=process.argv[3];
assert(source,'Supply an existing unpatched 2025-07-16 client');
const original=fs.readFileSync(source),pe=original.readUInt32LE(0x3c),opt=pe+24,base=original.readUInt32LE(opt+28),section=opt+original.readUInt16LE(pe+20);
const native=Buffer.alloc(64*1024*1024),sites=[0xC75165,0xD26DA0,0xD27471],globalOwner='global:InventoryCartCursorV2';
for(let i=0;i<original.readUInt16LE(pe+6);i++){
 const s=section+i*40;original.copy(native,original.readUInt32LE(s+12),original.readUInt32LE(s+20),original.readUInt32LE(s+20)+original.readUInt32LE(s+16));
}
const cases=[];
function fixture(legacy=false){
 const src=Buffer.from(native),records=new Map();let heap=0x2400000,active='test',tag=null;
 const write=(p,bytes)=>{const owner=active==='global'?'global:'+tag:active;assert(owner!=='global:null','untagged shared mutation');if(!records.has(owner))records.set(owner,new Map());for(let i=0;i<bytes.length;i++)records.get(owner).set(p+i,bytes[i]);};
 const context={Warp:{Path:root,TestMode:true},AutoCombatUIStatic:{},
  BinFile:function(p){this.Valid=fs.existsSync(p);this.ReadHex=()=>fs.readFileSync(p).toString('hex');this.Close=()=>{};},
  Exe:{BuildDate:20250716,Vir2Phy:va=>va-base,
   GetUint32:p=>src.readUInt32LE(p),GetHex:(p,n)=>src.subarray(p,p+n).toString('hex'),
   SetUint32:(p,v)=>{const b=Buffer.alloc(4);b.writeUInt32LE(v>>>0);write(p,b);},SetHex:(p,s)=>write(p,Buffer.from(s.replace(/\s/g,''),'hex')),
   Allocate:(n,align)=>{heap=(heap+align-1)&-align;const p=heap;heap+=n;return[p,base+p];},
   FindFunc:()=>base+0x2200000,
   SetJMP:(p,va)=>{const b=Buffer.alloc(5);b[0]=0xE9;b.writeInt32LE(va-(p+base+5),1);write(p,b);},
   SetCALL:(p,va)=>{const b=Buffer.alloc(5);b[0]=0xE8;b.writeInt32LE(va-(p+base+5),1);write(p,b);},
   ActivateGlobal:()=>{active='global';},BeginTag:t=>{assert(t);assert.equal(tag,null);records.delete('global:'+t);tag=t;},EndTag:()=>{tag=null;},
   DelTag:t=>records.delete('global:'+t)}};
 Object.defineProperty(context.Exe,'ActivePatch',{get:()=>active,set:p=>{active=p;}});
 vm.createContext(context);
 const cache=fs.readFileSync(path.join(root,'Scripts/Init/Cache.mjs'),'utf8').replace(/\bexport /g,'');
 vm.runInContext('(function(){'+cache+'\nglobalThis.CACHE={get,put,del,setup,addUser,delUser,hasUsers,getTag,init};})();CACHE.init();',context);
 const helpers=fs.readFileSync(path.join(root,'Scripts/Patches/AutoCombatUI.qjs'),'utf8');
 vm.runInContext(helpers.slice(helpers.indexOf('AutoCombatUIStatic.bytesToHex ='),helpers.indexOf('AutoCombatUIStatic.asciiBytes =')),context);
 const n=context.AutoCombatUIStatic;context.AutoCombatUI={nativeHelpers:n};
 n.allocateString=s=>n.allocateBytes(Array.from(Buffer.from(s+'\0')));n.buildResourcePath=n.allocateString;
 n.assertCode=(label,va,expected)=>{const e=expected.replace(/\s/g,'').toLowerCase(),actual=src.subarray(va-base,va-base+e.length/2).toString('hex');if(actual!==e)throw Error(label+' mismatch, got '+actual.match(/../g).join(' ').toUpperCase());};
 context.VipUI={nativeDrawing:{fit:()=>{const a=n.asm();a.emit(0xc3);return a;}}};
 for(const f of ['InventoryUI','CartUI']){
  const file=legacy==='lost-hover'?'Outputs/inventory-cart-hover-repair-20261013/before/Scripts/Patches/'+f+'.qjs':legacy?'Outputs/inventory-cart-cursor-conflict-20261013/before/Scripts/Patches/'+f+'.qjs':'Scripts/Patches/'+f+'.qjs';
  vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),context);
 }
 const merge=order=>{const out=Buffer.from(src),owners=new Map();for(const name of order||records.keys())for(const [p,v] of records.get(name)||[]){assert(!owners.has(p)||owners.get(p)===name,'overlapping independent patch ownership at '+(base+p).toString(16));owners.set(p,name);out[p]=v;}return out;};
 const apply=name=>{context.Exe.ActivePatch=name;assert.equal(context[name](name),true);assert.equal(context.Exe.ActivePatch,name);};
 const remove=name=>{context.Exe.ActivePatch=name;context[name].cleanup(name);assert.equal(context.Exe.ActivePatch,name);records.delete(name);};
 return {src,records,context,merge,apply,remove};
}
function check(f,label,selected){
 const route=f.context.CACHE.get('InventoryCart.Cursor.v2'),orders=[...f.records.keys()];
 const memory=f.merge(orders);assert.deepEqual(memory,f.merge(orders.reverse()),'serialization order changes result');
 for(const address of sites){assert.equal(memory[address-base],0xe8);assert.equal(address+5+memory.readInt32LE(address-base+1),selected.length?route.routerVir:0xA74410);}
 if(!selected.length){assert(!route);assert(!f.records.has(globalOwner));console.log('PASS '+label+': original calls restored');return;}
 const callbacks={};
 for(const [feature,key,size] of [['InventoryUI','inventory',172],['CartUI','cart',48]]){
  assert.equal(memory.readUInt32LE(route[key+'CellPhy']),selected.includes(feature)?route[key+'Vir']:0);
  if(!selected.includes(feature))continue;
  callbacks[key]=route[key+'Vir'];
  const meta=JSON.parse(fs.readFileSync(path.join(root,'Inputs',feature,'runtime.json'))),short=feature.slice(0,-2),runtime=callbacks[key]-meta.exports['@'+short+'CursorDraw@8'];
  const expected=key==='inventory'?route.cartDispatchVir:0xA74410;
  assert.equal(memory.readUInt32LE(runtime-base+meta.exports[short+'Api']+size-4),expected,'wrong fallback');
 }
 for(const [owner,writes] of f.records)if(owner!==globalOwner)for(const a of sites)for(let i=0;i<5;i++)assert(!writes.has(a-base+i),'cursor call written by individual patch');
 assert.equal(memory[0xA74410-base],0xE9,'Battle Pass entry hook overwritten');
 const code=va=>({address:va,hex:memory.subarray(va-base,va-base+27).toString('hex')});
 cases.push({label,route:JSON.parse(JSON.stringify(route)),callbacks,code:[code(route.routerVir),code(route.cartDispatchVir)]});
 console.log('PASS '+label+': source-only reads, one cursor owner, reverse serialization, correct fallbacks');
}
// This must reproduce the exact original-call mismatch reported by the user.
if(fs.existsSync(path.join(root,'Outputs/inventory-cart-cursor-conflict-20261013/before/Scripts/Patches/InventoryUI.qjs'))){
 const old=fixture(true);old.apply('CartUI');assert.throws(()=>old.apply('InventoryUI'),/cursor call mismatch, got E8 A6 F2 DF FF/);console.log('PASS reproduced original InventoryUI failure: E8 A6 F2 DF FF');
}
// The conflict fix opened the same tag for installCursor, deleting its hooks/code.
if(fs.existsSync(path.join(root,'Outputs/inventory-cart-hover-repair-20261013/before/Scripts/Patches/InventoryUI.qjs'))){
 const old=fixture('lost-hover');old.apply('InventoryUI');old.apply('CartUI');const memory=old.merge();
 for(const a of sites)assert.equal(a+5+memory.readInt32LE(a-base+1),0xA74410);
 const route=old.context.CACHE.get('InventoryCart.Cursor.v2');
 assert.equal(memory.subarray(route.routerVir-base,route.routerVir-base+27).compare(Buffer.alloc(27)),0);
 console.log('PASS reproduced missing hover: reopening tag erased all three hooks and dispatcher code');
}
for(const order of [['InventoryUI'],['CartUI'],['InventoryUI','CartUI'],['CartUI','InventoryUI']]){
 const f=fixture();f.src[0xA74410-base]=0xe9;f.src.writeInt32LE(0x123456,0xA74411-base);
 const selected=[];for(const name of order){f.apply(name);selected.push(name);check(f,selected.join(' -> '),selected);}
 for(const name of order){f.context.Exe.ActivePatch=name;f.context[name].cursorTarget();check(f,'refresh route from '+name,order);}
 for(const name of order){f.remove(name);check(f,'deselect '+name,order.filter(n=>f.records.has(n)));}
 for(const name of order)f.apply(name);check(f,'reselect '+order.join(' -> '),order);
}
{
 const f=fixture();f.src[0xC75165-base]=0x90;assert.throws(()=>f.apply('InventoryUI'),/original cursor call mismatch/);assert(!f.records.has(globalOwner));console.log('PASS modified source call rejected before shared registration');
}
{
 const f=fixture();f.src[0xA74410-base]=0xe9;f.apply('CartUI');f.context.InventoryUI.onApplied=()=>{throw Error('simulated missing asset');};assert.throws(()=>f.apply('InventoryUI'),/simulated missing asset/);f.remove('InventoryUI');check(f,'failed Inventory apply cleanup preserves Cart',['CartUI']);
}
if(output)fs.writeFileSync(output,JSON.stringify(cases,null,2));
