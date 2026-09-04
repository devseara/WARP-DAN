#!/usr/bin/env python3
"""Build native-framed Classic menu button states for AutoSupport."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
	REPO_ROOT / "Assets" / "AutoSupportUI" / "autosupport" / "menuicon"
)
STATE_PATTERNS = {
	"normal": "bt_*_old_normal.bmp",
	"mouseon": "bt_*_old_mouseon.bmp",
	"pressed": "bt_*_old_pressed.bmp",
}
BUTTON_SIZE = (32, 34)


def modal_native_frame(native_menu_root: Path, pattern: str) -> Image.Image:
	"""Recover the shared native chrome by taking the modal pixel across icons."""
	images: list[Image.Image] = []
	for path in sorted(native_menu_root.glob(pattern)):
		if "autosupport" in path.name.lower():
			continue
		image = Image.open(path).convert("RGB")
		if image.size == BUTTON_SIZE:
			images.append(image)
	if len(images) < 8:
		raise ValueError(
			f"need at least 8 native Classic button states for {pattern}, "
			f"found {len(images)} in {native_menu_root}"
		)
	planes = [list(image.get_flattened_data()) for image in images]
	pixels = [
		Counter(plane[index] for plane in planes).most_common(1)[0][0]
		for index in range(BUTTON_SIZE[0] * BUTTON_SIZE[1])
	]
	frame = Image.new("RGB", BUTTON_SIZE)
	frame.putdata(pixels)
	return frame


def heart_mask(offset_y: int) -> Image.Image:
	mask = Image.new("L", BUTTON_SIZE)
	draw = ImageDraw.Draw(mask)
	draw.ellipse((7, 10 + offset_y, 17, 20 + offset_y), fill=255)
	draw.ellipse((15, 10 + offset_y, 25, 20 + offset_y), fill=255)
	draw.polygon(
		[(7, 15 + offset_y), (25, 15 + offset_y),
		 (16, 28 + offset_y)],
		fill=255,
	)
	return mask


def draw_support_glyph(frame: Image.Image, state: str) -> Image.Image:
	"""Paint one stable heart/cross glyph inside the exact native button frame."""
	offset_y = 1 if state == "pressed" else 0
	mask = heart_mask(offset_y)
	outline = mask.filter(ImageFilter.MaxFilter(3))
	result = frame.convert("RGBA")
	ink = Image.new("RGBA", BUTTON_SIZE, (18, 7, 14, 0))
	ink.putalpha(outline)
	result.alpha_composite(ink)

	if state == "mouseon":
		top = (255, 128, 151)
		bottom = (232, 43, 78)
	elif state == "pressed":
		top = (238, 83, 108)
		bottom = (185, 19, 51)
	else:
		top = (250, 105, 132)
		bottom = (216, 30, 65)

	fill = Image.new("RGBA", BUTTON_SIZE)
	fill_pixels = fill.load()
	mask_pixels = mask.load()
	for y in range(BUTTON_SIZE[1]):
		ratio = min(1.0, max(0.0, (y - (10 + offset_y)) / 18.0))
		color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio)
			for i in range(3))
		for x in range(BUTTON_SIZE[0]):
			if mask_pixels[x, y]:
				fill_pixels[x, y] = (*color, 255)
	result.alpha_composite(fill)

	draw = ImageDraw.Draw(result)
	cross_shadow = (107, 16, 43, 255)
	cross = (255, 247, 249, 255)
	draw.rectangle((14, 14 + offset_y, 19, 24 + offset_y),
		fill=cross_shadow)
	draw.rectangle((11, 17 + offset_y, 22, 22 + offset_y),
		fill=cross_shadow)
	draw.rectangle((15, 15 + offset_y, 18, 23 + offset_y), fill=cross)
	draw.rectangle((12, 18 + offset_y, 21, 21 + offset_y), fill=cross)

	# A small gold sparkle keeps the menu glyph tied to the accepted controller.
	spark_dark = (98, 54, 5, 255)
	spark = (255, 205, 48, 255)
	draw.point((25, 10 + offset_y), fill=spark_dark)
	draw.line((25, 11 + offset_y, 25, 16 + offset_y), fill=spark_dark)
	draw.line((22, 13 + offset_y, 28, 13 + offset_y), fill=spark_dark)
	draw.line((25, 11 + offset_y, 25, 15 + offset_y), fill=spark)
	draw.line((23, 13 + offset_y, 27, 13 + offset_y), fill=spark)
	draw.point((25, 13 + offset_y), fill=(255, 245, 165, 255))

	return result.convert("RGB")


def build(native_menu_root: Path, output: Path) -> None:
	if not native_menu_root.is_dir():
		raise FileNotFoundError(native_menu_root)
	output.mkdir(parents=True, exist_ok=True)
	for state, pattern in STATE_PATTERNS.items():
		frame = modal_native_frame(native_menu_root, pattern)
		image = draw_support_glyph(frame, state)
		image.save(output / f"bt_autosupport_old_{state}.bmp", format="BMP")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--native-menu-root", type=Path, required=True)
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
	args = parser.parse_args()
	build(args.native_menu_root, args.output)


if __name__ == "__main__":
	main()
