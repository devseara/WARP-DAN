#!/usr/bin/env python3
"""Verify Riftlock client source invariants and an emitted 2025-07-16 PE."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import struct
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "Scripts" / "Patches" / "RiftlockTransport.qjs"
DISPATCH = ROOT / "Scripts" / "Patches" / "CustomPacketDispatch.qjs"
PROTOCOL = ROOT / "CustomDLL" / "src" / "riftlock" / "riftlock_protocol.h"
CLIENT = ROOT / "CustomDLL" / "src" / "riftlock" / "riftlock.cpp"

EXPECTED_IMPORTS = {
	"RiftlockInit",
	"RiftlockConnectionResetBridge",
	"RiftlockQueuePacketBridge",
	"RiftlockQueueDeferredPacketBridge",
	"RiftlockReceiveBytesBridge",
}


def require(condition: bool, message: str) -> None:
	if not condition:
		raise AssertionError(message)


def check_qjs(path: Path) -> None:
	raw = path.read_bytes()
	require(not raw.startswith(b"\xef\xbb\xbf"), f"{path.name}: UTF-8 BOM is forbidden")
	require(b"\r\n" in raw, f"{path.name}: CRLF line endings are required")
	require(b"\n" not in raw.replace(b"\r\n", b""), f"{path.name}: found LF-only line ending")
	require(b"new Date(" not in raw, f"{path.name}: new Date() is forbidden in WARP QJS")


def check_sources() -> None:
	check_qjs(PATCH)
	check_qjs(DISPATCH)
	protocol = PROTOCOL.read_text(encoding="utf-8")
	client = CLIENT.read_text(encoding="utf-8")
	for token in (
		"kProtocolVersion = 7",
		"kClientProbe = 0x0CEF",
		"kServerHello = 0x0CF0",
		"kClientHello = 0x0CF1",
		"kServerChallenge = 0x0CF2",
		"kClientChallenge = 0x0CF3",
		"kClientEnvelope = 0x0CF4",
		"kServerReady = 0x0CF5",
		"sizeof(ServerHello) == 140",
		"sizeof(ClientHello) == 532",
		"sizeof(ServerChallenge) == 60",
		"sizeof(ClientChallenge) == 484",
		"asset_sample_digest",
		"asset_loose_sample_count",
		"debug_digest",
		"suspicious_handle_count",
		"hook_digest",
		"hook_mismatch_count",
	):
		require(token in protocol, f"protocol contract token missing: {token}")
	for token in (
		'"riftlock/c2s/v1"',
		'"riftlock/s2c/v1"',
		'"riftlock/integrity/v2"',
		"crypto_sign_verify_detached",
		"crypto_scalarmult_curve25519",
		"crypto_auth_hmacsha256",
		"RiftlockQueuePacketBridge",
		"RiftlockQueueDeferredPacketBridge",
		"RiftlockReceiveBytesBridge",
	):
		require(token in client, f"client transport token missing: {token}")
	require("ws2_32" not in client.lower(), "Riftlock DLL must not hook or import Winsock")


def check_protocol_vectors() -> None:
	server_nonce = bytes(range(32))
	shared_secret = bytes(reversed(range(32)))
	client_nonce = bytes(range(32, 64))
	prk = hmac.new(server_nonce, shared_secret, hashlib.sha256).digest()
	require(
		prk.hex() == "9d2a0fddbe2de00ed0a9d9ec544d6be4be7b82ae931ce098c4ddfd326afeb11c",
		"Riftlock extract vector changed",
	)

	def expand(label: bytes) -> bytes:
		info = label + client_nonce + struct.pack("<IH", 1, 3) + b"\x01"
		return hmac.new(prk, info, hashlib.sha256).digest()

	client_to_server = expand(b"riftlock/c2s/v1")
	server_to_client = expand(b"riftlock/s2c/v1")
	require(
		client_to_server.hex() == "f4214e17a86fa44af23b4421b2babc99c09c3e8881ac3a015eefc15764513fba",
		"Riftlock c2s expansion vector changed",
	)
	require(
		server_to_client.hex() == "6a58dcdf2047092f521701b3bad80fc96223d015ddab8e1b1524f2bf22c23e8f",
		"Riftlock s2c expansion vector changed",
	)

	inner = bytes.fromhex("360478563412")
	prefix = struct.pack("<HHIHH", 0x0CF4, 12 + len(inner) + 16, 1, len(inner), 0)
	envelope = prefix + inner
	envelope += hmac.new(client_to_server, envelope, hashlib.sha256).digest()[:16]
	require(
		envelope.hex() == "f40c22000100000006000000360478563412fc69da47f1854368c648e224aeec0cab",
		"Riftlock envelope vector changed",
	)

	nonce = bytes(range(0xA0, 0xC0))
	challenge = struct.pack("<HHIHH", 0x0CF2, 60, 7, 1, 0) + nonce
	challenge += hmac.new(server_to_client, challenge, hashlib.sha256).digest()[:16]
	module_digest = hashlib.sha256(b"riftlock-module-vector").digest()
	memory_digest = hashlib.sha256(b"riftlock-memory-vector").digest()
	text_digest = hashlib.sha256(b"riftlock-text-vector").digest()
	asset_digest = hashlib.sha256(b"riftlock-asset-vector" + nonce).digest()
	debug_fields = struct.pack("<HHHHHHIIII", 0, 0, 1, 0, 0, 7, 0, 0, 0, 0)
	debug_digest = hashlib.sha256(b"riftlock-debug-vector" + debug_fields).digest()
	hook_fields = struct.pack("<HHHHHH", 0, 13, 0, 1, 0, 0) + bytes(32)
	hook_digest = hashlib.sha256(b"riftlock-hook-vector" + hook_fields).digest()
	response = (
		struct.pack("<HHI", 0x0CF3, 484, 7)
		+ nonce
		+ module_digest
		+ struct.pack("<HHI", 1, 0, 0)
		+ bytes(64)
		+ bytes(32)
		+ memory_digest
		+ struct.pack("<HHHHIIII", 0, 0, 0, 0, 0, 0, 0, 0)
		+ text_digest
		+ struct.pack("<HHIIB3s", 0, 16, 4096, 0, 0, bytes(3))
		+ asset_digest
		+ struct.pack("<HHHHIIB3s", 0, 2, 4, 4, 40960, 0, 0, bytes(3))
		+ debug_digest
		+ debug_fields
		+ hook_digest
		+ hook_fields
	)
	response += hmac.new(client_to_server, response, hashlib.sha256).digest()[:16]
	require(
		challenge.hex() == "f20c3c000700000001000000a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf8d3319efb00ff804040a4e125c99a46e",
		"Riftlock heartbeat challenge vector changed",
	)
	require(len(response) == 484, "Riftlock v7 heartbeat response size changed")
	require(
		hmac.compare_digest(
			response[-16:],
			hmac.new(client_to_server, response[:-16], hashlib.sha256).digest()[:16],
		),
		"Riftlock v7 heartbeat response MAC changed",
	)


def relative_target(pe: pefile.PE, virtual_address: int, displacement_offset: int) -> int:
	base = pe.OPTIONAL_HEADER.ImageBase
	displacement = struct.unpack(
		"<i", pe.get_data(virtual_address - base + displacement_offset, 4)
	)[0]
	return virtual_address + displacement_offset + 4 + displacement


def check_pe(path: Path) -> None:
	pe = pefile.PE(str(path), fast_load=False)
	require(pe.FILE_HEADER.Machine == 0x014C, "Riftlock target must be 32-bit x86")
	require(pe.OPTIONAL_HEADER.Magic == 0x010B, "Riftlock target must be PE32")

	imports = set()
	for descriptor in pe.DIRECTORY_ENTRY_IMPORT:
		if descriptor.dll.lower() != b"riftlock.dll":
			continue
		for symbol in descriptor.imports:
			if symbol.name:
				imports.add(symbol.name.decode("ascii"))
	require(imports == EXPECTED_IMPORTS, f"unexpected Riftlock imports: {sorted(imports)}")

	base = pe.OPTIONAL_HEADER.ImageBase
	connect = pe.get_data(0x00C13FC0 - base, 5)
	receive = pe.get_data(0x00C145D2 - base, 5)
	deferred = pe.get_data(0x00C1495D - base, 5)
	immediate = pe.get_data(0x00C1496C - base, 5)
	require(connect[:1] == b"\xE9", "connection reset prologue bridge is missing")
	require(receive[:1] == b"\xE8", "central receive-queue bridge is missing")
	require(deferred[:1] == b"\xE8", "deferred outgoing queue bridge is missing")
	require(immediate[:1] == b"\xE8", "immediate outgoing queue bridge is missing")

	for site, label in (
		(0x00C145D2, "receive"),
		(0x00C1495D, "deferred"),
		(0x00C1496C, "immediate"),
	):
		bridge = relative_target(pe, site, 1)
		code = pe.get_data(bridge - base, 17)
		require(code[:7] == b"\xFF\x34\x24\xC7\x44\x24\x04", f"{label} bridge stack ABI changed")
		require(code[7:11] == struct.pack("<I", 0x00C16640), f"{label} bridge lost stock queue target")
		require(code[11:13] == b"\xFF\x25", f"{label} bridge is not a static import jump")


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--exe", type=Path, help="emitted client EXE to inspect")
	args = parser.parse_args()
	check_sources()
	check_protocol_vectors()
	if args.exe:
		check_pe(args.exe.resolve())
	print("Riftlock client verification passed")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
