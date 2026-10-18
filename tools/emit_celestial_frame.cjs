/* Emit the production QJS frame bridge for a scoped existing-client upgrade. */
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const [frame, top, base] = process.argv.slice(2).map(Number);
if (![frame, top, base].every(v => Number.isInteger(v) && v > 0 && v <= 0xffffffff))
 throw Error('Expected frame, top-cell and bridge virtual addresses');
const context = {AutoCombatUIStatic:{}};
vm.createContext(context);
const helpers = fs.readFileSync(path.join(root, 'Scripts/Patches/AutoCombatUI.qjs'), 'utf8');
vm.runInContext(helpers.slice(helpers.indexOf('AutoCombatUIStatic.bytesToHex ='), helpers.indexOf('AutoCombatUIStatic.asciiBytes =')), context);
context.AutoCombatUI = {nativeHelpers:context.AutoCombatUIStatic};
vm.runInContext(fs.readFileSync(path.join(root, 'Scripts/Patches/CelestialDial.qjs'), 'utf8'), context);
process.stdout.write(context.CelestialDial.frameBridge(frame, top).finish(base).replace(/ /g, ''));
