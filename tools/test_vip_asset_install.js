/* Execute the actual Vip installer with explicit filesystem boundaries. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../Scripts/Patches/VipUI.qjs'), 'utf8').replace(/\r\n/g, '\n');
const config = source.slice(source.indexOf('const VipUIStatic = {'), source.indexOf('\n};') + 3);
const start = source.indexOf('VipUI.onApplied=function()');
assert(start > 0);
const installer = source.slice(start, source.indexOf('\n};', start) + 3);
assert(!source.includes('.flat('),'Target WARP runtime does not implement Array.flat');
const create = new Function('Warp', 'System', 'BinFile', 'ModernChatUI', config + '\nconst VipUI={};\n' + installer + '\nreturn {assets:[...new Set([...VipUIStatic.assets,...[].concat(...VipUIStatic.buttons),...VipUIStatic.purchase,...VipUIStatic.cardAssets,...[].concat(...VipUIStatic.mainButtons)].filter(Boolean))],install:VipUI.onApplied};');
const parent = p => p.slice(0, p.lastIndexOf('/'));
function fixture() {
    const root = 'F:/Custom target/game folder', target = root + '/data/texture/UI-prefix/vipui';
    const env = {Path:'X:/WARP',TgtExe:root+'/game.exe',TestMode:false};
    const files = new Map(), dirs = new Set([root]), calls = [];
    const state = {opened:0,closed:0,failDir:null,failCopy:null};
    const api = create(env, {
        DirPath(p) {assert.equal(p,env.TgtExe);return parent(p);},
        MkDir(p) {calls.push(['mkdir',p]);if(p===state.failDir || !dirs.has(parent(p)))return false;dirs.add(p);return true;},
        Copy(from,to,overwrite) {
            assert.equal(overwrite,false);calls.push(['copy',from,to]);
            if(to===state.failCopy || files.has(to) || !files.has(from) || !dirs.has(parent(to)))return false;
            files.set(to,files.get(from));return true;
        }
    }, function(p,mode) {assert.equal(mode,'r');state.opened++;this.Valid=files.has(p);this.Close=()=>state.closed++;},
    {nativeHelpers:{uiPrefix:()=> 'UI-prefix'}});
    assert.equal(api.assets.length,63);
    assert(api.assets.every(name=>!name.includes('readable_')));
    assert.deepEqual([...api.assets].sort(),fs.readdirSync(path.join(__dirname,'../Assets/VipUI')).sort(), 'Bundle must contain only used images');
    for(const name of api.assets) {
        assert(fs.existsSync(path.join(__dirname,'../Assets/VipUI',name)),name);
        files.set(env.Path+'/Assets/VipUI/'+name,'bundled:'+name);
    }
    return {...api,env,files,dirs,calls,state,root,target};
}
let f=fixture();f.install();assert.equal(f.calls.filter(c=>c[0]==='mkdir').length,4);
assert.equal(f.calls.filter(c=>c[0]==='copy').length,63);
for(const name of f.assets)assert.equal(f.files.get(f.target+'/'+name),'bundled:'+name);
assert.equal(f.state.opened,f.state.closed);
f.files.set(f.target+'/vip_design.png','custom artwork');f.calls.length=0;f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,0);
f.files.delete(f.target+'/item_main_bg.png');f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,1);assert.equal(f.files.get(f.target+'/vip_design.png'),'custom artwork');
f=fixture();f.env.TestMode=true;f.install();assert.equal(f.calls.length,0);assert.equal(f.state.opened,0);
f=fixture();f.state.failDir=f.root+'/data/texture';assert.throws(f.install,/cannot create/);assert(!f.calls.some(c=>c[0]==='copy'));
f=fixture();f.state.failCopy=f.target+'/upgrade_out.png';assert.throws(f.install,/cannot copy upgrade_out.png/);
f=fixture();f.files.delete(f.env.Path+'/Assets/VipUI/openstore_out.png');assert.throws(f.install,/cannot copy openstore_out.png/);
f=fixture();f.files.set(f.target+'/applyvip_out.png','custom complete button');
f.files.set(f.target+'/unknown-custom.png','unrelated image');f.install();
assert.equal(f.files.get(f.target+'/applyvip_out.png'),'custom complete button');
assert.equal(f.files.get(f.target+'/unknown-custom.png'),'unrelated image');
f=fixture();f.files.set(f.target+'/membership_crown.png','custom crown');f.install();assert.equal(f.files.get(f.target+'/membership_crown.png'),'custom crown');
// Repeat against real Windows directories with spaces and the client's UI prefix.
// The only removed file is a test-owned copy in this newly allocated directory.
const temp=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'vip-assets-install-'));
const env={Path:path.resolve(__dirname,'..').replaceAll('\\','/'),TgtExe:(temp+'/game.exe').replaceAll('\\','/'),TestMode:false};
const target=path.join(temp,'data','texture','À¯ÀúÀÎÅÍÆäÀÌ½º','vipui');
let copies=0;
const real=create(env,{
    DirPath:p=>path.dirname(p),
    MkDir(p){try{if(!fs.existsSync(p))fs.mkdirSync(p);return fs.statSync(p).isDirectory();}catch{return false;}},
    Copy(from,to,overwrite){assert.equal(overwrite,false);try{fs.copyFileSync(from,to,fs.constants.COPYFILE_EXCL);copies++;return true;}catch{return false;}}
},function(p,mode){assert.equal(mode,'r');this.Valid=fs.existsSync(p);this.Close=()=>{};},
{nativeHelpers:{uiPrefix:()=> 'À¯ÀúÀÎÅÍÆäÀÌ½º'}});
assert(!fs.existsSync(target));real.install();assert.equal(copies,63);
for(const name of real.assets)assert(fs.readFileSync(path.join(target,name)).equals(fs.readFileSync(path.join(env.Path,'Assets/VipUI',name))),name);
real.install();assert.equal(copies,63,'Repeat must not overwrite existing artwork');
fs.unlinkSync(path.join(target,'main_upgrade_press.png'));
real.install();assert.equal(copies,64,'Repair must only copy the missing PNG');
assert(fs.readFileSync(path.join(target,'main_upgrade_press.png')).equals(fs.readFileSync(path.join(env.Path,'Assets/VipUI/main_upgrade_press.png'))));
console.log('PASS: exactly 63 used VIP PNGs / 60 complete button states, canonical names, real folder creation, no-overwrite repeat and partial repair, test-mode isolation and explicit failure handling.');
