"""Model the zoom-dependent warp of 2025-07-16 sprite quads (see
docs/sprite-quad-depth.md). Without UniformSpriteRHW the residual is nonzero;
with uniform RHW the mapping is affine and the residual is exactly 0."""
# Client: vertex depth z_v = z + 0.16*(Y - sy)  (0xC4102B), rhw = 1/z_v,
# S = hpc/(7 z) (0x553E80), hpc = (h/2)/tan(7.5 deg) (0x556790).
import math
def disp(y, top, bot, S, hpc):
    """screen displacement (px, +down) of texel whose affine position is sprite-y"""
    z = hpc / (7*S)
    zt = z + 0.16*S*top; zb = z + 0.16*S*bot
    wt, wb = 1/zt, 1/zb
    a = (y - top)/(bot - top)
    t = a*wt/(a*wt + (1-a)*wb)
    return (t - a)*(bot - top)*S
body = (-86, 22)      # V16 A0 body quad, sprite px (2x canvas 216 tall at 0.5)
head = (-92, -55)     # typical native head quad around the -57 attach point
join = -57


def main():
    for h in (768, 1080):
        hpc = (h/2)/math.tan(math.radians(7.5))
        print(f'screen height {h}: hpc={hpc:.0f}')
        for S in (1.0, 1.25, 1.5, 1.75, 2.0):
            Sc = 1.69*S
            rel_n = disp(join, *body, S, hpc) - disp(join, *head, S, hpc)
            rel_c = disp(join, *body, Sc, hpc) - disp(join, *head, Sc, hpc)
            resid = rel_c - 1.69*rel_n
            print(f'  S={S:4.2f}->{Sc:4.2f}  z={hpc/(7*S):6.1f}->{hpc/(7*Sc):6.1f}  '
                  f'collar-vs-head normal={rel_n:+5.1f}px close={rel_c:+5.1f}px  '
                  f'residual after torso fit={resid:+5.1f} close px')


if __name__ == '__main__':
    main()
