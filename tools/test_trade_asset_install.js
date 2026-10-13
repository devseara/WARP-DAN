/* Execute the actual installer against explicit filesystem boundaries. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'Scripts/Patches/TradeUI.qjs'),'utf8');
assert(source.startsWith('/*'));assert(!/(?<!\r)\n/.test(source));
const installer=source.slice(source.indexOf('TradeUI.assets=()=>'));
const create=new Function('Warp','System','BinFile','ModernChatUI','const TradeUI={};\n'+installer+'\nreturn TradeUI;');
function fixture(){
 const files=new Map(),dirs=new Set(['F:/Game']),calls=[];const state={opened:0,closed:0,fail:null};
 const env={Path:'X:/WARP',TgtExe:'F:/Game/test.exe',TestMode:false},target='F:/Game/data/texture/UI';
 const parent=p=>p.slice(0,p.lastIndexOf('/'));
 const ui=create(env,{DirPath:parent,MkDir(p){if(p===state.fail || !dirs.has(parent(p)))return false;dirs.add(p);return true;},Copy(from,to,overwrite){assert.equal(overwrite,false);if(to===state.fail || files.has(to) || !files.has(from) || !dirs.has(parent(to)))return false;files.set(to,files.get(from));calls.push(to);return true;}},function(p,mode){assert.equal(mode,'r');state.opened++;this.Valid=files.has(p);this.Close=()=>state.closed++;},{nativeHelpers:{uiPrefix:()=> 'UI'}});
 for(const rel of ui.assets())files.set(env.Path+'/Assets/TradeUI/'+rel,fs.readFileSync(path.join(root,'Assets/TradeUI',rel)));
 return {ui,env,files,dirs,calls,state,target};
}
let f=fixture();assert.equal(f.ui.assets().length,21);f.ui.onApplied();assert.equal(f.calls.length,21);assert.equal(f.state.opened,f.state.closed);
f.files.set(f.target+'/tradeui/bg.png','custom');f.ui.onApplied();assert.equal(f.calls.length,21);assert.equal(f.files.get(f.target+'/tradeui/bg.png'),'custom');
f=fixture();f.env.TestMode=true;f.ui.onApplied();assert.equal(f.calls.length,0);
f=fixture();f.files.delete(f.env.Path+'/Assets/TradeUI/tradeui/bg.png');assert.throws(()=>f.ui.onApplied(),/missing bundled asset/);assert.equal(f.calls.length,0);
f=fixture();f.state.fail='F:/Game/data';assert.throws(()=>f.ui.onApplied(),/cannot create/);
const hashes=JSON.parse(fs.readFileSync(path.join(root,'Assets/TradeUI/sha256.json'),'utf8'));
assert.deepEqual(Object.keys(hashes).sort(),f.ui.assets().sort());for(const [rel,hash] of Object.entries(hashes))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'Assets/TradeUI',rel))).digest('hex'),hash);
console.log('PASS TradeUI asset hashes, fresh/missing-only install, custom art preservation, test mode and missing/failing filesystem boundaries');
