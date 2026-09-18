# Shared VIP crown artwork

`membership_crown.png` is the crown used on all five Apply VIP cards. The compact
main-window level boxes use crown regions from `vip_design.png`. Level zero is
empty; level N shows N crowns (maximum ten). The unused legacy `star_on.png`
is no longer bundled.

Edit the crown in your client's `data/texture/<UI prefix>/vipui` folder. Keep PNG
alpha transparency; do not replace it with a black/checkerboard background. The
client fits the entire image into 28px card icons, and bounds
source dimensions to 4096 pixels. Restart Ragnarok after artwork edits. No WARP
or server rebuild is needed for crown artwork-only changes.

Source: built-in image-generation tool, September 17, 2026. Original transparent
1254x1254 output copied without pixel changes into `Assets/VipUI/membership_crown.png`.
SHA-256: `620fd774907589457aef433639ce99ba7ac0e086f90a393d9bcd1e2471b05a10`.
Private original: `C:/Users/Vysache/.codex/generated_images/01a09e80-12ab-76e1-abed-6087de798997/exec-4594696a-c473-402a-ade9-e1bea505e20b.png`.

## Final generation prompt

Use case: stylized-concept. Asset type: tiny game UI VIP crown icon, transparent
PNG. Primary request: one compact warm champagne-gold three-point crown emblem
for a Ragnarok Online VIP membership card. Front view, simple squat crown with
high central point and lower left/right points, flat trapezoid base, small white
V/check-shaped highlight in center. Match a clean premium membership selector:
pale gold and peach facets, ivory rim highlight, subtle warm shading, not ornate.
Center it by itself on a genuinely transparent background with preserved alpha.
Strong clean silhouette readable at 24x24 pixels. Fill most of a square canvas
with slight padding. No lettering, no cards, no words, no prices, no numbers,
no frame, no unrelated objects, no checkerboard baked into image, no drop shadow
beyond crown.
