/* Apply the actual QJS against read-only source bytes; emit emulator writes, never a PE. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(process.argv[2]),output=process.argv[3];
const pe=source.readUInt32LE(0x3c),opt=pe+24,base=source.readUInt32LE(opt+28),section=opt+source.readUInt16LE(pe+20);
const original=Buffer.alloc(source.readUInt32LE(opt+56));
for(let i=0;i<source.readUInt16LE(pe+6);i++){
 const s=section+i*40;source.copy(original,source.readUInt32LE(s+12),source.readUInt32LE(s+20),source.readUInt32LE(s+20)+source.readUInt32LE(s+16));
}
const sites=[0x7890DE,0x78922E,0x7894E2,0x789500,0xCB84ED,0xCB8437,0xCB7870];
function apply(corrupt){
 const src=Buffer.from(original),writes=[],allocations=[];let heap=0x22000000;
 if(corrupt)src[corrupt-base]=0x90;
 const context={Warp:{Path:root},AutoCombatUIStatic:{},CODE:0,$$:()=>{},
  BinFile:function(p){this.Valid=fs.existsSync(p);this.ReadHex=()=>fs.readFileSync(p).toString('hex');this.Close=()=>{};},
  Exe:{BuildDate:20250716,Vir2Phy:va=>va-base,GetUint8:p=>src[p],GetUint32:p=>src.readUInt32LE(p),
   SetHex:(p,h)=>writes.push({va:p+base,hex:h.replace(/\s/g,'')}),
   Allocate:(n,align)=>{heap=(heap+align-1)&-align;const va=heap;heap+=n;allocations.push({va,size:n});return[va-base,va];},
   SetCALL:(p,target)=>{const b=Buffer.alloc(5);b[0]=0xe8;b.writeInt32LE(target-(base+p+5),1);writes.push({va:base+p,hex:b.toString('hex')});}}};
 vm.createContext(context);
 const helpers=fs.readFileSync(path.join(root,'Scripts/Patches/AutoCombatUI.qjs'),'utf8');
 vm.runInContext(helpers.slice(helpers.indexOf('AutoCombatUIStatic.bytesToHex ='),helpers.indexOf('AutoCombatUIStatic.asciiBytes =')),context);
 const n=context.AutoCombatUIStatic;context.AutoCombatUI={nativeHelpers:n};
 n.ItemInfoManager=0x159C088;n.ItemInfoLookup=0xA7E780;
 n.allocateString=s=>n.allocateBytes(Array.from(Buffer.from(s+'\0')));n.buildResourcePath=n.allocateString;
 n.assertCode=(label,va,expected)=>assert.equal(src.subarray(va-base,va-base+expected.replace(/\s/g,'').length/2).toString('hex'),expected.replace(/\s/g,'').toLowerCase(),label);
 vm.runInContext(fs.readFileSync(path.join(root,'Scripts/Patches/NoticeMarquee.qjs'),'utf8'),context);
 if(corrupt){assert.throws(()=>context.NoticeMarquee('NoticeMarquee'));assert.equal(writes.length,0);return;}
 assert.equal(context.NoticeMarquee('NoticeMarquee'),true);
 assert.deepEqual(writes.filter(w=>w.va<0x22000000).map(w=>w.va),sites);
 assert(writes.filter(w=>w.va<0x22000000).every(w=>w.hex.length===10));
 const record=writes.find(w=>w.va===allocations.at(-1).va),b=Buffer.from(record.hex,'hex');
 const fields=['marker','payload','api','measure','height','draw','split','links'];
 const contract=Object.fromEntries(fields.map((f,i)=>[f,b.readUInt32LE(i*4)]));
 if(output)fs.writeFileSync(output,JSON.stringify({contract,writes},null,2));
}
apply();for(const site of sites)apply(site);
console.log('PASS actual announcement QJS: seven scoped calls, payload validation, relocation, guards reject altered calls before any writes; no EXE emitted');
