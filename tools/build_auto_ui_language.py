"""Compile Auto UI translations to exact UTF-8 and native legacy byte catalogs."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "Inputs/AutoUI"
LANGUAGES = json.loads((DIRECTORY / "languages.json").read_text(encoding="ascii"))


def source_labels():
    labels = set()
    for name in ("AutoCombatUI", "AutoSupportUI"):
        source = (ROOT / f"Scripts/Patches/{name}.qjs").read_text(encoding="utf-8")
        block = source[source.index("\tconst tabLabels ="):
                       source.index("\tconst controllerPositionRegistry =")]
        labels.update(json.loads(literal) for literal in
                      re.findall(r'"(?:[^"\\]|\\.)*"', block))
    return labels


def compile_catalog(spec, labels):
    catalog = json.loads((DIRECTORY / (spec["locale"] + ".json")).read_text(encoding="utf-8"))
    if labels != catalog.keys():
        raise ValueError(f"{spec['locale']}: missing={labels - catalog.keys()}, "
                         f"unused={catalog.keys() - labels}")
    compiled = []
    for english, translated in catalog.items():
        assert isinstance(translated, str) and bool(translated) == bool(english), english
        assert re.findall(r"%(?:\.\d+)?[su%]", english) == re.findall(r"%(?:\.\d+)?[su%]", translated), english
        assert not re.search(r"<[/A-Z]|\{\d*\}|\\n", translated), "Unadapted CSV markup: " + english
        encodings = {}
        for key, codec in ((spec["codec"], spec["codec"]), ("utf8", "utf-8")):
            raw = translated.encode(codec, errors="strict")
            assert raw.decode(codec) == translated and b"\0" not in raw, english
            encodings[key] = list(raw)
        compiled.append("  " + json.dumps(english) + ": " + json.dumps(encodings))
    return ("{\n" + ",\n".join(compiled) + "\n}\n").encode("ascii")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    labels = source_labels()
    assert list(LANGUAGES)[0] == "English" and len(LANGUAGES) == 8
    assert len({spec["locale"] for spec in LANGUAGES.values()}) == len(LANGUAGES)
    for name, spec in LANGUAGES.items():
        if name == "English":
            continue
        data = compile_catalog(spec, labels)
        output = DIRECTORY / (spec["locale"] + ".bytes.json")
        if args.check:
            assert output.read_text(encoding="ascii").encode("ascii") == data, f"Rebuild {output.name}"
        else:
            output.write_bytes(data)
        print(f"PASS {name}: {len(labels)} labels, UTF-8/{spec['codePage']} round trips, format arguments")
