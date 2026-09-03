#!/usr/bin/env python3
"""Build AutoSupport controller TGAs and native STR effect folders."""

from __future__ import annotations

import argparse
import colorsys
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
from render_autohunt_controller_frames import bake


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "Assets" / "AutoSupportUI"
# Original AutoHunt/AutoPotion 128px glyph textures occupy about 116px. Trim
# ImageGen canvas padding, then fit AutoSupport to that same native footprint.
NATIVE_GLYPH_OCCUPANCY = 116.0 / 128.0


def split_states(source: Path) -> tuple[Image.Image, Image.Image]:
	image = Image.open(source).convert("RGBA")
	tile = min(image.height, image.width // 2)
	y = (image.height - tile) // 2
	left = image.crop((0, y, tile, y + tile))
	right_x = image.width - tile
	right = image.crop((right_x, y, right_x + tile, y + tile))
	return left, right


def trim_alpha(image: Image.Image) -> Image.Image:
	# Ignore the extremely faint asymmetric haze emitted around the generated
	# sprite sheet; it must not reduce the actual button/glyph footprint.
	bbox = image.getchannel("A").point(lambda value: 255 if value >= 8 else 0).getbbox()
	if bbox is None:
		raise ValueError("generated AutoSupport state is fully transparent")
	return image.crop(bbox)


def extract_support_glyph(image: Image.Image) -> Image.Image:
	"""Remove the generated button/frame and retain heart, cross and sparkle."""
	image = image.convert("RGBA")
	seed = Image.new("L", image.size)
	source = image.load()
	seed_pixels = seed.load()
	width, height = image.size
	for y in range(height):
		ny = (y + 0.5) / height
		for x in range(width):
			nx = (x + 0.5) / width
			red, green, blue, alpha = source[x, y]
			heart_fill = (
				0.31 <= nx <= 0.71 and 0.31 <= ny <= 0.67 and
				min(red, green, blue) > 105 and max(red, green, blue) > 180
			)
			gold_sparkle = (
				0.58 <= nx <= 0.75 and 0.23 <= ny <= 0.43 and
				red > 170 and green > 100 and red > blue + 35 and green > blue + 10
			)
			if alpha >= 8 and (heart_fill or gold_sparkle):
				seed_pixels[x, y] = 255
	mask = seed.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(6))
	result = image.copy()
	result.putalpha(Image.composite(image.getchannel("A"),
		Image.new("L", image.size, 0), mask))
	return result


def recolor_support_blue(image: Image.Image) -> Image.Image:
	"""Recolor one canonical red glyph; preserve identical RGBA geometry."""
	image = image.convert("RGBA")
	result = Image.new("RGBA", image.size)
	source = image.load()
	target = result.load()
	for y in range(image.height):
		for x in range(image.width):
			red, green, blue, alpha = source[x, y]
			if alpha == 0:
				continue
			gold = red > blue + 35 and green > blue + 10 and red > 150
			if gold:
				target[x, y] = (red, green, blue, alpha)
				continue
			hue, saturation, value = colorsys.rgb_to_hsv(
				red / 255.0, green / 255.0, blue / 255.0)
			if saturation > 0.03:
				hue = 0.55
			new_red, new_green, new_blue = colorsys.hsv_to_rgb(hue, saturation, value)
			target[x, y] = (round(new_red * 255), round(new_green * 255),
				round(new_blue * 255), alpha)
	return result


def fit_on_canvas(image: Image.Image, size: int, scale: float) -> Image.Image:
	trimmed = trim_alpha(image)
	box = max(1, min(size, round(size * scale)))
	ratio = min(box / trimmed.width, box / trimmed.height)
	content_size = (max(1, round(trimmed.width * ratio)),
		max(1, round(trimmed.height * ratio)))
	content = trimmed.resize(content_size, Image.Resampling.LANCZOS)
	canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	canvas.alpha_composite(content,
		((size - content.width) // 2, (size - content.height) // 2))
	return canvas


def save_tga(image: Image.Image, path: Path, size: int, scale: float = 1.0,
	offset: tuple[int, int] = (0, 0)) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	fitted = fit_on_canvas(image, size, scale)
	if offset != (0, 0):
		shifted = Image.new("RGBA", (size, size), (0, 0, 0, 0))
		shifted.alpha_composite(fitted, offset)
		fitted = shifted
	fitted.save(path, format="TGA", rle=False)


def patch_str(source: Path, target: Path, replacements: dict[str, str]) -> None:
	data = bytearray(source.read_bytes())
	for old, new in replacements.items():
		old_bytes = old.encode("ascii")
		new_bytes = new.encode("ascii")
		if len(new_bytes) >= 128:
			raise ValueError(f"STR texture name too long: {new}")
		start = 0
		found = 0
		while True:
			index = data.find(old_bytes, start)
			if index < 0:
				break
			if index + len(new_bytes) >= len(data):
				raise ValueError(f"truncated STR texture field in {source}")
			data[index:index + len(new_bytes)] = new_bytes
			data[index + len(new_bytes)] = 0
			if len(new_bytes) < len(old_bytes):
				data[index + len(new_bytes) + 1:index + len(old_bytes)] = b"\0" * (
					len(old_bytes) - len(new_bytes) - 1
				)
			start = index + len(new_bytes) + 1
			found += 1
		if found == 0:
			raise ValueError(f"{old!r} not found in {source}")
	target.parent.mkdir(parents=True, exist_ok=True)
	target.write_bytes(data)


def freeze_texture_geometry(path: Path, texture_name: str,
	reference_quad: bytes | None = None) -> bytes:
	"""Make every key of a glyph layer use one exact native quad."""
	data = bytearray(path.read_bytes())
	key_format = struct.Struct("<ii2f8f8ffiff4fiii")
	offset = 36
	changed = 0
	layer_count = struct.unpack_from("<i", data, 16)[0]
	for _ in range(layer_count):
		texture_count = struct.unpack_from("<i", data, offset)[0]
		offset += 4
		textures = []
		for _ in range(texture_count):
			textures.append(bytes(data[offset:offset + 128]).split(b"\0", 1)[0].decode("latin1"))
			offset += 128
		key_count = struct.unpack_from("<i", data, offset)[0]
		offset += 4
		key_offsets = [offset + index * key_format.size for index in range(key_count)]
		if texture_name in textures:
			ordinary = [item for item in key_offsets if struct.unpack_from("<i", data, item + 4)[0] == 0]
			if ordinary:
				def area(item: int) -> float:
					values = key_format.unpack_from(data, item)
					return ((max(values[12:16]) - min(values[12:16])) *
						(max(values[16:20]) - min(values[16:20])))
				largest = max(ordinary, key=area)
				quad = reference_quad or bytes(data[largest + 48:largest + 80])
				for item in ordinary:
					data[item + 48:item + 80] = quad
					changed += 1
		offset += key_count * key_format.size
	if changed == 0:
		raise ValueError(f"{texture_name!r} has no ordinary STR keys in {path}")
	path.write_bytes(data)
	return quad


def copy_shared(source_dir: Path, target_dir: Path, excluded: set[str]) -> None:
	target_dir.mkdir(parents=True, exist_ok=True)
	for source in source_dir.iterdir():
		if source.is_file() and source.name.lower() not in excluded:
			shutil.copy2(source, target_dir / source.name)


def build_baked_frames(output: Path) -> None:
	controller = output / "autosupport_controller"
	effect = output / "autosupport" / "effect" / "roz_autosupport"
	bake(effect / "autosupport_blue_loop", "autosupport_blue_loop.str",
		controller, 72, 30, 1.2)
	bake(effect / "autosupport_red", "autosupport_red.str",
		controller, 72, 30, 1.2, inactive=True)


def build_native_effect(
	red: Image.Image, blue: Image.Image, native_root: Path, output: Path
) -> None:
	effect_root = output / "autosupport" / "effect" / "roz_autosupport"
	potion_root = native_root / "roz_autopotion"
	red_source = potion_root / "autopotion_red"
	start_source = potion_root / "autopotion_blue_start"
	loop_source = potion_root / "autopotion_blue_loop"
	for required in (red_source, start_source, loop_source):
		if not required.is_dir():
			raise FileNotFoundError(required)

	red_glyph = extract_support_glyph(red)
	blue_glyph = recolor_support_blue(red_glyph)
	red_target = effect_root / "autosupport_red"
	start_target = effect_root / "autosupport_blue_start"
	loop_target = effect_root / "autosupport_blue_loop"
	copy_shared(red_source, red_target, {"auto_potion_red.tga", "autopotion_red.str"})
	copy_shared(
		start_source,
		start_target,
		{"auto_potion_blue.tga", "auto_potion_line.tga", "autopotion_blue_start.str"},
	)
	copy_shared(
		loop_source,
		loop_target,
		{"auto_potion_blue.tga", "autopotion_blue_loop.str"},
	)

	save_tga(red_glyph, red_target / "auto_support_red.tga", 128, NATIVE_GLYPH_OCCUPANCY)
	save_tga(blue_glyph, start_target / "auto_support_blue.tga", 128,
		NATIVE_GLYPH_OCCUPANCY)
	save_tga(blue_glyph, loop_target / "auto_support_blue.tga", 128,
		NATIVE_GLYPH_OCCUPANCY)
	line = ImageEnhance.Brightness(blue_glyph).enhance(1.35)
	save_tga(line, start_target / "auto_support_line.tga", 128,
		NATIVE_GLYPH_OCCUPANCY)

	patch_str(
		red_source / "autopotion_red.str",
		red_target / "autosupport_red.str",
		{"auto_potion_red.tga": "auto_support_red.tga"},
	)
	patch_str(
		start_source / "autopotion_blue_start.str",
		start_target / "autosupport_blue_start.str",
		{
			"auto_potion_blue.tga": "auto_support_blue.tga",
			"auto_potion_line.tga": "auto_support_line.tga",
		},
	)
	patch_str(
		loop_source / "autopotion_blue_loop.str",
		loop_target / "autosupport_blue_loop.str",
		{"auto_potion_blue.tga": "auto_support_blue.tga"},
	)
	canonical_quad = freeze_texture_geometry(
		red_target / "autosupport_red.str", "auto_support_red.tga")
	freeze_texture_geometry(start_target / "autosupport_blue_start.str",
		"auto_support_blue.tga", canonical_quad)
	freeze_texture_geometry(start_target / "autosupport_blue_start.str",
		"auto_support_line.tga", canonical_quad)
	freeze_texture_geometry(loop_target / "autosupport_blue_loop.str",
		"auto_support_blue.tga", canonical_quad)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--source", type=Path, required=True)
	parser.add_argument("--native-root", type=Path, required=True)
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
	args = parser.parse_args()
	red, blue = split_states(args.source)
	args.output.mkdir(parents=True, exist_ok=True)
	shutil.copy2(args.source, args.output / "autosupport_icon_source.png")
	build_native_effect(red, blue, args.native_root, args.output)
	build_baked_frames(args.output)


if __name__ == "__main__":
	main()
