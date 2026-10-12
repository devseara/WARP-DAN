#!/usr/bin/env python3
"""Build 75x100 collection card art and update CP949 item-info resources.

The source card illustrations are extracted from the client's cardbmp GRF
folder before invoking this tool.  The script is dry-run by default; --write
creates a byte-for-byte backup, writes only verified mappings, and emits a
manifest beside the backup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import struct
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from PIL import Image


ENTRY_RE = re.compile(r"(?m)^\t\[(\d+)\]\s*=\s*\{")
RESOURCE_RE = re.compile(
	r'(?m)^(\t\t(?:unidentified|identified)ResourceName\s*=\s*")([^"]*)(",\s*)$'
)
SAFE_RESOURCE_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class ItemInfoEntry:
	item_id: int
	start: int
	end: int
	resources: tuple[str, str]


@dataclass(frozen=True)
class Mapping:
	item_id: int
	aegis_name: str
	old_resource: str
	source: Path
	destination: Path


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--source-cardbmp", type=Path, required=True)
	parser.add_argument("--item-info", type=Path, required=True)
	parser.add_argument("--item-db-root", type=Path, required=True)
	parser.add_argument("--display-name-table", type=Path, required=True)
	parser.add_argument("--destination-collection", type=Path, required=True)
	parser.add_argument("--destination-item", type=Path)
	parser.add_argument("--unnamed-card-icon", type=Path)
	parser.add_argument("--backup-root", type=Path, required=True)
	parser.add_argument("--write", action="store_true")
	args = parser.parse_args()
	if (args.destination_item is None) != (args.unnamed_card_icon is None):
		parser.error("--destination-item and --unnamed-card-icon must be supplied together")
	return args


def load_item_info(path: Path) -> tuple[bytes, str, list[ItemInfoEntry]]:
	raw = path.read_bytes()
	if raw.startswith(b"\xef\xbb\xbf"):
		raise ValueError(f"{path} unexpectedly has a UTF-8 BOM")
	text = raw.decode("cp949", errors="strict")
	if text.encode("cp949") != raw:
		raise ValueError(f"{path} does not round-trip through CP949")
	matches = list(ENTRY_RE.finditer(text))
	entries: list[ItemInfoEntry] = []
	for index, match in enumerate(matches):
		start = match.start()
		end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
		block = text[start:end]
		resources = RESOURCE_RE.findall(block)
		values = tuple(value for _, value, _ in resources)
		if len(values) != 2:
			continue
		entries.append(ItemInfoEntry(int(match.group(1)), start, end, values))
	return raw, text, entries


def iter_yaml_bodies(paths: Iterable[Path]) -> Iterable[dict]:
	for path in paths:
		if not path.exists():
			continue
		document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
		body = document.get("Body", [])
		if isinstance(body, list):
			for entry in body:
				if isinstance(entry, dict):
					yield entry


def load_card_database(root: Path) -> dict[int, str]:
	paths = [
		root / "pre-re" / "item_db_etc.yml",
		root / "pre-re" / "item_db_usable.yml",
		root / "pre-re" / "item_db_equip.yml",
		root / "import" / "item_db_etc.yml",
		root / "import" / "item_db_usable.yml",
		root / "import" / "item_db_equip.yml",
	]
	cards: dict[int, str] = {}
	for entry in iter_yaml_bodies(paths):
		if str(entry.get("Type", "")) != "Card":
			continue
		item_id = int(entry["Id"])
		aegis_name = str(entry["AegisName"])
		if not SAFE_RESOURCE_RE.fullmatch(aegis_name):
			raise ValueError(f"Unsafe AegisName for {item_id}: {aegis_name!r}")
		cards[item_id] = aegis_name
	return cards


def decode_extracted_stem(stem: str) -> str:
	try:
		return stem.encode("cp1252", errors="strict").decode("cp949", errors="strict")
	except (UnicodeEncodeError, UnicodeDecodeError):
		return stem


def normalize_art_key(value: str) -> str:
	value = unicodedata.normalize("NFKC", value).casefold()
	return re.sub(r"[\s_-]+", "", value)


def load_display_names(path: Path) -> dict[int, str]:
	text = path.read_bytes().decode("cp949", errors="strict")
	return {
		int(match.group(1)): match.group(2)
		for match in re.finditer(r"(?m)^(\d+)#([^#]*)#", text)
	}


def load_source_art(root: Path) -> tuple[dict[str, Path], list[str]]:
	by_resource: dict[str, Path] = {}
	ambiguous: set[str] = set()
	duplicates: list[str] = []
	for path in sorted(root.rglob("*.bmp"), key=lambda value: value.name.casefold()):
		resource = decode_extracted_stem(path.stem)
		if resource in ambiguous:
			continue
		if resource in by_resource:
			duplicates.append(resource)
			ambiguous.add(resource)
			by_resource.pop(resource, None)
			continue
		by_resource[resource] = path
	return by_resource, duplicates


def build_mappings(
	entries: list[ItemInfoEntry], cards: dict[int, str], source_art: dict[str, Path],
	display_names: dict[int, str], destination_root: Path,
) -> tuple[list[Mapping], list[int], list[int]]:
	mappings: list[Mapping] = []
	missing_item_info: list[int] = []
	missing_art: list[int] = []
	entry_by_id = {entry.item_id: entry for entry in entries}
	source_by_folded = {resource.casefold(): path for resource, path in source_art.items()}
	source_by_display: dict[str, Path] = {}
	for resource, path in source_art.items():
		key = normalize_art_key(resource)
		if key in source_by_display and source_by_display[key] != path:
			# Variant names must never be guessed. Exact Aegis matches above still work.
			source_by_display.pop(key, None)
			continue
		source_by_display[key] = path
	destination_names: dict[str, int] = {}
	for item_id, aegis_name in sorted(cards.items()):
		entry = entry_by_id.get(item_id)
		if entry is None:
			missing_item_info.append(item_id)
			continue
		identified_resource = entry.resources[1]
		# Official pre-renewal card entries commonly share the Korean
		# "unnamed card" resource. cardbmp itself is keyed by the canonical
		# Aegis stem (usually lower-case), so prefer that verified one-to-one key.
		source = source_by_folded.get(aegis_name.casefold())
		if source is None and item_id in display_names:
			source = source_by_display.get(normalize_art_key(display_names[item_id]))
		if source is None:
			source = source_art.get(identified_resource)
		if source is None:
			source = source_art.get(entry.resources[0])
		if source is None:
			missing_art.append(item_id)
			continue
		key = aegis_name.casefold()
		other_id = destination_names.get(key)
		if other_id is not None and other_id != item_id:
			raise ValueError(
				f"Destination collision {aegis_name}.bmp for {other_id} and {item_id}"
			)
		destination_names[key] = item_id
		mappings.append(Mapping(
			item_id=item_id,
			aegis_name=aegis_name,
			old_resource=identified_resource,
			source=source,
			destination=destination_root / f"{aegis_name}.bmp",
		))
	return mappings, missing_item_info, missing_art


def rewrite_item_info(text: str, entries: list[ItemInfoEntry], mappings: list[Mapping]) -> str:
	resource_by_id = {mapping.item_id: mapping.aegis_name for mapping in mappings}
	parts: list[str] = []
	position = 0
	for entry in entries:
		resource = resource_by_id.get(entry.item_id)
		if resource is None:
			continue
		parts.append(text[position:entry.start])
		block = text[entry.start:entry.end]
		updated, count = RESOURCE_RE.subn(
			lambda match: f"{match.group(1)}{resource}{match.group(3)}", block
		)
		if count != 2:
			raise ValueError(f"Expected two resource fields for item {entry.item_id}, got {count}")
		parts.append(updated)
		position = entry.end
	parts.append(text[position:])
	return "".join(parts)


def resize_bmp(source: Path, destination: Path) -> None:
	with Image.open(source) as image:
		converted = image.convert("RGB")
		resized = converted.resize((75, 100), Image.Resampling.LANCZOS)
		resized.save(destination, format="BMP")


def verify_bmp(path: Path) -> None:
	data = path.read_bytes()
	if data[:2] != b"BM" or len(data) < 54:
		raise ValueError(f"Invalid BMP: {path}")
	width, height = struct.unpack_from("<ii", data, 18)
	bits = struct.unpack_from("<H", data, 28)[0]
	compression = struct.unpack_from("<I", data, 30)[0]
	if (width, abs(height), bits, compression) != (75, 100, 24, 0):
		raise ValueError(
			f"Unexpected BMP contract for {path}: {width}x{height}, {bits}bpp, c={compression}"
		)


def atomic_write(path: Path, data: bytes) -> None:
	with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
		temporary = Path(handle.name)
		handle.write(data)
	os.replace(temporary, path)


def main() -> int:
	args = parse_args()
	raw, text, entries = load_item_info(args.item_info)
	cards = load_card_database(args.item_db_root)
	display_names = load_display_names(args.display_name_table)
	source_art, duplicate_sources = load_source_art(args.source_cardbmp)
	if duplicate_sources:
		raise ValueError(f"Duplicate decoded cardbmp resources: {duplicate_sources[:10]}")
	mappings, missing_item_info, missing_art = build_mappings(
		entries, cards, source_art, display_names, args.destination_collection
	)
	updated_text = rewrite_item_info(text, entries, mappings)
	updated_bytes = updated_text.encode("cp949", errors="strict")
	if updated_bytes.decode("cp949").encode("cp949") != updated_bytes:
		raise ValueError("Updated item-info no longer round-trips through CP949")

	summary = {
		"source_bmp_count": len(source_art),
		"card_db_count": len(cards),
		"display_name_count": len(display_names),
		"item_info_entry_count": len(entries),
		"mapped_count": len(mappings),
		"missing_item_info_count": len(missing_item_info),
		"missing_art_count": len(missing_art),
		"missing_item_info_sample": missing_item_info[:20],
		"missing_art_sample": missing_art[:20],
	}
	mapped_sources = {mapping.source.resolve() for mapping in mappings}
	output_jobs: list[tuple[Path, Path, str]] = [
		(mapping.source, mapping.destination, "mapped") for mapping in mappings
	]
	claimed_destinations = {mapping.destination.name.casefold() for mapping in mappings}
	unmapped_collision_count = 0
	for source in sorted(set(source_art.values()), key=lambda value: value.name.casefold()):
		if source.resolve() in mapped_sources:
			continue
		destination = args.destination_collection / source.name
		if destination.name.casefold() in claimed_destinations:
			unmapped_collision_count += 1
			continue
		claimed_destinations.add(destination.name.casefold())
		output_jobs.append((source, destination, "unmapped"))
	summary["output_bmp_count"] = len(output_jobs)
	summary["unmapped_output_count"] = sum(1 for _, _, kind in output_jobs if kind == "unmapped")
	summary["unmapped_collision_count"] = unmapped_collision_count
	summary["named_item_icon_count"] = len(mappings) if args.destination_item else 0
	print(json.dumps(summary, indent=2))
	if not args.write:
		return 0
	if not mappings:
		raise ValueError("No verified card mappings; refusing to write")

	timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
	backup_dir = args.backup_root / f"iteminfo-cardbmp-{timestamp}"
	backup_dir.mkdir(parents=True, exist_ok=False)
	shutil.copy2(args.item_info, backup_dir / args.item_info.name)
	args.destination_collection.mkdir(parents=True, exist_ok=True)
	existing_backup = backup_dir / "collection-original"
	for source, destination, _ in output_jobs:
		if destination.exists():
			existing_backup.mkdir(parents=True, exist_ok=True)
			shutil.copy2(destination, existing_backup / destination.name)
		resize_bmp(source, destination)
		verify_bmp(destination)

	item_icon_jobs: list[tuple[Path, Path]] = []
	if args.destination_item:
		if not args.unnamed_card_icon.is_file():
			raise ValueError(f"Unnamed card icon does not exist: {args.unnamed_card_icon}")
		icon_bytes = args.unnamed_card_icon.read_bytes()
		if icon_bytes[:2] != b"BM":
			raise ValueError(f"Unnamed card icon is not a BMP: {args.unnamed_card_icon}")
		args.destination_item.mkdir(parents=True, exist_ok=True)
		existing_item_backup = backup_dir / "item-original"
		for mapping in mappings:
			destination = args.destination_item / f"{mapping.aegis_name}.bmp"
			if destination.exists() and destination.read_bytes() != icon_bytes:
				existing_item_backup.mkdir(parents=True, exist_ok=True)
				shutil.copy2(destination, existing_item_backup / destination.name)
			atomic_write(destination, icon_bytes)
			if destination.read_bytes() != icon_bytes:
				raise ValueError(f"Named item icon verification failed: {destination}")
			item_icon_jobs.append((args.unnamed_card_icon, destination))

	atomic_write(args.item_info, updated_bytes)
	verified_raw, _, verified_entries = load_item_info(args.item_info)
	if verified_raw != updated_bytes:
		raise ValueError("Written item-info bytes do not match verified output")
	verified_by_id = {entry.item_id: entry for entry in verified_entries}
	for mapping in mappings:
		entry = verified_by_id.get(mapping.item_id)
		if entry is None or entry.resources != (mapping.aegis_name, mapping.aegis_name):
			raise ValueError(f"Resource verification failed for item {mapping.item_id}")

	manifest = {
		**summary,
		"item_info": str(args.item_info),
		"destination_collection": str(args.destination_collection),
		"destination_item": str(args.destination_item) if args.destination_item else None,
		"unnamed_card_icon": str(args.unnamed_card_icon) if args.unnamed_card_icon else None,
		"backup": str(backup_dir / args.item_info.name),
		"mappings": [
			{
				"item_id": mapping.item_id,
				"aegis_name": mapping.aegis_name,
				"old_resource": mapping.old_resource,
				"source": str(mapping.source),
				"destination": str(mapping.destination),
			}
			for mapping in mappings
		],
		"outputs": [
			{"source": str(source), "destination": str(destination), "kind": kind}
			for source, destination, kind in output_jobs
		],
		"item_icons": [
			{"source": str(source), "destination": str(destination)}
			for source, destination in item_icon_jobs
		],
	}
	(backup_dir / "manifest.json").write_text(
		json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
	)
	print(json.dumps({
		"resource_updates": len(mappings),
		"written_bmps": len(output_jobs),
		"written_item_icons": len(item_icon_jobs),
		"backup_dir": str(backup_dir),
	}, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
