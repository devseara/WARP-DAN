"""Canonical Bestiary texture paths, matching the native QJS interface prefix."""
from pathlib import Path

UI_TEXTURE_DIRECTORY=bytes.fromhex('C0 AF C0 FA C0 CE C5 CD C6 E4 C0 CC BD BA').decode('latin-1')
UI_TEXTURE_KOREAN=UI_TEXTURE_DIRECTORY.encode('latin-1').decode('cp949')
BESTIARY_TEXTURE_ROOT=Path('data/texture')/UI_TEXTURE_DIRECTORY/'bestiary'

def bestiary_texture_root(manifest=None):
    if manifest is None:return BESTIARY_TEXTURE_ROOT
    # Keep old verification/build manifests readable while new builds publish
    # their exact native resource root explicitly.
    return Path('data/texture')/manifest.get('assetRoot','bestiary').replace('\\','/')
