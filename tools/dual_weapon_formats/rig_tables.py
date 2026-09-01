"""DWR3 (pose/transform rig) and DWC2 (per-view grip correction) binary
table structs and readers.

Promoted from tmp/recovered_dual/compile_weapon_coverage.py (struct
definitions and the DWR3 reader only -- that file's per-pair correction-table
*build* pipeline is superseded by the job-sprite compositor's socket +
hilt/tip landmark model and is not carried forward). See
docs/dual-wield-original-weapon-sprites.md's "DWR3/TRANSFORM binary format
quick-reference" section for the authoritative field-by-field description
this mirrors.
"""

from __future__ import annotations

import dataclasses
import hashlib
import struct

GENDERS = {0: "여", 1: "남"}

# DWR3 state -> (main_type, off_type). base types: 1=dagger, 2=sword, 6=axe.
STATE_HAND_TYPES = {
	6: (1, 1),
	7: (2, 2),
	8: (6, 6),
	9: (2, 1),
	11: (6, 1),
	13: (6, 2),
}

DWR3_HEADER = struct.Struct("<4sHBBIII")
DWR3_TRANSFORM = struct.Struct("<bbBBh")
DWC2_HEADER = struct.Struct("<4sHHII")
DWC2_CORRECTION = struct.Struct("<HBBBBBBhhBhB")


@dataclasses.dataclass(frozen=True)
class RigTransform:
	dx: int
	dy: int
	flags: int
	metadata: int
	rotation: int


def dense_index(family, gender, state, state_count, phase, direction, frame, hand) -> int:
	return ((((((family * 2 + gender) * state_count + state) * 2 + phase) * 8 + direction) * 8 + frame) * 2 + hand)


def parse_rig_bytes(rig: bytes) -> dict:
	magic, schema, family_count, state_count, index_count, transform_count, crc = (
		DWR3_HEADER.unpack_from(rig, 0)
	)
	if magic != b"DWR3" or schema != 3 or state_count != 15:
		raise ValueError("unexpected DWR3 header")
	family_offset = DWR3_HEADER.size
	index_offset = family_offset + family_count * 16
	transform_offset = index_offset + index_count * 2
	if transform_offset + transform_count * DWR3_TRANSFORM.size != len(rig):
		raise ValueError("DWR3 size mismatch")
	indices = struct.unpack_from(f"<{index_count}H", rig, index_offset)
	transforms = [
		RigTransform(*DWR3_TRANSFORM.unpack_from(rig, transform_offset + index * DWR3_TRANSFORM.size))
		for index in range(transform_count)
	]
	records = []
	for family in range(family_count):
		for gender in range(2):
			for state in range(state_count):
				for phase in range(2):
					for direction in range(8):
						for frame in range(8):
							for hand in range(2):
								dense = dense_index(family, gender, state, state_count, phase, direction, frame, hand)
								transform_index = indices[dense]
								if transform_index:
									records.append({
										"family": family,
										"gender": gender,
										"state": state,
										"phase": phase,
										"direction": direction,
										"frame": frame,
										"hand": hand,
										"transform_index": transform_index,
										"transform": transforms[transform_index - 1],
									})
	return {
		"bytes": rig,
		"sha256": hashlib.sha256(rig).hexdigest().upper(),
		"family_count": family_count,
		"state_count": state_count,
		"index_count": index_count,
		"transform_count": transform_count,
		"crc32": crc,
		"records": records,
	}


def correction_key(row: dict) -> tuple:
	return (
		row["view"], row["family"], row["gender"], row["phase"],
		row["direction"], row["source_key"], row["base_type"],
	)


def pack_dwc2(corrections: list[dict]) -> bytes:
	"""corrections: dicts with the DWC2_CORRECTION fields, sorted by correction_key."""
	import zlib

	payload = bytearray()
	for row in corrections:
		payload.extend(DWC2_CORRECTION.pack(
			row["view"], row["family"], row["gender"], row["phase"],
			row["direction"], row["source_key"], row["base_type"],
			row["dx"], row["dy"], row["mirror_xor"], row["rotation_delta"],
			row["selected_frame"],
		))
	header = DWC2_HEADER.pack(
		b"DWC2", 2, DWC2_CORRECTION.size, len(corrections), zlib.crc32(payload) & 0xFFFFFFFF,
	)
	return bytes(header) + bytes(payload)
