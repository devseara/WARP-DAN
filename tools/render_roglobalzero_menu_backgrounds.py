#!/usr/bin/env python3
"""Render complete RO Global Zero menu backgrounds for each visible row count."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


NEW_ROW_HEIGHT = 61
NEW_BASE_HEIGHT = 17
OLD_ROW_HEIGHT = 43
OLD_BASE_HEIGHT = 12
MAX_ROWS = 6


def resize_three_slice(source: Image.Image, height: int, cap: int) -> Image.Image:
	"""Resize only the center band, preserving both complete frame edges."""
	if height <= cap * 2:
		raise ValueError(f"target height {height} is too small for {cap}px caps")
	source = source.convert("RGBA")
	top = source.crop((0, 0, source.width, cap))
	center = source.crop((0, cap, source.width, source.height - cap))
	bottom = source.crop((0, source.height - cap, source.width, source.height))
	center = center.resize(
		(source.width, height - cap * 2),
		Image.Resampling.BILINEAR,
	)
	result = Image.new("RGBA", (source.width, height))
	result.paste(top, (0, 0))
	result.paste(center, (0, cap))
	result.paste(bottom, (0, height - cap))
	return result


def render_set(
	source_path: Path,
	output_dir: Path,
	prefix: str,
	row_height: int,
	base_height: int,
	cap: int,
) -> None:
	with Image.open(source_path) as source:
		for rows in range(1, MAX_ROWS + 1):
			height = rows * row_height + base_height
			output = resize_three_slice(source, height, cap)
			output.save(output_dir / f"{prefix}{rows}.tga", format="TGA")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--new", type=Path, required=True)
	parser.add_argument("--old", type=Path, required=True)
	parser.add_argument("--output", type=Path, required=True)
	args = parser.parse_args()
	args.output.mkdir(parents=True, exist_ok=True)
	render_set(
		args.new,
		args.output,
		"bg_m",
		NEW_ROW_HEIGHT,
		NEW_BASE_HEIGHT,
		7,
	)
	render_set(
		args.old,
		args.output,
		"bg_o",
		OLD_ROW_HEIGHT,
		OLD_BASE_HEIGHT,
		2,
	)


if __name__ == "__main__":
	main()
