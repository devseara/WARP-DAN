"""Check fixed Auto UI caption widths with Windows GDI and optionally render a preview."""

import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
FACES = {0: "Gulim", 1: "Arial", 2: "MS Gothic", 4: "MingLiU", 5: "Tahoma"}
# Conservative 13-pixel glyph height, measured against existing UI controls.
BOUNDS = {"Normal: SP <": 98, "Teleport if no combat for": 231,
          "Teleport if more than": 198, "Teleport if at least": 198,
          "seconds.": 134, " monsters on the screen.": 167, " nearby monsters.": 167,
          "Auto recover when below": 187, "or higher.": 75}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    g = c.WinDLL("gdi32", use_last_error=True)
    g.CreateCompatibleDC.argtypes = [w.HDC]; g.CreateCompatibleDC.restype = w.HDC
    g.CreateFontW.argtypes = [c.c_int] * 5 + [w.DWORD] * 8 + [w.LPCWSTR]; g.CreateFontW.restype = w.HFONT
    g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]; g.SelectObject.restype = w.HGDIOBJ
    g.DeleteObject.argtypes = [w.HGDIOBJ]; g.DeleteDC.argtypes = [w.HDC]
    g.GetTextExtentPoint32W.argtypes = [w.HDC, w.LPCWSTR, c.c_int, c.POINTER(w.SIZE)]
    g.TextOutW.argtypes = [w.HDC, c.c_int, c.c_int, w.LPCWSTR, c.c_int]
    g.CreateDIBSection.argtypes = [w.HDC, c.c_void_p, w.UINT, c.POINTER(c.c_void_p), w.HANDLE, w.DWORD]
    g.CreateDIBSection.restype = w.HBITMAP
    dc = g.CreateCompatibleDC(None)
    assert dc
    width, height = 930, 1050
    info = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
    bits = c.c_void_p()
    bitmap = g.CreateDIBSection(dc, info, 0, c.byref(bits), None, 0)
    assert bitmap and bits.value
    previous = g.SelectObject(dc, bitmap)
    c.memset(bits, 255, width * height * 4)
    directory = ROOT / "Inputs/AutoUI"
    languages = json.loads((directory / "languages.json").read_text(encoding="ascii"))
    source = json.loads((directory / "zh-TW.json").read_text(encoding="utf-8"))
    try:
        for row, (name, spec) in enumerate(languages.items()):
            data = ({key: key for key in source} if name == "English" else
                    json.loads((directory / (spec["locale"] + ".json")).read_text(encoding="utf-8")))
            face = FACES[spec["fontSelector"]]
            font = g.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, spec["charset"], 0, 0, 0, 0, face)
            assert font
            old = g.SelectObject(dc, font)
            try:
                for key, limit in BOUNDS.items():
                    size = w.SIZE()
                    assert g.GetTextExtentPoint32W(dc, data[key], len(data[key]), c.byref(size))
                    assert size.cx <= limit, (name, key, size.cx, limit)
                compact = g.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, spec["charset"], 0, 0, 0, 0, face)
                assert compact
                g.SelectObject(dc, compact)
                try:
                    for n in range(6):
                        key = f"{n} option" + ("s" if n != 1 else "")
                        size = w.SIZE()
                        assert g.GetTextExtentPoint32W(dc, data[key], len(data[key]), c.byref(size))
                        assert size.cx <= 69, (name, key, size.cx, "dropdown arrow overlap")
                finally:
                    g.SelectObject(dc, font); g.DeleteObject(compact)
                lines = [name + " / " + face,
                         data["AUTO HUNT SETTINGS"] + "    " + data["AUTO SUPPORT SETTINGS"],
                         " | ".join(data[key] for key in ("Basic", "Monster", "Player", "Skill", "Potion", "Looting", "Move", "Item")),
                         data["Configure the automatic hunting feature."],
                         data["Normal: SP <"] + " 10" + data[" %."],
                         data["Use teleport when an MVP boss monster appears."]]
                for n, line in enumerate(lines):
                    assert g.TextOutW(dc, 16, row * 130 + 8 + n * 19, line, len(line))
                print(f"PASS {name}: {len(BOUNDS)} fixed caption bounds and 6 dropdown labels, native font {face}")
            finally:
                g.SelectObject(dc, old); g.DeleteObject(font)
        if args.preview:
            raw = c.string_at(bits, width * height * 4)
            args.preview.write_bytes(struct.pack("<2sIHHI", b"BM", 14 + len(info) + len(raw), 0, 0, 54) + info + raw)
    finally:
        g.SelectObject(dc, previous); g.DeleteObject(bitmap); g.DeleteDC(dc)


if __name__ == "__main__":
    main()
