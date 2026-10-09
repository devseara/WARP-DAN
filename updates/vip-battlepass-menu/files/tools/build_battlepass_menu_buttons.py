"""Export the generated Battle Pass logo as native Renewal/Classic menu BMP states.

Matches the supplied booking BMP headers for the 45x41 menu family, including
24-bit RGB, magenta color key, resolution and trailing padding. Retains the
32x34 Classic family and both compatibility aliases (12 BMPs total). Source
artwork and reference samples remain unchanged.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Assets/BattlepassUI/menuicon"
SOURCE = OUT / "source/battlepass-emblem.png"
STATES = ("normal", "mouseon", "pressed")
SAMPLE_FAMILY = ("", "_disabled", "_mouseon", "_new", "_new_press", "_normal")
NEW_STATES = OUT / "source/battlepass-new-states.png"


def save_bitmap(output, name, manifest, template=None):
    stream = io.BytesIO()
    output.convert("RGB").save(stream, format="BMP")
    raw = stream.getvalue()
    if template is not None:
        # Keep the native sample's BMP container; replace only its pixel array.
        assert struct.unpack_from("<iiHHI", template, 18) == (45, 41, 1, 24, 0)
        offset = struct.unpack_from("<I", template, 10)[0]
        size = ((45 * 3 + 3) & ~3) * 41
        assert offset == 54 and len(raw) == offset + size
        raw = template[:offset] + raw[offset:] + template[offset + size:]
        assert len(raw) == struct.unpack_from("<I", raw, 2)[0]
    (OUT/name).write_bytes(raw)
    manifest["files"][name] = {"size": list(output.size), "sha256": hashlib.sha256(raw).hexdigest()}


def new_state(sheet, index):
    # Asset export only: separate the two tool-generated cells and fit each
    # complete silhouette into the native transparent canvas.
    middle = sheet.width // 2
    icon = sheet.crop((0 if index == 0 else middle, 0,
                       middle if index == 0 else sheet.width, sheet.height))
    bounds = icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()
    if not bounds:
        raise ValueError("Generated new-state cell is empty")
    icon = icon.crop(bounds)
    icon.thumbnail((39,35), Image.Resampling.LANCZOS)
    output = Image.new("RGB", (45,41), (255,0,255))
    output.paste(icon.convert("RGB"), ((45-icon.width)//2, (41-icon.height)//2),
                 icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0))
    return output


def main():
    with Image.open(SOURCE) as image:
        source = image.convert("RGBA")
    alpha = source.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError("Battle Pass logo must have visible artwork")
    logo = source.crop(bounds)
    preview = Image.new("RGB", (450,270), "#e6e2db")
    draw = ImageDraw.Draw(preview)
    samples = {suffix: (OUT / f"source/samples/bt_booking{suffix}.bmp").read_bytes()
               for suffix in SAMPLE_FAMILY}
    template = samples["_normal"]
    manifest = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "new_states_sha256": hashlib.sha256(NEW_STATES.read_bytes()).hexdigest(),
                "samples": {f"bt_booking{k}.bmp": hashlib.sha256(v).hexdigest() for k,v in samples.items()},
                "files": {}}
    for row, (prefix, size, fit) in enumerate((("", (45,41), (39,35)), ("old_", (32,34), (25,24)))):
        for column, state in enumerate(STATES):
            icon = logo.copy()
            icon.thumbnail(fit, Image.Resampling.LANCZOS)
            alpha = icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
            rgb = icon.convert("RGB")
            if state != "normal":
                rgb = ImageEnhance.Brightness(rgb).enhance(1.15 if state == "mouseon" else 0.88)
            if prefix:
                with Image.open(ROOT / f"Images/BestiaryUI/source/menuicon/classic_frame_{state}.bmp") as frame:
                    output = frame.convert("RGB")
                assert output.size == size
            else:
                output = Image.new("RGB", size, (255,0,255))
            x = (size[0]-icon.width)//2 + int(bool(prefix) and state == "pressed")
            y = (size[1]-icon.height)//2 + int(state == "pressed")
            output.paste(rgb, (x,y), alpha)
            name = f"bt_battlepass_{prefix}{state}.bmp"
            save_bitmap(output, name, manifest, None if prefix else template)
            show = output.convert("RGBA")
            show.putdata([(r,g,b,0 if r>=248 and g<4 and b>=248 else 255) for r,g,b,_ in show.get_flattened_data()])
            big = show.resize((size[0]*3,size[1]*3), Image.Resampling.NEAREST)
            preview.paste(big, (column*150,row*135), big)
            draw.text((column*150+4,row*135+123), ("Classic " if prefix else "Renewal ")+state, fill="#33291d")
    # The supplied base/disabled/normal samples are identical. Mirror those
    # aliases while retaining the Battle Pass hover and native pressed feedback.
    with Image.open(OUT / "bt_battlepass_normal.bmp") as normal:
        for suffix in ("", "_disabled"):
            save_bitmap(normal, f"bt_battlepass{suffix}.bmp", manifest, samples[suffix])
    with Image.open(NEW_STATES) as image:
        sheet = image.convert("RGBA")
    for index, suffix in enumerate(("_new", "_new_press")):
        save_bitmap(new_state(sheet,index), f"bt_battlepass{suffix}.bmp", manifest, samples[suffix])
    # Keep the compatibility aliases byte-identical to their existing states;
    # no additional native button behavior is needed.
    for alias, original in (("bt_battlepass_press.bmp", "bt_battlepass_pressed.bmp"),
                            ("bt_battlepass_old_disabled.bmp", "bt_battlepass_old_normal.bmp")):
        (OUT/alias).write_bytes((OUT/original).read_bytes())
        manifest["files"][alias] = dict(manifest["files"][original])
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    review = ROOT / "Outputs/battlepass-menu-20261008"
    review.mkdir(parents=True,exist_ok=True)
    preview.save(review/"battlepass-menu-preview.png")
    family_preview = Image.new("RGB", (570,390), "#e6e2db")
    labels = ImageDraw.Draw(family_preview)
    for index, suffix in enumerate(SAMPLE_FAMILY):
        name = f"bt_battlepass{suffix}.bmp"
        with Image.open(OUT/name) as icon:
            big = icon.resize((180,164), Image.Resampling.NEAREST)
        x,y = index%3*190,index//3*195
        family_preview.paste(big,(x,y))
        labels.text((x+2,y+168),name,fill="#33291d")
    family_preview.save(review/"battlepass-sample-states-preview.png")
    print("PASS: all 12 Battle Pass menu BMPs exported, including Renewal press and Classic disabled aliases.")


if __name__ == "__main__":
    main()
