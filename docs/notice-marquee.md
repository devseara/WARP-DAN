# Original announcements with item icons

Updated September 17, 2026 at the user's request: **no marquee, Notice label,
custom dark bar or replacement queue**. The format is simply the item image
immediately followed by its name, within the original announcement text.

The WARP title is **Original Announcements with Item Icons**. The internal
`NoticeMarquee` name and patch ID 10007 remain only for saved-profile compatibility.
Restart an already-open WARP to reload the revised patch. Target: 2025-07-16 Ragexe.

## Behavior and boundaries

- Native broadcast balloon position, background, border, colors, timer, message
  limit and stock insertion remain intact. Plain broadcasts use native routines.
- Tags `^i[909]Jellopy`, `^i[1201,0]Dagger`, and `^i[1201,1]Knife` render an 18px
  item image in a 20px slot directly before the name. Item identity is numeric;
  no display-name guessing. Missing artwork retains the name and its spacing.
- The icon and text are vertically centered within each line. Measurement and
  line height account for icons, retaining the stock four-pixel line gaps.
- The tagged 009A wrapping path keeps complete icon tags and native locale
  character boundaries together. Untagged wrapping is unchanged. Native vector
  ownership is retained; no global queue or per-frame allocation is introduced.
- Only balloon call sites `7890DE`, `78922E`, `7894E2`, `789500`, and the 009A
  splitter call `CB84ED` are replaced. Both stock insertion calls `CB8621` and
  `CB7943` still reach `788ED0`. No packet lengths or shared text hooks change.
- The existing 01C3 handler's packet/buffer limitations are not extended by this
  patch. This is a cosmetic renderer, not a packet-validation change.
- Item resource resolution uses the same identified/unidentified catalog keys as
  chat. The freestanding runtime has no imports and requires no installed DLL/art.
- ChatItemIcons continues to render the tags in chat; this patch does not replace
  or modify that feature. ITEML chat interactions remain independently owned.

## Source, build and recovery

`Scripts/Runtime/NoticeMarquee/stock.cpp` is the active runtime. Build with
`uv run --with pefile python tools/build_notice_marquee.py`; the builder emits
version-2 `Inputs/NoticeMarquee/runtime.bin` and its integrity metadata.
`Scripts/Patches/NoticeMarquee.qjs` verifies the payload and all original call
targets before embedding it. New EXEs contain `AnnouncementItemIcons.v1`.

The retired scrolling runtime, test, and documentation are recoverable from
`Outputs/stock-announcement-20260917/retired-marquee/`; previous September 16
staged builds are also retained. They are not used in new builds.

`tools/upgrade_stock_announcements.py` stages a guarded update of the existing
client, rather than rebuilding from a saved profile with different selections.
It verifies the expected source hash and old payload, restores both stock
producers, appends the new payload, and changes only the five scoped calls plus
necessary PE size/checksum fields. All other original bytes and the overlay are
preserved. The old embedded marquee is retained **inert**, not called.
It never installs or overwrites its source. Normal installation requires a
closed game process, verified backup and explicit test-install approval.

## Server

Normal/MVP rare-drop messages in `Ragnarok/src/map/mob.cpp` use
`drop_announce_icon::label` to send the true catalog ID before the existing name.
Public announcements use identified catalog artwork; actual pickup/drop chat
still uses the instance's identification state. Names, announcement eligibility,
rate text, RNG, drop policy, ownership, autoloot and rewards are unchanged.

The matching map-server is needed for automatic drop-announcement images.
For a script test: `announce "Icon test: ^i[909]Jellopy",bc_all;`.
Existing Gacha announcement templates/gameplay are intentionally unchanged.
No char-server protocol or database migration is required for this cosmetic change.

## Verification and deployment status

Work and logs: `Outputs/stock-announcement-20260917/`.

- `test_stock_announcement_icons.py` executes emitted x86 measure/draw/height/
  splitter/resolver helpers and the **actual stock balloon draw** with native
  tree/list layouts and explicit font/resource boundary doubles. It checks
  icon/name placement, stock centered background, stationary redraw, two-line
  spacing, ABI, identification, malformed/long input, multibyte wrapping,
  transparent pixels, surface clipping, missing art and burst messages.
- All five existing chat/input/redraw/item-icon suites are run against the
  targeted installed-client candidate, plus Battle Pass and native routing.
- Fresh combined Battle Pass/Gacha and reversed-order builds are byte-identical;
  combined and standalone feature suites verify the shared-build guard matrix.
- The September 15 preservation source guard still matches all 57 protected
  files. No baseline hashes or restore tags are updated.
- The current user's client/profile has **Battle Pass selected, Gacha absent**.
  The combined verifier therefore reports missing Gacha on that exact binary;
  this also occurs before the announcement update. Targeted routing checks use
  the actual BPUI selection. The separate combined candidate covers both systems.
  Do not silently enable Gacha or replace the user's current patch selection.

Original installed client SHA256:
`7C01CACD35E362B2C22066726CC8EBE49F6DF113D76991F2F2BF4F21B1F4CF8B`.
Targeted candidate: `incremental/Ragnarok.exe`, SHA256
`3AB00062167129EF9C625328151B760C2556C46D87ECB6AC91642C77BF67634D`.
The byte-scope audit is `incremental/Ragnarok.json`; only 36 existing bytes differ.
These are offline checks, not live in-game acceptance. Deployment receipts and
the pre-install EXE backup are kept in the same dated output directory.

No Git push, player-data mutation, baseline refresh, or automatic game/server
startup is part of this work. Test a normal broadcast, Jellopy/drop announcement,
multiple quick kills, and chat, then confirm the live appearance before accepting
a new preservation baseline.
