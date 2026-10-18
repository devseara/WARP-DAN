/* Exercise production cursor registration/cleanup in every selection order. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const helpers=fs.readFileSync(path.join(root,'Scripts/Patches/AutoCombatUI.qjs'),'utf8');
const names=['InventoryUI','CartUI','StorageUI','CelestialDial'];
const permutations=a=>a.length?a.flatMap((n,i)=>permutations(a.filter((_,j)=>i!==j)).map(p=>[n,...p])):[[]];
const cases=[];
for(const order of permutations(names)){
 const cache=new Map(),users=new Set(),writes=new Map(),calls=new Map();let next=0x2000000;
 const ctx={AutoCombatUIStatic:{},CODE:1,CACHE:{get:k=>cache.get(k),put:(k,v)=>cache.set(k,v),setup:()=>{},getTag:()=>1,addUser:(_,n)=>users.add(n),delUser:(_,n)=>users.delete(n),hasUsers:()=>users.size>0,del:k=>cache.delete(k)}};
 ctx.Exe={ActivePatch:1,ActivateGlobal:()=>{},BeginTag:()=>{},EndTag:()=>{},Vir2Phy:x=>x,SetHex:(p,h)=>writes.set(p,h.replace(/ /g,'')),SetUint32:(p,v)=>{const b=Buffer.alloc(4);b.writeUInt32LE(v);writes.set(p,b.toString('hex'));},SetCALL:(p,v)=>calls.set(p,v)};
 vm.createContext(ctx);vm.runInContext(helpers.slice(helpers.indexOf('AutoCombatUIStatic.bytesToHex ='),helpers.indexOf('AutoCombatUIStatic.asciiBytes =')),ctx);
 const alloc=(size,alignment)=>{next=Math.ceil(next/alignment)*alignment;const p=next;next+=size;return {phy:p,vir:p,size};};
 Object.assign(ctx.AutoCombatUIStatic,{assertCode:()=>{},allocateBytes:(b,a)=>{const p=alloc(b.length,a);ctx.Exe.SetHex(p.phy,Buffer.from(b).toString('hex'));return p;},allocateCode:a=>{const size=a.finish(next).replace(/ /g,'').length/2,p=alloc(size,16);ctx.Exe.SetHex(p.phy,a.finish(p.vir));return p;}});
 ctx.AutoCombatUI={nativeHelpers:ctx.AutoCombatUIStatic};
 for(const n of names)vm.runInContext(fs.readFileSync(path.join(root,'Scripts/Patches',n+'.qjs'),'utf8'),ctx);
 const callbacks={},fallbacks={};
 const capture=label=>{
  const route=cache.get('StorageInventoryCart.Cursor.v3');assert(route);
  const want=callbacks.celestial||route.routerVir;
  for(const site of [0xC75165,0xD26DA0,0xD27471])assert.equal(calls.get(site),want);
  assert.equal(fallbacks.inventory??route.cartDispatchVir,route.cartDispatchVir);
  assert.equal(fallbacks.cart??route.storageDispatchVir,route.storageDispatchVir);
  assert.equal(fallbacks.storage??0xA74410,0xA74410);
  assert.equal(fallbacks.celestial??route.routerVir,route.routerVir);
  const oldCallbacks={};for(const k of ['inventory','cart','storage'])if(callbacks[k])oldCallbacks[k]=callbacks[k];
  cases.push({label,route:JSON.parse(JSON.stringify(route)),callbacks:oldCallbacks,code:[...writes].map(([address,hex])=>({address,hex})),circleWrapper:callbacks.celestial||0});
 };
 for(const n of order){const key={InventoryUI:'inventory',CartUI:'cart',StorageUI:'storage',CelestialDial:'celestial'}[n];fallbacks[key]=ctx[n].cursorTarget();callbacks[key]=0x3000000+names.indexOf(n)*0x100;ctx[n].installCursor(callbacks[key]);capture(order.join(',')+': add '+n);}
 for(const n of [...order].reverse()){const key={InventoryUI:'inventory',CartUI:'cart',StorageUI:'storage',CelestialDial:'celestial'}[n];ctx[n].cleanup();delete callbacks[key];if(users.size)capture(order.join(',')+': remove '+n);else for(const site of [0xC75165,0xD26DA0,0xD27471])assert.equal(calls.get(site),fallbacks.celestial);}
}
fs.writeFileSync(process.argv[2],JSON.stringify(cases));console.log('PASS 24 selection orders and reverse cleanup; '+cases.length+' x86 fixture states emitted');
