/* Run the production LeftLootNotices QJS against a bounded PE staging adapter.
 * Receives the source layout as JSON on stdin; emits audited writes as JSON.
 * This tool never changes the source executable or any runtime payload.
 */
'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(request.source);
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');
const requireValue = (condition, message) => { if (!condition) throw Error(message); };
const integer = (value, label) => {
 requireValue(Number.isInteger(value) && value >= 0 && value <= 0xffffffff, 'Invalid '+label);
 return value;
};
requireValue(sha256(source) === request.source_sha256, 'Source changed before QJS emission');
const base = integer(request.image_base, 'image base');
const originalEnd = integer(request.source_mapped_end, 'source mapped end');
const allocationOffset = integer(request.allocation_offset, 'allocation offset');
const allocationRva = integer(request.allocation_rva, 'allocation RVA');
requireValue(originalEnd <= source.length && allocationOffset >= originalEnd, 'Invalid append range');
const maxAppend = 32 * 1024 * 1024;
const memory = Buffer.alloc(allocationOffset + maxAppend);
source.copy(memory, 0, 0, originalEnd);
let cursor = allocationOffset;
const allocations = [], writes = [], assertions = [];
const appendVa = base + allocationRva;
const inAllocation = (offset, size) => allocations.some(a => offset >= a.phy && offset + size <= a.phy + a.size);
const mapped = (offset, size) => {
 integer(offset, 'physical offset'); integer(size, 'byte count');
 requireValue(offset + size <= originalEnd || inAllocation(offset, size), 'Unmapped read/write range');
};
const parseHex = value => {
 const compact = String(value).replace(/\s/g, '');
 requireValue(/^(?:[0-9a-fA-F]{2})*$/.test(compact), 'Invalid hexadecimal bytes');
 return Buffer.from(compact, 'hex');
};
const write = (offset, bytes) => {
 mapped(offset, bytes.length);
 writes.push({offset, before:memory.subarray(offset, offset+bytes.length).toString('hex'), after:bytes.toString('hex')});
 bytes.copy(memory, offset);
};
const Exe = {
 BuildDate:20250716,
 Vir2Phy(va) {
  integer(va, 'virtual address');
  for (const section of request.sections) {
   const displacement = va - base - section.rva;
   if (displacement >= 0 && displacement < section.raw_size) return section.offset + displacement;
  }
  const displacement = va - appendVa;
  return displacement >= 0 && allocationOffset + displacement < cursor ? allocationOffset + displacement : -1;
 },
 GetHex(offset, size) { mapped(offset, size); return Array.from(memory.subarray(offset, offset+size), b => b.toString(16).padStart(2, '0')).join(' '); },
 GetUint32(offset) { mapped(offset, 4); return memory.readUInt32LE(offset); },
 SetHex(offset, value) { write(offset, parseHex(value)); },
 SetUint32(offset, value) { const bytes=Buffer.alloc(4); bytes.writeUInt32LE(integer(value, 'uint32')); write(offset, bytes); },
 Allocate(size, alignment=1) {
  integer(size, 'allocation size'); integer(alignment, 'allocation alignment');
  requireValue(size > 0 && alignment > 0 && alignment <= 4096 && !(alignment & (alignment-1)), 'Invalid allocation');
  const phy = Math.ceil(cursor/alignment)*alignment;
  const vir = appendVa + phy-allocationOffset;
  requireValue(vir % alignment === 0 && phy+size <= memory.length && vir+size <= 0xffffffff, 'Allocation overflow or misalignment');
  allocations.push({phy, vir, size, alignment}); cursor=phy+size;
  return [phy, vir];
 }
};
class BinFile {
 constructor(filename, mode) {
  requireValue(mode === 'r', 'BinFile is read-only');
  const resolved = path.resolve(filename);
  const allowed = ['runtime.bin', 'runtime.json'].map(name => path.join(root, 'Inputs', 'LeftLootNotices', name));
  requireValue(allowed.includes(resolved), 'Unexpected payload file: '+resolved);
  this.Valid = fs.existsSync(resolved); this.data = this.Valid ? fs.readFileSync(resolved) : null;
 }
 ReadHex() { requireValue(this.Valid, 'Missing payload file'); return this.data.toString('hex'); }
 Close() {}
}
const context = {AutoCombatUIStatic:{}, Exe, BinFile, Warp:{Path:root, TestMode:true}, CODE:0};
vm.createContext(context);
const helperPath = path.join(root, 'Scripts/Patches/AutoCombatUI.qjs');
const helpers = fs.readFileSync(helperPath, 'utf8');
// Evaluate these exact production assignments, without loading unrelated patches.
for (const name of ['bytesToHex', 'allocateBytes', 'asciiBytes', 'allocateString', 'assertCode']) {
 const prefix='AutoCombatUIStatic.'+name+' = ';
 const begin=helpers.indexOf(prefix), next=helpers.indexOf('\nAutoCombatUIStatic.', begin+prefix.length);
 requireValue(begin >= 0 && next > begin, 'Missing production helper '+name);
 vm.runInContext(helpers.slice(begin, next), context, {filename:helperPath, timeout:10000});
}
const assertCode=context.AutoCombatUIStatic.assertCode;
context.AutoCombatUIStatic.assertCode=function(label, va, expected) {
 const result=assertCode(label, va, expected); assertions.push({label, va, expected}); return result;
};
context.AutoCombatUI={nativeHelpers:context.AutoCombatUIStatic};
const patchPath=path.join(root, 'Scripts/Patches/LeftLootNotices.qjs');
const patch=fs.readFileSync(patchPath);
vm.runInContext(patch.toString('utf8'), context, {filename:patchPath, timeout:10000});
requireValue(vm.runInContext('LeftLootNotices()', context, {timeout:30000}) === true, 'QJS patch did not succeed');
process.stdout.write(JSON.stringify({
 source_sha256:sha256(source), patch_sha256:sha256(patch), helper_sha256:sha256(Buffer.from(helpers)),
 payload_sha256:sha256(fs.readFileSync(path.join(root, 'Inputs/LeftLootNotices/runtime.bin'))),
 allocations, writes, assertions, append_end:cursor, production_qjs_executed:true
}));
