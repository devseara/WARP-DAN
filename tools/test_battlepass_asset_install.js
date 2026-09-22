/* Exercises the actual Battle Pass QJS installer with filesystem doubles.
 * Optional CLI: node tools/test_battlepass_asset_install.js
 */
function verifyBattlepassAssetInstall(source) {
	const normalized = source.replace(/\r\n/g, "\n");
	const configStart = normalized.indexOf("BattlepassUIStatic.ClientAssets = [");
	const configEnd = normalized.indexOf("\n};", normalized.indexOf("BattlepassUIStatic.uiPrefix = function()"));
	const installStart = normalized.indexOf("BattlepassUIStatic.onApplied = function()");
	const installEnd = normalized.indexOf("\n};", installStart);
	if ([configStart, configEnd, installStart, installEnd].some(x => x < 0)) throw Error("Missing Battle Pass installer source");
	if (!normalized.includes("\tBattlepassUI.onApplied();")) throw Error("Direct patch application must install images");
	if (!normalized.includes("BattlepassUI.onApplied = BattlepassUIStatic.onApplied;")) throw Error("Missing WARP lifecycle callback");
	const create = new Function("Warp", "System", "BinFile", "const BattlepassUIStatic = {};\n" +
		normalized.slice(configStart, configEnd + 3) + "\n" + normalized.slice(installStart, installEnd + 3) +
		"\nreturn BattlepassUIStatic;");
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
		for (const file of api.ClientAssets) files.set(sourceDir + "/" + file, "bundled:" + file);
		return {...api, root, files, directories, operations, state, env, sourceDir, targetDir};
	};
	const expectError = (f, text) => {
		let failure;
		try { f.onApplied(); } catch (error) { failure = error.message; }
		check(failure && failure.includes(text), "Expected " + text + ", got " + failure);
		check(f.state.opened === f.state.closed, "All asset handles must close on failure");
	};
	let f = fixture(); f.onApplied();
	check(f.operations.filter(x => x[0] === "mkdir").length === 4, "Create all four folder levels");
	check(f.operations.filter(x => x[0] === "copy").length === 25, "Install all 25 BMPs");
	for (const file of f.ClientAssets) check(f.files.get(f.targetDir + "/" + file) === "bundled:" + file, "Wrong output image: " + file);
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
	return "PASS: fresh Battle Pass data tree, all 25 BMPs, repeat/repair preserves skins, lifecycle wiring, test mode, missing bundle and filesystem errors";
}

if (typeof module !== "undefined" && typeof require !== "undefined" && require.main === module) {
	const fs = require("node:fs"), path = require("node:path");
	console.log(verifyBattlepassAssetInstall(fs.readFileSync(path.join(__dirname, "../Scripts/Patches/BattlepassUI.qjs"), "utf8")));
}
