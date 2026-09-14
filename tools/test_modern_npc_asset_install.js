/* Runs the actual QJS installer with explicit filesystem boundary doubles. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../Scripts/Patches/ModernNpcDialog.qjs'), 'utf8').replace(/\r\n/g, '\n');
const config = source.slice(source.indexOf('const ModernNpcDialogStatic = {'), source.indexOf('\n};') + 3);
const start = source.indexOf('ModernNpcDialog.onApplied = function()');
const installer = source.slice(start, source.indexOf('\n};', start) + 3);
assert(start > 0 && config.length > 100);
const create = new Function('Warp', 'System', 'BinFile', 'ModernChatUI', config +
    '\nconst ModernNpcDialog = {};\n' + installer +
    '\nreturn {config: ModernNpcDialogStatic, install: ModernNpcDialog.onApplied};');
const prefix = String.fromCharCode(0xC0, 0xAF, 0xC0, 0xFA, 0xC0, 0xCE, 0xC5, 0xCD, 0xC6, 0xE4, 0xC0, 0xCC, 0xBD, 0xBA);
const parent = value => value.slice(0, value.lastIndexOf('/'));
function fixture() {
    const root = 'F:/Different target/game folder';
    const env = {Path: 'D:/warp/WARP20250716-main', TgtExe: root + '/Ragnarok.exe', TestMode: false};
    const files = new Map(), dirs = new Set([root]), operations = [];
    const state = {opened: 0, closed: 0, failDirectory: null, failCopy: null};
    const api = create(env, {
        DirPath(value) { assert.equal(value, env.TgtExe); return parent(value); },
        MkDir(value) {
            operations.push(['mkdir', value]);
            if (value === state.failDirectory || !dirs.has(parent(value))) return false;
            dirs.add(value); return true;
        },
        Copy(from, to, overwrite) {
            assert.equal(overwrite, false);
            operations.push(['copy', from, to]);
            if (to === state.failCopy || files.has(to) || !files.has(from) || !dirs.has(parent(to))) return false;
            files.set(to, files.get(from)); return true;
        }
    }, function(value, mode) {
        assert.equal(mode, 'r'); state.opened++;
        this.Valid = files.has(value);
        this.Close = () => { state.closed++; };
    }, {nativeHelpers: {uiPrefix: () => prefix}});
    const sourceDir = env.Path + '/Assets/ModernNpcDialog';
    const targetDir = root + '/data/texture/' + prefix + '/genericsui';
    for (const name of api.config.Assets) files.set(sourceDir + '/' + name, 'bundle:' + name);
    return {...api, root, env, files, dirs, operations, state, sourceDir, targetDir};
}
let f = fixture(); f.install();
assert.equal(f.operations.filter(op => op[0] === 'mkdir').length, 4);
assert.equal(f.operations.filter(op => op[0] === 'copy').length, 25);
for (const name of f.config.Assets) assert.equal(f.files.get(f.targetDir + '/' + name), 'bundle:' + name);
assert.equal(f.state.opened, f.state.closed);
f.files.set(f.targetDir + '/sell_out.png', 'user edited Sell');
f.operations.length = 0; f.install();
assert.equal(f.operations.length, 0);
f.files.delete(f.targetDir + '/ok_out.png'); f.install();
assert.equal(f.operations.filter(op => op[0] === 'copy').length, 1);
assert.equal(f.files.get(f.targetDir + '/sell_out.png'), 'user edited Sell');
f = fixture(); f.files.set(f.sourceDir + '/sell_off.png', 'optional disabled'); f.install();
assert.equal(f.files.get(f.targetDir + '/sell_off.png'), 'optional disabled');
f = fixture(); f.env.TestMode = true; f.install();
assert.equal(f.state.opened, 0); assert.equal(f.operations.length, 0);
f = fixture(); f.files.delete(f.sourceDir + '/sell_press.png');
assert.throws(f.install, /missing bundled image .*sell_press.png/);
assert.equal(f.operations.length, 0); assert.equal(f.state.opened, f.state.closed);
f = fixture(); f.state.failDirectory = f.root + '/data/texture';
assert.throws(f.install, /cannot create/);
assert(!f.operations.some(op => op[0] === 'copy'));
f = fixture(); f.state.failCopy = f.targetDir + '/ok_out.png';
assert.throws(f.install, /cannot copy ok_out.png/);
console.log('PASS: all 25 supplied PNGs, output directory chain, optional Sell disabled image, no-overwrite repeat/repair, test-mode isolation and explicit errors');
