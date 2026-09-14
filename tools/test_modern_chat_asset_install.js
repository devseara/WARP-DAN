/* Exercises the actual QJS asset installer with explicit filesystem doubles.
 * Optional CLI: node tools/test_modern_chat_asset_install.js
 */
function verifyChatAssetInstall(source) {
	const normalized = source.replace(/\r\n/g, "\n");
	const declaration = normalized.indexOf("const ModernChatUIStatic = {");
	const prefixEnd = normalized.indexOf("\n};", normalized.indexOf("ModernChatUIStatic.uiPrefix = function()"));
	const installStart = normalized.indexOf("ModernChatUI.onApplied = function()");
	const installEnd = normalized.indexOf("\n};", installStart);
	if ([declaration, prefixEnd, installStart, installEnd].some(x => x < 0)) throw Error("Missing QJS installer source");
	const create = new Function("Warp", "System", "BinFile",
		normalized.slice(declaration, prefixEnd + 3) + "\nconst ModernChatUI = {};\n" +
		normalized.slice(installStart, installEnd + 3) + "\nreturn {config: ModernChatUIStatic, install: ModernChatUI.onApplied};");
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
				check(overwrite === false, "Must never overwrite edited images");
				if (to === state.failCopy || files.has(to) || !files.has(from) || !directories.has(parent(to))) return false;
				files.set(to, files.get(from)); return true;
			}
		}, function(path, mode) {
			check(mode === "r", "BinFile must be read-only"); state.opened++;
			this.Valid = files.has(path);
			this.Close = () => { state.closed++; };
		});
		const sourceDir = warp + api.config.AssetPath;
		const targetDir = root + "/data/texture/" + api.config.uiPrefix() + "/uirenewal/chat";
		for (const file of api.config.Assets) files.set(sourceDir + "/" + file, "bundled:" + file);
		return {...api, root, files, directories, operations, state, env, sourceDir, targetDir};
	};
	const expectError = (f, text) => {
		let failure;
		try { f.install(); } catch (error) { failure = error.message; }
		check(failure && failure.includes(text), "Expected failure containing " + text + ", got " + failure);
		check(f.state.opened === f.state.closed, "All asset handles must close on failure");
	};
	let f = fixture();
	f.install();
	check(f.operations.filter(x => x[0] === "mkdir").length === 5, "Create the complete parent chain");
	check(f.operations.filter(x => x[0] === "copy").length === 19, "Install all 19 PNGs");
	for (const file of f.config.Assets) check(f.files.get(f.targetDir + "/" + file) === "bundled:" + file, "Wrong output image: " + file);
	check(f.state.opened === f.state.closed, "Close every asset handle");
	f.files.set(f.targetDir + "/icon_emotion.png", "user white smiley");
	f.operations.length = 0;
	f.install();
	check(f.operations.length === 0 && f.files.get(f.targetDir + "/icon_emotion.png") === "user white smiley", "Repeat must preserve custom images");
	f.files.delete(f.targetDir + "/icon_pm.png");
	f.install();
	check(f.operations.filter(x => x[0] === "copy").length === 1, "Repair only the missing PNG");
	check(f.files.get(f.targetDir + "/icon_emotion.png") === "user white smiley", "Repair must preserve custom images");
	f = fixture(); f.env.TestMode = true; f.install();
	check(f.operations.length === 0 && f.state.opened === 0, "Test mode must not access asset files");
	f = fixture(); f.files.delete(f.sourceDir + "/textbox_on.png");
	expectError(f, "missing bundled image " + f.sourceDir + "/textbox_on.png");
	check(f.operations.length === 0, "Incomplete bundle must fail before any writes");
	f = fixture(); f.state.failDirectory = f.root + "/data/texture";
	expectError(f, "cannot create " + f.state.failDirectory);
	check(!f.operations.some(x => x[0] === "copy"), "Directory failure must stop copying");
	f = fixture(); f.state.failCopy = f.targetDir + "/btn_close.png";
	expectError(f, " to " + f.state.failCopy);
	return "PASS: fresh output/data tree, all 19 PNGs, repeat/repair preserves edits, test-mode isolation, missing bundle and filesystem errors";
}

if (typeof module !== "undefined" && typeof require !== "undefined" && require.main === module) {
	const fs = require("node:fs"), path = require("node:path");
	console.log(verifyChatAssetInstall(fs.readFileSync(path.join(__dirname, "../Scripts/Patches/ModernChatUI.qjs"), "utf8")));
}
