/* Run the actual QJS onApplied installers against isolated filesystem boundaries. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const bundle = path.join(root, 'Assets/StorageInventoryUI');
const hashes = JSON.parse(fs.readFileSync(path.join(bundle, 'sha256.json'), 'utf8'));
for (const [relative, expected] of Object.entries(hashes)) {
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(bundle, relative))).digest('hex'), expected);
}

for (const patch of process.argv.slice(2).length ? process.argv.slice(2) : ['InventoryUI', 'CartUI']) {
    assert(['StorageUI', 'InventoryUI', 'CartUI'].includes(patch));
    const source = fs.readFileSync(path.join(root, `Scripts/Patches/${patch}.qjs`), 'utf8');
    assert(source.startsWith('/*'), `${patch}: UTF-8 without BOM`);
    assert(!/(?<!\r)\n/.test(source), `${patch}: all QJS lines must use CRLF`);
    const create = new Function('Warp', 'System', 'BinFile', 'ModernChatUI', `let ${patch};\n${source}\nreturn ${patch};`);
    function fixture() {
        const files = new Map(), dirs = new Set(['F:/Game']), copies = [];
        const state = {opened: 0, closed: 0, fail: null};
        const env = {Path: 'X:/WARP', TgtExe: 'F:/Game/test.exe', TestMode: false};
        const parent = p => p.slice(0, p.lastIndexOf('/'));
        const api = create(env, {
            DirPath: parent,
            MkDir(p) {
                if (p === state.fail || !dirs.has(parent(p))) return false;
                dirs.add(p); return true;
            },
            Copy(from, to, overwrite) {
                assert.equal(overwrite, false);
                if (to === state.fail || files.has(to) || !files.has(from) || !dirs.has(parent(to))) return false;
                files.set(to, files.get(from)); copies.push(to); return true;
            }
        }, function(p, mode) {
            assert.equal(mode, 'r'); state.opened++;
            this.Valid = files.has(p);
            this.Close = () => state.closed++;
        }, {nativeHelpers: {uiPrefix: () => 'UI'}});
        const assets = api.assets();
        assert.equal(new Set(assets).size, assets.length, `${patch}: duplicate assets`);
        for (const relative of assets) {
            assert(relative in hashes, `${patch}: unbundled asset ${relative}`);
            files.set(env.Path + '/Assets/StorageInventoryUI/' + relative, fs.readFileSync(path.join(bundle, relative)));
        }
        return {api, env, files, dirs, copies, state, target: 'F:/Game/data/texture/UI'};
    }
    let f = fixture();
    f.api.onApplied();
    assert.equal(f.copies.length, f.api.assets().length);
    assert.equal(f.state.opened, f.state.closed);
    const custom = f.target + '/' + f.api.assets()[0];
    f.files.set(custom, 'custom user artwork');
    f.api.onApplied();
    assert.equal(f.copies.length, f.api.assets().length);
    assert.equal(f.files.get(custom), 'custom user artwork');
    f = fixture(); f.env.TestMode = true; f.api.onApplied(); assert.equal(f.copies.length, 0);
    f = fixture(); f.files.delete(f.env.Path + '/Assets/StorageInventoryUI/' + f.api.assets().at(-1));
    assert.throws(() => f.api.onApplied(), /missing bundled asset/); assert.equal(f.copies.length, 0);
    f = fixture(); f.state.fail = 'F:/Game/data'; assert.throws(() => f.api.onApplied(), /cannot create/);
    console.log(`PASS ${patch}: actual installer, ${f.api.assets().length} original asset hashes, missing-only copies, custom art preservation, test mode, missing source and failed directory`);
}
