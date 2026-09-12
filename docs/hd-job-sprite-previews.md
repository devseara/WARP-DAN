# HD Job Sprite Previews — native ACT rendering

Updated: 2026-09-12. Target: **2025-07-16 Ragexe, 32-bit x86**.

Select **Fix HD Job Sprite Previews (Alt+Q / Alt+S)**, implemented by
`Scripts/Patches/NativeActJobPreviews.qjs` (local patch ID 385).
The native Equipment and Skill Tree blits ignore ACT layer scaling. This patch
applies existing scale, mirror, rotation and layer tint while drawing into the
windows' persistent native surfaces. A 2x SPR with ACT scale 0.5 therefore
retains its intended size in these previews as well as the world.

The patch uses existing SPR/ACT paths, palette resolution, head offsets and
frame selection. Applying the self-contained QJS needs no Python, compiler,
generated preview pack or runtime DLL. Supply matching world SPR/ACT resources
through the client's existing archive chain. Camera zoom is not a UI transform;
incorrect source ACT scales remain incorrect.

## Replacement and PR #70

[PR #70](https://github.com/CrazyBebop/WARP0716/pull/70), head
`d2dce84e7a04ada47f865d788769fdb78ea165c8`, contains the cleaned upstream
version. Its embedded machine-code payload, relocation list and used bridge
offsets match this checkout exactly. Local source formatting and test-export
metadata differ. The local QJS also retains the verified ClanBodySkins v11
resource-wrapper bypass and optional patch-order coordination; upstream accepts
only the stock loader layout.

`HDJobSpritePreviews` (old local ID 384) has been retired together with its
registration, generated-pack runtime, builder and dedicated runtime/WARP tests.
Replace that name with `NativeActJobPreviews` in saved external profiles and
reapply from the original client. ID 384 remains unused. Checked-in profiles
do not select the retired patch.

The native patch does not require `Assets/HDJobUI` or `data/sprite/hd_job_ui`.
Existing generated assets and historical fixture outputs are retained locally.
`tools/hd_job_ui_assets.py`, `tools/package_hd_job_ui_grf.py`, and their asset
tests remain because the native live-fixture builder reuses their SPR/ACT
parsers and GRF writer. They do not install the retired preview patch.
Earlier generated-pack records remain in Git history and
`docs/evidence/hd-job-ui/`. That stopped PR effort was separate from the
now-open native renderer PR #70.

## Maintained source and verification

The runtime source is `tools/native/native_act_job_ui.cpp`; its WARP template
is `tools/native/native_act_job_ui.qjs.in`. The generated QJS embeds static
x86 code, not sprite pixels. QJS and hashed runtime source have explicit CRLF
checkout rules. Intermediate native EXEs remain in `Outputs`.

Use Python 3.10+ and `tools/requirements-native-act-job-ui.txt`. The local
builder defaults to MSVC 14.51.36231's x86 compiler; pass `--compiler` for
another x86 `cl.exe` with `link.exe` alongside it. Other compiler versions
require regeneration and verification. The local reference client is
`2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe`,
SHA-256 `ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.
The builder requires that exact input before recording native byte checks.

```powershell
python tools/build_native_act_job_ui.py
python tools/build_native_act_job_ui.py --check
python tools/verify_native_act_job_ui.py
python tools/verify_native_act_job_ui_warp.py
```

The native test runs seven x86 cases: original-blitter pixel comparison,
scaling/mirror/rotation/clipping, atlas/invalid inputs, persistent surfaces,
both bridge ABIs and native delegation. The WARP test runs standalone, both
orders with `ReduceExpensiveUIRender`, changed-renderer/resource-loader
rejection, invalid-relocation rejection and safe reapplication. Optional local
integration checks add the v11 fixture and both ClanBodySkins patch orders:

```powershell
python tools/verify_native_act_job_ui_warp.py --clan-client path/to/clan-skins-v11-check.exe --clan-patch
```

`--clan-patch` requires the separately maintained local ClanBodySkins patch;
standalone verification does not. `tools/build_native_act_job_ui_test.py` and
`tools/native_act_test_archives.py` retain the local live-fixture packaging
workflow described below.

The [original native evidence](evidence/native-act-job-ui.json) records the
pre-retirement run, including now-retired mutual-exclusion cases. It remains
historical evidence. The male Monk live screenshot confirms HD world, standing
Equipment and seated Skill Tree rendering. Wider job/sex/direction/animation
and original-layout live coverage remains pending.

## v1 live failures and v2 correction

The user reported missing HD artwork on Monk, disappearance of the Alt+Q
avatar while dragging, and a missing Alt+S avatar. See the
[user screenshot](evidence/native-act-ui-v1-failures.png). V1's embedded archive list
was correct, but its eight-entry GRF only mapped Swordman. There were no Monk
entries. The confirmed game-folder Monk body ACTs have scale 1.0; the user
authorized mapping the existing HD clan artwork onto Monk for this test.

The v1 rendering path was wrong for these windows: native `0x00A1B7C0` queued
GPU geometry on `UIWindow+0x5C`, while the normal UI blit writes the persistent
CPU `CSurface` at `UIWindow+0x24`. Geometry-only tests did not cover that
compositing/lifetime contract. V1 is not an accepted working renderer.

V2 rasterizes the current native texture into that same CSurface. It sets the
native dirty byte and leaves window composition, movement, caching, fade and
reopening to the client. No screen-space geometry or resource pointers persist
in the bridge. Native palette resolution and texture lock/unlock ownership are
preserved; loaded ACT/SPR objects are read-only.

The rasterizer uses the profiled A1R5G5B5 and A4R4G4B4 texture formats, native
component expansion and DIB storage conventions, premultiplied bilinear
sampling, separate ACT X/Y scales, mirror, rotation and RGBA layer tint.
Sampling is clamped within the current image's atlas rectangle. Destination
writes are clipped to the actual surface bounds. No preview assets or resized
sprite resources are generated at runtime.

## Hook and resource boundaries

- Alt+Q's mode argument at `0x008B3557` selects the native scaled anchor path.
  The call at `0x007ACEF9` is routed to a surface wrapper only for Equipment
  vtable `0x0103223C`; other callers delegate to the native implementation.
  Existing job-specific scale behavior remains in force.
- The Skill Tree bridge at `0x00974E9E` uses the original frame's layer, image,
  resolved texture, atlas rectangle and head offsets. It preserves GPRs,
  flags, the caller stack, seated action/frame selection and component order.
- `CSurface` is the profiled 44-byte object with vtable `0x00FD5CE4`, width /
  height at `+4/+8`, CPU pixels at `+0x18` and dirty byte at `+0x1C`.
- Current ClanBodySkins application orders use CACHE and ReloadPatch to remove
  recorded preview routing. Exact v11 inputs restore only the nine profiled UI
  loader calls; clan world selection and complete-pair fallback remain.
- WARP GetHex sees original bytes rather than another patch's pending writes.
  The payload is relocated in memory and written once, which also avoids the
  overlapping-write failure observed when reapplying WARP's own output.

Maintained source is `tools/native/native_act_job_ui.cpp`; installation uses
`tools/native/native_act_job_ui.qjs.in` and generated
`Scripts/Patches/NativeActJobPreviews.qjs`. Build/check with
`tools/build_native_act_job_ui.py [--check]`. The reference original SHA-256 is
`ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.
No runtime DLL, CRT import, recv hook or world-renderer patch is installed.

## Verification and test release

`tools/verify_native_act_job_ui.py` now checks surface pixels and lifecycle,
not only queued geometry: unit-scale output against the real native blitter
for both formats, arbitrary scaling/mirror/rotation/clipping, pixel persistence
when moving without repainting, atlas cropping, invalid inputs, Equipment
thiscall/palette resolution, and the actual mid-function Skill Tree bridge.
The original run passed seven x86 tests and eight WARP cases, including
mutual-exclusion tests for the since-retired generated-pack implementation.
See the [historical verification evidence](evidence/native-act-job-ui.json).
The maintained WARP cases are listed above. These tests do not establish
additional live visual acceptance.

The current v3 fixture is built/deployed by `tools/build_native_act_job_ui_test.py`
into `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes`:

- `native-act-hd-v3.exe`
- `native_act_hd_v3.grf`
- `native-act-hd-v3-release.json` and `native-act-hd-v3-README.txt`

V3 retains the v2 renderer fix and removes the temporary Monk-to-Swordman
artwork substitution after the user reported the wrong job appearance.
The pack has eight SPR/ACT entries restricted to clan/ordinary Swordman.
At initial v3 packaging, Monk and Monk-high resolved their original resources
from the existing archive chain. The user then added a real 2x male Monk-high
pair to this GRF: `몽크_h_남.spr/.act`, ACT scale 0.5. Normal Monk requests
`몽크_남`, so matching normal-name aliases were added for both files. All ten
existing entries and every compressed sprite payload were preserved; the GRF
now has twelve entries. Male Monk uses the supplied HD Monk artwork. Female
Monk remains on its original assets. See the [alias receipt](evidence/native-act-hd-monk-alias.json).

The earlier v2 fixture had sixteen entries with explicitly requested test
aliases from clan Swordman artwork onto Monk. Reproducing that diagnostic now
requires `--monk-clan-test-alias`; the default preserves Monk appearance.

The v3 EXE embeds its own GRF first, followed by the original eight archives,
without either earlier test GRF. DATA.INI is unchanged. The AddPak sequence
and final EXE writes are verified by the packaging workflow. The later male
Monk aliases require a client restart but no EXE rebuild or DATA.INI change. Earlier releases remain separately named.

**Male Monk live case confirmed.** The user supplied a [working screenshot](evidence/native-act-ui-male-monk-confirmed.png) showing HD world rendering, standing Alt+Q and seated Alt+S. Wider live acceptance remains pending; drag Alt+Q, move both windows, verify Alt+S standing /
seated registration and head alignment, then test closing/reopening, relevant
directions/frames, both sexes, palettes, special job scales and relog.
