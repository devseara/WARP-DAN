# Status UI redesign contract

Target client: 2025-07-16 (`Exe.BuildDate === 20250716`).

## Ownership and compatibility

`RedesignedStatusWindow` skins the native `UIStatusWnd` and adds independent
client-side pending-allocation layers for the six Status and six Trait stats. The window remains
fixed at `280x253` and switches between the supplied Status and Trait
backgrounds through the native mode byte at `UIStatusWnd+0xFC`.
The profiled native constructor does not initialize that byte. The redesign's
OnCreate control builder explicitly resets it to `0` before constructing the
page controls, so every newly allocated Alt+A window starts on Status instead
of inheriting Trait mode from a freed instance across close/reopen cycles.

The inactive page tab remains the native control at `UIStatusWnd+0xF8` with
UUID `0x226`. `DisableTraitStatusButton` writes the redesign's shared
runtime flag when both patches are selected, so the redesign consumes `0x226`
before the native page toggle. `Tables/Patch.yml` registers
`RedesignedStatusWindow` immediately before `DisableTraitStatusButton`. When
both are selected, that application order is required: the redesign creates
the shared gate first, then Disable Trait sets it through the emitted bridge.
The generated clients verify gate 0 for normal and gate 1 for disabled. WARP
can compose the legacy Disable Trait patch in a separate pass, leaving its final
EB 0A/NOP marker at 0x008CBA61 while DIFF allocation addresses differ between
passes. Both the UUID dispatcher and the native message-0x22 child
synchronization at 0x008CBA42 therefore honor either the shared flag or that
final marker. The redesign preserves the stock SETNE result when Trait is
enabled, but forces the result to 0 before the native store when disabled.
This prevents repeated Alt+A hide/show cycles from reopening Trait.
HideTraitStatusButton is incompatible because it removes or redirects the
native control reused by this redesign.

The supplied assets are copied to:

`data/texture/<client UI prefix>/uirenewal/statusui`

Runtime assets:

- `bg_status_body.bmp` and `bg_trait_body.bmp`: opaque 24-bit selected-page
  bodies at the stock `(0,17)` origin. They are exact `280x236` crops of
  the supplied images with the first 17-pixel title strip removed. The native
  title bar remains the sole title owner. BMP is intentional: loading a PNG
  on this legacy parent surface enters the alpha-composited path and washes
  out the native text rendered above it.
- `menu_stats.png` and `menu_trait.png`: selected 33-pixel rail at
  `(0,17)`.
- `tab_*_out.png` and `tab_*_press.png`: inactive native page-control
  states.
- `p.png`: native increment-control sprite aligned at
  `(188,126+16n)`.
- `m.png`: decrement-control sprite aligned at `(207,126+16n)`.
- `ok_*` and `cancel_*`: out, over, press, and off states loaded into native
  UIButton slots 0 through 3.

The Status plus sprite uses two native fixed-copy constructors. Each copies the
resource string as `16 + 16 + 8 + 4` bytes through four independently encoded
absolute operands. The redesign redirects every chunk for both constructors to
one zero-padded private block; redirecting only the first 16-byte operand
produces a mixed invalid path and leaves the buttons without loaded hit-area
dimensions. The shared `basic_interface\\arw_right.bmp` string remains unchanged
because Alt+S and other native windows also reference it.

The original `bg_status.png` and `bg_trait.png` remain source assets and
are not loaded at runtime. Drawing either full `280x253` image at the stock
body origin duplicates the title bar and shifts all baked art down by 17
pixels.

The supplied `expanded_status` bonus browser is intentionally out of scope.
It requires a new data model and YML-backed category/bonus provider; the native
2025 Status window has no equivalent provider contract.

## Base-stat transaction contract

The six native base-stat increment controls retain UUIDs `0xCD..0xD2` and
children `UIStatusWnd+0xB4..+0xC8`, but their Status-page clicks now
increment six pending counters. Six new decrement controls use UUIDs
`0x7F0..0x7F5`; OK uses `0x7F6`, and Cancel uses `0x7F7`. These
controls are moved offscreen while the Trait page is active. Event dispatch
resolves both the UUID and the exact child pointer, so the controls remain
actionable even if another patch rewrites a button identifier.

The visible row order is Str, Agi, Vit, Int, Dex, Luk. Their native increment
UUIDs are CD, CE, CF, D0, D2, D1, while OK sends the corresponding status
parameter IDs 0D, 0E, 0F, 10, 11, 12. The separate UUID and packet arrays are
intentional: native D1/D2 order is opposite the visible Dex/Luk order.

Plus is accepted only when the projected stat remains at or below the cap for
the server-provided `SP_CLASS` and the sum of all projected costs fits the
current Status Point total. The QJS class table mirrors this server's
`player.conf`: normal and transcendent 99; third, trans-third, extended,
summoner, and fourth 130; baby 80; and baby-third 117. Baby ranges are tested
first, matching `pc_maxparameter()` precedence. Minus removes only a locally
pending point and never lowers a committed stat. Cancel clears all pending
counters. OK emits one native five-byte `0x00BB` packet per nonzero stat in
Str, Agi, Vit, Int, Dex, Luk order. Each packet is `uint16 opcode`, `uint16
statusId`, and `uint8 amount`; construction and transmission use the client's
packet object and send methods at `0x00C14D60` and `0x00C14920`. A queued
counter is cleared only after the native sender object is available.

The original UI-event approach cannot batch stats. The profiled native handler
at `0x00C8837B` rejects a request while `[this+0x2D4]` is nonzero, and the
first accepted request sets that single-flight flag at `0x00C88388`. Calling
the event manager six times in one OK click therefore accepted the first
selected stat and discarded the remainder. Direct native packet submission
avoids that UI-only gate; TCP preserves packet order and the server's normal
`pc_statusup` path remains authoritative for every final cost, stat cap, and
accepted value. If these `player.conf` values change, the embedded QJS cap
table must be updated with them.
Every successful pending mutation calls the native `UIStatusWnd` refresh
vfunc at `+0x98`. Therefore Plus immediately redraws the projected Base,
Req, and remaining Status Points; Minus reverses only uncommitted points;
Cancel restores the committed display; and only OK emits status requests.

The required-point formula is recalculated for every projected point:

- Below 100: `2 + floor((stat - 1) / 10)`.
- At or above 100: `16 + 4 * floor((stat - 100) / 5)`.

The six Trait increment controls retain UUIDs `0x227..0x22C` and native
children `UIStatusWnd+0xE0..+0xF4`. Their clicks are intercepted only while
the Trait page is active and update a second six-counter pending array.
Trait decrement controls use UUIDs `0x800..0x805`; OK uses `0x806`, and
Cancel uses `0x807`. These controls occupy the same asset coordinates as
their Status equivalents and move offscreen on the Status page.

Trait Plus is accepted only while `current + pending < 110` and the total
pending count fits the server-provided `SP_TRAITPOINT`. The cap 110 is the
actual `max_trait_parameter` in `conf/battle/player.conf`; Trait costs are one
point per increment in `pc_need_trait_point()`. Minus only reverses a pending
increment, Cancel clears all six Trait counters, and neither modifies committed
values. Trait OK sends one six-byte `PACKET_CZ_ADVANCED_STATUS_CHANGE` per
nonzero row in Pow, Sta, Wis, Spl, Con, Crt order: `int16 0x0B24`, `int16`
status ID `0xDB..0xE0`, and positive `int16` amount. It uses the same native
packet object and sender as Status. Direct packet submission is required for
mixed-row commits and preserves the server's authoritative validation.

All dynamic Status values and every relocated Trait value use the client native
UIWindow TextOutA renderers at 0x00A25A70 and 0x00A27B50, with native font
selector 1 and height 14 for Base, Bonus, Req, point totals, and derived values.
The fade was not a font or text-color defect: GDI writes correct RGB coverage
into this 32-bit DIB but clears the destination alpha byte for the affected
pixels. Once the PNG rail marks the parent surface alpha-capable, those
zero-alpha glyph pixels blend as transparent. Before every draw, the renderer
measures the formatted string through the native text-width routine at
0x00A21C90. After the draw it restores alpha to 255 over exactly that measured
glyph span plus both antialias edges. Longer Req and point totals therefore
cannot escape a fixed-width repair region or switch to a compact font. This is
the same surface repair model used by ROGlobalZeroExpBar and requires no glyph
assets, process-wide font hook, or duplicate draw pass.The native title label is drawn by the base-window path before the PNG rail,
so it requires a separate alpha repair over `(17,2)..(76,16)` after the rail
draw. This applies on both Status and Trait pages without replacing or
redrawing the title font.

Base and Bonus left anchors are x=85 and x=124, and the required value uses
right edge x=174 at y=126+16n. Base values, requirements, and remaining Status
Points are projected from the pending counters. Status Points use right edge
x=265 and y=151 inside the asset's x=223..269, y=151..166 box. The
four derived rows draw at y=27, 48, 69, and 90 with the same native 14-pixel
font and baseline contract. These positions follow the asset's 21-pixel row
cadence and place each glyph bottom directly above its underline at y=38, 59,
80, and 101. Rows 1 and 2 keep their
three-column right edges. The seven lower values follow the Physical Damage
convention and right-align against their underline endpoints: Hit/Flee/Perfect
Dodge use x=88/206/263 on row 3; Critical Rate/Critical Damage/Attack Speed/
Move Speed use x=88/147/206/263 on row 4. Critical Damage is read from
`CSession::GetStatus(SP_CRATE)`. The profiled `SP_SPEED` update handler at
`0x00CCF08F` bypasses that status map and writes the live raw value to
`0x015FBA94`; Move Speed reads that global and displays
`floor(10000 / rawSpeed)`.

The Trait asset underlines are y=46, 69, and 92. P.Atk/Res, S.Matk/Mres, and
H.Plus/C.Rate draw at y=35, 58, and 81, preserving the same 11-pixel
text-origin-to-underline relationship as Status. Their right edges are the
actual underline endpoints x=141 and x=251. The native selector 1 and 14-pixel
height remain unchanged for derived values. Projected Trait Base and Bonus use
left anchors x=85/x=124; Req uses right edge x=174 at y=126+16n with height 14.
Trait Points use right edge x=265 and y=151, and every projected draw restores
alpha to 255 over the measured glyph span.

## Tooltip contract

The original native base-stat, point, and Trait hover messages are preserved;
only their hit rectangles move. The thirteen redesigned top regions use exact
English labels because the 2025 native table has no entries for all of these
surfaces.

Status base mapping:

| Native tooltip | New origin |
| --- | --- |
| Str, Agi, Vit, Int, Dex, Luk | `(38,126+16n)` |
| Status Point | `(197,133)` |

Status derived mapping:

| Row | Region mapping |
| --- | --- |
| 1 | Physical Damage `43..149`; Physical Defense `151..209`; Vitality Defense `210..269` |
| 2 | Magical Damage `43..149`; Magical Defense `151..209`; Intelligence Defense `210..269` |
| 3 | Hit Rate `43..149`; Flee Rate `161..219`; Perfect Dodge `220..269` |
| 4 | Critical Rate `43..101`; Critical Damage `102..160`; Attack Speed `161..219`; Move Speed `220..269` |

The four rows use y origins 24, 42, 60, and 78. Hit Rate retains the supplied
asset's combined first-two-cell hover region, while its number is right-aligned
at the first underline edge. Row 4 uses four independent hit regions. Critical
Damage is read through the profiled status accessor as `SP_CRATE`. Move Speed
reads the live `SP_SPEED` packet destination at `0x015FBA94` directly and
displays `floor(10000 / rawSpeed)`, matching the client/server speed
representation.

Trait page mapping:

| Native tooltip | New origin |
| --- | --- |
| Pow, Sta, Wis, Spl, Con, Crt | `(38,126+16n)` |
| P.Atk, S.Matk, C.Rate | `(57,32)`, `(57,55)`, `(57,78)` |
| Res, Mres, H.Plus | `(170,32)`, `(170,55)`, `(170,78)` |
| Trait Status Point | `(197,133)` |

The native tab control caption is always assigned an empty string. Its inactive
icon is covered by an Equipment-style mouse-move prologue hook at `0x008BA610`.
The hook preserves the Status receiver and all registers, converts the local
cursor position through `0x00A1EF70`, and invokes the native tooltip manager at
`0x00A753D0` with the same flags and cursor offsets as
`RedesignedEquipmentWindow`: `Trait` on the Status page at
`(0,50)..(33,82)`, and `Stat` on the Trait page at `(0,17)..(33,49)`. The
native control caption remains empty, so the label never appears as click
feedback.
`tab_trait_out.png` is the supplied inactive
rail frame with the missing Trait silhouette reconstructed from
`tab_trait_press.png` using the exact grey Stats-tab palette and continuous
antialias blend; its frame pixels are unchanged.

The base hit-test loop is gated when `UIStatusWnd+0xFC == 1`; otherwise its
relocated rectangles overlap the Trait page and can win before the native
Trait loop. The gate executes after the stock callee-saved register pushes and
message-table initialization, preserving the function's stack contract.

## Reverse-engineering anchors

The 2025-07-16 x86 client exposes `UIStatusWnd` RTTI with vtable
`0x010329D4`. Profiled methods are constructor/on-create `0x008AED10`,
renderer `0x008B66A0`, tooltip hit-test `0x008BA610`, and event dispatcher
`0x008CB7C0`. The native Trait toggle compares event UUID `0x226`. The
redesign detours that dispatcher and checks a shared byte before allowing the
stock toggle case; `DisableTraitStatusButton` sets that byte when the
redesign owns the detour. The same dispatcher resolves native and custom child
pointers, then consumes the Status or Trait UUID set only on its owning page.

The rail renderer hooks immediately after the stock background draw. At that
point ESI still owns the native image manager returned by `0x00A90350`, while
EBX owns `UIStatusWnd*`. The `0x00A8D4A0` image-load call must receive
ECX=ESI; only the following `0x00A1D260` window draw receives ECX=EBX.
Passing the window as the image-loader receiver crashes at `0x00A8D543`
during login/UI construction.

The fourth-job Trait refresh loop at `0x008CB930` is active only when the
advanced-status controls exist. The redesign owns the complete 28-byte native
move block: it loads `[ESI+EDI]`, null-checks the child before loading its
vtable, and only then chooses the hidden or active coordinates. Splitting the
visibility and position paths leaves stale `ECX/EAX` on the Status-page branch;
Meister Alt+A then reaches `call [eax+0x10]` with `ECX == 0` and crashes at
`0x008CB94A`.

Any target-client update must re-profile the vtable, all resource loads,
coordinate-immediate encodings, draw calls, control-move loops, tooltip tables,
the native event-manager call, the message-0x22 child-state gate, and the
0x226 dispatcher gate. A clean WARP
build is a source/static gate, not visual acceptance: Alt+A Status and Trait,
hover-only tab balloons, all stat balloons, per-row mixed Plus projection,
Minus, OK, Cancel, insufficient-point behavior, the 110 Trait cap, server
rejection recovery, and Disable Trait must be exercised in the live client.
