/* Exercises the actual Battle Pass QJS installer with filesystem doubles.
 * Optional CLI: node tools/test_battlepass_asset_install.js
 */
function verifyBattlepassAssetInstall(source) {
	const normalized = source.replace(/\r\n/g, "\n");
	const configStart = normalized.indexOf("BattlepassUIStatic.ClientAssets = [");
	const configEnd = normalized.indexOf("\n};", normalized.indexOf("BattlepassUIStatic.uiPrefix = function()"));
	const installStart = normalized.indexOf("BattlepassUIStatic.onApplied = function()");
	const installEnd = normalized.indexOf("\n};", installStart);
	const selectStart = normalized.indexOf("BattlepassUI.onSelected = function()");
	const selectEnd = normalized.indexOf("\n};", selectStart);
	if ([configStart, configEnd, installStart, installEnd, selectStart, selectEnd].some(x => x < 0)) throw Error("Missing Battle Pass installer source");
	if (!normalized.includes("\tBattlepassUI.onApplied();")) throw Error("Direct patch application must install images");
	if (!normalized.includes("BattlepassUI.onApplied = BattlepassUIStatic.onApplied;")) throw Error("Missing WARP lifecycle callback");
	const create = new Function("Warp", "System", "BinFile", "const BattlepassUIStatic = {}, BattlepassUI = {};\n" +
		normalized.slice(configStart, configEnd + 3) + "\n" + normalized.slice(installStart, installEnd + 3) +
		"\n" + normalized.slice(selectStart, selectEnd + 3) +
		"\nreturn {...BattlepassUIStatic, onSelected: BattlepassUI.onSelected};");
	const check = (condition, message) => { if (!condition) throw Error(message); };
	const parent = path => path.slice(0, path.lastIndexOf("/"));
	const fixture = () => {
		const root = "F:/Different target/client folder", warp = "D:/warp/WARP20250716-main";
		const files = new Map(), directories = new Set([root]), operations = [];
		const state = {failDirectory: null, failCopy: null, opened: 0, closed: 0};
		const env = {Path: warp, TgtExe: root + "/Ragnarok.exe", TestMode: false};
		const api = create(env, {
			DirPath(path) { check(path === env.TgtExe, "Must use output EXE"); return parent(path); },
			MkDir(path) {
				operations.push(["mkdir", path]);
				if (path === state.failDirectory || !directories.has(parent(path))) return false;
				directories.add(path); return true;
			},
			Copy(from, to, overwrite) {
				operations.push(["copy", from, to, overwrite]);
				check(overwrite === false, "Must preserve client-side skins");
				if (to === state.failCopy || files.has(to) || !files.has(from) || !directories.has(parent(to))) return false;
				files.set(to, files.get(from)); return true;
			}
		}, function(path, mode) {
			check(mode === "r", "BinFile must be read-only"); state.opened++;
			this.Valid = files.has(path); this.Close = () => { state.closed++; };
		});
		const sourceDir = warp + "/Assets/BattlepassUI/client";
		const targetDir = root + "/data/texture/" + api.uiPrefix() + "/battlepassui";
		const menuDir = root + "/data/texture/" + api.uiPrefix() + "/uirenewal/menuicon";
		const menuSource = warp + "/Assets/BattlepassUI/menuicon";
		for (const file of api.ClientAssets) files.set(sourceDir + "/" + file, "bundled:" + file);
		for (const file of api.MenuAssets) files.set(menuSource + "/" + file, "bundled:" + file);
		for (const file of ["bg_m7.tga", "bg_o7.tga"]) files.set(warp + "/Assets/ROGlobalZeroMenu/menuicon/" + file, "bundled:" + file);
		return {...api, root, files, directories, operations, state, env, sourceDir, targetDir, menuDir, menuSource};
	};
	const expectError = (f, text) => {
		let failure;
		try { f.onApplied(); } catch (error) { failure = error.message; }
		check(failure && failure.includes(text), "Expected " + text + ", got " + failure);
		check(f.state.opened === f.state.closed, "All asset handles must close on failure");
	};
	let f = fixture(); f.onApplied();
	check(f.operations.filter(x => x[0] === "mkdir").length === 6, "Create the window and shared menu folders");
	check(f.operations.filter(x => x[0] === "copy").length === 43, "Install 29 window images, 12 menu icons and two backgrounds");
	for (const file of f.ClientAssets) check(f.files.get(f.targetDir + "/" + file) === "bundled:" + file, "Wrong output image: " + file);
	for (const file of [...f.MenuAssets, "bg_m7.tga", "bg_o7.tga"]) check(f.files.get(f.menuDir + "/" + file) === "bundled:" + file, "Wrong menu image: " + file);
	check(f.state.opened === f.state.closed, "Close all handles");
	f.files.set(f.targetDir + "/Window_Background.bmp", "custom skin");
	f.operations.length = 0; f.onApplied();
	check(f.operations.length === 0 && f.files.get(f.targetDir + "/Window_Background.bmp") === "custom skin", "Repeated lifecycle must preserve edits");
	f.files.delete(f.targetDir + "/Cursor_Hover.bmp"); f.onApplied();
	check(f.operations.filter(x => x[0] === "copy").length === 1, "Repair only the missing BMP");
	check(f.files.get(f.targetDir + "/Window_Background.bmp") === "custom skin", "Repair must preserve edits");
	f = fixture(); f.env.TestMode = true; f.onApplied();
	check(f.operations.length === 0 && f.state.opened === 0, "Test mode must not access files");
	f = fixture(); f.files.delete(f.sourceDir + "/Window_Background.bmp");
	expectError(f, "missing bundled image " + f.sourceDir + "/Window_Background.bmp");
	check(f.operations.length === 0, "Missing bundle must fail before writing");
	f = fixture(); f.state.failDirectory = f.root + "/data/texture";
	expectError(f, "cannot create " + f.state.failDirectory);
	check(!f.operations.some(x => x[0] === "copy"), "Stop on directory failure");
	f = fixture(); f.state.failCopy = f.targetDir + "/Abandon_Dialog_Background.bmp";
	expectError(f, " to " + f.state.failCopy);
	for (const file of f.MenuAssets) {
		f = fixture(); f.files.delete(f.menuSource + "/" + file);
		expectError(f, "missing bundled image " + f.menuSource + "/" + file);
		check(f.operations.length === 0, "Missing menu bundle must fail before writing");
		f = fixture(); f.onApplied(); f.files.set(f.menuDir + "/bg_m7.tga", "custom background");
		f.files.delete(f.menuDir + "/" + file); f.operations.length = 0; f.onApplied();
		check(f.operations.filter(x => x[0] === "copy").length === 1, "Repair only " + file);
		check(f.files.get(f.menuDir + "/bg_m7.tga") === "custom background", "Preserve custom menu background");
		f.files.set(f.menuDir + "/" + file, "custom icon"); f.operations.length = 0; f.onApplied();
		check(f.operations.length === 0 && f.files.get(f.menuDir + "/" + file) === "custom icon", "Preserve custom menu icon");
	}
	f = fixture(); f.state.failDirectory = f.menuDir; expectError(f, "cannot create " + f.menuDir);
	check(!f.operations.some(x => x[0] === "copy"), "Menu directory failure must precede all copies");
	f = fixture(); f.state.failCopy = f.menuDir + "/bt_battlepass_press.bmp"; expectError(f, " to " + f.state.failCopy);
	// Execute the actual checkbox callback, independent of the patch emitter.
	f = fixture(); f.onSelected();
	check(f.operations.filter(x => x[0] === "copy").length === 43, "Selection must create all assets automatically");
	for (const file of f.MenuAssets) check(f.files.get(f.menuDir + "/" + file) === "bundled:" + file, "Selection omitted " + file);
	f.files.set(f.menuDir + "/bt_battlepass_normal.bmp", "custom icon");
	f.operations.length = 0; f.onSelected(); f.onApplied();
	check(f.operations.length === 0, "Repeat selection/apply must preserve existing assets");
	f.files.delete(f.menuDir + "/bt_battlepass_press.bmp"); f.onSelected();
	check(f.operations.filter(x => x[0] === "copy").length === 1, "Reselection must repair missing icons");
	check(f.files.get(f.menuDir + "/bt_battlepass_normal.bmp") === "custom icon", "Reselection overwrote custom art");
	for (const target of [undefined, null, "", "  "]) {
		f = fixture(); const chosen = f.env.TgtExe; f.env.TgtExe = target; f.onSelected();
		check(f.operations.length === 0 && f.state.opened === 0, "Selection without an output must defer");
		f.env.TgtExe = chosen; f.onApplied();
		check(f.operations.filter(x => x[0] === "copy").length === 43, "Export must install after deferred selection");
	}
	f = fixture(); f.env.TestMode = true; f.onSelected();
	check(f.operations.length === 0 && f.state.opened === 0, "Selection in test mode must not access files");
	f = fixture(); f.onSelected(); f.operations.length = 0;
	const nextRoot = "F:/Another output folder"; f.directories.add(nextRoot); f.env.TgtExe = nextRoot + "/game.exe";
	f.onApplied();
	check(f.operations.filter(x => x[0] === "copy").length === 43, "Changed output must receive its own assets on export");
	check(f.operations.filter(x => x[0] === "copy").every(x => x[2].startsWith(nextRoot + "/")), "Changed output used stale selection path");
	return "PASS: Battle Pass auto-installs 12 menu icons on selection and all 43 assets on apply; repeat/repair, deferred/changed output, custom skins, test mode and filesystem failures verified";
}

if (typeof module !== "undefined" && typeof require !== "undefined" && require.main === module) {
	const fs = require("node:fs"), path = require("node:path");
	const assert = require("node:assert/strict"), crypto = require("node:crypto");
	const menu = path.join(__dirname, "../Assets/BattlepassUI/menuicon");
	const manifest = JSON.parse(fs.readFileSync(path.join(menu, "manifest.json"), "utf8"));
	assert.equal(Object.keys(manifest.files).length, 12);
	for (const [name, entry] of Object.entries(manifest.files)) {
		const bytes = fs.readFileSync(path.join(menu, name));
		assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), entry.sha256, name);
		assert.equal(bytes.toString("ascii", 0, 2), "BM");
		assert.deepEqual([bytes.readInt32LE(18), bytes.readInt32LE(22)], name.includes("_old_") ? [32, 34] : [45, 41]);
		assert.equal(bytes.readUInt16LE(28), 24);
	}
	console.log(verifyBattlepassAssetInstall(fs.readFileSync(path.join(__dirname, "../Scripts/Patches/BattlepassUI.qjs"), "utf8")));
}
