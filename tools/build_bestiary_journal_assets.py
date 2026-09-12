"""Extract the approved journal's UI chrome and installed GRF minimaps.

This builds native UI assets, not a new concept image. Crop coordinates refer
to the approved 1536x1024 artwork. Map pixels come from the active DATA.INI
priority order (including loose data overrides); no illustrative maps.
"""
from pathlib import Path
import argparse, configparser, hashlib, io, json, re
from PIL import Image
from dual_weapon_formats.grf_reader import GrfFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game', type=Path, required=True)
    args = ap.parse_args()
    out = ROOT / 'Images/BestiaryUI/journal'
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'Images/BestiaryUI/source/journal-reference.png'
    # Decorative artwork is already baked into the approved skin.
    records = []

    property_root = ROOT / 'Images/BestiaryUI/source/icons'
    for kind in ['element','race','size']:
        for path in sorted((property_root/kind).glob('icon_*.png')):
            name=kind+'_'+path.stem[5:]+'.bmp'
            source_icon=Image.open(path).convert('RGBA')
            source_icon.thumbnail((14,14),Image.Resampling.NEAREST)
            icon=Image.new('RGB',(14,14),(255,0,255))
            icon.paste(source_icon,((14-source_icon.width)//2,(14-source_icon.height)//2),source_icon.getchannel("A").point(lambda a:255 if a>=128 else 0))
            icon.save(out/name)
            records.append({'file':name,'source':str(path.relative_to(ROOT)),'size':[14,14]})

    config = configparser.ConfigParser()
    config.read(args.game / 'DATA.INI', encoding='utf-8-sig')
    filenames = [v for k, v in sorted(config['Data'].items(), key=lambda kv: int(kv[0]))]
    maps = {}
    prefix = 'data/texture/유저인터페이스/map/'
    for filename in filenames:
        path = args.game / filename
        if not path.is_file():
            continue
        grf = GrfFile(path)
        for key in sorted(grf.entries):
            if not key.startswith(prefix) or not key.endswith('.bmp'):
                continue
            stem = key[len(prefix):-4]
            if not re.fullmatch(r'[a-z0-9_@-]{1,23}', stem) or stem in maps:
                continue
            loose = args.game / key
            raw = loose.read_bytes() if loose.is_file() else grf.read(key)
            if raw is None:
                continue
            im = Image.open(io.BytesIO(raw)).convert('RGB')
            # Native BMP loading treats RGB565 magenta (F81F) as transparent.
            # Flatten every source pixel in that quantization bucket before resize.
            pixels = list(im.getdata())
            im.putdata([(244, 248, 252) if r >= 248 and g < 4 and b >= 248 else (r, g, b)
                        for r, g, b in pixels])
            original_size = im.size
            im.thumbnail((94, 43), Image.Resampling.NEAREST)
            thumb = Image.new('RGB', (94, 43), '#f4f8fc')
            thumb.paste(im, ((94-im.width)//2, (43-im.height)//2))
            leaf = 'map_' + stem + '.bmp'
            thumb.save(out / leaf)
            maps[stem] = {'file': leaf, 'source': str(loose) if loose.is_file() else filename + ':' + key,
                          'sha256': hashlib.sha256(raw).hexdigest(), 'source_size': original_size}
        grf.close()
    # WARP deploys the exact manifest; no recursive or guessed copy API needed.
    skin_source = ROOT / 'Images/BestiaryUI/source/journal-skin.png'
    Image.open(skin_source).convert('RGB').crop((20,12,1516,996)).resize((760,500),Image.Resampling.LANCZOS).save(out/'skin.bmp')
    records.append({'file':'skin.bmp','source':str(skin_source.relative_to(ROOT)),'size':[760,500]})
    files = sorted([r['file'] for r in records] + [m['file'] for m in maps.values()])
    manifest = {'reference': str(source.relative_to(ROOT)), 'reference_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'chrome': records, 'maps': maps, 'files': files}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Extracted {len(maps)} real minimaps and {len(records)} UI chrome crops.')


if __name__ == '__main__':
    main()
