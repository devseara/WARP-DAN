// Execute the actual installer with virtual files: no user's assets are modified.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'Scripts/Patches/ShopUI.qjs'),'utf8');
const files=new Set(),copies=[],dirs=[];
const context={Warp:{Path:'WARP',TgtExe:'GAME/test.exe',TestMode:false},ModernChatUI:{nativeHelpers:{uiPrefix:()=> 'UI'}},
 System:{DirPath:()=> 'GAME',MkDir:p=>(dirs.push(p),true),Copy:(s,d,overwrite)=>{assert.equal(overwrite,false);assert(files.has(s));assert(!files.has(d),'existing asset overwritten');files.add(d);copies.push([s,d]);return true;}},
 BinFile:function(p){this.Valid=files.has(p);this.Close=()=>{};}};
vm.createContext(context);vm.runInContext(source,context);
const list=Array.from(context.ShopUI.assets());assert.equal(list.length,21);assert(!list.some(s=>s.includes('cancel2')));
for(const file of list)files.add('WARP/Assets/ShopUI/'+file);
context.ShopUI.onApplied();assert.equal(copies.length,21);assert.equal(dirs.length,5);
context.ShopUI.onApplied();assert.equal(copies.length,21);assert.equal(dirs.length,5);
for(const file of list)files.delete('GAME/data/texture/UI/'+file);
files.add('GAME/data/texture/UI/genericsui/buy_out.png');context.ShopUI.onApplied();assert.equal(copies.length,41);
context.Warp.TestMode=true;context.ShopUI.onApplied();assert.equal(copies.length,41);
context.Warp.TestMode=false;files.delete('GAME/data/texture/UI/barter/bg_buy.png');files.delete('WARP/Assets/ShopUI/barter/bg_buy.png');assert.throws(()=>context.ShopUI.onApplied(),/missing bundled asset/);assert.equal(copies.length,41);
const crypto=require('crypto'),manifest=JSON.parse(fs.readFileSync(path.join(root,'Assets/ShopUI/sha256.json')));
for(const file of list){const data=fs.readFileSync(path.join(root,'Assets/ShopUI',file));assert.equal(crypto.createHash('sha256').update(data).digest('hex'),manifest[file]);}
console.log('PASS: 21 exact PNGs, matching Buy/Cancel states and three original Sell states, fresh/existing/partial installs, no overwrites, test-mode isolation and missing-source failure');
