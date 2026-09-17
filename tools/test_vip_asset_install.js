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
const create = new Function('Warp', 'System', 'BinFile', 'ModernChatUI', config + '\nconst VipUI={};\n' + installer + '\nreturn {assets:[...new Set([...VipUIStatic.assets,...[].concat(...VipUIStatic.buttons),...VipUIStatic.purchase,...VipUIStatic.cardAssets])],install:VipUI.onApplied};');
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
    assert.equal(api.assets.length,58);
    for(const name of api.assets) {
        assert(fs.existsSync(path.join(__dirname,'../Assets/VipUI',name)),name);
        files.set(env.Path+'/Assets/VipUI/'+name,'bundled:'+name);
    }
    return {...api,env,files,dirs,calls,state,root,target};
}
let f=fixture();f.install();assert.equal(f.calls.filter(c=>c[0]==='mkdir').length,4);
assert.equal(f.calls.filter(c=>c[0]==='copy').length,58);
for(const name of f.assets)assert.equal(f.files.get(f.target+'/'+name),'bundled:'+name);
assert.equal(f.state.opened,f.state.closed);
f.files.set(f.target+'/background.png','custom artwork');f.calls.length=0;f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,0);
f.files.delete(f.target+'/star_on.png');f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,1);assert.equal(f.files.get(f.target+'/background.png'),'custom artwork');
f=fixture();f.env.TestMode=true;f.install();assert.equal(f.calls.length,0);assert.equal(f.state.opened,0);
f=fixture();f.state.failDir=f.root+'/data/texture';assert.throws(f.install,/cannot create/);assert(!f.calls.some(c=>c[0]==='copy'));
f=fixture();f.state.failCopy=f.target+'/upgrade_out.png';assert.throws(f.install,/cannot copy upgrade_out.png/);
f=fixture();f.files.delete(f.env.Path+'/Assets/VipUI/openstore_out.png');assert.throws(f.install,/cannot copy openstore_out.png/);
f=fixture();f.files.set(f.target+'/applyvip_out.png','custom complete button');f.install();assert.equal(f.files.get(f.target+'/applyvip_out.png'),'custom complete button');
f=fixture();f.files.set(f.target+'/membership_crown.png','custom crown');f.install();assert.equal(f.files.get(f.target+'/membership_crown.png'),'custom crown');
console.log('PASS: 58 VIP PNGs / 52 complete button states and crown, dedicated Vip folder creation, no-overwrite repeat/repair including custom buttons/crown, test-mode isolation and explicit failure handling');
