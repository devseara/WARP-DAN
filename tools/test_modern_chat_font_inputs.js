/* Source-level regression test. GetUserInput is an explicit boundary double:
 * WARP can return false for a default-valued selection without saveDefault.
 * This exercises the actual getTabFont function, not a reimplementation.
 * Optional CLI: node tools/test_modern_chat_font_inputs.js
 */
function verifyChatFontInputs(source) {
	const normalized = source.replace(/\r\n/g, "\n");
	const start = normalized.indexOf("ModernChatUIStatic.getTabFont = function()");
	const end = normalized.indexOf("\n};", start);
	if (start < 0 || end < start) throw Error("getTabFont source not found");
	const run = new Function("Exe", "Cancel", "D_FontName", "D_FontSize", "D_Choice",
		"const ModernChatUIStatic = {};\n" + normalized.slice(start, end + 3) +
		"\nreturn ModernChatUIStatic.getTabFont();");
	const name = "$modernChatTabFontName", size = "$modernChatTabFontSize", style = "$modernChatTabFontStyle";
	const check = (answers, expected, error) => {
		const requests = [];
		const Exe = {GetUserInput(key, type, title, prompt, fallback, options) {
			requests.push({key, options});
			const value = Object.prototype.hasOwnProperty.call(answers, key) ? answers[key] : fallback;
			return value === fallback && !options.saveDefault ? false : value;
		}};
		let result, failure;
		try { result = run(Exe, message => {throw Error("Cancelled: " + message);}, 1, 2, 3); }
		catch (caught) { failure = caught.message; }
		if (error) {
			if (!failure || !failure.includes(error)) throw Error("Expected " + error + ", got " + failure);
		} else {
			if (failure || JSON.stringify(result) !== JSON.stringify(expected))
				throw Error("Unexpected result: " + (failure || JSON.stringify(result)));
			if (requests.length !== 3 || requests.some(request => !request.options.saveDefault))
				throw Error("Default font inputs must all be accepted and saved");
		}
	};
	check({}, {name: "Tahoma", size: 8, weight: 400});
	check({[name]: "Arial", [size]: 12, [style]: "Normal"}, {name: "Arial", size: 12, weight: 400});
	check({[name]: "Arial", [size]: 12, [style]: "Bold"}, {name: "Arial", size: 12, weight: 700});
	for (const key of [name, size, style]) check({[key]: false}, null, "Cancelled:");
	for (const invalid of [7, 17, 8.5]) check({[size]: invalid}, null, "between 8 and 16");
	check({[style]: "invalid"}, null, "unsupported tab font style");
	return "PASS: Normal/default 8/default family, Bold, real cancellation and invalid font inputs";
}

if (typeof module !== "undefined" && typeof require !== "undefined" && require.main === module) {
	const fs = require("node:fs"), path = require("node:path");
	console.log(verifyChatFontInputs(fs.readFileSync(path.join(__dirname, "../Scripts/Patches/ModernChatUI.qjs"), "utf8")));
}
