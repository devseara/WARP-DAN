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
const menuAssets=['','old_'].flatMap(theme=>['normal','mouseon','pressed'].map(state=>'menuicon/bt_vip_'+theme+state+'.bmp'));
menuAssets.push(...['bt_vip.bmp','bt_vip_disabled.bmp','bt_vip_new.bmp','bt_vip_new_press.bmp','bt_vip_press.bmp','bt_vip_old_disabled.bmp'].map(name=>'menuicon/'+name));
const bundleMenu=path.join(__dirname,'../Assets/VipUI/menuicon');
const manifest=JSON.parse(fs.readFileSync(path.join(bundleMenu,'manifest.json'),'utf8'));
assert.equal(menuAssets.length,12);
assert.deepEqual(Object.keys(manifest.files).sort(),menuAssets.map(name=>path.basename(name)).sort());
for(const [name,entry] of Object.entries(manifest.files)) {
    const bytes=fs.readFileSync(path.join(bundleMenu,name));
    assert.equal(require('node:crypto').createHash('sha256').update(bytes).digest('hex'),entry.sha256,name);
    assert.equal(bytes.toString('ascii',0,2),'BM',name);
    assert.deepEqual([bytes.readInt32LE(18),bytes.readInt32LE(22)],entry.size,name);
    assert.equal(bytes.readUInt16LE(28),24,name);
}
for(const [alias,original] of [['bt_vip_press.bmp','bt_vip_pressed.bmp'],['bt_vip_old_disabled.bmp','bt_vip_old_normal.bmp']])
    assert(fs.readFileSync(path.join(bundleMenu,alias)).equals(fs.readFileSync(path.join(bundleMenu,original))),alias);
const backgroundAssets=['bg_m7.tga','bg_o7.tga'];
const parent = p => p.slice(0, p.lastIndexOf('/'));
function fixture() {
    const root = 'F:/Custom target/game folder', target = root + '/data/texture/UI-prefix/vipui';
    const menuTarget = parent(target) + '/uirenewal/menuicon';
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
    assert.equal(api.assets.length,7);
    assert(api.assets.every(name=>!name.includes('readable_')));
    assert.deepEqual([...api.assets].sort(),['item_main_bg.png','membership_crown.png','vip_design.png','button_out.png','button_over.png','button_press.png','button_off.png'].sort());
    assert.deepEqual(fs.readdirSync(path.join(__dirname,'../Assets/VipUI')).filter(name=>name!=='menuicon').sort(),[...api.assets].sort(), 'Bundle must contain only used VIP images');
    for(const name of [...api.assets,...menuAssets]) {
        assert(fs.existsSync(path.join(__dirname,'../Assets/VipUI',name)),name);
        files.set(env.Path+'/Assets/VipUI/'+name,'bundled:'+name);
    }
    for(const name of backgroundAssets)files.set(env.Path+'/Assets/ROGlobalZeroMenu/menuicon/'+name,'bundled:'+name);
    return {...api,env,files,dirs,calls,state,root,target,menuTarget};
}
let f=fixture();f.install();assert.equal(f.calls.filter(c=>c[0]==='mkdir').length,6);
assert.equal(f.calls.filter(c=>c[0]==='copy').length,21);
for(const name of f.assets)assert.equal(f.files.get(f.target+'/'+name),'bundled:'+name);
for(const name of menuAssets)assert.equal(f.files.get(f.menuTarget+'/'+path.basename(name)),'bundled:'+name);
for(const name of backgroundAssets)assert.equal(f.files.get(f.menuTarget+'/'+name),'bundled:'+name);
assert(!f.dirs.has(f.target+'/menuicon'),'VIP icons must use the shared Renewal menu folder');
assert.equal(f.state.opened,f.state.closed);
assert(!f.calls.some(c=>c[0]==='copy' && c[2].includes('bt_booking')),'Reference samples must not be installed');
f.files.set(f.target+'/vip_design.png','custom artwork');f.calls.length=0;f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,0);
f.files.delete(f.target+'/item_main_bg.png');f.install();
assert.equal(f.calls.filter(c=>c[0]==='copy').length,1);assert.equal(f.files.get(f.target+'/vip_design.png'),'custom artwork');
f=fixture();f.env.TestMode=true;f.install();assert.equal(f.calls.length,0);assert.equal(f.state.opened,0);
f=fixture();f.state.failDir=f.root+'/data/texture';assert.throws(f.install,/cannot create/);assert(!f.calls.some(c=>c[0]==='copy'));
f=fixture();f.state.failCopy=f.target+'/button_out.png';assert.throws(f.install,/cannot copy button_out.png/);
f=fixture();f.files.delete(f.env.Path+'/Assets/VipUI/button_over.png');assert.throws(f.install,/cannot copy button_over.png/);
f=fixture();f.files.set(f.target+'/button_out.png','custom button background');
f.files.set(f.target+'/unknown-custom.png','unrelated image');f.install();
assert.equal(f.files.get(f.target+'/button_out.png'),'custom button background');
assert.equal(f.files.get(f.target+'/unknown-custom.png'),'unrelated image');
f=fixture();f.files.set(f.target+'/membership_crown.png','custom crown');f.install();assert.equal(f.files.get(f.target+'/membership_crown.png'),'custom crown');
f=fixture();f.files.set(f.menuTarget+'/'+path.basename(menuAssets[0]),'custom VIP menu icon');f.install();assert.equal(f.files.get(f.menuTarget+'/'+path.basename(menuAssets[0])),'custom VIP menu icon');
f=fixture();f.state.failCopy=f.menuTarget+'/'+path.basename(menuAssets[1]);assert.throws(f.install,/cannot copy bt_vip_/);
for(const name of ['bt_vip_press.bmp','bt_vip_old_disabled.bmp']) {
    f=fixture();f.files.set(f.menuTarget+'/'+name,'custom alias');f.install();
    assert.equal(f.files.get(f.menuTarget+'/'+name),'custom alias');
    f=fixture();f.files.delete(f.env.Path+'/Assets/VipUI/menuicon/'+name);
    assert.throws(f.install,new RegExp('cannot copy '+name.replace('.', '\\.')));
}
f=fixture();f.state.failDir=f.menuTarget;assert.throws(f.install,/cannot create/);
assert(!f.calls.some(c=>c[0]==='copy' && c[2].startsWith(f.menuTarget+'/')));
// A previous package's private icon folder must not prevent the correct folder
// being populated, and neither it nor existing shared-folder art is removed.
f=fixture();f.files.set(f.target+'/'+menuAssets[0],'older private icon');f.install();
assert.equal(f.files.get(f.target+'/'+menuAssets[0]),'older private icon');
assert.equal(f.files.get(f.menuTarget+'/'+path.basename(menuAssets[0])),'bundled:'+menuAssets[0]);
// Repeat against real temporary directories with spaces and the client prefix.
// The only removed file is a test-owned copy in this newly allocated directory.
const temp=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'vip-assets-install-'));
const env={Path:path.resolve(__dirname,'..').replaceAll('\\','/'),TgtExe:(temp+'/game.exe').replaceAll('\\','/'),TestMode:false};
const target=path.join(temp,'data','texture','À¯ÀúÀÎÅÍÆäÀÌ½º','vipui');
const menuTarget=path.join(path.dirname(target),'uirenewal','menuicon');
let copies=0;
const real=create(env,{
    DirPath:p=>path.dirname(p),
    MkDir(p){try{if(!fs.existsSync(p))fs.mkdirSync(p);return fs.statSync(p).isDirectory();}catch{return false;}},
    Copy(from,to,overwrite){assert.equal(overwrite,false);try{fs.copyFileSync(from,to,fs.constants.COPYFILE_EXCL);copies++;return true;}catch{return false;}}
},function(p,mode){assert.equal(mode,'r');this.Valid=fs.existsSync(p);this.Close=()=>{};},
{nativeHelpers:{uiPrefix:()=> 'À¯ÀúÀÎÅÍÆäÀÌ½º'}});
assert(!fs.existsSync(target));real.install();assert.equal(copies,21);
for(const name of real.assets)assert(fs.readFileSync(path.join(target,name)).equals(fs.readFileSync(path.join(env.Path,'Assets/VipUI',name))),name);
for(const name of menuAssets)assert(fs.readFileSync(path.join(menuTarget,path.basename(name))).equals(fs.readFileSync(path.join(env.Path,'Assets/VipUI',name))),name);
assert(!fs.existsSync(path.join(target,'menuicon')));
real.install();assert.equal(copies,21,'Repeat must not overwrite existing artwork');
fs.unlinkSync(path.join(target,'button_press.png'));
real.install();assert.equal(copies,22,'Repair must only copy the missing PNG');
assert(fs.readFileSync(path.join(target,'button_press.png')).equals(fs.readFileSync(path.join(env.Path,'Assets/VipUI/button_press.png'))));
for(const name of ['bt_vip_new.bmp','bt_vip_press.bmp','bt_vip_old_disabled.bmp']) {
    fs.unlinkSync(path.join(menuTarget,name));
    const before=copies;real.install();assert.equal(copies,before+1,'Repair must only restore missing '+name);
    assert(fs.readFileSync(path.join(menuTarget,name)).equals(fs.readFileSync(path.join(bundleMenu,name))),name);
}
if(process.argv[2])fs.writeFileSync(process.argv[2],JSON.stringify({textureRoot:path.dirname(path.dirname(target)),menuTarget,files:menuAssets.map(name=>path.basename(name))},null,2));
console.log('PASS: selecting VIP installs all 12 menu BMPs and 2 backgrounds into uirenewal/menuicon, verifies manifest hashes/formats/aliases, preserves 7 VIP PNG paths/custom artwork, creates missing folders, repairs missing files and handles copy failures; no private menu directory created.');
