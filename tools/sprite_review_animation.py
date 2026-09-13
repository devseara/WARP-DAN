"""Stable-color GIF previews and lossless APNG frame verification."""
import numpy as np
from PIL import Image


def save_review_animation(frames,path,duration,apng=None):
    assert frames and all(f.mode=='RGB' and f.size==frames[0].size for f in frames)
    samples=[]
    for i in np.linspace(0,len(frames)-1,min(16,len(frames)),dtype=int):
        small=frames[int(i)].copy();small.thumbnail((400,200));samples.append(small)
    atlas=Image.new('RGB',(max(f.width for f in samples),sum(f.height for f in samples)))
    y=0
    for f in samples:atlas.paste(f,(0,y));y+=f.height
    palette=atlas.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    indexed[0].save(path,save_all=True,append_images=indexed[1:],duration=duration,
        loop=0,disposal=2,optimize=False)
    if apng:
        frames[0].save(apng,save_all=True,append_images=frames[1:],duration=duration,
            loop=0,disposal=0,blend=0)
        with Image.open(apng) as decoded:
            assert decoded.n_frames==len(frames)
            for i,f in enumerate(frames):
                decoded.seek(i)
                assert np.array_equal(np.asarray(decoded.convert('RGB')),np.asarray(f))
