"""Controlled upper-armor volume adjustment on the registered Swordman rig.

The same 9% profile is applied to each canonical view before mirroring. Rows
above the collar and below the upper torso retain their exact registered pixels.
This is a local shape parameter; it does not change the shared body scale.
"""
import math

import numpy as np
from PIL import Image


PROFILES = {
    'male': dict(width_gain=.09, start=.015, full_start=.08,
                 full_end=.235, end=.31),
    'female': dict(width_gain=.09, start=.015, full_start=.08,
                   full_end=.205, end=.27),
}


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def gain_at(height_fraction, profile):
    if height_fraction <= profile['start'] or height_fraction >= profile['end']:
        return 1.0
    if height_fraction < profile['full_start']:
        amount = smoothstep((height_fraction-profile['start']) /
                            (profile['full_start']-profile['start']))
    elif height_fraction <= profile['full_end']:
        amount = 1.0
    else:
        amount = 1-smoothstep((height_fraction-profile['full_end']) /
                              (profile['end']-profile['full_end']))
    return 1 + profile['width_gain'] * amount


def widen_registered(image, axis_x, scale, source_alpha_box, sex):
    profile = PROFILES[sex]
    top, bottom = source_alpha_box[1], source_alpha_box[3]
    assert bottom > top
    pad = math.ceil(max(axis_x, image.width-1-axis_x) * profile['width_gain']) + 2
    result = Image.new('RGBA', (image.width+pad*2, image.height))
    result.paste(image, (pad,0))
    changed_rows = []
    row_scales = []
    for y in range(image.height):
        fraction = ((y+.5)/scale-top)/(bottom-top)
        stretch = gain_at(fraction, profile)
        row_scales.append(stretch)
        if stretch == 1:
            continue
        row = image.crop((0,y,image.width,y+1)).convert('RGBa')
        # Pillow affine coordinates refer to pixel centers. Preserve the
        # collar/spine axis and all vertical coordinates while expanding X.
        offset = (axis_x+.5)*(1-1/stretch)-pad/stretch
        # Linear interpolation is bounded by the input values. It cannot
        # turn a faint edge into a new opaque speck through cubic overshoot.
        row = row.transform((result.width,1), Image.Transform.AFFINE,
            (1/stretch,0,offset,0,1,0), resample=Image.Resampling.BILINEAR,
            fillcolor=(0,0,0,0)).convert('RGBA')
        result.paste(row,(0,y))
        changed_rows.append(y)
    assert changed_rows and max(row_scales) == 1 + profile['width_gain']
    before = np.asarray(image)
    after = np.asarray(result)
    unchanged = np.asarray(row_scales) == 1
    assert np.array_equal(after[unchanged,pad:pad+image.width],before[unchanged])
    assert np.all(after[unchanged,:pad]==0) and np.all(after[unchanged,pad+image.width:]==0)
    assert result.height == image.height
    bounds = result.getchannel('A').getbbox()
    assert bounds and bounds[0]>0 and bounds[2]<result.width
    return result, pad, dict(
        version=3,sex=sex,profile=dict(profile),peak_width_gain=profile['width_gain'],
        axis_x_4x=axis_x,canvas_padding_4x=pad,
        modified_rows_4x=[min(changed_rows),max(changed_rows)+1],
        unchanged_lower_from_row_4x=max(changed_rows)+1,
        original_registered_size=list(image.size),height_unchanged=True,
        collar_axis_unchanged=True,unmodified_rows_pixel_identical=True)
