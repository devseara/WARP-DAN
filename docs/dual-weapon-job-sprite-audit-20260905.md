# Job-sprite placement audit — 2026-09-05

Current implementation: [old attack motion, held pixel-edge contacts, anatomical slot mapping and installed bytes](dual-weapon-edge-contacts-20260905.md). The following acceptance records describe earlier builds; they do not accept the current build's live appearance.

The earlier experiments do **not** rule out a compositor attached to the job
body. They rule out narrower models: one shared pair-guide origin with a fixed
landmark per weapon view, or a single torso-relative pivot with shared reach.
No per-hand body-socket implementation was tested or deployed by that work.
This audit changes the historical analysis tool and documentation only.

## Corrected fitting bug

`tools/dual_hilt_fit_validate.py` fitted `R * H = +CSV_delta`, but validated
`T = socket - R * H`, hence `T - socket = -R * H`. Calibration and validation
used opposite signs. The fit now targets `-CSV_delta`, retaining the stated
socket-contact equation.

| Same 128 pair-28 attack cells | Mean residual | Maximum residual |
| --- | ---: | ---: |
| Original inconsistent signs, reproduced before editing | 37.552529 px | 106.228007 px |
| Corrected consistent signs | 31.907667 px | 107.054723 px |

The simplified model still fails. Its old numerical result must not be quoted
as a valid fit. Mirror agrees in 128/128 cells; raw ACT angle agrees in 116/128.
The regenerated `tools/_stage1_validation_report.json` records all cells and
source hashes. A synthetic 128-cell regression constructs known landmarks with
independent trigonometry, includes unseen rotations and reflections, and passes
with the fix. Reintroducing only the original sign in memory makes it fail at
`7.0 != -7.0` (14 px), demonstrating that the test catches the defect.

```powershell
.\.venv\Scripts\python.exe -B tools/test_dual_hilt_fit_validate.py
.\.venv\Scripts\python.exe -B tools/dual_hilt_fit_validate.py
```

## What the prior data actually represents

`dual_socket_extract.py` selects accepted ACT **layer 1, pair_guide**. It does
not extract either anatomical hand and never reads `ActFrame.anchors`. Its
CSV contains one shared origin per direction/frame. Weapon-center deltas
relative to that origin are not hand-socket positions relative to the body.

A rigid rotation preserves a fixed vector's radius, so the observed changing
pair-guide-relative radius genuinely rejects that precise fixed-vector model.
It does not reject separate hand sockets, direction-dependent projection,
per-frame sockets, or grips keyed to the actual selected SPR image. The test
also never measures a hilt-to-tip vector; the former report incorrectly implied
that it did. The report now states this limit.

`fit_pivot_offset.py` fits one offset from body_guide and minimizes variance of
weapon-center distance across directions. A poor fit does not prove that the
hands cannot be attached to the body: the objective assumes a shared radius
across differently drawn directions, and it supplies no independently measured
hand locations. The previous translation-model report is retained as historical
evidence; its copied 37.55/106.2 figures are superseded here.

## Native body ACT evidence

Read directly from the installed client's `spritedata.grf`, using the checked-in
GRF and ACT readers:

| Asset under `data/sprite/인간족/몸통/` | Actions / frames | Anchors per frame |
| --- | ---: | ---: |
| `여/어세신_여.act` | 104 / 456 | exactly 1 in all frames |
| `여/어쌔신크로스_여.act` | 104 / 448 | exactly 1 in all frames |

For female Assassin Cross, action 32 frame 0 has body layer
`(x=1,y=-23,sprite=54)` and anchor `(0,-52,0)`. Action 80 has nine frames and
action 88 eight frames. The existing single anchor does not supply two independent
hand sockets. Its native semantic role remains unverified by this audit; these
are archive records, not a claim about the live actor's resolved body pointer.

Reproduce the archive inspection from the repository root:

```powershell
@'
import sys, hashlib, collections
from pathlib import Path
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "tools/dual_weapon_formats")
from grf_reader import GrfFile
from act_reader import parse_act
client = Path(r"D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes")
grf = GrfFile(client / "spritedata.grf")
for name in ("어세신", "어쌔신크로스"):
    key = "data/sprite/인간족/몸통/여/" + name + "_여.act"
    raw = grf.read(key)
    actions = parse_act(raw)["actions"]
    counts = collections.Counter(len(f.anchors) for a in actions for f in a.frames)
    print(key, hashlib.sha256(raw).hexdigest(), len(actions), dict(counts))
    for i in (32, 80, 88):
        print(i, len(actions[i].frames), actions[i].frames[0].layers,
              actions[i].frames[0].anchors)
grf.close()
'@ | .\.venv\Scripts\python.exe -B -
```

## Viable alternatives and prerequisites

1. **Body sockets plus weapon grips.** Author or measure each physical hand's
   socket once per body resource/gender/action/direction/frame. Key the weapon
   grip and blade axis to the selected SPR image and its resource fingerprint,
   rather than assuming one point for all images of a view ID. In a verified
   actor-local coordinate system, place the weapon center at
   `hand_socket - weapon_transform * image_local_grip`, then apply the native
   actor-to-screen transform. Preserve per-cell visibility, source action/frame,
   palette, and front/back ordering. This can reduce per-pair authoring; it is
   an untested architecture, not an automatic recovery of missing coordinates.
2. **Reuse the native ACT producer.** Emit two isolated weapon layers from the
   current actor's resources before final screen-packet construction. This can
   let native code own projection and sprite geometry. It requires a profiled
   producer hook, explicit lifetime/ownership, and verified render ordering.
3. **Generate hand-specific ACT assets offline.** Bake validated transforms into
   resource variants and let the native renderer draw them. This trades more
   assets and resolver metadata for less custom geometry code. Exporting a
   combined ACT is not proof of live placement until actual native draw output
   matches the reference.

For all three, first reproduce the accepted sword/dagger result using original
job and weapon assets, including image selection and hilt contact, then compare
all directions and frames. Off-hand-only action 80 and dual action 88 need an
explicit timeline mapping; matching their numeric frame indices is insufficient.
An offline body+weapon preview is useful, but must use a verified native
transform contract and remain distinct from in-game acceptance.

## Source hashes (SHA-256)

| Input | SHA-256 |
| --- | --- |
| Accepted pair-28 guide ACT | `6126c72516f1cb165439c79e251ac265480ea0e82e832a42679f1b302e562d67` |
| Extracted pair-guide socket CSV | `e4586e462678f9c0775966604496ea20cf4fffa59cdf8f989c01bf5b330d608a` |
| Accepted pair-28 pose CSV | `7329786d42a9fbcaa9c0975251349702b434f6251c9023b655469c3b229cc898` |
| Female Assassin body ACT | `24ac05f9111dbc8b4abd388dfe8e9b651a8d1951bff2e9d08d7001056cbdcd71` |
| Female Assassin Cross body ACT | `78feed0bafe571dbb389fad5f8868f67313e411096ef56a190522744899b3781` |
| Corrected hilt validator | `79c68b0d007be5d2d88609bab2c54eeea6ff61768cdc2bfa87c860e5bff8c190` |
| Signed-transform regression | `fd743119312fe7fbff67202bc577c15db0a23e9d3906f0117ef85c7430ebb99f` |
| Regenerated stage-1 report | `5e6fb775266821e9346e6338fa12ae7ab3532e21a3cea9966436affa4e423aac` |
