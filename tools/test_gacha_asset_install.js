/* Execute the actual Gacha installer with explicit filesystem boundaries. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../Scripts/Patches/GachaUI.qjs'), 'utf8').replace(/\r\n/g, '\n');
const config = source.slice(source.indexOf('const GachaUIStatic = {'), source.indexOf('\n};') + 3);
const start = source.indexOf('GachaUI.onApplied = function()');
assert(start > 0);
const installer = source.slice(start, source.indexOf('\n};', start) + 3);
const create = new Function('Warp', 'System', 'BinFile', 'ModernChatUI', config + '\nconst GachaUI={};\n' + installer + '\nreturn {assets:GachaUIStatic.Assets,install:GachaUI.onApplied};');
const parent = p => p.slice(0, p.lastIndexOf('/'));
function fixture() {
    const root = 'F:/Custom target/game folder', target = root + '/data/texture/UI-prefix/genericsui';
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
    assert.deepEqual(api.assets,['arrow_off_left.png','arrow_off_right.png','arrow_on_left.png','arrow_on_right.png']);
    for(const name of api.assets) {
        assert(fs.existsSync(path.join(__dirname,'../Assets/GachaUI',name)),name);
        files.set(env.Path+'/Assets/GachaUI/'+name,'bundled:'+name);
    }
    return {...api,env,files,dirs,calls,state,root,target};
}
let f=fixture();f.install();assert.equal(f.calls.filter(c=>c[0]==='mkdir').length,4);
assert.equal(f.calls.filter(c=>c[0]==='copy').length,4);
for(const name of f.assets)assert.equal(f.files.get(f.target+'/'+name),'bundled:'+name);
assert.equal(f.state.opened,f.state.closed);
f.files.set(f.target+'/arrow_on_right.png','custom artwork');f.calls.length=0;f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,0);
f.files.delete(f.target+'/arrow_off_left.png');f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,1);assert.equal(f.files.get(f.target+'/arrow_on_right.png'),'custom artwork');
f=fixture();f.env.TestMode=true;f.install();assert.equal(f.calls.length,0);assert.equal(f.state.opened,0);
f=fixture();f.state.failDir=f.root+'/data/texture';assert.throws(f.install,/cannot create/);assert(!f.calls.some(c=>c[0]==='copy'));
f=fixture();f.state.failCopy=f.target+'/arrow_off_right.png';assert.throws(f.install,/cannot install arrow_off_right.png/);
f=fixture();f.files.delete(f.env.Path+'/Assets/GachaUI/arrow_on_left.png');assert.throws(f.install,/cannot install arrow_on_left.png/);
console.log('PASS: four packaged Gacha arrow PNGs, arbitrary target folder creation, no-overwrite repeat/repair, test-mode isolation and explicit failure handling');
