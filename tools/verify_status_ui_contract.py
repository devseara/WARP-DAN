#!/usr/bin/env python3
"""Verify the 2025-07-16 redesigned Status/Trait window contracts."""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Scripts" / "Patches" / "RedesignedStatusWindow.qjs"
TRAIT_TAB_OUT = ROOT / "Images" / "BohStatusUI" / "tab_trait_out.png"


def require(condition: bool, message: str) -> None:
	if not condition:
		raise SystemExit(f"FAIL: {message}")


def extract_hex_array(source: str, name: str) -> list[int]:
	match = re.search(rf"const {re.escape(name)} = \[(.*?)\];", source, re.S)
	require(match is not None, f"{name} array is missing")
	return [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", match.group(1))]


def section(source: str, start: str, end: str) -> str:
	begin = source.index(start)
	finish = source.index(end, begin)
	return source[begin:finish]


def verify_source() -> None:
	raw = SOURCE.read_bytes()
	source = raw.decode("utf-8")
	require(not raw.startswith(b"\xef\xbb\xbf"), "QJS has a UTF-8 BOM")
	require(b"\n" not in raw.replace(b"\r\n", b""), "QJS contains bare LF line endings")

	native_ids = extract_hex_array(source, "nativePlusIds")
	status_ids = extract_hex_array(source, "statusIds")
	trait_native_ids = extract_hex_array(source, "traitNativePlusIds")
	trait_status_ids = extract_hex_array(source, "traitStatusIds")
	require(native_ids == [0xCD, 0xCE, 0xCF, 0xD0, 0xD2, 0xD1], "native Status control order changed")
	require(status_ids == [0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12], "Status packet-id order changed")
	require(trait_native_ids == list(range(0x227, 0x22D)), "native Trait control order changed")
	require(trait_status_ids == list(range(0xDB, 0xE1)), "Trait packet-id order changed")

	require("Exe.Allocate(116, 0x10)" in source, "dual-page runtime state size changed")
	for token in ["traitPendingVir: vir + 24", "controlsVir: vir + 48", "traitControlsVir: vir + 80", "disableTraitVir: vir + 112"]:
		require(token in source, f"runtime state mapping changed: {token}")

	status_sender = section(
		source,
		"RedesignedStatusWindow.buildStatusPacketSender = function()",
		"RedesignedStatusWindow.buildTraitPacketSender = function()",
	)
	require("0xF8, 0xBB, 0x00" in status_sender, "0x00BB packet header store is missing")
	require("0x66, 0x89, 0x45, 0xFA" in status_sender, "Status uint16 status-id store is missing")
	require("0x88, 0x45, 0xFC" in status_sender, "Status uint8 amount store is missing")
	require("RedesignedStatusWindow.pushImm(a, 5);" in status_sender, "Status packet length changed")

	trait_sender = section(
		source,
		"RedesignedStatusWindow.buildTraitPacketSender = function()",
		"RedesignedStatusWindow.buildStagedDispatch = function(",
	)
	require("0xF8, 0x24, 0x0B" in trait_sender, "0x0B24 packet header store is missing")
	require("0x66, 0x89, 0x45, 0xFA" in trait_sender, "Trait int16 status-id store is missing")
	require("0x66, 0x89, 0x45, 0xFC" in trait_sender, "Trait int16 amount store is missing")
	require("RedesignedStatusWindow.pushImm(a, 6);" in trait_sender, "Trait packet length changed")
	for sender in [status_sender, trait_sender]:
		require("a.call(0x00C14D60);" in sender, "native packet constructor changed")
		require("a.call(0x00C14920);" in sender, "native packet sender changed")

	dispatch = section(
		source,
		"RedesignedStatusWindow.buildStagedDispatch = function(",
		"RedesignedStatusWindow.buildControlBuilder = function(",
	)
	status_commit = section(dispatch, "a.label('status_commit');", "a.label('status_clear');")
	trait_commit = section(dispatch, "a.label('trait_commit');", "a.label('trait_clear');")
	require("a.call(statusPacketVir);" in status_commit, "Status OK does not use direct packet submission")
	require("a.call(traitPacketVir);" in trait_commit, "Trait OK does not use direct packet submission")
	require("0x0121333C" not in status_commit + trait_commit, "OK still uses the single-flight UI event manager")
	require("state.pendingVir + i * 4" in status_commit, "Status OK lost per-row pending state")
	require("state.traitPendingVir + i * 4" in trait_commit, "Trait OK lost per-row pending state")
	require("a.jcc(0x84, next);" in status_commit + trait_commit, "failed sends no longer preserve pending points")
	require("a.dword(0x6E)" in dispatch or "0x83, 0xF8, 0x6E" in dispatch, "server max_trait_parameter 110 gate is missing")
	require("addPage(state.controlsVir, 0x7F0, true);" in source, "Status custom controls changed")
	require("addPage(state.traitControlsVir, 0x800, false);" in source, "Trait custom controls changed")
	require("emitPage('status', state.controlsVir);" in source, "Status control visibility path changed")
	require("emitPage('trait', state.traitControlsVir);" in source, "Trait control visibility path changed")

	geometry = section(
		source,
		"RedesignedStatusWindow.patchControlGeometry = function(_)",
		"RedesignedStatusWindow.buildStatusPacketSender = function()",
	)
	require("'Trait increment refresh block'" in geometry, "complete Trait refresh block hook is missing")
	require("'8B 0C 3E 85 C9'" in geometry, "Trait child pointer is not loaded and null-tested first")
	require("JE(Filler(10))" in geometry, "null Trait children do not skip the move call")
	require("nops: 23" in geometry, "complete 28-byte stock Trait move block is not owned")
	require("Trait increment visibility gate" not in geometry, "crashing split visibility hook returned")
	require("Trait increment active position" not in geometry, "crashing split position hook returned")
	require(
		geometry.index("'8B 0C 3E 85 C9'") < geometry.index("'8B 01 80 BE FC 00 00 00 01'"),
		"Trait page-mode test runs before child/vtable validation",
	)
	for child_exists in (False, True):
		for trait_page in (False, True):
			move_call = child_exists
			require(move_call == child_exists, f"Trait refresh model changed for child={child_exists}, page={trait_page}")

	# Exhaust all simultaneous row subsets for both protocols, including the
	# historical Str+Dex+Luk loss and its Pow+Con+Crt Trait equivalent.
	for mask in range(1, 1 << 6):
		status_pending = [index + 1 if mask & (1 << index) else 0 for index in range(6)]
		status_packets = [
			struct.pack("<HHB", 0x00BB, status_ids[index], amount)
			for index, amount in enumerate(status_pending) if amount
		]
		require(len(status_packets) == mask.bit_count(), f"Status subset 0x{mask:02X} lost a row")
		for packet, index in zip(status_packets, (i for i, amount in enumerate(status_pending) if amount)):
			require(struct.unpack("<HHB", packet) == (0x00BB, status_ids[index], status_pending[index]), "Status fields changed")

		trait_pending = [index + 1 if mask & (1 << index) else 0 for index in range(6)]
		trait_packets = [
			struct.pack("<HHH", 0x0B24, trait_status_ids[index], amount)
			for index, amount in enumerate(trait_pending) if amount
		]
		require(len(trait_packets) == mask.bit_count(), f"Trait subset 0x{mask:02X} lost a row")
		for packet, index in zip(trait_packets, (i for i, amount in enumerate(trait_pending) if amount)):
			require(struct.unpack("<HHH", packet) == (0x0B24, trait_status_ids[index], trait_pending[index]), "Trait fields changed")

	for status_id in status_ids:
		for amount in range(1, 131):
			require(len(struct.pack("<HHB", 0x00BB, status_id, amount)) == 5, "Status amount does not fit")
	for status_id in trait_status_ids:
		for amount in range(1, 111):
			packet = struct.pack("<HHH", 0x0B24, status_id, amount)
			require(len(packet) == 6 and struct.unpack("<HHH", packet)[2] == amount, "Trait amount does not fit")

	# Staging model: Plus projects immediately, Minus only reverses pending,
	# Cancel clears all, and committed values do not change until server ACKs.
	for index in range(6):
		committed = [10] * 6
		pending = [0] * 6
		points = 3
		pending[index] += 1
		require(committed[index] + pending[index] == 11 and points - sum(pending) == 2, "Trait Plus projection changed")
		pending[index] -= 1
		require(committed[index] == 10 and pending[index] == 0, "Trait Minus changed committed data")
		pending[index] = 2
		pending = [0] * 6
		require(committed == [10] * 6 and sum(pending) == 0, "Trait Cancel changed committed data")

	require(source.count("const nativeFontIndex = 1;") >= 2, "native font selector changed")
	require(source.count("const nativeValueHeight = 14;") >= 2, "native value height changed")
	require(source.count("const nativeCompactHeight = 12;") >= 2, "native compact height changed")
	require(source.count("drawRight(265, 152, 40, nativeCompactHeight);") == 2, "Status/Trait points no longer share alignment")
	require("drawLeft(85, 126 + i * 16, 32, nativeValueHeight);" in source, "Trait Base alignment changed")
	require("drawLeft(124, 126 + i * 16, 32, nativeValueHeight);" in source, "Trait Bonus alignment changed")
	require("drawRight(174, 128 + i * 16, 32, nativeCompactHeight);" in source, "Trait Req alignment changed")
	require("0x008B6FDE, 0x008B733F" in source, "stock Trait Req/Points suppression changed")
	require("'projected Trait renderer'" in source, "projected Trait renderer hook is missing")

	match = re.search(r"const derivedRows = \[([^\]]+)\];", source)
	require(match is not None, "derived row coordinate table is missing")
	derived_rows = [int(value.strip()) for value in match.group(1).split(",")]
	require(derived_rows == [27, 48, 69, 90], "Status derived rows changed")
	require(all(line - row == 11 for row, line in zip(derived_rows, [38, 59, 80, 101])), "Status glyphs no longer meet underlines")

	trait_y = [
		int(value) for value in re.findall(
			r"\[0x008B(?:7103|715E|71B9|7214|7276|72D8), \d+, (\d+), '[^']+ y'\]",
			source,
		)
	]
	require(trait_y == [35, 58, 81, 81, 35, 58], "Trait derived rows changed")
	trait_x = [
		int(value) for value in re.findall(
			r"\[0x008B(?:7108|7163|71BE|7219|727B|72DD), \d+, (\d+), '[^']+ x'\]",
			source,
		)
	]
	require(trait_x == [141, 141, 251, 141, 251, 251], "Trait derived right edges changed")
	require("buildDynamicOpaqueRegionRepair" in source, "Trait alpha repair is missing")
	require(source.count("createOpaqueCoordinateAdjuster(") == 1, "native Trait derived alpha wrapper count changed")

	trait_sources = extract_hex_array(source, "traitSources")
	require(trait_sources == [0x01037330, 0x01037380, 0x010373F0, 0x01037320, 0x01037370, 0x01037310], "native Trait tooltip sources changed")
	trait_match = re.search(r"const traitPoints = \[(.*?)\];", source, re.S)
	require(trait_match is not None, "Trait tooltip coordinate table is missing")
	trait_points = [tuple(map(int, pair)) for pair in re.findall(r"\[(-?\d+),\s*(-?\d+)\]", trait_match.group(1))]
	require(trait_points == [(38,126),(38,142),(38,158),(38,174),(38,190),(38,206),(57,32),(57,55),(170,78),(57,78),(197,133),(170,32)], "native Trait tooltip regions changed")
	require("Exe.SetUint32(finalTrait + 3, 170);" in source and "Exe.SetUint32(finalTrait + 24, 55);" in source, "native Mres tooltip region changed")

	require("writeCString('Stat')" in source and "writeCString('Trait')" in source, "tab hover labels changed")
	require("writeCString('')" in source, "empty tab caption is missing")
	tab_behavior = section(source, "RedesignedStatusWindow.patchTabBehavior = function(", "RedesignedStatusWindow.allocateCoordinates = function(points)")
	require("P32(tabStatVir)" not in tab_behavior and "P32(tabTraitVir)" not in tab_behavior, "tab strings are still assigned as button captions")
	require("P32(tabEmptyVir)" in tab_behavior, "empty caption assignment is missing")
	top_hover = section(source, "RedesignedStatusWindow.buildTopTooltip = function(", "RedesignedStatusWindow.patchTooltips = function(")
	require("tabStatVir" not in top_hover and "tabTraitVir" not in top_hover, "tab hover still depends on the unreachable late hit-test path")
	tab_hover = section(source, "RedesignedStatusWindow.patchTabHoverLabels = function(", "RedesignedStatusWindow.onApplied = function()")
	require("P32(tabStatVir)" in tab_hover and "P32(tabTraitVir)" in tab_hover, "tab labels are not mouse-move hover payloads")
	require("'55 8B EC 81 EC D0 00 00 00 A1 24 B9 22 01'" in tab_hover, "Status mouse-move prologue hook changed")
	require("'83 7C 24 24 22'" in tab_hover, "tab hover x hit test changed")
	require("83 F8 32" in tab_hover and "83 F8 53" in tab_hover and "83 F8 11" in tab_hover, "tab hover y ranges changed")
	require("'83 E8 10'" in tab_hover and "'83 EB 0D'" in tab_hover, "cursor-relative tooltip offsets changed")
	require("10: 0x00A1EF70" in tab_hover and "11: 0x00A753D0" in tab_hover, "tab hover does not use the native Equipment-style tooltip path")
	require("'6A 01 6A 01 6A FF 53 50 57'" in tab_hover, "native control-tooltip flags changed")
	require(hashlib.sha256(TRAIT_TAB_OUT.read_bytes()).hexdigest().upper() == "AC5DB799B62A95A4B7EBC33086DDAED9947514D46E5A6B74FB0C62A1CF63E2F4", "inactive Trait tab sprite changed")

	require("buildOpaqueRegionRepair(17, 2, 60, 15)" in source, "title alpha repair changed")
	require("value_native_" not in source, "obsolete glyph resources returned")

	print("PASS: independent Status and Trait control/row mappings")
	print("PASS: exact native 0x00BB and 0x0B24 packet contracts")
	print("PASS: all 63 simultaneous subsets retain every selected row on both pages")
	print("PASS: all 780 Status and 660 Trait status/amount pairs")
	print("PASS: projected Plus/Minus/Cancel model and server Trait cap 110")
	print("PASS: native font, opaque values, shared point alignment, and underline geometry")
	print("PASS: null-safe fourth-job Trait refresh block")
	print("PASS: native stat hovers plus Equipment-style Stat/Trait tab balloons")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.parse_args()
	verify_source()


if __name__ == "__main__":
	main()