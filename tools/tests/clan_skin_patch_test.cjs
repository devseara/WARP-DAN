// Exercise patch rejection before any executable mutation.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const source=fs.readFileSync(path.join(root,'Scripts/Patches/ClanBodySkins.qjs'),'utf8');
let corrupt=false,missing=false,oldApi=false,reads=0,writes=0;
const context=vm.createContext({
  CODE:0, Warp:{Path:root}, $$:()=>{},
  Exe:{BuildDate:20250716,Vir2Phy:()=>{reads++;throw Error('native-read');},Allocate:()=>{writes++;throw Error('unexpected-write');}},
  BinFile:class {
    constructor(name){this.name=name;this.Valid=!missing;}
    ReadHex(){let b=fs.readFileSync(this.name);if(corrupt&&this.name.endsWith('.cskb')){b=Buffer.from(b);b[b.length-1]^=1;}if(oldApi&&this.name.endsWith('runtime.json')){const m=JSON.parse(b);m.api_version=1;b=Buffer.from(JSON.stringify(m));}return b.toString('hex');}
    Close(){}
  }
});
vm.runInContext(source,context);
const run=s=>vm.runInContext(s,context);
assert.equal(run('ClanBodySkins.validate()'),true);
context.Exe.BuildDate=20260219;assert.equal(run('ClanBodySkins.validate()'),false);
assert.throws(()=>run('ClanBodySkins("test")'),/2025-07-16/);assert.equal(reads,0);assert.equal(writes,0);
context.Exe.BuildDate=20250716;missing=true;assert.throws(()=>run('ClanBodySkins("test")'),/missing/);assert.equal(reads,0);
missing=false;corrupt=true;assert.throws(()=>run('ClanBodySkins("test")'),/CRC mismatch/);assert.equal(reads,0);assert.equal(writes,0);
corrupt=false;oldApi=true;assert.throws(()=>run('ClanBodySkins("test")'),/metadata\/CRC mismatch/);assert.equal(reads,0);assert.equal(writes,0);oldApi=false;
assert.throws(()=>run('ClanBodySkins("test")'),/native-read/);assert.equal(reads,1);assert.equal(writes,0);
console.log('PASS: unsupported client, missing/corrupt payload rejection; valid payload reaches native-profile validation before writes.');
