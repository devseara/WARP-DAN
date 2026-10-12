// Execute the actual installer with virtual files: no user's assets are modified.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'Scripts/Patches/BarterUI.qjs'),'utf8');
const files=new Set(),copies=[],dirs=[];
const context={Warp:{Path:'WARP',TgtExe:'GAME/test.exe',TestMode:false},ModernChatUI:{nativeHelpers:{uiPrefix:()=> 'UI'}},
 System:{DirPath:()=> 'GAME',MkDir:p=>(dirs.push(p),true),Copy:(s,d,overwrite)=>{assert.equal(overwrite,false);assert(files.has(s));assert(!files.has(d),'existing asset overwritten');files.add(d);copies.push([s,d]);return true;}},
 BinFile:function(p){this.Valid=files.has(p);this.Close=()=>{};}};
vm.createContext(context);vm.runInContext(source,context);
const list=Array.from(context.BarterUI.assets());assert.equal(list.length,17);assert(!list.some(s=>s.includes('cancel2')));
for(const file of list)files.add('WARP/Assets/BarterUI/'+file);
context.BarterUI.onApplied();assert.equal(copies.length,17);assert.equal(dirs.length,5);
context.BarterUI.onApplied();assert.equal(copies.length,17);assert.equal(dirs.length,5);
for(const file of list)files.delete('GAME/data/texture/UI/'+file);
files.add('GAME/data/texture/UI/genericsui/buy_out.png');context.BarterUI.onApplied();assert.equal(copies.length,33);
context.Warp.TestMode=true;context.BarterUI.onApplied();assert.equal(copies.length,33);
context.Warp.TestMode=false;files.delete('GAME/data/texture/UI/barter/bg_buy.png');files.delete('WARP/Assets/BarterUI/barter/bg_buy.png');assert.throws(()=>context.BarterUI.onApplied(),/missing bundled asset/);assert.equal(copies.length,33);
const crypto=require('crypto'),manifest=JSON.parse(fs.readFileSync(path.join(root,'Assets/BarterUI/sha256.json')));
for(const file of list){const data=fs.readFileSync(path.join(root,'Assets/BarterUI',file));assert.equal(crypto.createHash('sha256').update(data).digest('hex'),manifest[file]);}
console.log('PASS: 17 exact PNGs, matching four-state buttons, fresh/existing/partial installs, no overwrites, test-mode isolation and missing-source failure');
