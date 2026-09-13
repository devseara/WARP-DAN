"""Register every directional master with one uniform scale per job and sex.

Native sprite extents include pose-dependent hands, boots and clothing. They
are placement guides, not independent width/height targets for new artwork.
"""
import math

import numpy as np
from PIL import Image


def reference_scale(front_art, native_collar_y, native_foot_y):
    bounds = front_art.getchannel('A').point(lambda p: 255 if p > 32 else 0).getbbox()
    assert bounds and native_foot_y > native_collar_y
    scale = 4 * (native_foot_y - native_collar_y) / (bounds[3] - bounds[1])
    return scale, dict(reference_alpha_box=list(bounds),
                      reference_native_collar_y=native_collar_y,
                      reference_native_foot_y=native_foot_y,
                      uniform_scale_4x=scale)


def register_master(art, scale, collar_center_x, foot_y, mirror=False, upper_body=None):
    """Scale around the source origin, then translate its collar and sole.

    Canvas rounding must not create a different X or Y magnification. An
    explicit equal-axis affine transform preserves the exact common scale;
    only the transparent output canvas is rounded to integer dimensions.
    """
    alpha = np.asarray(art)[:, :, 3]
    bounds = art.getchannel('A').point(lambda p: 255 if p > 32 else 0).getbbox()
    assert bounds
    _, xx = np.where(alpha[:max(6, round(art.height * .055))] > 64)
    source_collar_x = (float(xx.min()) + float(xx.max())) / 2
    size = (math.ceil(art.width * scale), math.ceil(art.height * scale))
    inverse = (1 / scale, 0, 0, 0, 1 / scale, 0)
    result = art.convert('RGBa').transform(size, Image.Transform.AFFINE, inverse,
        resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0)).convert('RGBA')
    collar_x4 = source_collar_x * scale
    original_collar_x4 = result.width - 1 - collar_x4 if mirror else collar_x4
    base_left = round(collar_center_x * 4 - original_collar_x4)
    padding = 0
    upper_body_proof = None
    if upper_body is not None:
        from swordman_upper_body import widen_registered
        result, padding, upper_body_proof = widen_registered(result, collar_x4, scale, bounds, upper_body)
        collar_x4 += padding
        size = result.size
    if mirror:
        result = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        collar_x4 = result.width - 1 - collar_x4
    # Preserve the prior placement exactly. Re-rounding after an integer
    # padding shift can change half-pixel ties through round-to-even.
    left = base_left - padding
    top = round(foot_y * 4 - bounds[3] * scale)
    collar_error = left + collar_x4 - collar_center_x * 4
    foot_error = top + bounds[3] * scale - foot_y * 4
    assert abs(collar_error) <= .5 and abs(foot_error) <= .5
    return result, left, top, dict(
        source_size=list(art.size), source_alpha_box=list(bounds), post_scale_mirror=mirror,
        scale_x_4x=scale, scale_y_4x=scale, inverse_affine=list(inverse),
        collar_registration_error_4x=collar_error,
        sole_registration_error_4x=foot_error,
        source_collar_x=source_collar_x, native_sole_y=foot_y,
        registered_size=list(size), upper_body_adjustment=upper_body_proof,
        body_scale_box_4x=[left, top, left + size[0], top + size[1]])
