# RO Global UI warp/reopen resolution

Last updated: 2026-08-12

Status: accepted in live New UI and Classic UI testing.

## Fixed scope

The accepted patch set fixes:

- RO Global menu slicing after close, hidden warp/teleport, and reopen.
- Missing or misplaced native MENU controls after the same lifecycle.
- Auto Hunt visibility, hit testing, tooltip, and click handling in both themes.
- RO Global status-area launcher placement after map changes.
- Third-job, fourth-job, mounted, baby, and costume Job icons through existing
  original framed class-lineage art at big2 size.
- Classic-only Basic Information minimize/close controls.
- Alt+A Req and point-total font growth and transparent digit fragments.

## Root cause

The menu previously derived parent height from expanded state. There are 25
visible native commands, exactly five complete rows. Auto Hunt was counted as
an optional twenty-sixth command only while expanded, even though Auto Hunt and
the native MENU toggle require a separate bottom control row.

Closing the menu changed the derived row count from six to five. A hidden map
change could then construct a fresh five-row UIMenuIconWnd and backing surface.
Reopening expanded the existing object back to six rows, but the bottom native
controls had already been created or composited against the shorter lifecycle.
This caused the sliced frame and missing button pixels.

The v45 binary trace proved that the draw wrapper remained active and that the
menu, surface, pixels, and native child pointers were valid. The decisive state
change was the five-row/six-row transition, not an invalid pointer, failed
texture load, or theme-specific coordinate.

## Accepted design

The row invariant is:

    rows = ceil(visible native commands / 5) + 1 permanent control row

With 25 native commands, the maximum and accepted live layout is six rows.
Collapse changes control visibility but never parent or surface height.

Auto Hunt is a real native UIButton child owned by UIMenuIconWnd. It uses the
stock UIButton draw entry, native normal/hover/pressed image assignment, native
child-tree composition, and the first slot of the permanent control row. The
native MENU control keeps its final slot. New UI retains a native-compositor
fallback for the MENU normal image; Classic uses the native toggle and no
custom full-panel background.

Layout repair runs after native creation, when visibility changes to shown,
and after MakeWindow returns a menu during map transitions. Each reopen or
post-map repair also refreshes the separate WindowManager rectangle. Native
OnCreate is never replayed on an existing instance.

## Live acceptance

On 2026-08-12 the user confirmed all reported defects fixed after testing both
New UI and Classic UI, including the exact sequence:

1. Open the menu.
2. Close the menu.
3. Warp or teleport while closed.
4. Reopen the menu.
5. Verify the full frame, MENU control, and visible/clickable Auto Hunt button.

Accepted live candidate before source cleanup:

    2025-07-16_Ragexe_175220998_clientinfo_menu_native_autohunt_v47.exe

SHA-256:

    E87B60E8D3BB2E588DD84E90C532A10C317E3FC96CDADB91A2CC2C0A4655160B

## Cleanup regression and correction

The first cleaned rebuild crashed during menu construction at 0x01C3D3CF.
The cleanup had removed MenuZeroStatic.GetWindow under the incorrect assumption
that it was used only by a retired refresh emitter. The active launcher
synchronizer also calls that address four times.

QuickJS converted the undefined rel32 target into zero displacement, producing
CALL to the next instruction at 0x01C3D387. EAX therefore retained an unrelated
value; the synchronizer copied it into ESI as if it were a UIWindow pointer and
faulted while reading ESI+0x1C.

The correction restores:

    GetWindow: 0x00A47B90

The local x86 assembler now rejects non-numeric byte/dword operands and
undefined, non-finite, or non-positive rel32 targets. A missing native address
therefore fails the WARP build instead of silently producing CALL +0.

The corrected PE audit requires all four active launcher lookup calls to target
0x00A47B90 and rejects any self-call to the instruction immediately following
CALL. The corrected cleaned build SHA-256 is:

    755C8015D7BC60033B61AFB732C6C18E05A87F4413AA7A7FC6A6BC58BEB072B0
## Cleanup

After acceptance, the source tree removed:

- The self-recording binary trace writer and decoder.
- Detached event-proxy and transparent/no-op draw experiments.
- The disabled Auto Hunt parent-overlay path.
- Generated duplicate Job icon packs; runtime ID aliases now reuse installed
  original framed icons directly.
- Seventh-row New/Classic backgrounds, which cannot be selected by the
  25-command plus permanent-control-row contract.
- Historical debug screenshots from the investigation phase.

The cleaned source intentionally produces a different executable hash from the
v47 diagnostic-era build because inactive trace and experiment allocations no
longer enter the PE. The accepted runtime ownership and lifecycle invariants are
unchanged.

Any target-client update must re-profile the native menu vtable, MakeWindow
seam, UIButton vtable slots, resource manager calls, and WindowManager update.
Static source/build checks are necessary but live New/Classic close, hidden
warp/teleport, reopen testing remains the final acceptance gate.