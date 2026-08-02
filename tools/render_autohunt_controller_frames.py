#!/usr/bin/env python3
"""Bake Ragnarok STR controller effects into QJS-friendly TGA frames."""

from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


@dataclass
class KeyFrame:
	frame: int
	offset: tuple[float, float]
	xy: tuple[float, ...]
	texture_index: float
	animation_type: int
	delay: float
	angle: float
	color: tuple[float, ...]
	source_alpha: int
	destination_alpha: int
	interpolated: bool = False


@dataclass
class Layer:
	textures: list[str]
	keys: list[KeyFrame]


@dataclass
class StrEffect:
	fps: int
	max_frame: int
	layers: list[Layer]


def _read_cstring(block: bytes) -> str:
	return block.split(b"\0", 1)[0].decode("latin1")


def load_str(path: Path) -> StrEffect:
	data = path.read_bytes()
	if data[:4] != b"STRM":
		raise ValueError(f"{path}: not a Ragnarok STR file")
	fps, max_frame, layer_count = struct.unpack_from("<iii", data, 8)
	offset = 36
	layers: list[Layer] = []
	key_format = struct.Struct("<ii2f8f8ffiff4fiii")
	for _ in range(layer_count):
		texture_count = struct.unpack_from("<i", data, offset)[0]
		offset += 4
		textures = []
		for _ in range(texture_count):
			textures.append(_read_cstring(data[offset:offset + 128]))
			offset += 128
		key_count = struct.unpack_from("<i", data, offset)[0]
		offset += 4
		raw_keys = []
		for _ in range(key_count):
			values = key_format.unpack_from(data, offset)
			offset += key_format.size
			raw_keys.append(values)
		keys: list[KeyFrame] = []
		for index, values in enumerate(raw_keys):
			frame, record_type = values[:2]
			if record_type == 1:
				if keys and not (
					index + 1 < len(raw_keys)
					and raw_keys[index + 1][1] == 0
					and raw_keys[index + 1][0] == frame
				):
					keys[-1].interpolated = True
				continue
			keys.append(KeyFrame(
				frame=frame,
				offset=(values[2], values[3]),
				xy=tuple(values[12:20]),
				texture_index=values[20],
				animation_type=values[21],
				delay=values[22],
				angle=values[23] / (1024.0 / 360.0),
				color=tuple(values[24:28]),
				source_alpha=values[28],
				destination_alpha=values[29],
			))
		layers.append(Layer(textures, keys))
	if offset != len(data):
		raise ValueError(f"{path}: parsed {offset} of {len(data)} bytes")
	return StrEffect(fps, max_frame, layers)


def _lerp(a: float, b: float, t: float) -> float:
	return a + (b - a) * t


def interpolate(layer: Layer, frame: int) -> KeyFrame | None:
	if not layer.keys or frame < layer.keys[0].frame:
		return None
	base_index = -1
	for index, key in enumerate(layer.keys):
		if key.frame <= frame:
			base_index = index
		else:
			break
	if base_index < 0:
		return None
	base = layer.keys[base_index]
	if frame == base.frame or not base.interpolated or base_index + 1 >= len(layer.keys):
		return base
	next_key = layer.keys[base_index + 1]
	if frame >= next_key.frame:
		return next_key
	t = (frame - base.frame) / (next_key.frame - base.frame)
	return KeyFrame(
		frame=frame,
		offset=(_lerp(base.offset[0], next_key.offset[0], t),
			_lerp(base.offset[1], next_key.offset[1], t)),
		xy=tuple(_lerp(a, b, t) for a, b in zip(base.xy, next_key.xy)),
		texture_index=base.texture_index,
		animation_type=base.animation_type,
		delay=base.delay,
		angle=_lerp(base.angle, next_key.angle, t),
		color=tuple(_lerp(a, b, t) for a, b in zip(base.color, next_key.color)),
		source_alpha=base.source_alpha,
		destination_alpha=base.destination_alpha,
		interpolated=True,
	)


def texture_index(layer: Layer, key: KeyFrame) -> int:
	index = int(key.texture_index)
	if key.animation_type in (2, 3):
		base = max((item for item in layer.keys if item.frame <= key.frame),
			key=lambda item: item.frame)
		index = int(base.texture_index + base.delay * (key.frame - base.frame))
		if key.animation_type == 2:
			index = min(index, len(layer.textures) - 1)
		else:
			index %= len(layer.textures)
	return max(0, min(index, len(layer.textures) - 1))


def tint(image: Image.Image, color: tuple[float, ...]) -> Image.Image:
	red, green, blue, alpha = image.split()
	red = red.point(lambda value: int(value * color[0] / 255.0))
	green = green.point(lambda value: int(value * color[1] / 255.0))
	blue = blue.point(lambda value: int(value * color[2] / 255.0))
	alpha = alpha.point(lambda value: int(value * color[3] / 255.0))
	return Image.merge("RGBA", (red, green, blue, alpha))


def blend(canvas: Image.Image, sprite: Image.Image, position: tuple[int, int],
		source_alpha: int, destination_alpha: int) -> None:
	if source_alpha == 5 and destination_alpha == 6:
		canvas.alpha_composite(sprite, position)
		return
	# STR glow layers use SRCALPHA/DESTALPHA. Screen blending is a close
	# precomposited equivalent and preserves the transparent controller edge.
	left, top = position
	right = min(canvas.width, left + sprite.width)
	bottom = min(canvas.height, top + sprite.height)
	clip_left = max(0, left)
	clip_top = max(0, top)
	if right <= clip_left or bottom <= clip_top:
		return
	source = sprite.crop((clip_left - left, clip_top - top,
		right - left, bottom - top))
	destination = canvas.crop((clip_left, clip_top, right, bottom))
	if source_alpha == 5 and destination_alpha == 7:
		composite = ImageChops.screen(destination, source)
	else:
		composite = Image.alpha_composite(destination, source)
	canvas.paste(composite, (clip_left, clip_top))


def render_frame(effect: StrEffect, root: Path, frame: int, size: int,
		scale: float) -> Image.Image:
	canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	texture_cache: dict[str, Image.Image] = {}
	for layer in effect.layers:
		key = interpolate(layer, frame)
		if key is None or not layer.textures or key.color[3] <= 0:
			continue
		name = layer.textures[texture_index(layer, key)]
		if name not in texture_cache:
			texture_cache[name] = Image.open(root / name).convert("RGBA")
		image = texture_cache[name]
		width = max(1, round((max(key.xy[:4]) - min(key.xy[:4])) * scale))
		height = max(1, round((max(key.xy[4:]) - min(key.xy[4:])) * scale))
		image = image.resize((width, height), Image.Resampling.LANCZOS)
		image = tint(image, key.color)
		if abs(key.angle) > 0.001:
			image = image.rotate(-key.angle, resample=Image.Resampling.BICUBIC, expand=True)
		center_x = size / 2.0 + (key.offset[0] - 320.0) * scale
		center_y = size / 2.0 + (key.offset[1] - 240.0) * scale
		position = (round(center_x - image.width / 2.0),
			round(center_y - image.height / 2.0))
		blend(canvas, image, position, key.source_alpha, key.destination_alpha)
	return canvas


def bake(effect_dir: Path, str_name: str, output_dir: Path, size: int,
		frame_count: int, scale: float, inactive: bool = False) -> None:
	effect = load_str(effect_dir / str_name)
	output_dir.mkdir(parents=True, exist_ok=True)
	if inactive:
		frames = [0]
	else:
		frames = [round(index * effect.max_frame / frame_count)
			for index in range(frame_count)]
	for index, source_frame in enumerate(frames):
		image = render_frame(effect, effect_dir, source_frame, size, scale)
		name = "inactive.tga" if inactive else f"active_{index:02d}.tga"
		image.save(output_dir / name, format="TGA", compression=None)


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--autobattle", type=Path, required=True)
	parser.add_argument("--autopotion", type=Path, required=True)
	parser.add_argument("--output", type=Path,
		default=Path("Assets/AutoCombatUI"))
	parser.add_argument("--size", type=int, default=72)
	parser.add_argument("--scale", type=float, default=1.2)
	parser.add_argument("--frames", type=int, default=30)
	args = parser.parse_args()
	for name, root in (("autobattle", args.autobattle),
			("autopotion", args.autopotion)):
		bake(root / f"{name}_blue_loop", f"{name}_blue_loop.str",
			args.output / name, args.size, args.frames, args.scale)
		bake(root / f"{name}_red", f"{name}_red.str",
			args.output / name, args.size, args.frames, args.scale, inactive=True)


if __name__ == "__main__":
	main()
