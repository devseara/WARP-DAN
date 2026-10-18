// Execute language selection/allocation and real asset-copy handlers in isolation.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const output = fs.mkdtempSync(path.join(root, 'Outputs', 'auto-ui-options-'));
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8');
const copies = [];
const languages = JSON.parse(read('Inputs/AutoUI/languages.json'));
let choice, designChoice, supportDesignChoice, prompts = 0, savedReads = 0, failCopy = false, failMkdir = false;
const context = vm.createContext({
	D_Choice: 1, ASCII: 0,
	Warp: {Path: root + '/', TgtExe: path.join(output, 'client.exe'), TestMode: false},
	Exe: {
		GetUserInput(key, type, title, message, defaultValue, options) {
			prompts++;
			if (key === '$autoSupportUIDesign') {
				assert.equal(defaultValue, 'RO Global AutoSupport UI');
				assert.deepEqual(Array.from(options.choices), ['RO Global AutoSupport UI', 'Custom AutoSupport UI v1']);
				assert.equal(options.saveDefault, true);
				return supportDesignChoice === undefined ? defaultValue : supportDesignChoice;
			}
			if (key === '$autoCombatUIDesign') {
				assert.equal(defaultValue, 'RO Global AutoHunt UI');
				assert.deepEqual(Array.from(options.choices), ['RO Global AutoHunt UI', 'Custom AutoHunt UI v1']);
				assert.equal(options.saveDefault, true);
				return designChoice === undefined ? defaultValue : designChoice;
			}
			assert.equal(defaultValue, 'English');
			assert.deepEqual(Array.from(options.choices), Object.keys(languages));
			return choice === undefined ? defaultValue : choice;
		},
		GetSavedInput() { savedReads++; return false; }
	},
	Cancel(message) { throw Error('CANCEL: ' + message); },
	TextFile: class {
		constructor(name) { this.Valid = fs.existsSync(name); this.text = this.Valid ? fs.readFileSync(name, 'ascii') : ''; this.Size = this.text.length; }
		Read() { return this.text; }
		Close() {}
	},
	System: {
		DirPath: path.dirname,
		MkDir(name) { if (failMkdir) return false; fs.mkdirSync(name, {recursive: true}); return true; },
		Copy(source, target, overwrite) {
			if (failCopy) return false;
			assert.equal(overwrite, true);
			assert.ok(path.resolve(target).startsWith(output + path.sep));
			fs.copyFileSync(source, target);
			assert.ok(fs.readFileSync(source).equals(fs.readFileSync(target)));
			copies.push(target);
			return true;
		}
	}
});
function load(relative) {
	const text = read(relative);
	assert.equal(text.slice(0, 2), '/*', relative);
	assert.ok(!/(?<!\r)\n/.test(text), relative + ' requires CRLF');
	vm.runInContext(text, context, {filename: relative});
}
function run(code) { return vm.runInContext(code, context); }
load('Scripts/Patches/AutoCombatUI.qjs');
assert.equal(run('AutoCombatUIStatic.selectDesign()'), 'RO Global AutoHunt UI');
designChoice = 'Custom AutoHunt UI v1';
assert.equal(run('AutoCombatUIStatic.selectDesign()'), 'Custom AutoHunt UI v1');
designChoice = false;
assert.throws(() => run('AutoCombatUIStatic.selectDesign()'), /CANCEL/);
designChoice = 'unsupported';
assert.throws(() => run('AutoCombatUIStatic.selectDesign()'), /unsupported/);
context.Warp.TestMode = true;
const designPrompts = prompts;
assert.equal(run('AutoCombatUIStatic.selectDesign()'), 'RO Global AutoHunt UI');
assert.equal(prompts, designPrompts);
context.Warp.TestMode = false;
assert.equal(run('AutoUILanguage.select("$test", "Test")'), 'English');
for (choice of Object.keys(languages))
	assert.equal(run('AutoUILanguage.select("$test", "Test")'), choice);
for (choice of ['Chinese Traditional', 'Chinese Traditional (Big5 / CP950)'])
	assert.equal(run('AutoUILanguage.select("$test", "Test")'), 'Traditional Chinese');
choice = false;
assert.throws(() => run('AutoUILanguage.select("$test", "Test")'), /CANCEL/);
choice = 'unsupported';
assert.throws(() => run('AutoUILanguage.select("$test", "Test")'), /unsupported/);
context.Warp.TestMode = true;
const promptCount = prompts;
assert.equal(run('AutoUILanguage.select("$test", "Test")'), 'English');
assert.equal(prompts, promptCount);
context.Warp.TestMode = false;
let translatedCount = 0;
for (const [name, spec] of Object.entries(languages)) {
	if (name === 'English') continue;
	context.spec = spec;
	const catalog = JSON.parse(read(`Inputs/AutoUI/${spec.locale}.json`));
	const bytes = JSON.parse(read(`Inputs/AutoUI/${spec.locale}.bytes.json`));
	for (const english of Object.keys(catalog)) {
		context.label = english;
		assert.deepEqual(Array.from(run('AutoUILanguage.bytes(spec, label, spec.codec)')), bytes[english][spec.codec].concat(0));
		assert.deepEqual(Array.from(run('AutoUILanguage.bytes(spec, label, "utf8")')),
			[...Buffer.from(catalog[english], 'utf8'), 0]);
		translatedCount++;
	}
}
assert.throws(() => run('AutoUILanguage.bytes(spec, "missing label", "utf8")'), /missing/);
for (const name of ['AutoSupportUI', 'ItemCollectionUI',
	'RedesignedEquipmentWindow', 'RedesignedStatusWindow', 'FluentEmoji']) {
	load(`Scripts/Patches/${name}.qjs`);
}
assert.equal(run('AutoSupportUIStatic.selectDesign()'), 'RO Global AutoSupport UI');
supportDesignChoice = 'Custom AutoSupport UI v1';
assert.equal(run('AutoSupportUIStatic.selectDesign()'), supportDesignChoice);
supportDesignChoice = false;
assert.throws(() => run('AutoSupportUIStatic.selectDesign()'), /CANCEL/);
supportDesignChoice = 'unsupported';
assert.throws(() => run('AutoSupportUIStatic.selectDesign()'), /unsupported/);
context.Warp.TestMode = true;
const supportPrompts = prompts;
assert.equal(run('AutoSupportUIStatic.selectDesign()'), 'RO Global AutoSupport UI');
assert.equal(prompts, supportPrompts);
context.Warp.TestMode = false;
// Raw strings and initial fallback bytes remain ASCII; native runtime selects
// the final encoding from the separately retained UTF-8 and Big5 sources.
for (const name of ['AutoCombatUI', 'AutoSupportUI']) {
	run(`${name}Static.allocateBytes = bytes => ({vir: 123, size: bytes.length, bytes: Array.from(bytes)});
		${name}Static.LocalizedStrings = [];
		${name}Static.Language = "Traditional Chinese";`);
	assert.deepEqual(Array.from(run(`${name}Static.allocateUiString("Basic").bytes`)).slice(0, 6), [...Buffer.from('Basic'), 0]);
	assert.equal(run(`${name}Static.LocalizedStrings.length`), 1);
	assert.deepEqual(Array.from(run(`${name}Static.allocateString("Basic").bytes`)), [...Buffer.from('Basic'), 0]);
	run(`${name}Static.Language = AutoUILanguage.English`);
	assert.deepEqual(Array.from(run(`${name}Static.allocateUiString("Basic").bytes`)), [...Buffer.from('Basic'), 0]);
}
// Use the shipped manifest parser with the filesystem reader supplied by Node.
context.readManifest = name => fs.readFileSync(name, 'utf8');
run('FluentEmojiStatic.readUtf8 = readManifest');
const counts = {};
for (const name of ['AutoCombatUI', 'AutoSupportUI', 'ItemCollectionUI', 'RedesignedEquipmentWindow', 'RedesignedStatusWindow', 'FluentEmoji']) {
	const start = copies.length;
	context.Warp.TestMode = true;
	run(`${name}.onApplied()`);
	assert.equal(copies.length, start, 'TestMode must not copy');
	context.Warp.TestMode = false;
	run(`${name}.onApplied()`);
	counts[name] = copies.length - start;
	assert.ok(counts[name] > 0);
	// A prior false profile setting must no longer suppress deployment.
	assert.equal(savedReads, 0);
	failCopy = true;
	assert.throws(() => run(`${name}.onApplied()`), /copy/);
	failCopy = false;
	failMkdir = true;
	assert.throws(() => run(`${name}.onApplied()`), /create/);
	failMkdir = false;
}
console.log(JSON.stringify({passed: true, strings: translatedCount, languages: Object.keys(languages).length, copies: counts, output}));
